"""Pure functions for MTA arrival logic. Works on both CircuitPython and desktop.

Times are Unix seconds. "Now" comes from the train API's own HTTP Date header, so the
board needs no clock sync and no timezone setting. Keep epoch math in ints: CircuitPython
floats have ~22 bits of precision, far too few for epoch seconds.
"""

TRAIN_URL = 'https://api.wheresthefuckingtrain.com/by-id/%s'
MAX_MINUTES = 99  # 3-digit minutes overflow the time row (test_layout.py)

_MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def days_from_civil(y, m, d):
    """Days since 1970-01-01 for a Gregorian date (Howard Hinnant's days_from_civil)."""
    if m <= 2:
        y -= 1
    era = y // 400
    yoe = y - era * 400                      # year of era, 0..399
    doy = (153 * ((m + 9) % 12) + 2) // 5 + d - 1  # day of year, March-based
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def iso_to_epoch(s):
    """'2026-11-07T16:37:43-05:00' -> Unix seconds. Requires an offset or Z."""
    day, clock = s.split('T')
    y, mo, d = day.split('-')
    secs = (days_from_civil(int(y), int(mo), int(d)) * 86400
            + int(clock[0:2]) * 3600 + int(clock[3:5]) * 60 + int(clock[6:8]))
    tz = clock[8:]
    if tz.startswith('.'):  # fractional seconds: whole minutes are all the sign shows
        tz = tz.lstrip('.0123456789')
    if tz == 'Z':
        return secs
    if len(tz) != 6 or tz[0] not in '+-':
        raise ValueError('no UTC offset in %r' % s)
    offset = int(tz[1:3]) * 3600 + int(tz[4:6]) * 60
    return secs - offset if tz[0] == '+' else secs + offset


def http_date_to_epoch(s):
    """'Sat, 07 Nov 2026 21:31:56 GMT' (RFC 7231 Date header) -> Unix seconds."""
    _, d, mon, y, hms, _ = s.split()
    h, mi, sec = hms.split(':')
    return (days_from_civil(int(y), _MONTHS.index(mon) + 1, int(d)) * 86400
            + int(h) * 3600 + int(mi) * 60 + int(sec))


def server_time(headers, payload):
    """Current time per the train API: its Date header, else the feed's 'updated' stamp."""
    date = headers.get('date')
    return http_date_to_epoch(date) if date else iso_to_epoch(payload['updated'])


def arrival_minutes(entries, route, now):
    """Minutes until each `route` arrival, soonest first. Drops departed and > MAX_MINUTES."""
    minutes = []
    for e in entries:
        if e['route'] == route:
            m = round((iso_to_epoch(e['time']) - now) / 60)
            if 0 <= m <= MAX_MINUTES:
                minutes.append(m)
    minutes.sort()
    return minutes


def parse_station(payload, route, now):
    """Train API payload -> (north_minutes, south_minutes). Raises on unexpected shape."""
    station = payload['data'][0]
    return (arrival_minutes(station.get('N', []), route, now),
            arrival_minutes(station.get('S', []), route, now))


def format_arrival_triple(minutes_list):
    v0 = str(minutes_list[0]) if len(minutes_list) > 0 else '-'
    v1 = str(minutes_list[1]) if len(minutes_list) > 1 else '-'
    v2 = str(minutes_list[2]) if len(minutes_list) > 2 else '-'
    return v0, v1, v2
