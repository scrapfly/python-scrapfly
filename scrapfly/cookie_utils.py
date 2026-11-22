import re
from datetime import datetime, timezone
from typing import Optional, Union


_DELIMITERS = re.compile(r'[\x09\x20-\x2F\x3B-\x40\x5B-\x60\x7B-\x7E]+')
_TIME = re.compile(r'^(\d{1,2}):(\d{1,2}):(\d{1,2})(?:\D.*)?$')
_DAY = re.compile(r'^(\d{1,2})(?:\D.*)?$')
_YEAR = re.compile(r'^(\d{2,4})(?:\D.*)?$')
_EPOCH = re.compile(r'^[+-]?\d+(?:\.\d+)?$')
_MONTHS = {
    'jan': 1,
    'feb': 2,
    'mar': 3,
    'apr': 4,
    'may': 5,
    'jun': 6,
    'jul': 7,
    'aug': 8,
    'sep': 9,
    'oct': 10,
    'nov': 11,
    'dec': 12,
}


def parse_cookie_expires(value: str) -> Optional[Union[int, float]]:
    value = value.strip()

    if _EPOCH.fullmatch(value):
        return float(value) if '.' in value else int(value)

    day = None
    month = None
    year = None
    clock = None

    for token in _DELIMITERS.split(value):
        if not token:
            continue

        match = _TIME.fullmatch(token)
        if clock is None and match:
            clock = tuple(int(part) for part in match.groups())
            continue

        match = _DAY.fullmatch(token)
        if day is None and match:
            day = int(match.group(1))
            continue

        if month is None and token[:3].lower() in _MONTHS:
            month = _MONTHS[token[:3].lower()]
            continue

        match = _YEAR.fullmatch(token)
        if year is None and match:
            year = int(match.group(1))

    if day is None or month is None or year is None or clock is None:
        return None

    if 70 <= year <= 99:
        year += 1900
    elif year <= 69:
        year += 2000

    hour, minute, second = clock

    if year < 1601 or not 1 <= day <= 31 or hour > 23 or minute > 59 or second > 59:
        return None

    try:
        return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None
