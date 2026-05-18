from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from auth import get_current_user, require_role
from cache import cache_response, invalidate_mutation_caches
from database import get_db
from email_tasks import notify_goal_submitted
from notification_service import create_notification
from models import (
    ApprovalAction,
    Goal,
    GoalApproval,
    GoalStatus,
    SharedGoalLink,
    UomType,
    User,
    UserRole,
)
from schemas import (
    GoalCreate,
    GoalListResponse,
    GoalResponse,
    GoalUpdate,
    MessageResponse,
    SubmitAllResponse,
    TeamEmployeeGoals,
    TeamGoalsResponse,
)
from utils import (
    MAX_TOTAL_WEIGHTAGE,
    get_manager_direct_reports,
    sum_goal_weightage,
    validate_goal_count,
    validate_goal_weightage,
    validate_uom_fields,
    write_audit_log,
)

router = APIRouter(
    prefix="/goals",
    tags=["goals"],
    dependencies=[Depends(get_current_user)],
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _latest_return_comment(goal: Goal, db: Session | None = None) -> str | None:
    if db is None:
        return None
    record = (
        db.query(GoalApproval)
        .filter(
            GoalApproval.goal_id == goal.id,
            GoalApproval.action == ApprovalAction.returned,
        )
        .order_by(GoalApproval.acted_at.desc())
        .first()
    )
    return record.comment if record else None


def _goal_response(
    goal: Goal,
    *,
    return_comment: str | None = None,
    db: Session | None = None,
) -> GoalResponse:
    comment = return_comment
    if comment is None and db is not None:
        comment = _latest_return_comment(goal, db)

    return GoalResponse(
        id=goal.id,
        employee_id=goal.employee_id,
        thrust_area=goal.thrust_area,
        title=goal.title,
        description=goal.description,
        uom_type=goal.uom_type.value if isinstance(goal.uom_type, UomType) else goal.uom_type,
        target_value=goal.target_value,
        target_date=goal.target_date,
        weightage=goal.weightage,
        is_locked=goal.is_locked,
        is_shared=goal.is_shared,
        parent_shared_goal_id=goal.parent_shared_goal_id,
        status=goal.status.value if isinstance(goal.status, GoalStatus) else goal.status,
        created_at=goal.created_at,
        updated_at=goal.updated_at,
        return_comment=comment,
    )


def _build_goal_list(goals: list[Goal], db: Session) -> GoalListResponse:
    total_weightage = sum_goal_weightage(goals)
    goal_count = len(goals)
    return GoalListResponse(
        goals=[_goal_response(goal, db=db) for goal in goals],
        total_weightage=total_weightage,
        remaining_weightage=round(MAX_TOTAL_WEIGHTAGE - total_weightage, 2),
        goal_count=goal_count,
        can_add_more=goal_count < 8,
    )


def _get_goal_or_404(goal_id: int, db: Session) -> Goal:
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return goal


def _is_manager_of(manager: User, employee_id: int, db: Session) -> bool:
    employee = db.query(User).filter(User.id == employee_id).first()
    return employee is not None and employee.manager_id == manager.id


def _can_view_goal(user: User, goal: Goal, db: Session) -> bool:
    if user.role == UserRole.admin:
        return True
    if goal.employee_id == user.id:
        return True
    if user.role == UserRole.manager and _is_manager_of(user, goal.employee_id, db):
        return True
    return False


def _ensure_can_view(user: User, goal: Goal, db: Session) -> None:
    if not _can_view_goal(user, goal, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden")


def _ensure_employee_owner(user: User, goal: Goal) -> None:
    if goal.employee_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden")


def _ensure_editable(goal: Goal) -> None:
    if goal.is_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This goal is locked after approval. "
                "Contact Admin to unlock it."
            ),
        )
    if goal.status not in (GoalStatus.draft, GoalStatus.returned):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only draft or returned goals can be modified",
        )


def _ensure_resubmitable(goal: Goal) -> None:
    if goal.status != GoalStatus.returned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only returned goals can be resubmitted",
        )
    if goal.is_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Goal is locked and cannot be resubmitted",
        )


def _employee_goals(db: Session, employee_id: int) -> list[Goal]:
    return (
        db.query(Goal)
        .filter(Goal.employee_id == employee_id)
        .order_by(Goal.created_at.desc())
        .all()
    )


def _validate_submission_weightage(goals: list[Goal], *, for_submit_all: bool = False) -> None:
    total = sum_goal_weightage(goals)
    if total != MAX_TOTAL_WEIGHTAGE:
        if for_submit_all:
            remaining = round(MAX_TOTAL_WEIGHTAGE - total, 2)
            detail = (
                "Total weightage must equal 100% before submitting. "
                f"Current total: {total:g}%. You need {remaining:g}% more."
            )
        else:
            detail = (
                "Total weightage must equal 100% before submitting. "
                f"Current total: {total:g}%. Please adjust your goals."
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _team_submission_status(goals: list[Goal]) -> str:
    if not goals:
        return "not_started"

    statuses = {goal.status for goal in goals}
    if statuses == {GoalStatus.approved}:
        return "approved"
    if GoalStatus.draft in statuses or GoalStatus.returned in statuses:
        if GoalStatus.submitted in statuses or GoalStatus.approved in statuses:
            return "partial"
        return "not_started"
    if statuses == {GoalStatus.submitted}:
        return "submitted"
    if GoalStatus.submitted in statuses and GoalStatus.approved not in statuses:
        return "submitted"
    return "partial"


def _manager_team_cache_key(**kwargs) -> str:
    current_user = kwargs["current_user"]
    return f"manager:team:{current_user.id}"


@router.post("/", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.employee))],
):
    validate_goal_count(current_user.id, db)
    validate_goal_weightage(current_user.id, payload.weightage, db)

    goal = Goal(
        employee_id=current_user.id,
        thrust_area=payload.thrust_area,
        title=payload.title,
        description=payload.description,
        uom_type=UomType(payload.uom_type),
        target_value=payload.target_value,
        target_date=payload.target_date,
        weightage=payload.weightage,
        status=GoalStatus.draft,
        is_locked=False,
    )
    db.add(goal)
    db.flush()

    write_audit_log(
        db,
        entity="goal",
        entity_id=goal.id,
        changed_by=current_user.id,
        change_description=f"Goal created: {goal.title}",
    )
    db.commit()
    invalidate_mutation_caches(goals=True)
    db.refresh(goal)
    return _goal_response(goal)


@router.get("/my", response_model=GoalListResponse)
def list_my_goals(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.employee))],
):
    goals = _employee_goals(db, current_user.id)
    return _build_goal_list(goals, db)


@router.get("/team", response_model=TeamGoalsResponse)
@cache_response(_manager_team_cache_key, expire_seconds=120)
def list_team_goals(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.manager))],
):
    reports = get_manager_direct_reports(db, current_user.id)

    team = []
    for employee in reports:
        goals = _employee_goals(db, employee.id)
        team.append(
            {
                "employee_id": employee.id,
                "employee_name": employee.name,
                "goals": [_goal_response(goal) for goal in goals],
                "total_weightage": sum_goal_weightage(goals),
                "submission_status": _team_submission_status(goals),
            }
        )

    return TeamGoalsResponse(
        team=[TeamEmployeeGoals(**entry) for entry in team],
    )


@router.post("/submit-all", response_model=SubmitAllResponse)
def submit_all_goals(
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.employee))],
):
    goals = (
        db.query(Goal)
        .filter(
            Goal.employee_id == current_user.id,
            Goal.status.in_([GoalStatus.draft, GoalStatus.returned]),
        )
        .all()
    )
    if not goals:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No draft goals found to submit",
        )

    all_goals = _employee_goals(db, current_user.id)
    _validate_submission_weightage(all_goals, for_submit_all=True)
    total = sum_goal_weightage(all_goals)

    for goal in goals:
        goal.status = GoalStatus.submitted
        goal.updated_at = _utc_now()

    write_audit_log(
        db,
        entity="goal",
        entity_id=current_user.id,
        changed_by=current_user.id,
        change_description=f"All {len(goals)} goals submitted for approval",
    )
    manager = None
    if current_user.manager_id:
        manager = db.query(User).filter(User.id == current_user.manager_id).first()
        if manager:
            create_notification(
                db,
                user_id=manager.id,
                type="goals_submitted",
                message=f"{current_user.name} submitted {len(goals)} goal(s) for approval",
                link="/manager/dashboard",
            )
    db.commit()
    invalidate_mutation_caches(goals=True)
    if manager:
        background_tasks.add_task(
            notify_goal_submitted,
            manager.email,
            manager.name,
            current_user.name,
            len(goals),
        )
    return SubmitAllResponse(
        message="All goals submitted successfully",
        submitted_count=len(goals),
        total_weightage=total,
    )


@router.get("/{goal_id}", response_model=GoalResponse)
def get_goal(
    goal_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    goal = _get_goal_or_404(goal_id, db)
    _ensure_can_view(current_user, goal, db)
    return _goal_response(goal, db=db)


@router.put("/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: int,
    payload: GoalUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.employee))],
):
    goal = _get_goal_or_404(goal_id, db)
    _ensure_employee_owner(current_user, goal)

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return _goal_response(goal)

    if goal.is_locked:
        shared_weightage_only = (
            goal.is_shared
            and goal.parent_shared_goal_id is not None
            and set(updates.keys()) <= {"weightage"}
        )
        if not shared_weightage_only:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "This goal is locked after approval. "
                    "Contact Admin to unlock it."
                ),
            )

    if goal.is_shared and goal.parent_shared_goal_id is not None:
        disallowed = [field for field in updates if field != "weightage"]
        if disallowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "This is a shared goal. Only weightage can be modified. "
                    "Title and target are set by your manager/admin."
                ),
            )
        if "weightage" not in updates or updates["weightage"] is None:
            return _goal_response(goal)

        validate_goal_weightage(
            current_user.id,
            updates["weightage"],
            db,
            exclude_goal_id=goal.id,
        )
        goal.weightage = updates["weightage"]
        goal.updated_at = _utc_now()

        link = (
            db.query(SharedGoalLink)
            .filter(
                SharedGoalLink.parent_goal_id == goal.parent_shared_goal_id,
                SharedGoalLink.recipient_employee_id == current_user.id,
            )
            .first()
        )
        if link:
            link.custom_weightage = updates["weightage"]

        write_audit_log(
            db,
            entity="goal",
            entity_id=goal.id,
            changed_by=current_user.id,
            change_description=f"Shared goal weightage updated to {updates['weightage']}%",
        )
        db.commit()
        invalidate_mutation_caches(goals=True)
        db.refresh(goal)
        return _goal_response(goal)

    _ensure_editable(goal)

    if "weightage" in updates and updates["weightage"] is not None:
        validate_goal_weightage(
            current_user.id,
            updates["weightage"],
            db,
            exclude_goal_id=goal.id,
        )

    target_value = updates.get("target_value", goal.target_value)
    target_date = updates.get("target_date", goal.target_date)
    if "target_value" in updates or "target_date" in updates:
        validate_uom_fields(goal.uom_type, target_value, target_date)

    changed_fields = []
    for field, value in updates.items():
        setattr(goal, field, value)
        changed_fields.append(field)

    goal.updated_at = _utc_now()

    write_audit_log(
        db,
        entity="goal",
        entity_id=goal.id,
        changed_by=current_user.id,
        change_description=f"Goal updated: {', '.join(changed_fields)} changed",
    )
    db.commit()
    invalidate_mutation_caches(goals=True)
    db.refresh(goal)
    return _goal_response(goal)


@router.delete("/{goal_id}", response_model=MessageResponse)
def delete_goal(
    goal_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.employee))],
):
    goal = _get_goal_or_404(goal_id, db)
    _ensure_employee_owner(current_user, goal)
    _ensure_editable(goal)

    title = goal.title
    db.delete(goal)

    write_audit_log(
        db,
        entity="goal",
        entity_id=goal_id,
        changed_by=current_user.id,
        change_description=f"Goal deleted: {title}",
    )
    db.commit()
    invalidate_mutation_caches(goals=True)
    return MessageResponse(message="Goal deleted successfully")


@router.post("/{goal_id}/submit", response_model=GoalResponse)
def submit_goal(
    goal_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.employee))],
):
    goal = _get_goal_or_404(goal_id, db)
    _ensure_employee_owner(current_user, goal)

    if goal.status == GoalStatus.submitted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This goal is already submitted and awaiting approval.",
        )

    if goal.status not in (GoalStatus.draft, GoalStatus.returned):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft or returned goals can be submitted",
        )

    all_goals = _employee_goals(db, current_user.id)
    _validate_submission_weightage(all_goals)

    goal.status = GoalStatus.submitted
    goal.updated_at = _utc_now()

    write_audit_log(
        db,
        entity="goal",
        entity_id=goal.id,
        changed_by=current_user.id,
        change_description=f"Goal '{goal.title}' submitted for approval",
    )
    db.commit()
    invalidate_mutation_caches(goals=True)
    db.refresh(goal)
    return _goal_response(goal, db=db)


@router.post("/{goal_id}/resubmit", response_model=GoalResponse)
def resubmit_goal(
    goal_id: int,
    payload: GoalUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.employee))],
):
    goal = _get_goal_or_404(goal_id, db)
    _ensure_employee_owner(current_user, goal)
    _ensure_resubmitable(goal)

    updates = payload.model_dump(exclude_unset=True)
    if updates:
        if "weightage" in updates and updates["weightage"] is not None:
            validate_goal_weightage(
                current_user.id,
                updates["weightage"],
                db,
                exclude_goal_id=goal.id,
            )

        target_value = updates.get("target_value", goal.target_value)
        target_date = updates.get("target_date", goal.target_date)
        if "target_value" in updates or "target_date" in updates:
            validate_uom_fields(goal.uom_type, target_value, target_date)

        for field, value in updates.items():
            setattr(goal, field, value)

    validate_uom_fields(goal.uom_type, goal.target_value, goal.target_date)

    goal.status = GoalStatus.submitted
    goal.is_locked = False
    goal.updated_at = _utc_now()

    write_audit_log(
        db,
        entity="goal",
        entity_id=goal.id,
        changed_by=current_user.id,
        change_description="Goal resubmitted after revision",
    )
    db.commit()
    invalidate_mutation_caches(goals=True)
    db.refresh(goal)
    return _goal_response(goal, db=db)
