import asyncio
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import (
    EscalationLog,
    EscalationType,
    Goal,
    GoalStatus,
    Notification,
    Quarter,
    QuarterlyCheckin,
    User,
    UserRole,
)
from cycle_helpers import get_current_active_quarter


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_notification(
    db: Session,
    *,
    user_id: int,
    type: str,
    message: str,
    link: str,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        type=type,
        message=message,
        link=link,
    )
    db.add(notification)
    return notification


def _notification_item(n: Notification) -> dict:
    return {
        "id": n.id,
        "type": n.type,
        "message": n.message,
        "link": n.link,
        "created_at": n.created_at,
        "is_read": n.is_read,
    }


def get_notifications_for_user(db: Session, user: User) -> list[dict]:
    items: list[dict] = []
    seen_keys: set[str] = set()

    persisted = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    for n in persisted:
        items.append(_notification_item(n))
        seen_keys.add(f"{n.type}:{n.message}")

    if user.role == UserRole.employee:
        returned = (
            db.query(Goal)
            .filter(
                Goal.employee_id == user.id,
                Goal.status == GoalStatus.returned,
            )
            .count()
        )
        if returned > 0:
            msg = f"{returned} goal(s) returned for revision"
            if msg not in seen_keys:
                items.insert(
                    0,
                    {
                        "id": -1,
                        "type": "goal_returned",
                        "message": msg,
                        "link": "/employee/dashboard",
                        "created_at": _utc_now(),
                        "is_read": False,
                    },
                )

        active_q, _ = get_current_active_quarter(db)
        approved = db.query(Goal).filter(
            Goal.employee_id == user.id,
            Goal.status == GoalStatus.approved,
        ).all()
        pending_titles = []
        for goal in approved:
            checkin = (
                db.query(QuarterlyCheckin)
                .filter(
                    QuarterlyCheckin.goal_id == goal.id,
                    QuarterlyCheckin.quarter == Quarter(active_q),
                )
                .first()
            )
            if not checkin:
                pending_titles.append(goal.title)
        if pending_titles:
            msg = f"{len(pending_titles)} pending {active_q} check-in(s)"
            items.insert(
                0,
                {
                    "id": -2,
                    "type": "checkin_reminder",
                    "message": msg,
                    "link": "/employee/checkins",
                    "created_at": _utc_now(),
                    "is_read": False,
                },
            )

    elif user.role == UserRole.manager:
        reports = db.query(User).filter(
            User.manager_id == user.id,
            User.role == UserRole.employee,
        ).all()
        report_ids = [r.id for r in reports]
        pending = 0
        if report_ids:
            pending = (
                db.query(Goal)
                .filter(
                    Goal.employee_id.in_(report_ids),
                    Goal.status == GoalStatus.submitted,
                )
                .count()
            )
        if pending > 0:
            items.insert(
                0,
                {
                    "id": -3,
                    "type": "pending_approval",
                    "message": f"{pending} goal(s) awaiting your approval",
                    "link": "/manager/dashboard",
                    "created_at": _utc_now(),
                    "is_read": False,
                },
            )

        if report_ids:
            team_escalations = (
                db.query(EscalationLog)
                .filter(
                    EscalationLog.is_resolved.is_(False),
                    EscalationLog.manager_id == user.id,
                )
                .count()
            )
            if team_escalations > 0:
                items.insert(
                    0,
                    {
                        "id": -4,
                        "type": "team_escalation",
                        "message": f"{team_escalations} team escalation(s) need attention",
                        "link": "/manager/dashboard",
                        "created_at": _utc_now(),
                        "is_read": False,
                    },
                )

    elif user.role == UserRole.admin:
        unresolved = (
            db.query(EscalationLog)
            .filter(EscalationLog.is_resolved.is_(False))
            .count()
        )
        if unresolved > 0:
            critical = (
                db.query(EscalationLog)
                .filter(
                    EscalationLog.is_resolved.is_(False),
                    EscalationLog.escalation_type == EscalationType.checkin_not_logged,
                )
                .count()
            )
            items.insert(
                0,
                {
                    "id": -5,
                    "type": "admin_escalation",
                    "message": f"{unresolved} unresolved escalation(s)"
                    + (f" ({critical} critical)" if critical else ""),
                    "link": "/admin/escalations",
                    "created_at": _utc_now(),
                    "is_read": False,
                    "critical": critical > 0,
                },
            )

    items.sort(key=lambda x: x["created_at"], reverse=True)
    return items[:50]


def mark_all_read(db: Session, user_id: int) -> int:
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read.is_(False))
        .update({Notification.is_read: True})
    )
    db.commit()
    return count


def run_async(coro) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        asyncio.run(coro)
