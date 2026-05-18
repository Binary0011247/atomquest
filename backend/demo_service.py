"""Demo simulation helpers for hackathon live demonstrations."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from auth import get_password_hash
from cache import invalidate_mutation_caches
from escalation import run_escalation_check
from models import (
    AuditLog,
    CheckinStatus,
    EscalationLog,
    EscalationType,
    Goal,
    GoalApproval,
    GoalStatus,
    Notification,
    Quarter,
    QuarterlyCheckin,
    SharedGoalLink,
    UomType,
    User,
    UserRole,
)
from utils import write_audit_log


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def seed_demo_users(db: Session) -> list[str]:
    """Create default demo users if they do not exist."""
    created_emails: list[str] = []

    def get_or_create(
        *,
        name: str,
        email: str,
        password: str,
        role: UserRole,
        manager_id: int | None = None,
    ) -> User:
        user = db.query(User).filter(User.email == email).first()
        if user:
            return user
        user = User(
            name=name,
            email=email,
            hashed_password=get_password_hash(password),
            role=role,
            manager_id=manager_id,
        )
        db.add(user)
        db.flush()
        created_emails.append(email)
        return user

    get_or_create(
        name="Aryan Admin",
        email="admin@atomquest.com",
        password="admin123",
        role=UserRole.admin,
    )
    meera = get_or_create(
        name="Meera Manager",
        email="manager@atomquest.com",
        password="manager123",
        role=UserRole.manager,
    )
    for name, email in [
        ("Priya Employee", "priya@atomquest.com"),
        ("Raj Employee", "raj@atomquest.com"),
        ("Sneha Employee", "sneha@atomquest.com"),
    ]:
        get_or_create(
            name=name,
            email=email,
            password="emp123",
            role=UserRole.employee,
            manager_id=meera.id,
        )

    db.commit()
    return created_emails


def count_emails_for_escalation(log: EscalationLog, *, days: int, has_manager: bool) -> int:
    """Estimate outbound emails matching escalation._notify_escalation behavior."""
    emails = 0
    if log.escalation_type == EscalationType.goal_not_submitted:
        emails += 1
        if days >= 5 and has_manager:
            emails += 1
        if days >= 7:
            emails += 1
    elif log.escalation_type == EscalationType.approval_pending_too_long:
        emails += 1
    elif log.escalation_type == EscalationType.checkin_not_logged:
        emails += 1
        if days >= 7:
            emails += 1
    return emails


def simulate_escalation(db: Session) -> dict:
    seven_days_ago = _utc_now() - timedelta(days=7)
    draft_goals = (
        db.query(Goal)
        .filter(Goal.status == GoalStatus.draft)
        .all()
    )
    goals_affected = len(draft_goals)

    if goals_affected:
        db.query(Goal).filter(Goal.status == GoalStatus.draft).update(
            {Goal.created_at: seven_days_ago},
            synchronize_session=False,
        )
        db.commit()

    sim_start = _utc_now()
    escalations_created = run_escalation_check(db)

    new_logs = (
        db.query(EscalationLog)
        .filter(EscalationLog.created_at >= sim_start)
        .all()
    )

    emails_sent = 0
    for log in new_logs:
        employee = (
            db.query(User).filter(User.id == log.employee_id).first()
            if log.employee_id
            else None
        )
        has_manager = bool(employee and employee.manager_id)
        emails_sent += count_emails_for_escalation(log, days=7, has_manager=has_manager)

    invalidate_mutation_caches(goals=True, checkins=True)

    return {
        "message": "Escalation simulation complete",
        "goals_affected": goals_affected,
        "escalations_created": escalations_created,
        "emails_sent": emails_sent,
    }


def reset_demo_data(db: Session) -> dict:
    db.query(QuarterlyCheckin).delete(synchronize_session=False)
    db.query(GoalApproval).delete(synchronize_session=False)
    db.query(EscalationLog).delete(synchronize_session=False)
    db.query(AuditLog).delete(synchronize_session=False)
    db.query(SharedGoalLink).delete(synchronize_session=False)
    db.query(Notification).delete(synchronize_session=False)
    # Child shared goals reference parent goals via parent_shared_goal_id
    db.query(Goal).filter(Goal.parent_shared_goal_id.isnot(None)).delete(
        synchronize_session=False
    )
    db.query(Goal).delete(synchronize_session=False)
    db.commit()

    seed_demo_users(db)
    invalidate_mutation_caches(goals=True, checkins=True)

    return {"message": "Demo reset complete. Fresh data loaded."}


def _employee_by_email(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise ValueError(f"Demo user not found: {email}. Run seed first.")
    return user


def _delete_goals_by_ids(db: Session, goal_ids: list[int]) -> None:
    if not goal_ids:
        return

    child_ids = [
        row[0]
        for row in db.query(Goal.id)
        .filter(Goal.parent_shared_goal_id.in_(goal_ids))
        .all()
    ]
    all_goal_ids = list(set(goal_ids + child_ids))

    db.query(QuarterlyCheckin).filter(QuarterlyCheckin.goal_id.in_(all_goal_ids)).delete(
        synchronize_session=False
    )
    db.query(EscalationLog).filter(EscalationLog.goal_id.in_(all_goal_ids)).delete(
        synchronize_session=False
    )
    db.query(GoalApproval).filter(GoalApproval.goal_id.in_(all_goal_ids)).delete(
        synchronize_session=False
    )
    db.query(SharedGoalLink).filter(SharedGoalLink.parent_goal_id.in_(all_goal_ids)).delete(
        synchronize_session=False
    )
    if child_ids:
        db.query(Goal).filter(Goal.id.in_(child_ids)).delete(synchronize_session=False)
    db.query(Goal).filter(Goal.id.in_(goal_ids)).delete(synchronize_session=False)


def _clear_employee_goals(db: Session, employee_id: int) -> None:
    goal_ids = [
        g.id for g in db.query(Goal.id).filter(Goal.employee_id == employee_id).all()
    ]
    _delete_goals_by_ids(db, goal_ids)


def _create_goal(
    db: Session,
    *,
    employee_id: int,
    thrust_area: str,
    title: str,
    uom_type: UomType,
    weightage: float,
    target_value: float | None = None,
    target_date: date | None = None,
    status: GoalStatus = GoalStatus.approved,
    changed_by: int,
) -> Goal:
    goal = Goal(
        employee_id=employee_id,
        thrust_area=thrust_area,
        title=title,
        uom_type=uom_type,
        target_value=target_value,
        target_date=target_date,
        weightage=weightage,
        status=status,
        is_locked=status == GoalStatus.approved,
        is_shared=False,
    )
    db.add(goal)
    db.flush()
    write_audit_log(
        db,
        entity="goal",
        entity_id=goal.id,
        changed_by=changed_by,
        change_description=f"Demo goal created: {title}",
    )
    return goal


def _create_checkin(
    db: Session,
    *,
    goal: Goal,
    quarter: Quarter,
    actual_value: float | None,
    actual_date: date | None,
    changed_by: int,
    manager_comment: str | None = None,
    manager_id: int | None = None,
) -> QuarterlyCheckin:
    checkin = QuarterlyCheckin(
        goal_id=goal.id,
        quarter=quarter,
        actual_value=actual_value,
        actual_date=actual_date,
        status=CheckinStatus.on_track,
        employee_note="Q1 demo check-in",
    )
    if manager_comment and manager_id:
        checkin.manager_comment = manager_comment
    db.add(checkin)
    db.flush()
    write_audit_log(
        db,
        entity="checkin",
        entity_id=goal.id,
        changed_by=changed_by,
        change_description=f"Demo Q1 check-in logged for {goal.title}",
    )
    if manager_comment and manager_id:
        write_audit_log(
            db,
            entity="checkin",
            entity_id=goal.id,
            changed_by=manager_id,
            change_description=f"Manager comment on {goal.title} Q1: {manager_comment}",
        )
    return checkin


def fast_forward_demo(db: Session) -> dict:
    admin = _employee_by_email(db, "admin@atomquest.com")
    manager = _employee_by_email(db, "manager@atomquest.com")
    priya = _employee_by_email(db, "priya@atomquest.com")
    raj = _employee_by_email(db, "raj@atomquest.com")
    sneha = _employee_by_email(db, "sneha@atomquest.com")

    for emp in (priya, raj, sneha):
        _clear_employee_goals(db, emp.id)

    goals_created = 0
    checkins_created = 0

    priya_goals = [
        _create_goal(
            db,
            employee_id=priya.id,
            thrust_area="Sales",
            title="Sales Revenue",
            uom_type=UomType.numeric_min,
            target_value=100_000.0,
            weightage=40.0,
            changed_by=admin.id,
        ),
        _create_goal(
            db,
            employee_id=priya.id,
            thrust_area="Customer Service",
            title="Customer Satisfaction",
            uom_type=UomType.numeric_min,
            target_value=90.0,
            weightage=30.0,
            changed_by=admin.id,
        ),
        _create_goal(
            db,
            employee_id=priya.id,
            thrust_area="Technology",
            title="Product Launch",
            uom_type=UomType.timeline,
            target_date=date(2026, 9, 30),
            weightage=20.0,
            changed_by=admin.id,
        ),
        _create_goal(
            db,
            employee_id=priya.id,
            thrust_area="Safety",
            title="Safety Incidents",
            uom_type=UomType.zero,
            weightage=10.0,
            changed_by=admin.id,
        ),
    ]
    goals_created += len(priya_goals)

    priya_checkins = [
        _create_checkin(
            db,
            goal=priya_goals[0],
            quarter=Quarter.Q1,
            actual_value=85_000.0,
            actual_date=None,
            changed_by=priya.id,
            manager_comment="Great progress! On track to exceed target.",
            manager_id=manager.id,
        ),
        _create_checkin(
            db,
            goal=priya_goals[1],
            quarter=Quarter.Q1,
            actual_value=87.0,
            actual_date=None,
            changed_by=priya.id,
        ),
        _create_checkin(
            db,
            goal=priya_goals[2],
            quarter=Quarter.Q1,
            actual_value=None,
            actual_date=date(2026, 9, 25),
            changed_by=priya.id,
        ),
        _create_checkin(
            db,
            goal=priya_goals[3],
            quarter=Quarter.Q1,
            actual_value=0.0,
            actual_date=None,
            changed_by=priya.id,
        ),
    ]
    checkins_created += len(priya_checkins)

    raj_goals = [
        _create_goal(
            db,
            employee_id=raj.id,
            thrust_area="Finance",
            title="Cost Reduction",
            uom_type=UomType.numeric_max,
            target_value=50_000.0,
            weightage=50.0,
            changed_by=admin.id,
        ),
        _create_goal(
            db,
            employee_id=raj.id,
            thrust_area="HR",
            title="Training Hours",
            uom_type=UomType.numeric_min,
            target_value=40.0,
            weightage=30.0,
            changed_by=admin.id,
        ),
        _create_goal(
            db,
            employee_id=raj.id,
            thrust_area="Operations",
            title="Process Improvement",
            uom_type=UomType.timeline,
            target_date=date(2026, 12, 31),
            weightage=20.0,
            changed_by=admin.id,
        ),
    ]
    goals_created += len(raj_goals)

    raj_checkins = [
        _create_checkin(
            db,
            goal=raj_goals[0],
            quarter=Quarter.Q1,
            actual_value=65_000.0,
            actual_date=None,
            changed_by=raj.id,
        ),
        _create_checkin(
            db,
            goal=raj_goals[1],
            quarter=Quarter.Q1,
            actual_value=25.0,
            actual_date=None,
            changed_by=raj.id,
        ),
        _create_checkin(
            db,
            goal=raj_goals[2],
            quarter=Quarter.Q1,
            actual_value=None,
            actual_date=date(2027, 1, 15),
            changed_by=raj.id,
            manager_comment="Timeline needs attention. Plan to recover?",
            manager_id=manager.id,
        ),
    ]
    checkins_created += len(raj_checkins)

    sneha_goals = [
        _create_goal(
            db,
            employee_id=sneha.id,
            thrust_area="Sales",
            title="Revenue",
            uom_type=UomType.numeric_min,
            target_value=200_000.0,
            weightage=60.0,
            status=GoalStatus.submitted,
            changed_by=admin.id,
        ),
        _create_goal(
            db,
            employee_id=sneha.id,
            thrust_area="HR",
            title="Team Training",
            uom_type=UomType.numeric_min,
            target_value=20.0,
            weightage=40.0,
            status=GoalStatus.submitted,
            changed_by=admin.id,
        ),
    ]
    goals_created += len(sneha_goals)

    for g in sneha_goals:
        write_audit_log(
            db,
            entity="goal",
            entity_id=g.id,
            changed_by=sneha.id,
            change_description=f"Demo goal submitted for approval: {g.title}",
        )

    db.commit()
    invalidate_mutation_caches(goals=True, checkins=True)

    return {
        "message": "Demo data created successfully",
        "employees_setup": 3,
        "goals_created": goals_created,
        "checkins_created": checkins_created,
    }
