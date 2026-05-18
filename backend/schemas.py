from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from models import UserRole

UomTypeLiteral = Literal["numeric_min", "numeric_max", "timeline", "zero"]
SubmissionStatusLiteral = Literal[
    "not_started", "partial", "submitted", "approved", "has_returned"
]


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: UserRole
    manager_id: int | None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class SeedResponse(BaseModel):
    message: str
    users: list[str]


class GoalCreate(BaseModel):
    thrust_area: str
    title: str
    description: Optional[str] = None
    uom_type: UomTypeLiteral
    target_value: Optional[float] = None
    target_date: Optional[date] = None
    weightage: float

    @model_validator(mode="after")
    def validate_uom(self) -> "GoalCreate":
        from utils import validate_uom_fields

        validate_uom_fields(self.uom_type, self.target_value, self.target_date)
        return self


class GoalUpdate(BaseModel):
    thrust_area: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    target_value: Optional[float] = None
    target_date: Optional[date] = None
    weightage: Optional[float] = None


class GoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    thrust_area: str
    title: str
    description: Optional[str] = None
    uom_type: str
    target_value: Optional[float] = None
    target_date: Optional[date] = None
    weightage: float
    is_locked: bool
    is_shared: bool
    parent_shared_goal_id: Optional[int] = None
    status: str
    created_at: datetime
    updated_at: datetime
    return_comment: Optional[str] = None


class GoalListResponse(BaseModel):
    goals: list[GoalResponse]
    total_weightage: float
    remaining_weightage: float
    goal_count: int
    can_add_more: bool


class MessageResponse(BaseModel):
    message: str


class SubmitAllResponse(BaseModel):
    message: str
    submitted_count: int
    total_weightage: float


class TeamEmployeeGoals(BaseModel):
    employee_id: int
    employee_name: str
    goals: list[GoalResponse]
    total_weightage: float
    submission_status: SubmissionStatusLiteral


class TeamGoalsResponse(BaseModel):
    team: list[TeamEmployeeGoals] = Field(default_factory=list)


class ApprovalAction(BaseModel):
    action: Literal["approved", "returned"]
    comment: Optional[str] = None
    edited_target_value: Optional[float] = None
    edited_target_date: Optional[date] = None
    edited_weightage: Optional[float] = None


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    goal_id: int
    manager_id: int
    action: str
    comment: Optional[str] = None
    acted_at: datetime


class TeamGoalSummary(BaseModel):
    employee_id: int
    employee_name: str
    employee_email: str
    total_goals: int
    submitted_goals: int
    approved_goals: int
    returned_goals: int
    total_weightage: float
    submission_status: SubmissionStatusLiteral
    goals: list[GoalResponse]


class ManagerDashboardResponse(BaseModel):
    team_summary: list[TeamGoalSummary] = Field(default_factory=list)
    pending_approvals_count: int
    total_team_members: int


class PendingGoalItem(BaseModel):
    goal: GoalResponse
    employee_id: int
    employee_name: str
    employee_email: str
    submitted_at: datetime


class PendingEmployeeGroup(BaseModel):
    employee_id: int
    employee_name: str
    employee_email: str
    submitted_goals_count: int
    goals: list[GoalResponse] = Field(default_factory=list)


class PendingApprovalsResponse(BaseModel):
    groups: list[PendingEmployeeGroup] = Field(default_factory=list)
    total_pending_goals: int = 0


class GoalReviewResponse(BaseModel):
    message: str
    goal: GoalResponse


class ApproveAllResponse(BaseModel):
    message: str
    employee_name: str
    approved_count: int
    goal_titles: list[str] = Field(default_factory=list)


class ApprovalHistoryItem(BaseModel):
    goal_id: int
    goal_title: str
    action: str
    comment: Optional[str] = None
    manager_name: str
    acted_at: datetime


class ApprovalHistoryResponse(BaseModel):
    history: list[ApprovalHistoryItem] = Field(default_factory=list)


QuarterLiteral = Literal["Q1", "Q2", "Q3", "Q4"]
CheckinStatusLiteral = Literal["not_started", "on_track", "completed"]


class CheckinCreate(BaseModel):
    quarter: QuarterLiteral
    actual_value: Optional[float] = None
    actual_date: Optional[date] = None
    status: CheckinStatusLiteral = "not_started"
    employee_note: Optional[str] = None


class CheckinUpdate(BaseModel):
    actual_value: Optional[float] = None
    actual_date: Optional[date] = None
    status: Optional[CheckinStatusLiteral] = None
    employee_note: Optional[str] = None


class ManagerCheckinComment(BaseModel):
    manager_comment: str

    @model_validator(mode="after")
    def validate_comment(self) -> "ManagerCheckinComment":
        if not self.manager_comment or not self.manager_comment.strip():
            raise ValueError("manager_comment cannot be empty")
        return self


class CheckinResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    goal_id: int
    quarter: str
    actual_value: Optional[float] = None
    actual_date: Optional[date] = None
    status: str
    employee_note: Optional[str] = None
    manager_comment: Optional[str] = None
    progress_score: Optional[float] = None
    score_color: Optional[str] = None
    updated_at: datetime


class CheckinUpsertResponse(CheckinResponse):
    synced_to_employees: int = 0


class GoalWithCheckins(BaseModel):
    goal: GoalResponse
    checkins: list[CheckinResponse] = Field(default_factory=list)
    latest_checkin: Optional[CheckinResponse] = None
    overall_progress: Optional[float] = None


class EmployeeProgressReport(BaseModel):
    employee_id: int
    employee_name: str
    employee_email: str
    goals: list[GoalWithCheckins] = Field(default_factory=list)
    average_progress: float = 0.0
    completed_checkins: int = 0
    total_required_checkins: int = 0
    completion_rate: float = 0.0
    quarters: list[dict] = Field(default_factory=list)
    at_risk_count: int = 0


class CycleConfig(BaseModel):
    cycle_year: int
    goal_setting_start: date
    q1_checkin_start: date
    q2_checkin_start: date
    q3_checkin_start: date
    q4_checkin_start: date
    is_active: bool = True


class CycleConfigUpdate(BaseModel):
    goal_setting_start: date | None = None
    q1_checkin_start: date | None = None
    q2_checkin_start: date | None = None
    q3_checkin_start: date | None = None
    q4_checkin_start: date | None = None


class CycleConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cycle_year: int
    goal_setting_start: date
    q1_checkin_start: date
    q2_checkin_start: date
    q3_checkin_start: date
    q4_checkin_start: date
    is_active: bool


class GoalUnlockRequest(BaseModel):
    reason: str

    @model_validator(mode="after")
    def validate_reason(self) -> "GoalUnlockRequest":
        if not self.reason or not self.reason.strip():
            raise ValueError("reason is required")
        return self


class GoalUnlockResponse(BaseModel):
    message: str
    goal_id: int
    reason: str


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity: str
    entity_id: int
    changed_by: int
    changed_by_name: str
    change_description: str
    changed_at: datetime


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


class OrgUser(BaseModel):
    id: int
    name: str
    email: str
    role: str
    manager_id: int | None = None
    manager_name: str | None = None
    is_active: bool
    goal_count: int
    submission_status: str


class UserCreateAdmin(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole
    manager_id: int | None = None


class UserUpdateAdmin(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    role: UserRole | None = None
    manager_id: int | None = None
    is_active: bool | None = None


class AdminDashboardResponse(BaseModel):
    total_employees: int
    total_managers: int
    total_goals: int
    goals_approved: int
    goals_pending: int
    goals_returned: int
    employees_not_started: int
    employees_submitted: int
    employees_approved: int
    checkin_completion_rates: dict[str, float]
    recent_audit_logs: list[AuditLogResponse]


class AchievementReportRow(BaseModel):
    employee_id: int
    employee_name: str
    manager_name: str
    goal_title: str
    thrust_area: str
    uom_type: str
    target_value: float | None = None
    target_date: date | None = None
    weightage: float
    q1_actual: float | None = None
    q1_score: float | None = None
    q2_actual: float | None = None
    q2_score: float | None = None
    q3_actual: float | None = None
    q3_score: float | None = None
    q4_actual: float | None = None
    q4_score: float | None = None
    overall_score: float | None = None


class EmployeeCompletionRow(BaseModel):
    employee_id: int
    employee_name: str
    manager_name: str | None = None
    has_created_goals: bool
    has_submitted_goals: bool
    has_approved_goals: bool
    q1_done: bool
    q2_done: bool
    q3_done: bool
    q4_done: bool


class ManagerCompletionRow(BaseModel):
    manager_id: int
    manager_name: str
    pending_approvals_count: int
    completed_checkin_reviews_count: int


class LockedGoalItem(BaseModel):
    goal_id: int
    title: str
    employee_name: str
    employee_email: str
    thrust_area: str


class CompletionReportResponse(BaseModel):
    employees: list[EmployeeCompletionRow] = Field(default_factory=list)
    managers: list[ManagerCompletionRow] = Field(default_factory=list)
    goal_status_distribution: dict[str, int] = Field(default_factory=dict)
    thrust_area_distribution: dict[str, int] = Field(default_factory=dict)
    uom_type_distribution: dict[str, int] = Field(default_factory=dict)


class QuarterTrendItem(BaseModel):
    quarter: str
    avg_score: float
    total_goals: int


class ThrustAreaAnalytics(BaseModel):
    thrust_area: str
    goal_count: int
    avg_score: float


class UomDistributionItem(BaseModel):
    uom_type: str
    count: int
    percentage: float


class PerformerRow(BaseModel):
    employee_id: int
    employee_name: str
    manager_name: str
    avg_score: float


class AtRiskEmployeeRow(BaseModel):
    employee_id: int
    employee_name: str
    manager_name: str
    avg_score: float
    at_risk_goals: int


class ManagerEffectivenessRow(BaseModel):
    manager_id: int
    manager_name: str
    team_size: int
    avg_approval_time_days: float
    checkin_comment_rate: float
    team_avg_score: float


class EmployeeHeatmapRow(BaseModel):
    employee_id: int
    employee_name: str
    manager_name: str
    q1_score: float | None = None
    q2_score: float | None = None
    q3_score: float | None = None
    q4_score: float | None = None


class AnalyticsOverviewResponse(BaseModel):
    goal_achievement_trend: list[QuarterTrendItem]
    thrust_area_distribution: list[ThrustAreaAnalytics]
    uom_type_distribution: list[UomDistributionItem]
    top_performers: list[PerformerRow]
    at_risk_employees: list[AtRiskEmployeeRow]
    manager_effectiveness: list[ManagerEffectivenessRow]
    employee_heatmap: list[EmployeeHeatmapRow] = Field(default_factory=list)
    org_avg_score: float = 0.0
    total_checkins_completed: int = 0
    top_thrust_area: str | None = None


class EmployeeAnalyticsInfo(BaseModel):
    id: int
    name: str
    email: str
    manager_name: str | None = None


class GoalSummaryStats(BaseModel):
    total: int
    approved: int
    pending: int
    returned: int


class QuarterScoreItem(BaseModel):
    quarter: str
    avg_score: float | None = None
    goals_checked_in: int
    total_goals: int


class GoalDetailAnalytics(BaseModel):
    goal_title: str
    thrust_area: str
    uom_type: str
    target: str
    q1_score: float | None = None
    q2_score: float | None = None
    q3_score: float | None = None
    q4_score: float | None = None
    trend: str


class EmployeeAnalyticsResponse(BaseModel):
    employee: EmployeeAnalyticsInfo
    goal_summary: GoalSummaryStats
    quarter_scores: list[QuarterScoreItem]
    goal_details: list[GoalDetailAnalytics]
    overall_avg_score: float
    best_quarter: str
    worst_quarter: str


class ManagerAnalyticsInfo(BaseModel):
    id: int
    name: str
    email: str


class TeamQuarterScore(BaseModel):
    quarter: str
    avg_score: float
    completion_rate: float


class EmployeeComparisonRow(BaseModel):
    employee_name: str
    avg_score: float
    checkins_completed: int
    goals_at_risk: int


class ManagerAnalyticsResponse(BaseModel):
    manager: ManagerAnalyticsInfo
    team_size: int
    team_members: list[str]
    pending_approvals: int
    avg_approval_days: float
    team_quarter_scores: list[TeamQuarterScore]
    employee_comparison: list[EmployeeComparisonRow]
    checkin_review_rate: float


class MyProgressResponse(BaseModel):
    employee_name: str
    total_goals: int
    approved_goals: int
    quarter_scores: dict[str, float | None]
    overall_avg: float
    goals_at_risk: int
    best_performing_goal: dict | None = None
    needs_attention: list[dict] = Field(default_factory=list)


class TeamSummaryResponse(BaseModel):
    team_avg_score: float
    top_performer: dict | None = None
    needs_support: list[dict] = Field(default_factory=list)
    quarter_completion_rates: dict[str, float]
    pending_my_actions: dict[str, int]


class EscalationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    escalation_type: str
    employee_id: int | None = None
    manager_id: int | None = None
    goal_id: int | None = None
    message: str
    is_resolved: bool
    created_at: datetime
    resolved_at: datetime | None = None


class GoalNotSubmittedEscalation(EscalationLogResponse):
    employee_name: str
    days_since_created: int
    goal_count: int


class ApprovalPendingEscalation(EscalationLogResponse):
    goal_title: str
    employee_name: str
    manager_name: str | None = None
    days_waiting: int


class CheckinNotLoggedEscalation(EscalationLogResponse):
    employee_name: str
    goal_title: str
    quarter: str


class EscalationGroupedResponse(BaseModel):
    goal_not_submitted: list[GoalNotSubmittedEscalation] = Field(default_factory=list)
    approval_pending_too_long: list[ApprovalPendingEscalation] = Field(default_factory=list)
    checkin_not_logged: list[CheckinNotLoggedEscalation] = Field(default_factory=list)
    total_unresolved: int = 0


class EscalationRunResponse(BaseModel):
    message: str
    new_escalations: int


class NotificationItem(BaseModel):
    id: int
    type: str
    message: str
    link: str
    created_at: datetime
    is_read: bool = False
    critical: bool = False


class NotificationListResponse(BaseModel):
    notifications: list[NotificationItem]
    unread_count: int = 0


class GoogleAuthUrlResponse(BaseModel):
    auth_url: str


class GoogleCallbackResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic
    is_new_user: bool


class SharedGoalPushRequest(BaseModel):
    thrust_area: str
    title: str
    description: Optional[str] = None
    uom_type: UomTypeLiteral
    target_value: Optional[float] = None
    target_date: Optional[date] = None
    recipient_employee_ids: list[int] = Field(min_length=1)
    default_weightage: float

    @model_validator(mode="after")
    def validate_uom(self) -> "SharedGoalPushRequest":
        from utils import validate_uom_fields

        validate_uom_fields(self.uom_type, self.target_value, self.target_date)
        return self


class SharedGoalRecipientInfo(BaseModel):
    employee_id: int
    employee_name: str
    custom_weightage: float
    child_goal_id: int
    quarters_with_checkins: list[str] = Field(default_factory=list)


class SharedGoalListItem(BaseModel):
    parent_goal: GoalResponse
    recipients: list[SharedGoalRecipientInfo] = Field(default_factory=list)
    total_recipients: int
    created_by_name: str


class SharedGoalPushResponse(BaseModel):
    message: str
    parent_goal_id: int
    pushed_to_count: int
    recipient_names: list[str]


PhaseOverrideLiteral = Literal["Q1", "Q2", "Q3", "Q4", "goal_setting"]


class PhaseOverrideRequest(BaseModel):
    phase: PhaseOverrideLiteral


class PhaseOverrideResponse(BaseModel):
    message: str


class CurrentPhaseResponse(BaseModel):
    phase: str
    label: str
    description: str
    active_quarter: Optional[str] = None
    goal_setting_open: bool
    checkin_open: bool
    next_phase: str
    phase_override_active: bool = False
    override_phase: Optional[str] = None


class DemoSimulateEscalationResponse(BaseModel):
    message: str
    goals_affected: int
    escalations_created: int
    emails_sent: int


class DemoResetResponse(BaseModel):
    message: str


class DemoFastForwardResponse(BaseModel):
    message: str
    employees_setup: int
    goals_created: int
    checkins_created: int
