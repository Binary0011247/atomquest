from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from auth import get_current_user, require_role
from cache import invalidate_mutation_caches
from database import get_db
from email_tasks import notify_goal_approved, notify_goal_returned
from notification_service import create_notification
from models import (
    ApprovalAction as ApprovalActionEnum,
    Goal,
    GoalApproval,
    GoalStatus,
    User,
    UserRole,
)
from routers.goals import _goal_response, _latest_return_comment, _utc_now
from schemas import (
    ApprovalAction as ApprovalActionRequest,
    ApprovalHistoryItem,
    ApprovalHistoryResponse,
    ApprovalResponse,
    ApproveAllResponse,
    GoalReviewResponse,
    ManagerDashboardResponse,
    PendingApprovalsResponse,
    PendingEmployeeGroup,
    TeamGoalSummary,
)
from utils import get_manager_direct_reports, sum_goal_weightage, validate_uom_fields, write_audit_log

router = APIRouter(
    prefix="/approvals",
    tags=["approvals"],
    dependencies=[Depends(get_current_user)],
)


def _get_direct_report_or_403(manager: User, employee_id: int, db: Session) -> User:
    employee = db.query(User).filter(User.id == employee_id).first()
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )
    if (
        employee.manager_id != manager.id
        or employee.role != UserRole.employee
        or not employee.is_active
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This employee is not in your team",
        )
    return employee


def _get_goal_for_manager(goal_id: int, manager: User, db: Session) -> Goal:
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")

    employee = db.query(User).filter(User.id == goal.employee_id).first()
    if employee is None or employee.manager_id != manager.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This employee is not in your team",
        )
    return goal


def _get_manager_reports(db: Session, manager_id: int) -> list[User]:
    return get_manager_direct_reports(db, manager_id)


def _employee_goals(db: Session, employee_id: int) -> list[Goal]:
    return (
        db.query(Goal)
        .filter(Goal.employee_id == employee_id)
        .order_by(Goal.updated_at.asc())
        .all()
    )


def _compute_submission_status(goals: list[Goal]) -> str:
    if not goals:
        return "not_started"

    if any(goal.status == GoalStatus.returned for goal in goals):
        return "has_returned"

    statuses = {goal.status for goal in goals}

    if statuses == {GoalStatus.approved}:
        return "approved"

    if statuses == {GoalStatus.submitted}:
        return "submitted"

    has_draft = GoalStatus.draft in statuses
    has_submitted = GoalStatus.submitted in statuses

    if has_draft and not has_submitted:
        return "partial"

    if has_submitted and GoalStatus.approved not in statuses:
        if all(goal.status == GoalStatus.submitted for goal in goals):
            return "submitted"

    if GoalStatus.approved in statuses and GoalStatus.submitted not in statuses:
        if all(goal.status == GoalStatus.approved for goal in goals):
            return "approved"

    return "partial"


def _build_team_goal_summary(employee: User, goals: list[Goal], db: Session) -> TeamGoalSummary:
    return TeamGoalSummary(
        employee_id=employee.id,
        employee_name=employee.name,
        employee_email=employee.email,
        total_goals=len(goals),
        submitted_goals=sum(1 for g in goals if g.status == GoalStatus.submitted),
        approved_goals=sum(1 for g in goals if g.status == GoalStatus.approved),
        returned_goals=sum(1 for g in goals if g.status == GoalStatus.returned),
        total_weightage=sum_goal_weightage(goals),
        submission_status=_compute_submission_status(goals),
        goals=[
            _goal_response(goal, return_comment=_latest_return_comment(goal, db))
            for goal in goals
        ],
    )


def _validate_manager_weightage_edit(
    goal: Goal,
    new_weightage: float,
    db: Session,
) -> None:
    other_goals = (
        db.query(Goal)
        .filter(Goal.employee_id == goal.employee_id, Goal.id != goal.id)
        .all()
    )
    other_total = sum_goal_weightage(other_goals)
    if other_total + new_weightage > 100.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Edited weightage would exceed 100% for this employee",
        )


def _apply_manager_edits(
    goal: Goal,
    payload: ApprovalActionRequest,
    db: Session,
    manager: User,
) -> None:
    if (
        payload.edited_target_value is not None
        and payload.edited_target_value != goal.target_value
    ):
        old = goal.target_value
        goal.target_value = payload.edited_target_value
        write_audit_log(
            db,
            entity="goal",
            entity_id=goal.id,
            changed_by=manager.id,
            change_description=(
                f"Manager edited target_value from {old} to {payload.edited_target_value} "
                "before approval"
            ),
        )

    if payload.edited_target_date is not None and payload.edited_target_date != goal.target_date:
        goal.target_date = payload.edited_target_date
        write_audit_log(
            db,
            entity="goal",
            entity_id=goal.id,
            changed_by=manager.id,
            change_description="Manager edited target_date before approval",
        )

    if payload.edited_weightage is not None and payload.edited_weightage != goal.weightage:
        _validate_manager_weightage_edit(goal, payload.edited_weightage, db)
        old = goal.weightage
        goal.weightage = payload.edited_weightage
        write_audit_log(
            db,
            entity="goal",
            entity_id=goal.id,
            changed_by=manager.id,
            change_description=(
                f"Manager edited weightage from {old} to {payload.edited_weightage} "
                "before approval"
            ),
        )

    if (
        payload.edited_target_value is not None
        or payload.edited_target_date is not None
        or payload.edited_weightage is not None
    ):
        validate_uom_fields(goal.uom_type, goal.target_value, goal.target_date)
        goal.updated_at = _utc_now()


def _create_approval_record(
    db: Session,
    *,
    goal: Goal,
    manager: User,
    action: ApprovalActionEnum,
    comment: str | None,
) -> GoalApproval:
    record = GoalApproval(
        goal_id=goal.id,
        manager_id=manager.id,
        action=action,
        comment=comment,
        acted_at=_utc_now(),
    )
    db.add(record)
    return record


@router.get("/dashboard", response_model=ManagerDashboardResponse)
def manager_dashboard(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.manager))],
):
    reports = _get_manager_reports(db, current_user.id)
    team_summary = [
        _build_team_goal_summary(employee, _employee_goals(db, employee.id), db)
        for employee in reports
    ]

    pending_count = (
        db.query(Goal)
        .join(User, Goal.employee_id == User.id)
        .filter(
            User.manager_id == current_user.id,
            User.is_active.is_(True),
            Goal.status == GoalStatus.submitted,
        )
        .count()
    )

    return ManagerDashboardResponse(
        team_summary=team_summary,
        pending_approvals_count=pending_count,
        total_team_members=len(reports),
    )


@router.get("/pending", response_model=PendingApprovalsResponse)
def list_pending_approvals(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.manager))],
):
    goals = (
        db.query(Goal)
        .join(User, Goal.employee_id == User.id)
        .options(joinedload(Goal.employee))
        .filter(
            User.manager_id == current_user.id,
            User.is_active.is_(True),
            Goal.status == GoalStatus.submitted,
        )
        .order_by(User.name.asc(), Goal.updated_at.asc())
        .all()
    )

    by_employee: dict[int, dict] = {}
    for goal in goals:
        emp = goal.employee
        if emp.id not in by_employee:
            by_employee[emp.id] = {
                "employee_id": emp.id,
                "employee_name": emp.name,
                "employee_email": emp.email,
                "submitted_goals_count": 0,
                "goals": [],
            }
        by_employee[emp.id]["goals"].append(_goal_response(goal, db=db))
        by_employee[emp.id]["submitted_goals_count"] += 1

    groups = sorted(
        [PendingEmployeeGroup(**data) for data in by_employee.values()],
        key=lambda g: g.employee_name.lower(),
    )
    return PendingApprovalsResponse(
        groups=groups,
        total_pending_goals=len(goals),
    )


@router.post("/{goal_id}/review", response_model=GoalReviewResponse)
def review_goal(
    goal_id: int,
    payload: ApprovalActionRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.manager))],
):
    goal = _get_goal_for_manager(goal_id, current_user, db)

    if goal.status != GoalStatus.submitted:
        status_val = (
            goal.status.value if hasattr(goal.status, "value") else goal.status
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Only submitted goals can be reviewed. "
                f"Current status: {status_val}"
            ),
        )

    action_enum = ApprovalActionEnum(payload.action)

    if action_enum == ApprovalActionEnum.returned:
        if not payload.comment or not payload.comment.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A comment is required when returning a goal to the employee",
            )

        goal.status = GoalStatus.returned
        goal.is_locked = False
        goal.updated_at = _utc_now()
        _create_approval_record(
            db,
            goal=goal,
            manager=current_user,
            action=action_enum,
            comment=payload.comment.strip(),
        )
        write_audit_log(
            db,
            entity="goal",
            entity_id=goal.id,
            changed_by=current_user.id,
            change_description=f"Goal returned. Reason: {payload.comment.strip()}",
        )
        employee = db.query(User).filter(User.id == goal.employee_id).first()
        if employee:
            create_notification(
                db,
                user_id=employee.id,
                type="goal_returned",
                message=f"Goal '{goal.title}' was returned for revision",
                link="/employee/dashboard",
            )
        db.commit()
        invalidate_mutation_caches(goals=True)
        db.refresh(goal)
        if employee:
            background_tasks.add_task(
                notify_goal_returned,
                employee.email,
                employee.name,
                goal.title,
                current_user.name,
                payload.comment.strip(),
            )
        return GoalReviewResponse(
            message="Goal returned to employee",
            goal=_goal_response(
                goal,
                return_comment=payload.comment.strip(),
                db=db,
            ),
        )

    _apply_manager_edits(goal, payload, db, current_user)
    goal.status = GoalStatus.approved
    goal.is_locked = True
    goal.updated_at = _utc_now()
    _create_approval_record(
        db,
        goal=goal,
        manager=current_user,
        action=action_enum,
        comment=payload.comment,
    )
    write_audit_log(
        db,
        entity="goal",
        entity_id=goal.id,
        changed_by=current_user.id,
        change_description="Goal approved by manager",
    )
    employee = db.query(User).filter(User.id == goal.employee_id).first()
    if employee:
        create_notification(
            db,
            user_id=employee.id,
            type="goal_approved",
            message=f"Goal '{goal.title}' was approved",
            link="/employee/checkins",
        )
    db.commit()
    invalidate_mutation_caches(goals=True)
    db.refresh(goal)
    if employee:
        background_tasks.add_task(
            notify_goal_approved,
            employee.email,
            employee.name,
            goal.title,
            current_user.name,
        )
    return GoalReviewResponse(
        message="Goal approved and locked",
        goal=_goal_response(goal, db=db),
    )


@router.post("/approve-all/{employee_id}", response_model=ApproveAllResponse)
def approve_all_goals(
    employee_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.manager))],
):
    employee = _get_direct_report_or_403(current_user, employee_id, db)
    submitted_goals = [
        goal
        for goal in _employee_goals(db, employee.id)
        if goal.status == GoalStatus.submitted
    ]

    if not submitted_goals:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No submitted goals found for this employee",
        )

    goal_titles = []
    for goal in submitted_goals:
        goal.status = GoalStatus.approved
        goal.is_locked = True
        goal.updated_at = _utc_now()
        goal_titles.append(goal.title)
        _create_approval_record(
            db,
            goal=goal,
            manager=current_user,
            action=ApprovalActionEnum.approved,
            comment=None,
        )

    count = len(submitted_goals)
    write_audit_log(
        db,
        entity="goal",
        entity_id=employee.id,
        changed_by=current_user.id,
        change_description=(
            f"Bulk approval: {count} goals approved for employee {employee.name}"
        ),
    )
    db.commit()
    invalidate_mutation_caches(goals=True)

    return ApproveAllResponse(
        message="All goals approved successfully",
        employee_name=employee.name,
        approved_count=count,
        goal_titles=goal_titles,
    )


@router.get("/history/{employee_id}", response_model=ApprovalHistoryResponse)
def approval_history(
    employee_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.manager))],
):
    _get_direct_report_or_403(current_user, employee_id, db)

    records = (
        db.query(GoalApproval)
        .join(Goal, GoalApproval.goal_id == Goal.id)
        .join(User, GoalApproval.manager_id == User.id)
        .filter(Goal.employee_id == employee_id)
        .order_by(GoalApproval.acted_at.desc())
        .all()
    )

    history = []
    for record in records:
        goal = db.query(Goal).filter(Goal.id == record.goal_id).first()
        manager = db.query(User).filter(User.id == record.manager_id).first()
        action = (
            record.action.value
            if isinstance(record.action, ApprovalActionEnum)
            else record.action
        )
        history.append(
            ApprovalHistoryItem(
                goal_id=record.goal_id,
                goal_title=goal.title if goal else "Unknown",
                action=action,
                comment=record.comment,
                manager_name=manager.name if manager else "Unknown",
                acted_at=record.acted_at,
            )
        )

    return ApprovalHistoryResponse(history=history)
