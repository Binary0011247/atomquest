import enum
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    employee = "employee"
    manager = "manager"
    admin = "admin"


class UomType(str, enum.Enum):
    numeric_min = "numeric_min"
    numeric_max = "numeric_max"
    timeline = "timeline"
    zero = "zero"


class GoalStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    approved = "approved"
    returned = "returned"


class ApprovalAction(str, enum.Enum):
    approved = "approved"
    returned = "returned"


class Quarter(str, enum.Enum):
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"


class CheckinStatus(str, enum.Enum):
    not_started = "not_started"
    on_track = "on_track"
    completed = "completed"


class EscalationType(str, enum.Enum):
    goal_not_submitted = "goal_not_submitted"
    approval_pending_too_long = "approval_pending_too_long"
    checkin_not_logged = "checkin_not_logged"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False),
        nullable=False,
    )
    manager_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    manager: Mapped[Optional["User"]] = relationship(
        "User",
        remote_side="User.id",
        back_populates="direct_reports",
        foreign_keys=[manager_id],
    )
    direct_reports: Mapped[list["User"]] = relationship(
        "User",
        back_populates="manager",
        foreign_keys=[manager_id],
    )
    goals: Mapped[list["Goal"]] = relationship(
        "Goal",
        back_populates="employee",
        foreign_keys="Goal.employee_id",
    )
    goal_approvals: Mapped[list["GoalApproval"]] = relationship(
        "GoalApproval",
        back_populates="manager",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="changed_by_user",
    )
    shared_goal_links: Mapped[list["SharedGoalLink"]] = relationship(
        "SharedGoalLink",
        back_populates="recipient_employee",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="user",
    )


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    thrust_area: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    uom_type: Mapped[UomType] = mapped_column(
        Enum(UomType, name="uom_type", native_enum=False),
        nullable=False,
    )
    target_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    weightage: Mapped[float] = mapped_column(Float, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parent_shared_goal_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("goals.id"), nullable=True
    )
    status: Mapped[GoalStatus] = mapped_column(
        Enum(GoalStatus, name="goal_status", native_enum=False),
        default=GoalStatus.draft,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    employee: Mapped["User"] = relationship(
        "User",
        back_populates="goals",
        foreign_keys=[employee_id],
    )
    parent_shared_goal: Mapped[Optional["Goal"]] = relationship(
        "Goal",
        remote_side="Goal.id",
        back_populates="derived_goals",
        foreign_keys=[parent_shared_goal_id],
    )
    derived_goals: Mapped[list["Goal"]] = relationship(
        "Goal",
        back_populates="parent_shared_goal",
        foreign_keys=[parent_shared_goal_id],
    )
    approvals: Mapped[list["GoalApproval"]] = relationship(
        "GoalApproval",
        back_populates="goal",
    )
    quarterly_checkins: Mapped[list["QuarterlyCheckin"]] = relationship(
        "QuarterlyCheckin",
        back_populates="goal",
    )
    shared_goal_links: Mapped[list["SharedGoalLink"]] = relationship(
        "SharedGoalLink",
        back_populates="parent_goal",
    )


class GoalApproval(Base):
    __tablename__ = "goal_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("goals.id"), nullable=False
    )
    manager_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    action: Mapped[ApprovalAction] = mapped_column(
        Enum(ApprovalAction, name="approval_action", native_enum=False),
        nullable=False,
    )
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    acted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    goal: Mapped["Goal"] = relationship("Goal", back_populates="approvals")
    manager: Mapped["User"] = relationship("User", back_populates="goal_approvals")


class QuarterlyCheckin(Base):
    __tablename__ = "quarterly_checkins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("goals.id"), nullable=False
    )
    quarter: Mapped[Quarter] = mapped_column(
        Enum(Quarter, name="quarter", native_enum=False),
        nullable=False,
    )
    actual_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[CheckinStatus] = mapped_column(
        Enum(CheckinStatus, name="checkin_status", native_enum=False),
        default=CheckinStatus.not_started,
        nullable=False,
    )
    employee_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    manager_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    goal: Mapped["Goal"] = relationship("Goal", back_populates="quarterly_checkins")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    change_description: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    changed_by_user: Mapped["User"] = relationship(
        "User",
        back_populates="audit_logs",
    )


class CycleConfig(Base):
    __tablename__ = "cycle_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cycle_year: Mapped[int] = mapped_column(Integer, nullable=False)
    goal_setting_start: Mapped[date] = mapped_column(Date, nullable=False)
    q1_checkin_start: Mapped[date] = mapped_column(Date, nullable=False)
    q2_checkin_start: Mapped[date] = mapped_column(Date, nullable=False)
    q3_checkin_start: Mapped[date] = mapped_column(Date, nullable=False)
    q4_checkin_start: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class EscalationLog(Base):
    __tablename__ = "escalation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    escalation_type: Mapped[EscalationType] = mapped_column(
        Enum(EscalationType, name="escalation_type", native_enum=False),
        nullable=False,
    )
    employee_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    manager_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    goal_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("goals.id"), nullable=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    employee: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[employee_id],
    )
    manager: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[manager_id],
    )
    goal: Mapped[Optional["Goal"]] = relationship(
        "Goal",
        foreign_keys=[goal_id],
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str] = mapped_column(String, nullable=False, default="/")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="notifications")


class SharedGoalLink(Base):
    __tablename__ = "shared_goal_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_goal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("goals.id"), nullable=False
    )
    recipient_employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    custom_weightage: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    parent_goal: Mapped["Goal"] = relationship(
        "Goal",
        back_populates="shared_goal_links",
    )
    recipient_employee: Mapped["User"] = relationship(
        "User",
        back_populates="shared_goal_links",
    )


__all__ = [
    "User",
    "Goal",
    "GoalApproval",
    "QuarterlyCheckin",
    "AuditLog",
    "CycleConfig",
    "EscalationLog",
    "Notification",
    "SharedGoalLink",
    "UserRole",
    "UomType",
    "GoalStatus",
    "ApprovalAction",
    "Quarter",
    "CheckinStatus",
    "EscalationType",
]
