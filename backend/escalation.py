from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

import os

from cycle_helpers import get_current_active_quarter
from models import (
    EscalationLog,
    EscalationType,
    Goal,
    GoalStatus,
    Quarter,
    QuarterlyCheckin,
    User,
    UserRole,
)
from email_service import (
    send_escalation_employee,
    send_escalation_hr,
    send_escalation_manager,
)

GOAL_SUBMIT_THRESHOLD_DAYS = 3
APPROVAL_PENDING_THRESHOLD_DAYS = 2
CHECKIN_GRACE_DAYS = 14


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _days_between(start: datetime, end: datetime | None = None) -> int:
    end = end or _utc_now()
    start_naive = start.replace(tzinfo=None) if start.tzinfo else start
    end_naive = end.replace(tzinfo=None) if end.tzinfo else end
    return max(0, (end_naive.date() - start_naive.date()).days)


def _has_unresolved(
    db: Session,
    escalation_type: EscalationType,
    *,
    employee_id: int | None = None,
    manager_id: int | None = None,
    goal_id: int | None = None,
    quarter: str | None = None,
) -> bool:
    query = db.query(EscalationLog).filter(
        EscalationLog.escalation_type == escalation_type,
        EscalationLog.is_resolved.is_(False),
    )
    if employee_id is not None:
        query = query.filter(EscalationLog.employee_id == employee_id)
    if manager_id is not None:
        query = query.filter(EscalationLog.manager_id == manager_id)
    if goal_id is not None:
        query = query.filter(EscalationLog.goal_id == goal_id)
    if quarter is not None:
        query = query.filter(EscalationLog.message.contains(f"Q{quarter.lstrip('Q')}"))
    return query.first() is not None


def _notify_escalation(
    db: Session,
    log: EscalationLog,
    *,
    employee: User | None,
    manager: User | None,
    goal: Goal | None,
    days: int,
) -> None:
    from notification_service import create_notification, run_async

    action = log.message
    goal_title = goal.title if goal else None

    if log.escalation_type == EscalationType.goal_not_submitted and employee:
        create_notification(
            db,
            user_id=employee.id,
            type="escalation",
            message=action,
            link="/employee/dashboard",
        )
        run_async(
            send_escalation_employee(
                employee.email,
                employee.name,
                "Submit your goals for approval",
                days,
            )
        )
        if days >= 5 and manager:
            run_async(
                send_escalation_manager(
                    manager.email,
                    manager.name,
                    employee.name,
                    "Goals not submitted",
                    days,
                )
            )
    elif log.escalation_type == EscalationType.approval_pending_too_long and manager:
        create_notification(
            db,
            user_id=manager.id,
            type="escalation",
            message=action,
            link="/manager/dashboard",
        )
        run_async(
            send_escalation_manager(
                manager.email,
                manager.name,
                employee.name if employee else "Team member",
                "Approve pending goals",
                days,
                goal_title,
            )
        )
    elif log.escalation_type == EscalationType.checkin_not_logged and employee:
        create_notification(
            db,
            user_id=employee.id,
            type="escalation",
            message=action,
            link="/employee/checkins",
        )
        run_async(
            send_escalation_employee(
                employee.email,
                employee.name,
                "Log quarterly check-in",
                days,
                goal_title,
            )
        )

    if days >= 7 and employee:
        hr_email = os.getenv("HR_EMAIL", "admin@atomquest.com")
        hr_user = db.query(User).filter(User.email == hr_email).first()
        hr_name = hr_user.name if hr_user else "HR Admin"
        mgr_name = manager.name if manager else "Unassigned"
        run_async(
            send_escalation_hr(
                hr_email,
                hr_name,
                employee.name,
                mgr_name,
                action,
                days,
                goal_title,
            )
        )


def run_escalation_check(db: Session) -> int:
    """Run all escalation rules; return count of newly created logs."""
    new_count = 0
    now = _utc_now()
    today = now.date()

    draft_goals = (
        db.query(Goal)
        .join(User, Goal.employee_id == User.id)
        .filter(Goal.status == GoalStatus.draft, User.role == UserRole.employee)
        .all()
    )
    employees_draft: dict[int, list[Goal]] = {}
    for goal in draft_goals:
        employees_draft.setdefault(goal.employee_id, []).append(goal)

    for employee_id, goals in employees_draft.items():
        stale = [g for g in goals if _days_between(g.created_at, now) > GOAL_SUBMIT_THRESHOLD_DAYS]
        if not stale:
            continue
        if _has_unresolved(db, EscalationType.goal_not_submitted, employee_id=employee_id):
            continue

        employee = db.query(User).filter(User.id == employee_id).first()
        if not employee:
            continue
        oldest = min(stale, key=lambda g: g.created_at)
        days = _days_between(oldest.created_at, now)
        log = EscalationLog(
            escalation_type=EscalationType.goal_not_submitted,
            employee_id=employee_id,
            message=(
                f"Employee {employee.name} has not submitted goals after {days} days"
            ),
        )
        db.add(log)
        db.flush()
        manager = (
            db.query(User).filter(User.id == employee.manager_id).first()
            if employee.manager_id
            else None
        )
        _notify_escalation(db, log, employee=employee, manager=manager, goal=None, days=days)
        new_count += 1

    submitted_goals = (
        db.query(Goal)
        .join(User, Goal.employee_id == User.id)
        .filter(Goal.status == GoalStatus.submitted)
        .all()
    )
    for goal in submitted_goals:
        days = _days_between(goal.updated_at, now)
        if days <= APPROVAL_PENDING_THRESHOLD_DAYS:
            continue
        if _has_unresolved(
            db, EscalationType.approval_pending_too_long, goal_id=goal.id
        ):
            continue

        employee = db.query(User).filter(User.id == goal.employee_id).first()
        if not employee:
            continue
        manager = (
            db.query(User).filter(User.id == employee.manager_id).first()
            if employee.manager_id
            else None
        )
        log = EscalationLog(
            escalation_type=EscalationType.approval_pending_too_long,
            manager_id=employee.manager_id,
            goal_id=goal.id,
            message=(
                f"Goal '{goal.title}' submitted by {employee.name} "
                f"has been waiting {days} days for approval"
            ),
        )
        db.add(log)
        db.flush()
        _notify_escalation(
            db, log, employee=employee, manager=manager, goal=goal, days=days
        )
        new_count += 1

    active_quarter, quarter_start = get_current_active_quarter(db, today)
    days_into_quarter = max(0, (today - quarter_start).days)
    if today < quarter_start + timedelta(days=CHECKIN_GRACE_DAYS):
        db.commit()
        return new_count

    approved_goals = db.query(Goal).filter(Goal.status == GoalStatus.approved).all()
    for goal in approved_goals:
        checkin = (
            db.query(QuarterlyCheckin)
            .filter(
                QuarterlyCheckin.goal_id == goal.id,
                QuarterlyCheckin.quarter == Quarter(active_quarter),
            )
            .first()
        )
        if checkin is not None:
            continue
        if _has_unresolved(
            db,
            EscalationType.checkin_not_logged,
            goal_id=goal.id,
            quarter=active_quarter,
        ):
            continue

        employee = db.query(User).filter(User.id == goal.employee_id).first()
        if not employee:
            continue
        manager = (
            db.query(User).filter(User.id == employee.manager_id).first()
            if employee.manager_id
            else None
        )
        log = EscalationLog(
            escalation_type=EscalationType.checkin_not_logged,
            employee_id=goal.employee_id,
            goal_id=goal.id,
            message=(
                f"Employee {employee.name} has not logged "
                f"{active_quarter} check-in for goal '{goal.title}'"
            ),
        )
        db.add(log)
        db.flush()
        _notify_escalation(
            db,
            log,
            employee=employee,
            manager=manager,
            goal=goal,
            days=days_into_quarter,
        )
        new_count += 1

    db.commit()
    return new_count
