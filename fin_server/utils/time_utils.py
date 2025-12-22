from datetime import datetime
import zoneinfo
from typing import Optional, Dict, Any


def _resolve_tz_name(zone: str = 'IST', settings: Optional[Dict[str, Any]] = None) -> str:
    """Resolve a timezone name from an optional settings map and a zone hint.

    Priority:
      1) settings['timezone'] if present (user- or account-level)
      2) explicit zone parameter (e.g. 'IST', 'Asia/Kolkata', 'Europe/Berlin')
      3) fallback to Asia/Kolkata (IST)
    """
    # settings can be any mapping; tolerate missing keys
    if settings and isinstance(settings, dict):
        tz_val = settings.get('timezone') or settings.get('timeZone') or settings.get('tz')
        if isinstance(tz_val, str) and tz_val.strip():
            zone = tz_val.strip()
    if isinstance(zone, str) and zone.upper() == 'IST':
        return 'Asia/Kolkata'
    return zone or 'Asia/Kolkata'


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
        tz = zoneinfo.ZoneInfo('Asia/Kolkata')

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
