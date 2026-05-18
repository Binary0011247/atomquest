from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from models import CycleConfig

QUARTER_ORDER = ("Q1", "Q2", "Q3", "Q4")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_active_cycle(db: Session) -> CycleConfig | None:
    return db.query(CycleConfig).filter(CycleConfig.is_active.is_(True)).first()


def quarter_start_dates(cycle: CycleConfig | None, year: int) -> dict[str, date]:
    if cycle:
        return {
            "Q1": cycle.q1_checkin_start,
            "Q2": cycle.q2_checkin_start,
            "Q3": cycle.q3_checkin_start,
            "Q4": cycle.q4_checkin_start,
        }
    return {
        "Q1": date(year, 1, 1),
        "Q2": date(year, 4, 1),
        "Q3": date(year, 7, 1),
        "Q4": date(year, 10, 1),
    }


def get_current_active_quarter(db: Session, today: date | None = None) -> tuple[str, date]:
    today = today or _utc_now().date()
    cycle = get_active_cycle(db)
    year = cycle.cycle_year if cycle else today.year
    starts = quarter_start_dates(cycle, year)

    active_quarter = "Q4"
    active_start = starts["Q4"]
    for quarter in QUARTER_ORDER:
        if today >= starts[quarter]:
            active_quarter = quarter
            active_start = starts[quarter]
    return active_quarter, active_start
