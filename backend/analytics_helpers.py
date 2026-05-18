"""Shared analytics score aggregation for admin and reports."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models import (
    ApprovalAction,
    Goal,
    GoalApproval,
    GoalStatus,
    Quarter,
    QuarterlyCheckin,
    User,
    UserRole,
)
from utils import calculate_progress_score

QUARTERS = ("Q1", "Q2", "Q3", "Q4")


def _quarter_val(q) -> str:
    return q.value if hasattr(q, "value") else q


def _uom_val(uom) -> str:
    return uom.value if hasattr(uom, "value") else uom


def score_for_checkin(goal: Goal, checkin: QuarterlyCheckin | None) -> float | None:
    if not checkin:
        return None
    if checkin.actual_value is None and checkin.actual_date is None:
        return None
    return calculate_progress_score(
        goal.uom_type,
        goal.target_value,
        checkin.actual_value,
        goal.target_date,
        checkin.actual_date,
    )


def employee_quarter_averages(db: Session, employee_id: int) -> dict[str, float | None]:
    goals = db.query(Goal).filter(Goal.employee_id == employee_id).all()
    by_q: dict[str, list[float]] = {q: [] for q in QUARTERS}
    for goal in goals:
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
                by_q[q].append(s)
    return {
        q: round(sum(vals) / len(vals), 2) if vals else None
        for q, vals in by_q.items()
    }


def employee_overall_avg(db: Session, employee_id: int) -> float | None:
    goals = db.query(Goal).filter(Goal.employee_id == employee_id).all()
    scores: list[float] = []
    for goal in goals:
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
    if not scores:
        return None
    return round(sum(scores) / len(scores), 2)


def count_at_risk_goals(db: Session, employee_id: int, threshold: float = 60.0) -> int:
    goals = db.query(Goal).filter(Goal.employee_id == employee_id).all()
    at_risk = 0
    for goal in goals:
        goal_scores: list[float] = []
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
                goal_scores.append(s)
        if goal_scores:
            avg = sum(goal_scores) / len(goal_scores)
            if avg < threshold:
                at_risk += 1
    return at_risk


def total_checkins_completed(db: Session) -> int:
    return (
        db.query(QuarterlyCheckin)
        .filter(
            (QuarterlyCheckin.actual_value.isnot(None))
            | (QuarterlyCheckin.actual_date.isnot(None))
        )
        .count()
    )


def goal_achievement_trend(db: Session) -> list[dict]:
    trend = []
    for q in QUARTERS:
        checkins = (
            db.query(QuarterlyCheckin, Goal)
            .join(Goal, QuarterlyCheckin.goal_id == Goal.id)
            .filter(QuarterlyCheckin.quarter == Quarter(q))
            .all()
        )
        scores: list[float] = []
        goal_ids: set[int] = set()
        for checkin, goal in checkins:
            s = score_for_checkin(goal, checkin)
            if s is not None:
                scores.append(s)
                goal_ids.add(goal.id)
        trend.append(
            {
                "quarter": q,
                "avg_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
                "total_goals": len(goal_ids),
            }
        )
    return trend


def thrust_area_distribution(db: Session) -> list[dict]:
    area_scores: dict[str, list[float]] = defaultdict(list)
    area_counts: dict[str, int] = defaultdict(int)
    goals = db.query(Goal).all()
    for goal in goals:
        area_counts[goal.thrust_area] += 1
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
                area_scores[goal.thrust_area].append(s)
    result = []
    for area, count in area_counts.items():
        scores = area_scores.get(area, [])
        result.append(
            {
                "thrust_area": area,
                "goal_count": count,
                "avg_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
            }
        )
    return sorted(result, key=lambda x: -x["avg_score"])


def uom_type_distribution(db: Session) -> list[dict]:
    goals = db.query(Goal).all()
    counts: dict[str, int] = defaultdict(int)
    for goal in goals:
        counts[_uom_val(goal.uom_type)] += 1
    total = len(goals) or 1
    labels = {
        "numeric_min": "Numeric Min",
        "numeric_max": "Numeric Max",
        "timeline": "Timeline",
        "zero": "Zero",
    }
    return [
        {
            "uom_type": labels.get(k, k),
            "count": v,
            "percentage": round((v / total) * 100, 1),
        }
        for k, v in sorted(counts.items(), key=lambda x: -x[1])
    ]


def top_performers(db: Session, limit: int = 5) -> list[dict]:
    employees = db.query(User).filter(User.role == UserRole.employee).all()
    ranked = []
    for emp in employees:
        avg = employee_overall_avg(db, emp.id)
        if avg is None:
            continue
        manager = (
            db.query(User).filter(User.id == emp.manager_id).first()
            if emp.manager_id
            else None
        )
        ranked.append(
            {
                "employee_id": emp.id,
                "employee_name": emp.name,
                "manager_name": manager.name if manager else "—",
                "avg_score": avg,
            }
        )
    ranked.sort(key=lambda x: -x["avg_score"])
    return ranked[:limit]


def at_risk_employees(db: Session, threshold: float = 60.0) -> list[dict]:
    employees = db.query(User).filter(User.role == UserRole.employee).all()
    result = []
    for emp in employees:
        avg = employee_overall_avg(db, emp.id)
        if avg is None or avg >= threshold:
            continue
        manager = (
            db.query(User).filter(User.id == emp.manager_id).first()
            if emp.manager_id
            else None
        )
        result.append(
            {
                "employee_id": emp.id,
                "employee_name": emp.name,
                "manager_name": manager.name if manager else "—",
                "avg_score": avg,
                "at_risk_goals": count_at_risk_goals(db, emp.id, threshold),
            }
        )
    result.sort(key=lambda x: x["avg_score"])
    return result


def manager_effectiveness(db: Session) -> list[dict]:
    managers = db.query(User).filter(User.role == UserRole.manager).all()
    result = []
    for mgr in managers:
        team = db.query(User).filter(
            User.manager_id == mgr.id, User.role == UserRole.employee
        ).all()
        team_ids = [e.id for e in team]
        if not team_ids:
            continue

        approval_days: list[float] = []
        for goal in db.query(Goal).filter(Goal.employee_id.in_(team_ids)).all():
            if goal.status != GoalStatus.approved:
                continue
            approval = (
                db.query(GoalApproval)
                .filter(
                    GoalApproval.goal_id == goal.id,
                    GoalApproval.action == ApprovalAction.approved,
                )
                .order_by(GoalApproval.acted_at.desc())
                .first()
            )
            if approval and goal.created_at:
                acted = approval.acted_at
                created = goal.created_at
                if acted.tzinfo is None:
                    acted = acted.replace(tzinfo=timezone.utc)
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                days = (acted - created).total_seconds() / 86400
                approval_days.append(max(days, 0))

        team_checkins = (
            db.query(QuarterlyCheckin)
            .join(Goal, QuarterlyCheckin.goal_id == Goal.id)
            .filter(Goal.employee_id.in_(team_ids))
            .all()
        )
        with_comment = sum(1 for c in team_checkins if c.manager_comment)
        comment_rate = (
            round((with_comment / len(team_checkins)) * 100, 1) if team_checkins else 0.0
        )

        team_scores: list[float] = []
        for eid in team_ids:
            avg = employee_overall_avg(db, eid)
            if avg is not None:
                team_scores.append(avg)

        result.append(
            {
                "manager_id": mgr.id,
                "manager_name": mgr.name,
                "team_size": len(team),
                "avg_approval_time_days": round(
                    sum(approval_days) / len(approval_days), 1
                )
                if approval_days
                else 0.0,
                "checkin_comment_rate": comment_rate,
                "team_avg_score": round(sum(team_scores) / len(team_scores), 2)
                if team_scores
                else 0.0,
            }
        )
    result.sort(key=lambda x: -x["team_avg_score"])
    return result


def employee_heatmap_rows(db: Session) -> list[dict]:
    employees = db.query(User).filter(User.role == UserRole.employee).order_by(User.name).all()
    rows = []
    for emp in employees:
        q_avgs = employee_quarter_averages(db, emp.id)
        manager = (
            db.query(User).filter(User.id == emp.manager_id).first()
            if emp.manager_id
            else None
        )
        rows.append(
            {
                "employee_id": emp.id,
                "employee_name": emp.name,
                "manager_name": manager.name if manager else "—",
                "q1_score": q_avgs["Q1"],
                "q2_score": q_avgs["Q2"],
                "q3_score": q_avgs["Q3"],
                "q4_score": q_avgs["Q4"],
            }
        )
    return rows


def goal_trend(scores: list[float | None]) -> str:
    valid = [s for s in scores if s is not None]
    if len(valid) < 2:
        return "stable"
    first_half = valid[: len(valid) // 2] or valid[:1]
    second_half = valid[len(valid) // 2 :] or valid[-1:]
    a = sum(first_half) / len(first_half)
    b = sum(second_half) / len(second_half)
    if b - a > 5:
        return "improving"
    if a - b > 5:
        return "declining"
    return "stable"
