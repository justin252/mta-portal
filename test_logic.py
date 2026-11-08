import json
import os
from datetime import date, datetime, timezone

import pytest

from logic import (MAX_MINUTES, STALE_AFTER, arrival_minutes, clock_text, days_from_civil, freshness,
                   http_date_to_epoch, iso_to_epoch, parse_station, server_clock, server_time,
                   times_text, utc_offset)

FIXTURES = os.path.join(os.path.dirname(__file__), 'test_fixtures')
# Date header served with the saved train_*.json fixtures
FIXTURE_DATE = 'Sat, 07 Nov 2026 21:31:56 GMT'


def load(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return json.load(f)


def oracle(iso):
    """Independent epoch conversion via CPython's datetime."""
    return int(datetime.fromisoformat(iso).timestamp())


class TestDaysFromCivil:
    @pytest.mark.parametrize('y,m,d', [
        (1970, 1, 1), (1969, 12, 31), (2000, 2, 29), (2000, 3, 1), (1900, 3, 1),
        (2024, 2, 29), (2026, 11, 7), (2026, 12, 31), (2027, 1, 1), (2100, 2, 28), (2100, 3, 1),
    ])
    def test_matches_datetime(self, y, m, d):
        assert days_from_civil(y, m, d) == date(y, m, d).toordinal() - date(1970, 1, 1).toordinal()

    def test_every_day_for_a_decade(self):
        start = date(2020, 1, 1).toordinal()
        for ordinal in range(start, start + 3653):
            day = date.fromordinal(ordinal)
            assert days_from_civil(day.year, day.month, day.day) == ordinal - date(1970, 1, 1).toordinal()


class TestIsoToEpoch:
    @pytest.mark.parametrize('iso', [
        '2026-11-07T16:37:43-05:00',   # EST, as the train API sends it
        '2026-07-04T09:05:00-04:00',   # EDT
        '2026-11-01T01:30:00-04:00',   # DST fall-back hour, first pass
        '2026-11-01T01:30:00-05:00',   # same wall time, second pass
        '2026-12-31T23:59:59-05:00',   # crosses into the next UTC year
        '2026-11-07T21:31:56+00:00',
    ])
    def test_matches_datetime(self, iso):
        assert iso_to_epoch(iso) == oracle(iso)

    def test_z_suffix(self):
        assert iso_to_epoch('2026-11-07T21:31:56Z') == oracle('2026-11-07T21:31:56+00:00')

    def test_fractional_seconds_dropped(self):
        assert iso_to_epoch('2026-11-07T16:37:43.875-05:00') == oracle('2026-11-07T16:37:43-05:00')

    def test_missing_offset_rejected(self):
        # A naive time would silently shift every arrival by the board's UTC offset
        with pytest.raises(ValueError):
            iso_to_epoch('2026-11-07T16:37:43')


class TestHttpDateToEpoch:
    def test_fixture_date(self):
        assert http_date_to_epoch(FIXTURE_DATE) == int(
            datetime(2026, 11, 7, 21, 31, 56, tzinfo=timezone.utc).timestamp())

    def test_leap_day(self):
        assert http_date_to_epoch('Thu, 29 Feb 2024 00:00:00 GMT') == int(
            datetime(2024, 2, 29, tzinfo=timezone.utc).timestamp())

    def test_garbage_rejected(self):
        with pytest.raises(Exception):
            http_date_to_epoch('yesterday-ish')


class TestServerTime:
    def test_prefers_date_header(self):
        assert server_time({'date': FIXTURE_DATE}, {'updated': '2000-01-01T00:00:00Z'}) == \
            http_date_to_epoch(FIXTURE_DATE)

    def test_falls_back_to_payload_updated(self):
        payload = load('train_L11.json')
        assert server_time({}, payload) == oracle(payload['updated'])


class TestArrivalMinutes:
    NOW = oracle('2026-11-07T16:00:00-05:00')

    def entry(self, route, offset_s):
        return {'route': route, 'time': datetime.fromtimestamp(self.NOW + offset_s, timezone.utc).isoformat()}

    def test_rounds_and_sorts(self):
        entries = [self.entry('L', 600), self.entry('L', 90), self.entry('L', 29)]
        assert arrival_minutes(entries, 'L', self.NOW) == [0, 2, 10]

    def test_filters_route(self):
        entries = [self.entry('G', 120), self.entry('L', 300)]
        assert arrival_minutes(entries, 'L', self.NOW) == [5]

    def test_drops_departed_keeps_just_arriving(self):
        entries = [self.entry('L', -300), self.entry('L', -20), self.entry('L', 0)]
        assert arrival_minutes(entries, 'L', self.NOW) == [0, 0]

    def test_drops_beyond_max(self):
        # 3-digit minutes overflow the 46px time row (see test_layout.py)
        entries = [self.entry('L', MAX_MINUTES * 60), self.entry('L', (MAX_MINUTES + 1) * 60)]
        assert arrival_minutes(entries, 'L', self.NOW) == [MAX_MINUTES]

    def test_empty(self):
        assert arrival_minutes([], 'L', self.NOW) == []


class TestParseStation:
    NOW = http_date_to_epoch(FIXTURE_DATE)

    @pytest.mark.parametrize('fixture,route', [('train_L11.json', 'L'), ('train_G29.json', 'G')])
    def test_real_payload(self, fixture, route):
        payload = load(fixture)
        station = payload['data'][0]
        north, south = parse_station(payload, route, self.NOW)
        for got, entries in ((north, station['N']), (south, station['S'])):
            want = sorted(m for m in (round((oracle(e['time']) - self.NOW) / 60)
                                      for e in entries if e['route'] == route) if 0 <= m <= MAX_MINUTES)
            assert got == want and got, 'expected non-empty %s arrivals' % route

    def test_g29_ignores_l_trains(self):
        # Metropolitan Av / Lorimer St serves both lines; the G screen must not show L trains
        payload = load('train_G29.json')
        north, _ = parse_station(payload, 'G', self.NOW)
        all_north, _ = parse_station(payload, 'L', self.NOW)
        assert north and all_north and north != all_north

    def test_missing_direction_is_empty(self):
        assert parse_station({'data': [{'N': []}]}, 'L', self.NOW) == ([], [])

    @pytest.mark.parametrize('payload', [
        {'data': []},
        {'error': 'not found'},
        {'data': [{'N': [{'route': 'L'}]}]},
        {'data': [{'N': [{'route': 'L', 'time': 'soon'}]}]},
        [],
    ])
    def test_malformed_payload_raises(self, payload):
        # Raising (not returning garbage) is the contract: app.py counts it as a failed fetch
        with pytest.raises(Exception):
            parse_station(payload, 'L', self.NOW)


class TestClock:
    @pytest.mark.parametrize('iso,offset', [
        ('2026-11-07T18:49:02-05:00', -5 * 3600),
        ('2026-07-04T09:05:00-04:00', -4 * 3600),   # daylight saving: the API's offset changes with it
        ('2026-11-07T21:31:56Z', 0),
        ('2026-11-07T16:37:43.875+05:30', 5 * 3600 + 1800),
    ])
    def test_utc_offset(self, iso, offset):
        assert utc_offset(iso) == offset

    @pytest.mark.parametrize('local,text', [
        ('2026-11-07T00:05:00', '12:05'),   # just after midnight
        ('2026-11-07T06:05:59', '6:05'),
        ('2026-11-07T12:52:00', '12:52'),   # noon hour
        ('2026-11-07T13:00:00', '1:00'),
        ('2026-11-07T23:59:00', '11:59'),
    ])
    def test_clock_text(self, local, text):
        epoch = iso_to_epoch(local + '-05:00')
        assert clock_text(epoch, -5 * 3600) == text

    def test_server_clock_from_real_payload(self):
        epoch, offset = server_clock({'date': FIXTURE_DATE}, load('train_L11.json'))
        assert (offset, clock_text(epoch, offset)) == (-5 * 3600, '4:31')  # 21:31:56 GMT


class TestTimesText:
    def test_three_soonest(self):
        assert times_text([2, 6, 11, 15]) == '2,6,11'

    def test_fewer_than_three_padded(self):
        # '-' fills the row out to three slots (design review: "8,-,-" over "8")
        assert times_text([4, 12]) == '4,12,-'
        assert times_text([8]) == '8,-,-'

    def test_none(self):
        assert times_text([]) == '-,-,-'


class TestFreshness:
    @pytest.mark.parametrize('has_data,age,failures,expected', [
        (True, 0, 0, 'live'),
        (True, STALE_AFTER, 2, 'live'),
        (True, STALE_AFTER + 1, 3, 'stale'),
        (False, 5, 0, 'loading'),     # just booted, first fetch not back yet
        (False, 40, 2, 'offline'),    # no data and fetches failing
    ])
    def test_states(self, has_data, age, failures, expected):
        assert freshness(has_data, age, failures) == expected
