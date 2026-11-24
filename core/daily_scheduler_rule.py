"""Daily scheduler rule engine for TKS Engine 3.0.

Implements the standard rule:
- DEFAULT_SCHEDULE_TIME = "18:00"
- DEFAULT_SCHEDULE_TIMEZONE = "America/Sao_Paulo"
- VIDEOS_PER_ACCOUNT_PER_DAY = 1
- DEFAULT_CAPTION = "ABSURDO"

Consecutive daily allocation:
- Video 1: Next available day at 18:00 (America/Sao_Paulo).
- Video 2: Next day at 18:00.
- Video N: N-th consecutive day at 18:00.
"""
from __future__ import annotations

import logging
import zoneinfo
from datetime import datetime, timedelta
from typing import Any

from core.db_manager import DatabaseManager

logger = logging.getLogger("tks.daily_scheduler")

DEFAULT_SCHEDULE_TIME = "18:00"
DEFAULT_SCHEDULE_TIMEZONE = "America/Sao_Paulo"
VIDEOS_PER_ACCOUNT_PER_DAY = 1
DEFAULT_CAPTION = "ABSURDO"


def get_account_booked_dates(account_id: str, db: DatabaseManager | None = None) -> set[str]:
    """Retrieve all dates where this account already has an active or scheduled video."""
    db_mgr = db or DatabaseManager.get_instance()
    booked: set[str] = set()

    with db_mgr.get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT schedule_time FROM jobs
            WHERE account_id = ?
              AND status IN ('READY_FOR_UPLOAD', 'ASSIGNED', 'RUNNING', 'UPLOADING', 'PROCESSING', 'SUBMITTING', 'SCHEDULED', 'PUBLISHED')
              AND schedule_time IS NOT NULL
            """,
            (account_id,),
        )
        for row in cursor.fetchall():
            raw = str(row["schedule_time"]).strip()
            # Handle formats: "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DD"
            parts = raw.split(" ")
            date_part = parts[0]
            if len(date_part) == 10 and date_part.count("-") == 2:
                booked.add(date_part)

    return booked


def calculate_next_daily_slot(
    account_id: str,
    db: DatabaseManager | None = None,
    target_time: str = DEFAULT_SCHEDULE_TIME,
    tz_name: str = DEFAULT_SCHEDULE_TIMEZONE,
    exclude_job_id: str | None = None,
) -> tuple[datetime, str]:
    """Find the next available consecutive date for this account at target_time.

    :return: (datetime_object, formatted_string_YYYY_MM_DD_HH_MM_SS)
    """
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo("America/Sao_Paulo")

    now = datetime.now(tz)

    # Parse target hour and minute
    time_parts = target_time.split(":")
    target_hour = int(time_parts[0]) if len(time_parts) > 0 else 18
    target_minute = int(time_parts[1]) if len(time_parts) > 1 else 0

    booked_dates = get_account_booked_dates(account_id, db=db)

    # If modifying a specific job, ignore its own current booking
    if exclude_job_id and db:
        with db.get_connection() as conn:
            c = conn.execute("SELECT schedule_time FROM jobs WHERE id = ?", (exclude_job_id,))
            row = c.fetchone()
            if row and row["schedule_time"]:
                own_date = str(row["schedule_time"]).split(" ")[0]
                booked_dates.discard(own_date)

    candidate_date = now.date()

    # Search up to 10 days in advance (TikTok official limit)
    for _ in range(15):
        candidate_dt = datetime(
            candidate_date.year,
            candidate_date.month,
            candidate_date.day,
            target_hour,
            target_minute,
            0,
            tzinfo=tz,
        )

        date_str = candidate_date.strftime("%Y-%m-%d")

        # Must be at least 30 minutes in the future from now
        is_far_enough = candidate_dt > (now + timedelta(minutes=30))

        if is_far_enough and date_str not in booked_dates:
            formatted = candidate_dt.strftime("%Y-%m-%d %H:%M:%S")
            return candidate_dt, formatted

        candidate_date += timedelta(days=1)

    # Fallback to tomorrow at target time if all slots are saturated
    fallback_date = now.date() + timedelta(days=1)
    fallback_dt = datetime(
        fallback_date.year,
        fallback_date.month,
        fallback_date.day,
        target_hour,
        target_minute,
        0,
        tzinfo=tz,
    )
    return fallback_dt, fallback_dt.strftime("%Y-%m-%d %H:%M:%S")
