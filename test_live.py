"""Contract tests against the real APIs (network). Run with `make test-live`.

These catch what fixtures can't: a URL that starts returning 404 (the old NWS grid point
did, for months), or a response that changes shape.
"""
import json
import ssl
import time
import urllib.request

import certifi
import pytest

import layout
from logic import TRAIN_URL, parse_station, server_time
from weather import CONDITIONS, WEATHER_URL, map_condition, parse_weather

pytestmark = pytest.mark.live


def get(url):
    ctx = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(url, headers={'User-Agent': 'mta-portal'})
    with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
        assert resp.status == 200
        return json.load(resp), {k.lower(): v for k, v in resp.headers.items()}


@pytest.mark.parametrize('line', layout.LINES)
def test_train_api(line):
    payload, headers = get(TRAIN_URL % layout.STATIONS[line]['stop_id'])
    now = server_time(headers, payload)
    assert abs(now - time.time()) < 300, 'server clock is %ds off' % (now - time.time())
    north, south = parse_station(payload, line, now)
    assert north or south, 'no %s trains at all: service change, or the API stopped listing them' % line


def test_weather_api():
    weather = parse_weather(get(WEATHER_URL)[0])
    assert -40 < weather['lo_f'] <= weather['hi_f'] < 130
    known = any(lo <= weather['code'] <= hi for lo, hi, _, _ in CONDITIONS)
    assert known, 'unmapped weather code %d shows as %r' % (weather['code'], map_condition(weather['code']))
