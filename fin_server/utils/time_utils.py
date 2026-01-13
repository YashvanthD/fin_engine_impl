from datetime import datetime
import zoneinfo
from typing import Optional, Dict, Any

from config import config

# Default timezone from config
DEFAULT_TZ = config.DEFAULT_TIMEZONE


def _resolve_tz_name(zone: str = 'IST', settings: Optional[Dict[str, Any]] = None) -> str:
    """Resolve a timezone name from an optional settings map and a zone hint.

    Priority:
      1) settings['timezone'] if present (user- or account-level)
      2) explicit zone parameter (e.g. 'IST', 'Asia/Kolkata', 'Europe/Berlin')
      3) fallback to DEFAULT_TIMEZONE from config
    """
    # settings can be any mapping; tolerate missing keys
    if settings and isinstance(settings, dict):
        tz_val = settings.get('timezone') or settings.get('timeZone') or settings.get('tz')
        if isinstance(tz_val, str) and tz_val.strip():
            zone = tz_val.strip()
    if isinstance(zone, str) and zone.upper() == 'IST':
        return DEFAULT_TZ
    return zone or DEFAULT_TZ


def get_time_date(zone: str = 'IST', dt: datetime = None, include_time: bool = True, settings: Optional[Dict[str, Any]] = None) -> str:
    """Return formatted date or datetime string in the requested timezone.

    This is the single source of truth for timezone-aware date/time
    formatting. Other modules should prefer this (or get_time_date_dt)
    instead of calling datetime.now() directly.

    If a settings map is provided, its 'timezone' (or 'timeZone'/'tz')
    field overrides the zone parameter.
    """
    tz_name = _resolve_tz_name(zone=zone, settings=settings)
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except Exception:
        tz = zoneinfo.ZoneInfo(DEFAULT_TZ)

    if dt is None:
        now = datetime.now(tz)
    else:
        if dt.tzinfo is None:
            now = dt.replace(tzinfo=tz)
        else:
            now = dt.astimezone(tz)

    if not include_time:
        return now.strftime('%Y-%m-%d')
    return now.strftime('%Y-%m-%d %H:%M')


def get_time_date_dt(zone: str = 'IST', dt: datetime = None, include_time: bool = True, settings: Optional[Dict[str, Any]] = None) -> datetime:
    """Return a datetime object corresponding to get_time_date output.

    Accepts the same settings map as get_time_date for timezone
    resolution.
    """
    s = get_time_date(zone=zone, dt=dt, include_time=include_time, settings=settings)
    fmt = '%Y-%m-%d %H:%M' if include_time else '%Y-%m-%d'
    return datetime.strptime(s, fmt)


def now_std(include_time: bool = True) -> datetime:
    """Return current datetime in the application's standard timezone (IST).

    This helper is intended for storage and internal logic. For user-facing
    formatting or parsing that should respect user/account settings, continue
    to use get_time_date / get_time_date_dt with a settings map.
    """
    return get_time_date_dt(zone='IST', include_time=include_time, settings=None)


def normalize_date(value) -> Optional[datetime]:
    """Normalize various date formats to a datetime object.

    Handles:
    - datetime objects (returned as-is)
    - ISO format strings (e.g., "2026-01-13T10:30:00")
    - Date strings (e.g., "2026-01-13")
    - Epoch timestamps (int or float)
    - None (returns None)

    Returns:
        datetime object or None if parsing fails
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    # Handle epoch timestamps
    if isinstance(value, (int, float)):
        try:
            # Assume milliseconds if value is very large
            if value > 1e12:
                value = value / 1000
            return datetime.fromtimestamp(value)
        except Exception:
            return None

    # Handle string formats
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

        # Try various formats
        formats = [
            '%Y-%m-%dT%H:%M:%S.%fZ',  # ISO with microseconds and Z
            '%Y-%m-%dT%H:%M:%SZ',      # ISO with Z
            '%Y-%m-%dT%H:%M:%S.%f',    # ISO with microseconds
            '%Y-%m-%dT%H:%M:%S',       # ISO
            '%Y-%m-%d %H:%M:%S',       # Standard datetime
            '%Y-%m-%d %H:%M',          # Without seconds
            '%Y-%m-%d',                # Date only
            '%d-%m-%Y',                # Day first
            '%m/%d/%Y',                # US format
        ]

        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue

        return None

    return None


def to_iso_string(value) -> Optional[str]:
    """Convert a date value to ISO format string.

    Args:
        value: datetime, epoch, or date string

    Returns:
        ISO format string (YYYY-MM-DDTHH:MM:SS) or None
    """
    dt = normalize_date(value)
    if dt:
        return dt.isoformat()
    return None


def to_epoch(value) -> Optional[int]:
    """Convert a date value to epoch timestamp (seconds).

    Args:
        value: datetime, ISO string, or epoch

    Returns:
        Epoch timestamp in seconds or None
    """
    dt = normalize_date(value)
    if dt:
        return int(dt.timestamp())
    return None


