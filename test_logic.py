import json
import os
from datetime import date, datetime, timezone

import pytest

from logic import (MAX_MINUTES, arrival_minutes, days_from_civil, format_arrival_triple,
                   http_date_to_epoch, iso_to_epoch, parse_station, server_time)

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


class TestFormatArrivalTriple:
    def test_three_values(self):
        assert format_arrival_triple([10, 20, 30]) == ('10', '20', '30')

    def test_two_values(self):
        assert format_arrival_triple([10, 20]) == ('10', '20', '-')

    def test_one_value(self):
        assert format_arrival_triple([10]) == ('10', '-', '-')

    def test_empty(self):
        assert format_arrival_triple([]) == ('-', '-', '-')

    def test_more_than_three(self):
        assert format_arrival_triple([10, 20, 30, 40]) == ('10', '20', '30')
