import csv
import io
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from auth import get_current_user, get_password_hash, require_role
from cache import cache_response, invalidate_mutation_caches
from database import get_db
from models import (
    ApprovalAction,
    AuditLog,
    CycleConfig,
    EscalationLog,
    EscalationType,
    Goal,
    GoalApproval,
    GoalStatus,
    Quarter,
    QuarterlyCheckin,
    SharedGoalLink,
    UomType,
    User,
    UserRole,
)
from escalation import run_escalation_check
from schemas import (
    AchievementReportRow,
    AdminDashboardResponse,
    AuditLogListResponse,
    AuditLogResponse,
    CompletionReportResponse,
    CycleConfig as CycleConfigCreate,
    CycleConfigResponse,
    CycleConfigUpdate,
    EmployeeCompletionRow,
    GoalUnlockRequest,
    GoalUnlockResponse,
    LockedGoalItem,
    ManagerCompletionRow,
    OrgUser,
    UserCreateAdmin,
    UserUpdateAdmin,
    AnalyticsOverviewResponse,
    AtRiskEmployeeRow,
    EmployeeAnalyticsResponse,
    EmployeeAnalyticsInfo,
    EmployeeComparisonRow,
    EmployeeHeatmapRow,
    GoalDetailAnalytics,
    GoalSummaryStats,
    ManagerAnalyticsInfo,
    ManagerAnalyticsResponse,
    ManagerEffectivenessRow,
    PerformerRow,
    QuarterScoreItem,
    QuarterTrendItem,
    TeamQuarterScore,
    ThrustAreaAnalytics,
    UomDistributionItem,
    EscalationGroupedResponse,
    EscalationLogResponse,
    EscalationRunResponse,
    GoalNotSubmittedEscalation,
    ApprovalPendingEscalation,
    CheckinNotLoggedEscalation,
    SharedGoalListItem,
    SharedGoalPushRequest,
    SharedGoalPushResponse,
    SharedGoalRecipientInfo,
    CurrentPhaseResponse,
    PhaseOverrideRequest,
    PhaseOverrideResponse,
    DemoSimulateEscalationResponse,
    DemoResetResponse,
    DemoFastForwardResponse,
)
from demo_service import fast_forward_demo, reset_demo_data, simulate_escalation
from routers.goals import _goal_response
from analytics_helpers import (
    QUARTERS as ANALYTICS_QUARTERS,
    at_risk_employees,
    count_at_risk_goals,
    employee_heatmap_rows,
    employee_overall_avg,
    employee_quarter_averages,
    goal_achievement_trend,
    goal_trend,
    manager_effectiveness,
    score_for_checkin,
    thrust_area_distribution,
    top_performers,
    total_checkins_completed,
    uom_type_distribution,
)
from utils import (
    calculate_progress_score,
    get_active_quarter,
    get_current_phase,
    get_next_phase_hint,
    get_phase_override,
    is_goal_setting_phase,
    set_phase_override,
    write_audit_log,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(get_current_user)],
)

public_router = APIRouter(prefix="/admin", tags=["admin"])

QUARTERS = ("Q1", "Q2", "Q3", "Q4")


@public_router.get("/current-phase", response_model=CurrentPhaseResponse)
def get_current_phase_info():
    phase_info = get_current_phase()
    override = get_phase_override()
    return CurrentPhaseResponse(
        **phase_info,
        goal_setting_open=is_goal_setting_phase(),
        checkin_open=get_active_quarter() is not None,
        next_phase=get_next_phase_hint(),
        phase_override_active=override is not None,
        override_phase=override,
    )


@router.post("/demo/override-phase", response_model=PhaseOverrideResponse)
def override_phase_for_demo(
    payload: PhaseOverrideRequest,
    _: Annotated[User, Depends(require_role(UserRole.admin))],
):
    set_phase_override(payload.phase)
    return PhaseOverrideResponse(message=f"Phase overridden to {payload.phase}")


@router.post("/demo/simulate-escalation", response_model=DemoSimulateEscalationResponse)
def demo_simulate_escalation(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_role(UserRole.admin))],
):
    result = simulate_escalation(db)
    return DemoSimulateEscalationResponse(**result)


@router.post("/demo/reset", response_model=DemoResetResponse)
def demo_reset(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_role(UserRole.admin))],
):
    result = reset_demo_data(db)
    return DemoResetResponse(**result)


@router.post("/demo/fast-forward", response_model=DemoFastForwardResponse)
def demo_fast_forward(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_role(UserRole.admin))],
):
    result = fast_forward_demo(db)
    return DemoFastForwardResponse(**result)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _compute_submission_status(goals: list[Goal]) -> str:
    if not goals:
        return "not_started"
    if any(g.status == GoalStatus.returned for g in goals):
        return "has_returned"
    if all(g.status == GoalStatus.approved for g in goals):
        return "approved"
    if all(g.status == GoalStatus.submitted for g in goals):
        return "submitted"
    if any(g.status == GoalStatus.draft for g in goals) and not any(
        g.status == GoalStatus.submitted for g in goals
    ):
        return "partial"
    if any(g.status == GoalStatus.submitted for g in goals):
        return "submitted"
    return "partial"


def _audit_log_response(log: AuditLog, db: Session) -> AuditLogResponse:
    user = db.query(User).filter(User.id == log.changed_by).first()
    return AuditLogResponse(
        id=log.id,
        entity=log.entity,
        entity_id=log.entity_id,
        changed_by=log.changed_by,
        changed_by_name=user.name if user else "Unknown",
        change_description=log.change_description,
        changed_at=log.changed_at,
    )


def _build_org_user(user: User, db: Session) -> OrgUser:
    goals = db.query(Goal).filter(Goal.employee_id == user.id).all()
    manager = (
        db.query(User).filter(User.id == user.manager_id).first()
        if user.manager_id
        else None
    )
    return OrgUser(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role.value if isinstance(user.role, UserRole) else user.role,
        manager_id=user.manager_id,
        manager_name=manager.name if manager else None,
        is_active=user.is_active,
        goal_count=len(goals) if user.role == UserRole.employee else 0,
        submission_status=_compute_submission_status(goals) if goals else "not_started",
    )


def _employee_has_checkin_in_quarter(db: Session, employee_id: int, quarter: str) -> bool:
    return (
        db.query(QuarterlyCheckin)
        .join(Goal, QuarterlyCheckin.goal_id == Goal.id)
        .filter(
            Goal.employee_id == employee_id,
            QuarterlyCheckin.quarter == Quarter(quarter),
        )
        .first()
        is not None
    )


def _build_achievement_rows(db: Session) -> list[AchievementReportRow]:
    rows: list[AchievementReportRow] = []
    employees = db.query(User).filter(User.role == UserRole.employee).order_by(User.name).all()

    for employee in employees:
        manager = (
            db.query(User).filter(User.id == employee.manager_id).first()
            if employee.manager_id
            else None
        )
        goals = db.query(Goal).filter(Goal.employee_id == employee.id).all()

        for goal in goals:
            checkins_by_q: dict[str, QuarterlyCheckin | None] = {}
            for q in QUARTERS:
                checkins_by_q[q] = (
                    db.query(QuarterlyCheckin)
                    .filter(
                        QuarterlyCheckin.goal_id == goal.id,
                        QuarterlyCheckin.quarter == Quarter(q),
                    )
                    .first()
                )

            uom = goal.uom_type.value if hasattr(goal.uom_type, "value") else goal.uom_type

            def actual_and_score(q: str) -> tuple[float | None, float | None]:
                c = checkins_by_q[q]
                if not c:
                    return None, None
                score = calculate_progress_score(
                    goal.uom_type,
                    goal.target_value,
                    c.actual_value,
                    goal.target_date,
                    c.actual_date,
                )
                if uom == "timeline":
                    return None, score
                return c.actual_value, score

            q1_a, q1_s = actual_and_score("Q1")
            q2_a, q2_s = actual_and_score("Q2")
            q3_a, q3_s = actual_and_score("Q3")
            q4_a, q4_s = actual_and_score("Q4")
            scores = [s for s in (q1_s, q2_s, q3_s, q4_s) if s is not None]
            overall = round(sum(scores) / len(scores), 2) if scores else None

            rows.append(
                AchievementReportRow(
                    employee_id=employee.id,
                    employee_name=employee.name,
                    manager_name=manager.name if manager else "—",
                    goal_title=goal.title,
                    thrust_area=goal.thrust_area,
                    uom_type=uom,
                    target_value=goal.target_value,
                    target_date=goal.target_date,
                    weightage=goal.weightage,
                    q1_actual=q1_a,
                    q1_score=q1_s,
                    q2_actual=q2_a,
                    q2_score=q2_s,
                    q3_actual=q3_a,
                    q3_score=q3_s,
                    q4_actual=q4_a,
                    q4_score=q4_s,
                    overall_score=overall,
                )
            )
    return rows


@router.get("/dashboard", response_model=AdminDashboardResponse)
@cache_response("admin:dashboard", expire_seconds=300)
def admin_dashboard(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_role(UserRole.admin))],
):
    employees = db.query(User).filter(User.role == UserRole.employee).all()
    total_employees = len(employees)
    total_managers = db.query(User).filter(User.role == UserRole.manager).count()
    total_goals = db.query(Goal).count()
    goals_approved = db.query(Goal).filter(Goal.status == GoalStatus.approved).count()
    goals_pending = db.query(Goal).filter(Goal.status == GoalStatus.submitted).count()
    goals_returned = db.query(Goal).filter(Goal.status == GoalStatus.returned).count()

    employees_not_started = 0
    employees_submitted = 0
    employees_approved = 0

    for emp in employees:
        goals = db.query(Goal).filter(Goal.employee_id == emp.id).all()
        if not goals:
            employees_not_started += 1
            continue
        if all(g.status == GoalStatus.approved for g in goals):
            employees_approved += 1
        elif all(g.status == GoalStatus.submitted for g in goals):
            employees_submitted += 1

    checkin_rates: dict[str, float] = {}
    for q in QUARTERS:
        if total_employees == 0:
            checkin_rates[q] = 0.0
            continue
        with_checkin = sum(
            1 for emp in employees if _employee_has_checkin_in_quarter(db, emp.id, q)
        )
        checkin_rates[q] = round((with_checkin / total_employees) * 100, 2)

    recent = (
        db.query(AuditLog).order_by(AuditLog.changed_at.desc()).limit(20).all()
    )

    return AdminDashboardResponse(
        total_employees=total_employees,
        total_managers=total_managers,
        total_goals=total_goals,
        goals_approved=goals_approved,
        goals_pending=goals_pending,
        goals_returned=goals_returned,
        employees_not_started=employees_not_started,
        employees_submitted=employees_submitted,
        employees_approved=employees_approved,
        checkin_completion_rates=checkin_rates,
        recent_audit_logs=[_audit_log_response(log, db) for log in recent],
    )


@router.get("/users", response_model=list[OrgUser])
def list_users(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_role(UserRole.admin))],
    role: str | None = None,
    manager_id: int | None = None,
    status: str | None = None,
):
    query = db.query(User)
    if role:
        query = query.filter(User.role == UserRole(role))
    if manager_id is not None:
        query = query.filter(User.manager_id == manager_id)
    users = query.order_by(User.name).all()
    result = [_build_org_user(u, db) for u in users]
    if status:
        result = [u for u in result if u.submission_status == status]
    return result


@router.post("/users", response_model=OrgUser, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateAdmin,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        role=payload.role,
        manager_id=payload.manager_id if payload.role == UserRole.employee else None,
    )
    db.add(user)
    db.flush()
    write_audit_log(
        db,
        entity="user",
        entity_id=user.id,
        changed_by=current_user.id,
        change_description=f"Admin created user: {payload.email} with role {payload.role.value}",
    )
    db.commit()
    invalidate_mutation_caches()
    db.refresh(user)
    return _build_org_user(user, db)


@router.put("/users/{user_id}", response_model=OrgUser)
def update_user(
    user_id: int,
    payload: UserUpdateAdmin,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    updates = payload.model_dump(exclude_unset=True)
    if "role" in updates and user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    changed = []
    for field, value in updates.items():
        if field == "role" and value is not None:
            setattr(user, field, UserRole(value) if isinstance(value, str) else value)
        else:
            setattr(user, field, value)
        changed.append(field)

    if changed:
        write_audit_log(
            db,
            entity="user",
            entity_id=user.id,
            changed_by=current_user.id,
            change_description=f"Admin updated user {user.email}: {', '.join(changed)}",
        )
    db.commit()
    invalidate_mutation_caches()
    db.refresh(user)
    return _build_org_user(user, db)


@router.get("/goals/locked", response_model=list[LockedGoalItem])
def list_locked_goals(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_role(UserRole.admin))],
    search: str | None = None,
):
    query = (
        db.query(Goal)
        .join(User, Goal.employee_id == User.id)
        .filter(Goal.is_locked.is_(True), Goal.status == GoalStatus.approved)
    )
    if search:
        term = f"%{search}%"
        query = query.filter(
            (Goal.title.ilike(term)) | (User.name.ilike(term)) | (User.email.ilike(term))
        )
    results = query.order_by(User.name, Goal.title).all()
    items = []
    for goal in results:
        emp = db.query(User).filter(User.id == goal.employee_id).first()
        items.append(
            LockedGoalItem(
                goal_id=goal.id,
                title=goal.title,
                employee_name=emp.name if emp else "Unknown",
                employee_email=emp.email if emp else "",
                thrust_area=goal.thrust_area,
            )
        )
    return items


@router.post("/goals/unlock/{goal_id}", response_model=GoalUnlockResponse)
def unlock_goal(
    goal_id: int,
    payload: GoalUnlockRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
):
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    reason = payload.reason.strip()
    goal.is_locked = False
    goal.status = GoalStatus.draft
    goal.updated_at = _utc_now()

    write_audit_log(
        db,
        entity="goal",
        entity_id=goal.id,
        changed_by=current_user.id,
        change_description=f"Admin unlocked goal {goal_id}. Reason: {reason}",
    )
    db.commit()
    invalidate_mutation_caches(goals=True)

    return GoalUnlockResponse(
        message="Goal unlocked. Employee must edit and resubmit for manager re-approval.",
        goal_id=goal_id,
        reason=reason,
    )


@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_role(UserRole.admin))],
    entity: str | None = None,
    changed_by: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    query = db.query(AuditLog)
    if entity:
        query = query.filter(AuditLog.entity == entity)
    if changed_by is not None:
        query = query.filter(AuditLog.changed_by == changed_by)
    if from_date:
        query = query.filter(AuditLog.changed_at >= datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc))
    if to_date:
        query = query.filter(AuditLog.changed_at <= datetime.combine(to_date, datetime.max.time(), tzinfo=timezone.utc))

    if search:
        matching_ids = [
            u.id
            for u in db.query(User).filter(User.name.ilike(f"%{search}%")).all()
        ]
        if matching_ids:
            query = query.filter(AuditLog.changed_by.in_(matching_ids))
        else:
            return AuditLogListResponse(logs=[], total=0, page=page, page_size=page_size)

    total = query.count()
    logs = (
        query.order_by(AuditLog.changed_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return AuditLogListResponse(
        logs=[_audit_log_response(log, db) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/reports/achievement", response_model=list[AchievementReportRow])
@cache_response("admin:reports:achievement", expire_seconds=900)
def achievement_report(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_role(UserRole.admin))],
):
    return _build_achievement_rows(db)


@router.get("/reports/achievement/export")
def achievement_report_export(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_role(UserRole.admin))],
):
    rows = _build_achievement_rows(db)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Employee Name",
            "Manager Name",
            "Goal Title",
            "Thrust Area",
            "UoM Type",
            "Target",
            "Weightage",
            "Q1 Actual",
            "Q1 Score%",
            "Q2 Actual",
            "Q2 Score%",
            "Q3 Actual",
            "Q3 Score%",
            "Q4 Actual",
            "Q4 Score%",
            "Overall Score%",
        ]
    )
    for row in rows:
        target = row.target_value if row.target_value is not None else row.target_date
        writer.writerow(
            [
                row.employee_name,
                row.manager_name,
                row.goal_title,
                row.thrust_area,
                row.uom_type,
                target,
                row.weightage,
                row.q1_actual,
                row.q1_score,
                row.q2_actual,
                row.q2_score,
                row.q3_actual,
                row.q3_score,
                row.q4_actual,
                row.q4_score,
                row.overall_score,
            ]
        )
    output.seek(0)
    filename = f"achievement_report_{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/completion", response_model=CompletionReportResponse)
def completion_report(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_role(UserRole.admin))],
):
    employees = db.query(User).filter(User.role == UserRole.employee).order_by(User.name).all()
    employee_rows: list[EmployeeCompletionRow] = []

    for emp in employees:
        goals = db.query(Goal).filter(Goal.employee_id == emp.id).all()
        manager = (
            db.query(User).filter(User.id == emp.manager_id).first()
            if emp.manager_id
            else None
        )
        employee_rows.append(
            EmployeeCompletionRow(
                employee_id=emp.id,
                employee_name=emp.name,
                manager_name=manager.name if manager else None,
                has_created_goals=len(goals) > 0,
                has_submitted_goals=bool(goals)
                and all(g.status in (GoalStatus.submitted, GoalStatus.approved) for g in goals)
                and any(g.status == GoalStatus.submitted for g in goals),
                has_approved_goals=bool(goals) and all(g.status == GoalStatus.approved for g in goals),
                q1_done=_employee_has_checkin_in_quarter(db, emp.id, "Q1"),
                q2_done=_employee_has_checkin_in_quarter(db, emp.id, "Q2"),
                q3_done=_employee_has_checkin_in_quarter(db, emp.id, "Q3"),
                q4_done=_employee_has_checkin_in_quarter(db, emp.id, "Q4"),
            )
        )

    managers = db.query(User).filter(User.role == UserRole.manager).all()
    manager_rows: list[ManagerCompletionRow] = []
    for mgr in managers:
        report_ids = [u.id for u in db.query(User).filter(User.manager_id == mgr.id).all()]
        pending = (
            db.query(Goal)
            .filter(Goal.employee_id.in_(report_ids), Goal.status == GoalStatus.submitted)
            .count()
            if report_ids
            else 0
        )
        reviewed = (
            db.query(QuarterlyCheckin)
            .filter(QuarterlyCheckin.manager_comment.isnot(None))
            .join(Goal, QuarterlyCheckin.goal_id == Goal.id)
            .filter(Goal.employee_id.in_(report_ids))
            .count()
            if report_ids
            else 0
        )
        manager_rows.append(
            ManagerCompletionRow(
                manager_id=mgr.id,
                manager_name=mgr.name,
                pending_approvals_count=pending,
                completed_checkin_reviews_count=reviewed,
            )
        )

    all_goals = db.query(Goal).all()
    status_dist: dict[str, int] = {}
    thrust_dist: dict[str, int] = {}
    uom_dist: dict[str, int] = {}
    for g in all_goals:
        st = g.status.value if hasattr(g.status, "value") else g.status
        status_dist[st] = status_dist.get(st, 0) + 1
        thrust_dist[g.thrust_area] = thrust_dist.get(g.thrust_area, 0) + 1
        uom = g.uom_type.value if hasattr(g.uom_type, "value") else g.uom_type
        uom_dist[uom] = uom_dist.get(uom, 0) + 1

    return CompletionReportResponse(
        employees=employee_rows,
        managers=manager_rows,
        goal_status_distribution=status_dist,
        thrust_area_distribution=thrust_dist,
        uom_type_distribution=uom_dist,
    )


@router.post("/cycles", response_model=CycleConfigResponse, status_code=status.HTTP_201_CREATED)
def create_cycle(
    payload: CycleConfigCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
):
    db.query(CycleConfig).update({CycleConfig.is_active: False})
    cycle = CycleConfig(
        cycle_year=payload.cycle_year,
        goal_setting_start=payload.goal_setting_start,
        q1_checkin_start=payload.q1_checkin_start,
        q2_checkin_start=payload.q2_checkin_start,
        q3_checkin_start=payload.q3_checkin_start,
        q4_checkin_start=payload.q4_checkin_start,
        is_active=payload.is_active,
    )
    db.add(cycle)
    db.flush()
    write_audit_log(
        db,
        entity="admin",
        entity_id=cycle.id,
        changed_by=current_user.id,
        change_description=f"Admin created new cycle for year {payload.cycle_year}",
    )
    db.commit()
    invalidate_mutation_caches()
    db.refresh(cycle)
    return CycleConfigResponse.model_validate(cycle)


@router.get("/cycles", response_model=list[CycleConfigResponse])
def list_cycles(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_role(UserRole.admin))],
):
    cycles = db.query(CycleConfig).order_by(CycleConfig.cycle_year.desc()).all()
    return [CycleConfigResponse.model_validate(c) for c in cycles]


@router.put("/cycles/{cycle_id}", response_model=CycleConfigResponse)
def update_cycle(
    cycle_id: int,
    payload: CycleConfigUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
):
    cycle = db.query(CycleConfig).filter(CycleConfig.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")

    changes: list[str] = []
    for field, label in [
        ("goal_setting_start", "goal_setting_start"),
        ("q1_checkin_start", "q1_checkin_start"),
        ("q2_checkin_start", "q2_checkin_start"),
        ("q3_checkin_start", "q3_checkin_start"),
        ("q4_checkin_start", "q4_checkin_start"),
    ]:
        value = getattr(payload, field)
        if value is not None and getattr(cycle, field) != value:
            changes.append(f"{label}={value}")
            setattr(cycle, field, value)

    if changes:
        write_audit_log(
            db,
            entity="admin",
            entity_id=cycle.id,
            changed_by=current_user.id,
            change_description=f"Admin updated cycle {cycle.cycle_year}: {', '.join(changes)}",
        )
    db.commit()
    invalidate_mutation_caches()
    db.refresh(cycle)
    return CycleConfigResponse.model_validate(cycle)


@router.put("/cycles/{cycle_id}/activate", response_model=CycleConfigResponse)
def activate_cycle(
    cycle_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
):
    cycle = db.query(CycleConfig).filter(CycleConfig.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")

    db.query(CycleConfig).update({CycleConfig.is_active: False})
    cycle.is_active = True
    write_audit_log(
        db,
        entity="admin",
        entity_id=cycle.id,
        changed_by=current_user.id,
        change_description=f"Admin activated cycle for year {cycle.cycle_year}",
    )
    db.commit()
    invalidate_mutation_caches()
    db.refresh(cycle)
    return CycleConfigResponse.model_validate(cycle)


@router.get(
    "/analytics/overview",
    response_model=AnalyticsOverviewResponse,
    summary="Organization-wide analytics overview",
)
@cache_response("admin:analytics:overview", expire_seconds=600)
def analytics_overview(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_role(UserRole.admin))],
):
    trend = goal_achievement_trend(db)
    thrust = thrust_area_distribution(db)
    performers = top_performers(db, 5)
    at_risk = at_risk_employees(db)
    employees = db.query(User).filter(User.role == UserRole.employee).all()
    org_scores = [s for s in (employee_overall_avg(db, e.id) for e in employees) if s is not None]
    org_avg = round(sum(org_scores) / len(org_scores), 2) if org_scores else 0.0

    return AnalyticsOverviewResponse(
        goal_achievement_trend=[QuarterTrendItem(**t) for t in trend],
        thrust_area_distribution=[ThrustAreaAnalytics(**t) for t in thrust],
        uom_type_distribution=[UomDistributionItem(**u) for u in uom_type_distribution(db)],
        top_performers=[PerformerRow(**p) for p in performers],
        at_risk_employees=[AtRiskEmployeeRow(**e) for e in at_risk],
        manager_effectiveness=[ManagerEffectivenessRow(**m) for m in manager_effectiveness(db)],
        employee_heatmap=[EmployeeHeatmapRow(**h) for h in employee_heatmap_rows(db)],
        org_avg_score=org_avg,
        total_checkins_completed=total_checkins_completed(db),
        top_thrust_area=thrust[0]["thrust_area"] if thrust else None,
    )


@router.get(
    "/analytics/employee/{employee_id}",
    response_model=EmployeeAnalyticsResponse,
    summary="Individual employee analytics",
)
def analytics_employee(
    employee_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_role(UserRole.admin))],
):
    emp = db.query(User).filter(User.id == employee_id).first()
    if not emp or emp.role != UserRole.employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    manager = (
        db.query(User).filter(User.id == emp.manager_id).first() if emp.manager_id else None
    )
    goals = db.query(Goal).filter(Goal.employee_id == emp.id).all()
    q_avgs = employee_quarter_averages(db, emp.id)

    quarter_scores = []
    for q in ANALYTICS_QUARTERS:
        checked = 0
        for g in goals:
            if (
                db.query(QuarterlyCheckin)
                .filter(
                    QuarterlyCheckin.goal_id == g.id,
                    QuarterlyCheckin.quarter == Quarter(q),
                )
                .first()
            ):
                checked += 1
        quarter_scores.append(
            QuarterScoreItem(
                quarter=q,
                avg_score=q_avgs[q],
                goals_checked_in=checked,
                total_goals=len(goals),
            )
        )

    goal_details = []
    for goal in goals:
        q_scores = []
        for q in ANALYTICS_QUARTERS:
            checkin = (
                db.query(QuarterlyCheckin)
                .filter(
                    QuarterlyCheckin.goal_id == goal.id,
                    QuarterlyCheckin.quarter == Quarter(q),
                )
                .first()
            )
            q_scores.append(score_for_checkin(goal, checkin))
        uom = goal.uom_type.value if hasattr(goal.uom_type, "value") else goal.uom_type
        target = (
            str(goal.target_date)
            if uom == "timeline"
            else str(goal.target_value) if goal.target_value is not None else "—"
        )
        goal_details.append(
            GoalDetailAnalytics(
                goal_title=goal.title,
                thrust_area=goal.thrust_area,
                uom_type=uom,
                target=target,
                q1_score=q_scores[0],
                q2_score=q_scores[1],
                q3_score=q_scores[2],
                q4_score=q_scores[3],
                trend=goal_trend(q_scores),
            )
        )

    overall = employee_overall_avg(db, emp.id) or 0.0
    valid_q = {k: v for k, v in q_avgs.items() if v is not None}
    best_q = max(valid_q, key=valid_q.get) if valid_q else "Q1"
    worst_q = min(valid_q, key=valid_q.get) if valid_q else "Q1"

    return EmployeeAnalyticsResponse(
        employee=EmployeeAnalyticsInfo(
            id=emp.id,
            name=emp.name,
            email=emp.email,
            manager_name=manager.name if manager else None,
        ),
        goal_summary=GoalSummaryStats(
            total=len(goals),
            approved=sum(1 for g in goals if g.status == GoalStatus.approved),
            pending=sum(1 for g in goals if g.status == GoalStatus.submitted),
            returned=sum(1 for g in goals if g.status == GoalStatus.returned),
        ),
        quarter_scores=quarter_scores,
        goal_details=goal_details,
        overall_avg_score=overall,
        best_quarter=best_q,
        worst_quarter=worst_q,
    )


@router.get(
    "/analytics/manager/{manager_id}",
    response_model=ManagerAnalyticsResponse,
    summary="Manager-level team analytics",
)
def analytics_manager(
    manager_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_role(UserRole.admin))],
):
    mgr = db.query(User).filter(User.id == manager_id).first()
    if not mgr or mgr.role != UserRole.manager:
        raise HTTPException(status_code=404, detail="Manager not found")

    team = db.query(User).filter(
        User.manager_id == mgr.id, User.role == UserRole.employee
    ).all()
    team_ids = [e.id for e in team]

    pending = (
        db.query(Goal)
        .filter(Goal.employee_id.in_(team_ids), Goal.status == GoalStatus.submitted)
        .count()
        if team_ids
        else 0
    )

    approval_days: list[float] = []
    if team_ids:
        for goal in db.query(Goal).filter(Goal.employee_id.in_(team_ids)).all():
            if goal.status != GoalStatus.approved:
                continue
            approval = (
                db.query(GoalApproval)
                .filter(
                    GoalApproval.goal_id == goal.id,
                    GoalApproval.action == ApprovalAction.approved,
                )
                .order_by(GoalApproval.acted_at.desc())
                .first()
            )
            if approval and goal.created_at:
                acted = approval.acted_at
                created = goal.created_at
                if acted.tzinfo is None:
                    acted = acted.replace(tzinfo=timezone.utc)
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                approval_days.append(max((acted - created).total_seconds() / 86400, 0))

    team_quarter_scores = []
    for q in ANALYTICS_QUARTERS:
        q_scores: list[float] = []
        total_slots = 0
        completed = 0
        for eid in team_ids:
            emp_goals = db.query(Goal).filter(Goal.employee_id == eid).all()
            for goal in emp_goals:
                total_slots += 1
                checkin = (
                    db.query(QuarterlyCheckin)
                    .filter(
                        QuarterlyCheckin.goal_id == goal.id,
                        QuarterlyCheckin.quarter == Quarter(q),
                    )
                    .first()
                )
                if checkin and (
                    checkin.actual_value is not None or checkin.actual_date is not None
                ):
                    completed += 1
                    s = score_for_checkin(goal, checkin)
                    if s is not None:
                        q_scores.append(s)
        team_quarter_scores.append(
            TeamQuarterScore(
                quarter=q,
                avg_score=round(sum(q_scores) / len(q_scores), 2) if q_scores else 0.0,
                completion_rate=round((completed / total_slots) * 100, 1)
                if total_slots
                else 0.0,
            )
        )

    employee_comparison = []
    for emp in team:
        checkins_done = 0
        for g in db.query(Goal).filter(Goal.employee_id == emp.id).all():
            for c in db.query(QuarterlyCheckin).filter(QuarterlyCheckin.goal_id == g.id).all():
                if c.actual_value is not None or c.actual_date is not None:
                    checkins_done += 1
        employee_comparison.append(
            EmployeeComparisonRow(
                employee_name=emp.name,
                avg_score=employee_overall_avg(db, emp.id) or 0.0,
                checkins_completed=checkins_done,
                goals_at_risk=count_at_risk_goals(db, emp.id),
            )
        )

    team_checkins = (
        db.query(QuarterlyCheckin)
        .join(Goal, QuarterlyCheckin.goal_id == Goal.id)
        .filter(Goal.employee_id.in_(team_ids))
        .all()
        if team_ids
        else []
    )
    with_comment = sum(1 for c in team_checkins if c.manager_comment)
    review_rate = (
        round((with_comment / len(team_checkins)) * 100, 1) if team_checkins else 0.0
    )

    return ManagerAnalyticsResponse(
        manager=ManagerAnalyticsInfo(id=mgr.id, name=mgr.name, email=mgr.email),
        team_size=len(team),
        team_members=[e.name for e in team],
        pending_approvals=pending,
        avg_approval_days=round(sum(approval_days) / len(approval_days), 1)
        if approval_days
        else 0.0,
        team_quarter_scores=team_quarter_scores,
        employee_comparison=sorted(employee_comparison, key=lambda x: -x.avg_score),
        checkin_review_rate=review_rate,
    )


def _days_since(dt: datetime) -> int:
    now = _utc_now()
    start = dt.replace(tzinfo=None) if dt.tzinfo else dt
    end = now.replace(tzinfo=None) if now.tzinfo else now
    return max(0, (end.date() - start.date()).days)


def _build_escalation_grouped(db: Session) -> EscalationGroupedResponse:
    logs = (
        db.query(EscalationLog)
        .filter(EscalationLog.is_resolved.is_(False))
        .order_by(EscalationLog.created_at.desc())
        .all()
    )

    goal_not_submitted: list[GoalNotSubmittedEscalation] = []
    approval_pending: list[ApprovalPendingEscalation] = []
    checkin_not_logged: list[CheckinNotLoggedEscalation] = []

    for log in logs:
        base = {
            "id": log.id,
            "escalation_type": log.escalation_type.value
            if hasattr(log.escalation_type, "value")
            else log.escalation_type,
            "employee_id": log.employee_id,
            "manager_id": log.manager_id,
            "goal_id": log.goal_id,
            "message": log.message,
            "is_resolved": log.is_resolved,
            "created_at": log.created_at,
            "resolved_at": log.resolved_at,
        }

        if log.escalation_type == EscalationType.goal_not_submitted:
            employee = (
                db.query(User).filter(User.id == log.employee_id).first()
                if log.employee_id
                else None
            )
            draft_goals = (
                db.query(Goal)
                .filter(
                    Goal.employee_id == log.employee_id,
                    Goal.status == GoalStatus.draft,
                )
                .all()
            )
            oldest = min(draft_goals, key=lambda g: g.created_at) if draft_goals else None
            days = _days_since(oldest.created_at) if oldest else _days_since(log.created_at)
            goal_not_submitted.append(
                GoalNotSubmittedEscalation(
                    **base,
                    employee_name=employee.name if employee else "Unknown",
                    days_since_created=days,
                    goal_count=len(draft_goals),
                )
            )
        elif log.escalation_type == EscalationType.approval_pending_too_long:
            goal = db.query(Goal).filter(Goal.id == log.goal_id).first() if log.goal_id else None
            employee = (
                db.query(User).filter(User.id == goal.employee_id).first() if goal else None
            )
            manager = (
                db.query(User).filter(User.id == log.manager_id).first()
                if log.manager_id
                else None
            )
            days = _days_since(goal.updated_at) if goal else _days_since(log.created_at)
            approval_pending.append(
                ApprovalPendingEscalation(
                    **base,
                    goal_title=goal.title if goal else "—",
                    employee_name=employee.name if employee else "Unknown",
                    manager_name=manager.name if manager else None,
                    days_waiting=days,
                )
            )
        elif log.escalation_type == EscalationType.checkin_not_logged:
            goal = db.query(Goal).filter(Goal.id == log.goal_id).first() if log.goal_id else None
            employee = (
                db.query(User).filter(User.id == log.employee_id).first()
                if log.employee_id
                else None
            )
            quarter = "Q1"
            for q in QUARTERS:
                if q in log.message:
                    quarter = q
                    break
            checkin_not_logged.append(
                CheckinNotLoggedEscalation(
                    **base,
                    employee_name=employee.name if employee else "Unknown",
                    goal_title=goal.title if goal else "—",
                    quarter=quarter,
                )
            )

    return EscalationGroupedResponse(
        goal_not_submitted=goal_not_submitted,
        approval_pending_too_long=approval_pending,
        checkin_not_logged=checkin_not_logged,
        total_unresolved=len(logs),
    )


@router.get("/escalations", response_model=EscalationGroupedResponse)
def list_escalations(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_role(UserRole.admin))],
):
    return _build_escalation_grouped(db)


@router.post("/escalations/{escalation_id}/resolve", response_model=EscalationLogResponse)
def resolve_escalation(
    escalation_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin))],
):
    log = db.query(EscalationLog).filter(EscalationLog.id == escalation_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Escalation not found")
    if log.is_resolved:
        raise HTTPException(status_code=400, detail="Escalation is already resolved")

    log.is_resolved = True
    log.resolved_at = _utc_now()
    write_audit_log(
        db,
        entity="escalation",
        entity_id=log.id,
        changed_by=current_user.id,
        change_description="Escalation resolved by admin",
    )
    db.commit()
    db.refresh(log)
    return EscalationLogResponse(
        id=log.id,
        escalation_type=log.escalation_type.value
        if hasattr(log.escalation_type, "value")
        else log.escalation_type,
        employee_id=log.employee_id,
        manager_id=log.manager_id,
        goal_id=log.goal_id,
        message=log.message,
        is_resolved=log.is_resolved,
        created_at=log.created_at,
        resolved_at=log.resolved_at,
    )


@router.post("/escalations/run", response_model=EscalationRunResponse)
def run_escalations(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_role(UserRole.admin))],
):
    new_count = run_escalation_check(db)
    return EscalationRunResponse(
        message="Escalation check complete",
        new_escalations=new_count,
    )


def _recipient_checkin_quarters(db: Session, child_goal_id: int) -> list[str]:
    checkins = (
        db.query(QuarterlyCheckin)
        .filter(QuarterlyCheckin.goal_id == child_goal_id)
        .all()
    )
    return [
        c.quarter.value if isinstance(c.quarter, Quarter) else c.quarter
        for c in checkins
    ]


@router.get("/shared-goals", response_model=list[SharedGoalListItem])
def list_shared_goals(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_role(UserRole.admin, UserRole.manager))],
):
    parent_goals = (
        db.query(Goal)
        .filter(
            Goal.is_shared.is_(True),
            Goal.parent_shared_goal_id.is_(None),
        )
        .order_by(Goal.created_at.desc())
        .all()
    )

    items: list[SharedGoalListItem] = []
    for parent in parent_goals:
        links = (
            db.query(SharedGoalLink)
            .filter(SharedGoalLink.parent_goal_id == parent.id)
            .all()
        )
        recipients: list[SharedGoalRecipientInfo] = []
        for link in links:
            employee = (
                db.query(User).filter(User.id == link.recipient_employee_id).first()
            )
            child = (
                db.query(Goal)
                .filter(
                    Goal.parent_shared_goal_id == parent.id,
                    Goal.employee_id == link.recipient_employee_id,
                )
                .first()
            )
            if not employee or not child:
                continue
            recipients.append(
                SharedGoalRecipientInfo(
                    employee_id=employee.id,
                    employee_name=employee.name,
                    custom_weightage=link.custom_weightage,
                    child_goal_id=child.id,
                    quarters_with_checkins=_recipient_checkin_quarters(db, child.id),
                )
            )

        owner = db.query(User).filter(User.id == parent.employee_id).first()
        items.append(
            SharedGoalListItem(
                parent_goal=_goal_response(parent, db=db),
                recipients=recipients,
                total_recipients=len(recipients),
                created_by_name=owner.name if owner else "Unknown",
            )
        )
    return items


@router.post("/shared-goals/push", response_model=SharedGoalPushResponse)
def push_shared_goal(
    payload: SharedGoalPushRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.admin, UserRole.manager))],
):
    if payload.default_weightage < 10 or payload.default_weightage > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Default weightage must be between 10 and 100",
        )

    recipients = (
        db.query(User)
        .filter(
            User.id.in_(payload.recipient_employee_ids),
            User.role == UserRole.employee,
            User.is_active.is_(True),
        )
        .all()
    )
    if len(recipients) != len(set(payload.recipient_employee_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more recipient employees were not found",
        )

    parent = Goal(
        employee_id=current_user.id,
        thrust_area=payload.thrust_area,
        title=payload.title,
        description=payload.description,
        uom_type=UomType(payload.uom_type),
        target_value=payload.target_value,
        target_date=payload.target_date,
        weightage=payload.default_weightage,
        is_shared=True,
        status=GoalStatus.approved,
        is_locked=True,
    )
    db.add(parent)
    db.flush()

    recipient_names: list[str] = []
    for recipient in recipients:
        child = Goal(
            employee_id=recipient.id,
            parent_shared_goal_id=parent.id,
            thrust_area=payload.thrust_area,
            title=payload.title,
            description=payload.description,
            uom_type=UomType(payload.uom_type),
            target_value=payload.target_value,
            target_date=payload.target_date,
            weightage=payload.default_weightage,
            is_shared=True,
            status=GoalStatus.approved,
            is_locked=True,
        )
        db.add(child)
        db.flush()

        db.add(
            SharedGoalLink(
                parent_goal_id=parent.id,
                recipient_employee_id=recipient.id,
                custom_weightage=payload.default_weightage,
            )
        )
        write_audit_log(
            db,
            entity="goal",
            entity_id=child.id,
            changed_by=current_user.id,
            change_description=(
                f"Shared goal pushed to employee {recipient.name}: {payload.title}"
            ),
        )
        recipient_names.append(recipient.name)

    write_audit_log(
        db,
        entity="goal",
        entity_id=parent.id,
        changed_by=current_user.id,
        change_description=(
            f"Shared goal created and pushed to {len(recipient_names)} employees: "
            f"{payload.title}"
        ),
    )
    db.commit()
    invalidate_mutation_caches(goals=True)

    return SharedGoalPushResponse(
        message="Goal pushed successfully",
        parent_goal_id=parent.id,
        pushed_to_count=len(recipient_names),
        recipient_names=recipient_names,
    )
