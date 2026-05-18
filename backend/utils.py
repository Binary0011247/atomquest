from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Goal, UomType, User, UserRole

MAX_GOALS_PER_EMPLOYEE = 8
MIN_GOAL_WEIGHTAGE = 10.0
MAX_TOTAL_WEIGHTAGE = 100.0


def _employee_goals_query(db: Session, employee_id: int, exclude_goal_id: int | None = None):
    query = db.query(Goal).filter(Goal.employee_id == employee_id)
    if exclude_goal_id is not None:
        query = query.filter(Goal.id != exclude_goal_id)
    return query


def validate_goal_weightage(
    employee_id: int,
    new_weightage: float,
    db: Session,
    exclude_goal_id: int | None = None,
) -> float:
    if new_weightage < MIN_GOAL_WEIGHTAGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Each goal must have at least {MIN_GOAL_WEIGHTAGE:g}% weightage",
        )

    query = db.query(func.coalesce(func.sum(Goal.weightage), 0.0)).filter(
        Goal.employee_id == employee_id,
    )
    if exclude_goal_id is not None:
        query = query.filter(Goal.id != exclude_goal_id)

    existing_total = float(query.scalar() or 0.0)
    total = existing_total + new_weightage

    if total > MAX_TOTAL_WEIGHTAGE:
        maximum_for_goal = round(MAX_TOTAL_WEIGHTAGE - existing_total, 2)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"This weightage would exceed 100%. "
                f"You have {existing_total:g}% allocated to "
                f"other goals. Maximum for this goal: {maximum_for_goal:g}%"
            ),
        )

    return round(MAX_TOTAL_WEIGHTAGE - total, 2)


def get_manager_direct_reports(db: Session, manager_id: int) -> list[User]:
    """Active employees who report to this manager only."""
    return (
        db.query(User)
        .filter(
            User.manager_id == manager_id,
            User.role == UserRole.employee,
            User.is_active.is_(True),
        )
        .order_by(User.name)
        .all()
    )


def validate_goal_count(
    employee_id: int,
    db: Session,
    exclude_goal_id: int | None = None,
) -> None:
    count = _employee_goals_query(db, employee_id, exclude_goal_id).count()
    if count >= MAX_GOALS_PER_EMPLOYEE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 8 goals allowed per employee",
        )


def validate_uom_fields(
    uom_type: str | UomType,
    target_value: float | None,
    target_date: date | None,
) -> None:
    uom = uom_type.value if isinstance(uom_type, UomType) else uom_type

    if uom in ("numeric_min", "numeric_max"):
        if target_value is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"target_value is required for uom_type '{uom}'",
            )
        return

    if uom == "timeline":
        if target_date is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="target_date is required for uom_type 'timeline'",
            )
        return

    if uom == "zero":
        return

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid uom_type '{uom}'",
    )


def calculate_progress_score(
    uom_type: str | UomType,
    target_value: float | None,
    actual_value: float | None,
    target_date: date | None,
    actual_date: date | None,
) -> float:
    uom = uom_type.value if isinstance(uom_type, UomType) else uom_type

    try:
        if uom == "numeric_min":
            if target_value is None or actual_value is None or target_value == 0:
                return 0.0
            return round((actual_value / target_value) * 100, 2)

        if uom == "numeric_max":
            if target_value is None or actual_value is None:
                return 0.0
            if actual_value == 0:
                return 100.0
            return round((target_value / actual_value) * 100, 2)

        if uom == "timeline":
            if target_date is None or actual_date is None:
                return 0.0
            return 100.0 if actual_date <= target_date else 0.0

        if uom == "zero":
            if actual_value is None:
                return 0.0
            return 100.0 if actual_value == 0 else 0.0
    except ZeroDivisionError:
        return 0.0

    return 0.0


def sum_goal_weightage(goals: list[Goal]) -> float:
    return round(sum(goal.weightage for goal in goals), 2)


def get_score_color(score: float | None) -> str:
    if score is None:
        return "red"
    if score >= 90:
        return "green"
    if score >= 60:
        return "yellow"
    return "red"


PHASE_OVERRIDE: str | None = None


def set_phase_override(phase: str | None) -> None:
    global PHASE_OVERRIDE
    PHASE_OVERRIDE = phase


def get_phase_override() -> str | None:
    return PHASE_OVERRIDE


def get_active_quarter() -> str | None:
    if PHASE_OVERRIDE:
        if PHASE_OVERRIDE == "goal_setting":
            return None
        return PHASE_OVERRIDE

    month = datetime.now().month
    quarter_map = {
        7: "Q1",
        8: "Q1",
        9: "Q1",
        10: "Q2",
        11: "Q2",
        12: "Q2",
        1: "Q3",
        2: "Q3",
        3: "Q3",
        4: "Q4",
    }
    return quarter_map.get(month)


def is_goal_setting_phase() -> bool:
    if PHASE_OVERRIDE:
        return PHASE_OVERRIDE == "goal_setting"
    return datetime.now().month in (5, 6)


def get_current_phase() -> dict:
    if PHASE_OVERRIDE:
        if PHASE_OVERRIDE == "goal_setting":
            return {
                "phase": "goal_setting",
                "label": "Goal Setting Phase",
                "description": "Create and submit your goals for manager approval",
                "active_quarter": None,
            }
        return {
            "phase": "checkin",
            "label": f"{PHASE_OVERRIDE} Check-in Phase",
            "description": f"Log your {PHASE_OVERRIDE} actual achievements",
            "active_quarter": PHASE_OVERRIDE,
        }

    month = datetime.now().month
    if month in (5, 6):
        return {
            "phase": "goal_setting",
            "label": "Goal Setting Phase",
            "description": "Create and submit your goals for manager approval",
            "active_quarter": None,
        }
    active_q = get_active_quarter()
    if active_q:
        return {
            "phase": "checkin",
            "label": f"{active_q} Check-in Phase",
            "description": f"Log your {active_q} actual achievements",
            "active_quarter": active_q,
        }
    return {
        "phase": "closed",
        "label": "No Active Phase",
        "description": "No check-in window is currently open",
        "active_quarter": None,
    }


def get_next_phase_hint() -> str:
    month = datetime.now().month
    if PHASE_OVERRIDE == "goal_setting" or (not PHASE_OVERRIDE and month in (5, 6)):
        return "Q1 Check-in opens July 1st"
    active = get_active_quarter()
    if active == "Q1":
        return "Q2 Check-in opens October 1st"
    if active == "Q2":
        return "Q3 Check-in opens January 1st"
    if active == "Q3":
        return "Q4 Check-in opens April 1st"
    if active == "Q4":
        return "Goal Setting opens May 1st"
    return "Q1 Check-in opens July 1st"


def get_current_quarter() -> str:
    """Legacy helper; returns active quarter or best guess for UI defaults."""
    active = get_active_quarter()
    if active:
        return active
    month = datetime.now().month
    if month in (5, 6):
        return "Q1"
    if month in (7, 8, 9):
        return "Q1"
    if month in (10, 11, 12):
        return "Q2"
    if month in (1, 2, 3):
        return "Q3"
    return "Q4"


def is_checkin_window_open(quarter: str) -> bool:
    active = get_active_quarter()
    return active is not None and active == quarter


def validate_checkin_actual_fields(
    uom_type: str | UomType,
    actual_value: float | None,
    actual_date: date | None,
) -> None:
    uom = uom_type.value if isinstance(uom_type, UomType) else uom_type

    if uom in ("numeric_min", "numeric_max"):
        if actual_value is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"actual_value is required for uom_type '{uom}'",
            )
        return

    if uom == "timeline":
        if actual_date is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="actual_date is required for uom_type 'timeline'",
            )
        return

    if uom == "zero":
        if actual_value is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="actual_value is required for uom_type 'zero' (use 0 for success)",
            )
        return

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid uom_type '{uom}'",
    )


def write_audit_log(
    db: Session,
    *,
    entity: str,
    entity_id: int,
    changed_by: int,
    change_description: str,
) -> None:
    from models import AuditLog

    db.add(
        AuditLog(
            entity=entity,
            entity_id=entity_id,
            changed_by=changed_by,
            change_description=change_description,
        )
    )
