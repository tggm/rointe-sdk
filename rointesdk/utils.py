import datetime as dt
DEFAULT_TIME_ZONE: dt.tzinfo = dt.timezone.utc


def now(time_zone: dt.tzinfo | None = None) -> dt.datetime:
    """Get now in specified time zone."""
    return dt.datetime.now(time_zone or DEFAULT_TIME_ZONE)