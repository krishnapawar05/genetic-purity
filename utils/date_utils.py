"""
Centralized Date & Time Utility for Gen Pure Vision.
Enforces the mandatory application-wide date/time display format:
DD-MM-YYYY HH:MM AM/PM (e.g., 10-08-2026 06:28 PM) in Asia/Kolkata (IST, UTC+05:30) timezone.
"""

from datetime import datetime, timezone, timedelta
import zoneinfo

try:
    IST = zoneinfo.ZoneInfo("Asia/Kolkata")
except Exception:
    IST = timezone(timedelta(hours=5, minutes=30))

# Mandatory display format pattern
DATE_TIME_DISPLAY_FORMAT = "%d-%m-%Y %I:%M %p"


def get_current_ist_time() -> datetime:
    """Returns current timezone-aware datetime in Asia/Kolkata (IST)."""
    return datetime.now(IST)


def format_datetime(value, fallback: str = "--") -> str:
    """
    Formats a datetime object, ISO datetime string, or timestamp string into the exact
    required display format in Asia/Kolkata (IST, UTC+05:30):
    DD-MM-YYYY HH:MM AM/PM (e.g., 10-08-2026 06:28 PM).
    """
    if value is None or value == "":
        return fallback

    dt_obj = None

    if isinstance(value, datetime):
        dt_obj = value
    elif isinstance(value, str):
        val_str = value.strip()
        if not val_str or val_str.lower() in ('none', 'null', 'n/a', '--'):
            return fallback

        # Attempt parsing common string representations
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%d-%m-%Y %I:%M %p",
            "%d-%m-%Y %H:%M:%S",
        ):
            try:
                dt_obj = datetime.strptime(val_str, fmt)
                break
            except ValueError:
                pass

        if dt_obj is None:
            try:
                clean_str = val_str.replace("Z", "+00:00")
                dt_obj = datetime.fromisoformat(clean_str)
            except Exception:
                pass

    if dt_obj is None:
        return fallback

    # If datetime object has no tzinfo, treat as UTC (MongoDB default) and convert to Asia/Kolkata
    if dt_obj.tzinfo is None:
        dt_obj = dt_obj.replace(tzinfo=timezone.utc).astimezone(IST)
    else:
        dt_obj = dt_obj.astimezone(IST)

    return dt_obj.strftime(DATE_TIME_DISPLAY_FORMAT)
