from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from analytics_helpers import (
    QUARTERS,
    count_at_risk_goals,
    employee_overall_avg,
    employee_quarter_averages,
    score_for_checkin,
)
from auth import get_current_user, require_role
from database import get_db
from models import Goal, GoalStatus, Quarter, QuarterlyCheckin, User, UserRole
from utils import get_manager_direct_reports
from schemas import MyProgressResponse, TeamSummaryResponse

router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "/my-progress",
    response_model=MyProgressResponse,
    summary="Employee personal progress summary",
)
def my_progress(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.employee))],
):
    goals = db.query(Goal).filter(Goal.employee_id == current_user.id).all()
    q_avgs = employee_quarter_averages(db, current_user.id)
    overall = employee_overall_avg(db, current_user.id) or 0.0

    best_goal = None
    best_score = -1.0
    needs_attention = []

    for goal in goals:
        scores = []
        for q in QUARTERS:
            checkin = (
                db.query(QuarterlyCheckin)
                .filter(
                    QuarterlyCheckin.goal_id == goal.id,
                    QuarterlyCheckin.quarter == Quarter(q),
                )
                .first()
            )
            s = score_for_checkin(goal, checkin)
            if s is not None:
                scores.append(s)
        if scores:
            avg = sum(scores) / len(scores)
            if avg > best_score:
                best_score = avg
                best_goal = {"title": goal.title, "score": round(avg, 2)}
            if avg < 60:
                needs_attention.append({"title": goal.title, "score": round(avg, 2)})

    return MyProgressResponse(
        employee_name=current_user.name,
        total_goals=len(goals),
        approved_goals=sum(1 for g in goals if g.status == GoalStatus.approved),
        quarter_scores=q_avgs,
        overall_avg=overall,
        goals_at_risk=count_at_risk_goals(db, current_user.id),
        best_performing_goal=best_goal,
        needs_attention=needs_attention,
    )


@router.get(
    "/team-summary",
    response_model=TeamSummaryResponse,
    summary="Manager team performance summary",
)
def team_summary(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_role(UserRole.manager))],
):
    team = get_manager_direct_reports(db, current_user.id)
    team_ids = [e.id for e in team]

    team_avgs = [employee_overall_avg(db, e.id) for e in team]
    team_avgs_valid = [a for a in team_avgs if a is not None]
    team_avg = (
        round(sum(team_avgs_valid) / len(team_avgs_valid), 2) if team_avgs_valid else 0.0
    )

    top_performer = None
    if team:
        ranked = [
            (e.name, employee_overall_avg(db, e.id) or 0.0)
            for e in team
        ]
        ranked.sort(key=lambda x: -x[1])
        if ranked[0][1] > 0:
            top_performer = {"name": ranked[0][0], "score": ranked[0][1]}

    needs_support = [
        {"name": e.name, "score": employee_overall_avg(db, e.id) or 0.0}
        for e in team
        if (employee_overall_avg(db, e.id) or 100) < 60
    ]

    quarter_rates = {}
    for q in QUARTERS:
        total_slots = 0
        completed = 0
        for eid in team_ids:
            for goal in db.query(Goal).filter(Goal.employee_id == eid).all():
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
        quarter_rates[q] = round((completed / total_slots) * 100, 1) if total_slots else 0.0

    pending_approvals = (
        db.query(Goal)
        .filter(Goal.employee_id.in_(team_ids), Goal.status == GoalStatus.submitted)
        .count()
        if team_ids
        else 0
    )

    checkins_needing_review = 0
    if team_ids:
        checkins = (
            db.query(QuarterlyCheckin)
            .join(Goal, QuarterlyCheckin.goal_id == Goal.id)
            .filter(Goal.employee_id.in_(team_ids))
            .all()
        )
        checkins_needing_review = sum(
            1 for c in checkins if not c.manager_comment and c.actual_value is not None
        )

    return TeamSummaryResponse(
        team_avg_score=team_avg,
        top_performer=top_performer,
        needs_support=needs_support,
        quarter_completion_rates=quarter_rates,
        pending_my_actions={
            "approvals": pending_approvals,
            "checkin_reviews": checkins_needing_review,
        },
    )
