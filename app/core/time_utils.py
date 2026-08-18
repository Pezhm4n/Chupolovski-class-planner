# -*- coding: utf-8 -*-
"""
Golestoon Timezone & Datetime Utilities.

Provides standard Iran Standard Time (IRST/IRDT, UTC+3:30) conversions,
elapsed time calculations, and localized datetime formatting.

Architecture Layer: Layer 1 / Core Utility
Dependencies: Python Standard Library (`datetime`, `typing`).
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

# Iran Standard Time: UTC + 3 hours and 30 minutes
IRAN_OFFSET = timedelta(hours=3, minutes=30)
IRAN_TZ = timezone(IRAN_OFFSET, name="IRST")


def get_iran_now() -> datetime:
    """Return the current datetime in Iran Standard Time (UTC+3:30)."""
    return datetime.now(timezone.utc).astimezone(IRAN_TZ)


def to_iran_datetime(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Convert any datetime (aware UTC, naive, or other TZ) to Iran Standard Time.
    """
    if dt is None:
        return None

    if not isinstance(dt, datetime):
        return None

    # If datetime is timezone-aware:
    if dt.tzinfo is not None:
        return dt.astimezone(IRAN_TZ)

    # If datetime is naive, assume it represents UTC (standard for server timestamps)
    # or local time. We treat naive UTC timestamps by attaching UTC then converting.
    dt_utc = dt.replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(IRAN_TZ)


def get_elapsed_minutes(dt: Optional[datetime]) -> float:
    """
    Calculate the elapsed minutes from a given datetime to now.
    """
    if dt is None:
        return 999999.0

    now_utc = datetime.now(timezone.utc)

    if dt.tzinfo is not None:
        dt_utc = dt.astimezone(timezone.utc)
    else:
        dt_utc = dt.replace(tzinfo=timezone.utc)

    elapsed_seconds = (now_utc - dt_utc).total_seconds()
    return max(0.0, elapsed_seconds / 60.0)


def format_iran_datetime(dt: Optional[datetime], is_persian: bool = True) -> str:
    """
    Format a datetime in Iran Standard Time.

    Example Output:
        Persian: '2026-08-18 16:45 (به وقت تهران)'
        English: '2026-08-18 16:45 (Iran Time)'
    """
    if dt is None:
        return "—"

    iran_dt = to_iran_datetime(dt)
    if iran_dt is None:
        return "—"

    time_str = iran_dt.strftime("%Y-%m-%d %H:%M")
    suffix = " (به وقت تهران)" if is_persian else " (Iran Time)"
    return f"{time_str}{suffix}"
