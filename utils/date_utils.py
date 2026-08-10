"""
Centralized Date & Time Utility for Gen Pure Vision.
Enforces the mandatory application-wide date/time display format:
DD-MM-YYYY HH AM/PM (e.g., 07-08-2026 03:45 PM).
"""

from datetime import datetime

# Mandatory display format pattern
DATE_TIME_DISPLAY_FORMAT = "%d-%m-%Y %I:%M %p"


def format_datetime(value, fallback: str = "--") -> str:
    """
    Formats a datetime object, ISO datetime string, or timestamp string into the exact
    required display format: DD-MM-YYYY HH AM/PM (e.g., 07-08-2026 03:45 PM).

    Handles:
    - datetime.datetime objects
    - ISO datetime strings (e.g. '2026-08-07 15:45:00', '2026-08-07T15:45:00.000Z')
    - None / empty / invalid values (returns fallback e.g. '--' or 'N/A')
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

    return dt_obj.strftime(DATE_TIME_DISPLAY_FORMAT)
