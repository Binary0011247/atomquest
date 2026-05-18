from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from cache import invalidate_mutation_caches
from database import get_db
from models import (
    CheckinStatus,
    Goal,
    GoalStatus,
    Quarter,
    QuarterlyCheckin,
    SharedGoalLink,
    User,
    UserRole,
)
from routers.goals import _goal_response, _utc_now
from schemas import (
    CheckinCreate,
    CheckinResponse,
    CheckinUpdate,
    CheckinUpsertResponse,
    EmployeeProgressReport,
    GoalWithCheckins,
    ManagerCheckinComment,
)
from utils import (
    calculate_progress_score,
    get_active_quarter,
    get_current_phase,
    get_manager_direct_reports,
    get_score_color,
    validate_checkin_actual_fields,
    write_audit_log,
)

router = APIRouter(
    prefix="/checkins",
    tags=["checkins"],
    dependencies=[Depends(get_current_user)],
)

QUARTERS = ("Q1", "Q2", "Q3", "Q4")


def _ensure_approved_locked(goal: Goal) -> None:
    if goal.status != GoalStatus.approved or not goal.is_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Goals must be approved before check-ins can be logged",
        )


def _checkin_progress(goal: Goal, checkin: QuarterlyCheckin) -> float:
    return calculate_progress_score(
        goal.uom_type,
        goal.target_value,
        checkin.actual_value,
        goal.target_date,
        checkin.actual_date,
    )


def _to_checkin_response(goal: Goal, checkin: QuarterlyCheckin) -> CheckinResponse:
    score = _checkin_progress(goal, checkin)
    return CheckinResponse(
        id=checkin.id,
        goal_id=checkin.goal_id,
        quarter=checkin.quarter.value if isinstance(checkin.quarter, Quarter) else checkin.quarter,
        actual_value=checkin.actual_value,
        actual_date=checkin.actual_date,
        status=checkin.status.value if isinstance(checkin.status, CheckinStatus) else checkin.status,
        employee_note=checkin.employee_note,
        manager_comment=checkin.manager_comment,
        progress_score=score,
        score_color=get_score_color(score),
        updated_at=checkin.updated_at,
    )


def _average_scores(responses: list[CheckinResponse]) -> float | None:
    scores = [r.progress_score for r in responses if r.progress_score is not None]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 2)


def _build_goal_with_checkins(
    goal: Goal,
    checkins: list[QuarterlyCheckin],
    db: Session,
) -> GoalWithCheckins:
    responses = [_to_checkin_response(goal, c) for c in checkins]
    latest = max(checkins, key=lambda c: c.updated_at) if checkins else None
    return GoalWithCheckins(
        goal=_goal_response(goal, db=db),
        checkins=responses,
        latest_checkin=_to_checkin_response(goal, latest) if latest else None,
        overall_progress=_average_scores(responses),
    )


def _approved_goals(db: Session, employee_id: int) -> list[Goal]:
    return (
        db.query(Goal)
        .filter(
            Goal.employee_id == employee_id,
            Goal.status == GoalStatus.approved,
            Goal.is_locked.is_(True),
        )
        .order_by(Goal.title)
        .all()
    )


def sync_shared_goal_checkins(
    goal_id: int,
    checkin_data: QuarterlyCheckin,
    db: Session,
    *,
    changed_by: int,
) -> int:
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal or not goal.is_shared:
        return 0

    shared_links = (
        db.query(SharedGoalLink)
        .filter(SharedGoalLink.parent_goal_id == goal_id)
        .all()
    )

    synced_count = 0
    quarter = (
        checkin_data.quarter.value
        if isinstance(checkin_data.quarter, Quarter)
        else checkin_data.quarter
    )

    for link in shared_links:
        recipient_goal = (
            db.query(Goal)
            .filter(
                Goal.parent_shared_goal_id == goal_id,
                Goal.employee_id == link.recipient_employee_id,
            )
            .first()
        )
        if not recipient_goal:
            continue

        existing_checkin = (
            db.query(QuarterlyCheckin)
            .filter(
                QuarterlyCheckin.goal_id == recipient_goal.id,
                QuarterlyCheckin.quarter == checkin_data.quarter,
            )
            .first()
        )

        sync_note = (
            f"Auto-synced from primary owner. "
            f"Original note: {checkin_data.employee_note or 'None'}"
        )

        if existing_checkin:
            existing_checkin.actual_value = checkin_data.actual_value
            existing_checkin.actual_date = checkin_data.actual_date
            existing_checkin.status = checkin_data.status
            existing_checkin.employee_note = sync_note
            existing_checkin.updated_at = _utc_now()
        else:
            db.add(
                QuarterlyCheckin(
                    goal_id=recipient_goal.id,
                    quarter=checkin_data.quarter,
                    actual_value=checkin_data.actual_value,
                    actual_date=checkin_data.actual_date,
                    status=checkin_data.status,
                    employee_note=sync_note,
                )
            )

        synced_count += 1
        write_audit_log(
            db,
            entity="checkin",
            entity_id=recipient_goal.id,
            changed_by=changed_by,
            change_description=(
                f"Check-in auto-synced from shared goal owner for {quarter}"
            ),
        )

    if synced_count:
        db.commit()
    return synced_count


def _checkin_upsert_response(
    goal: Goal,
    checkin: QuarterlyCheckin,
    *,
    synced_to_employees: int = 0,
) -> CheckinUpsertResponse:
    base = _to_checkin_response(goal, checkin)
    return CheckinUpsertResponse(
        **base.model_dump(),
        synced_to_employees=synced_to_employees,
    )


def _get_checkin_or_404(checkin_id: int, db: Session) -> QuarterlyCheckin:
    checkin = db.query(QuarterlyCheckin).filter(QuarterlyCheckin.id == checkin_id).first()
    if checkin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check-in not found")
    return checkin


def _build_employee_report(
    employee: User,
    goals: list[Goal],
    db: Session,
    *,
    quarter_filter: str | None = None,
) -> EmployeeProgressReport:
    goal_entries: list[GoalWithCheckins] = []
    completed = 0
    scores: list[float] = []
    at_risk = 0

    for goal in goals:
        query = db.query(QuarterlyCheckin).filter(QuarterlyCheckin.goal_id == goal.id)
        if quarter_filter:
            query = query.filter(QuarterlyCheckin.quarter == Quarter(quarter_filter))
        checkins = query.order_by(QuarterlyCheckin.updated_at.desc()).all()

        entry = _build_goal_with_checkins(goal, checkins, db)
        goal_entries.append(entry)

        if quarter_filter:
            if checkins:
                completed += 1
                if entry.latest_checkin and entry.latest_checkin.progress_score is not None:
                    scores.append(entry.latest_checkin.progress_score)
                    if entry.latest_checkin.progress_score < 60:
                        at_risk += 1
        else:
            for response in entry.checkins:
                if response.progress_score is not None:
                    scores.append(response.progress_score)
                    if response.progress_score < 60:
                        at_risk += 1
            completed += len(entry.checkins)

    required = len(goals) if quarter_filter else len(goals) * len(QUARTERS)
    if quarter_filter:
        required = len(goals)

    quarter_summaries = []
    for q in QUARTERS:
        q_scores: list[float] = []
        q_done = 0
        for goal in goals:
            checkin = (
                db.query(QuarterlyCheckin)
                .filter(
                    QuarterlyCheckin.goal_id == goal.id,
                    QuarterlyCheckin.quarter == Quarter(q),
                )
                .first()
            )
            if checkin:
                q_done += 1
                score = _checkin_progress(goal, checkin)
                q_scores.append(score)
        quarter_summaries.append(
            {
                "quarter": q,
                "checkins_submitted": q_done,
                "checkins_required": len(goals),
                "completion_rate": round((q_done / len(goals)) * 100, 2) if goals else 0.0,
                "average_progress": round(sum(q_scores) / len(q_scores), 2) if q_scores else 0.0,
            }
        )

    avg = round(sum(scores) / len(scores), 2) if scores else 0.0
    rate = round((completed / required) * 100, 2) if required else 0.0

    return EmployeeProgressReport(
        employee_id=employee.id,
        employee_name=employee.name,
        employee_email=employee.email,
        goals=goal_entries,
        average_progress=avg,
        completed_checkins=completed,
        total_required_checkins=required,
        completion_rate=rate,
        quarters=quarter_summaries if not quarter_filter else [],
        at_risk_count=at_risk,
    )


@router.post("/{goal_id}", response_model=CheckinUpsertResponse)
def upsert_checkin(
    goal_id: int,
    payload: CheckinCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.employee))],
):
    demo_mode = request.headers.get("X-Demo-Mode", "false").lower() == "true"
    is_admin = current_user.role == UserRole.admin

    if not demo_mode and not is_admin:
        active_quarter = get_active_quarter()
        if not active_quarter:
            phase = get_current_phase()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"No check-in window is currently open. "
                    f"Current phase: {phase['label']}. "
                    f"Check-in windows: Q1 (July-Sept), "
                    f"Q2 (Oct-Dec), Q3 (Jan-Mar), "
                    f"Q4 (Mar-Apr)."
                ),
            )
        if payload.quarter != active_quarter:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Only {active_quarter} check-ins are accepted right now. "
                    f"You attempted to submit for {payload.quarter}. "
                    f"Please wait for the correct window."
                ),
            )

    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if goal is None or goal.employee_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")

    _ensure_approved_locked(goal)
    validate_checkin_actual_fields(goal.uom_type, payload.actual_value, payload.actual_date)

    checkin = (
        db.query(QuarterlyCheckin)
        .filter(
            QuarterlyCheckin.goal_id == goal_id,
            QuarterlyCheckin.quarter == Quarter(payload.quarter),
        )
        .first()
    )

    is_new = checkin is None
    if is_new:
        checkin = QuarterlyCheckin(
            goal_id=goal_id,
            quarter=Quarter(payload.quarter),
            status=CheckinStatus(payload.status),
        )
        db.add(checkin)

    checkin.actual_value = payload.actual_value
    checkin.actual_date = payload.actual_date
    checkin.status = CheckinStatus(payload.status)
    checkin.employee_note = payload.employee_note
    checkin.updated_at = _utc_now()

    score = _checkin_progress(goal, checkin)
    value_display = payload.actual_value if payload.actual_value is not None else payload.actual_date
    write_audit_log(
        db,
        entity="checkin",
        entity_id=goal_id,
        changed_by=current_user.id,
        change_description=(
            f"Check-in logged for {payload.quarter}: actual={value_display}, score={score}%"
        ),
    )
    db.commit()
    invalidate_mutation_caches(checkins=True)
    db.refresh(checkin)

    synced = sync_shared_goal_checkins(
        goal_id,
        checkin,
        db,
        changed_by=current_user.id,
    )
    if synced:
        invalidate_mutation_caches(checkins=True)

    return _checkin_upsert_response(goal, checkin, synced_to_employees=synced)


@router.get("/my", response_model=list[GoalWithCheckins])
def list_my_checkins(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.employee))],
):
    goals = _approved_goals(db, current_user.id)
    result = []
    for goal in goals:
        checkins = (
            db.query(QuarterlyCheckin)
            .filter(QuarterlyCheckin.goal_id == goal.id)
            .order_by(QuarterlyCheckin.quarter)
            .all()
        )
        result.append(_build_goal_with_checkins(goal, checkins, db))
    return result


@router.get("/my/{quarter}", response_model=list[GoalWithCheckins])
def list_my_checkins_for_quarter(
    quarter: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.employee))],
):
    if quarter not in QUARTERS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid quarter")

    goals = _approved_goals(db, current_user.id)
    result = []
    for goal in goals:
        checkin = (
            db.query(QuarterlyCheckin)
            .filter(
                QuarterlyCheckin.goal_id == goal.id,
                QuarterlyCheckin.quarter == Quarter(quarter),
            )
            .first()
        )
        checkins = [checkin] if checkin else []
        result.append(_build_goal_with_checkins(goal, checkins, db))
    return result


@router.put("/{checkin_id}", response_model=CheckinUpsertResponse)
def update_checkin(
    checkin_id: int,
    payload: CheckinUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.employee))],
):
    checkin = _get_checkin_or_404(checkin_id, db)
    goal = db.query(Goal).filter(Goal.id == checkin.goal_id).first()

    if goal is None or goal.employee_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden")

    if checkin.manager_comment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit after manager has reviewed this check-in",
        )

    updates = payload.model_dump(exclude_unset=True)
    if "actual_value" in updates:
        checkin.actual_value = updates["actual_value"]
    if "actual_date" in updates:
        checkin.actual_date = updates["actual_date"]
    if "status" in updates and updates["status"] is not None:
        checkin.status = CheckinStatus(updates["status"])
    if "employee_note" in updates:
        checkin.employee_note = updates["employee_note"]

    validate_checkin_actual_fields(goal.uom_type, checkin.actual_value, checkin.actual_date)
    checkin.updated_at = _utc_now()

    quarter = checkin.quarter.value if isinstance(checkin.quarter, Quarter) else checkin.quarter
    write_audit_log(
        db,
        entity="checkin",
        entity_id=checkin.id,
        changed_by=current_user.id,
        change_description=f"Check-in updated for {quarter}",
    )
    db.commit()
    invalidate_mutation_caches(checkins=True)
    db.refresh(checkin)

    synced = sync_shared_goal_checkins(
        goal.id,
        checkin,
        db,
        changed_by=current_user.id,
    )
    if synced:
        invalidate_mutation_caches(checkins=True)

    return _checkin_upsert_response(goal, checkin, synced_to_employees=synced)


@router.post("/{checkin_id}/manager-comment", response_model=CheckinResponse)
def add_manager_comment(
    checkin_id: int,
    payload: ManagerCheckinComment,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.manager))],
):
    checkin = _get_checkin_or_404(checkin_id, db)
    goal = db.query(Goal).filter(Goal.id == checkin.goal_id).first()
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")

    employee = db.query(User).filter(User.id == goal.employee_id).first()
    if (
        employee is None
        or employee.manager_id != current_user.id
        or not employee.is_active
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden")

    comment = payload.manager_comment.strip()
    checkin.manager_comment = comment
    checkin.updated_at = _utc_now()

    quarter = checkin.quarter.value if isinstance(checkin.quarter, Quarter) else checkin.quarter
    write_audit_log(
        db,
        entity="checkin",
        entity_id=checkin.id,
        changed_by=current_user.id,
        change_description=f"Manager added check-in comment for {quarter}: {comment}",
    )
    db.commit()
    invalidate_mutation_caches(checkins=True)
    db.refresh(checkin)
    return _to_checkin_response(goal, checkin)


@router.get("/team/overview", response_model=list[EmployeeProgressReport])
def team_checkin_overview(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.manager))],
):
    reports = []
    for employee in get_manager_direct_reports(db, current_user.id):
        goals = _approved_goals(db, employee.id)
        reports.append(_build_employee_report(employee, goals, db))
    return reports


@router.get("/team/{quarter}", response_model=list[EmployeeProgressReport])
def team_checkins_for_quarter(
    quarter: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.manager))],
):
    if quarter not in QUARTERS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid quarter")

    reports = []
    employees = get_manager_direct_reports(db, current_user.id)
    for employee in employees:
        goals = _approved_goals(db, employee.id)
        reports.append(_build_employee_report(employee, goals, db, quarter_filter=quarter))
    return reports
