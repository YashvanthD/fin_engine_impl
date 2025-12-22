import time
from datetime import datetime
import zoneinfo


def get_time_date(zone: str = 'IST', dt: datetime = None, include_time: bool = True) -> str:
    """Return formatted date or datetime string in the requested timezone.

    This is the single source of truth for timezone-aware date/time
    formatting. Other modules should prefer this (or get_time_date_dt)
    instead of calling datetime.now() directly.
    """
    if zone.upper() == 'IST':
        tz_name = 'Asia/Kolkata'
    else:
        tz_name = zone
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


def get_time_date_dt(zone: str = 'IST', dt: datetime = None, include_time: bool = True) -> datetime:
    """Return a datetime object corresponding to get_time_date output."""
    s = get_time_date(zone=zone, dt=dt, include_time=include_time)
    fmt = '%Y-%m-%d %H:%M' if include_time else '%Y-%m-%d'
    return datetime.strptime(s, fmt)

