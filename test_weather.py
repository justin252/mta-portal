"""Tests for weather.py: Open-Meteo current conditions."""
import json
import os

import pytest

from weather import (CONDITIONS, DEFAULT_CONDITION, NIGHT, format_hi_lo, format_temperature,
                     map_condition, parse_weather)

ROOT = os.path.dirname(__file__)
FIXTURES = os.path.join(ROOT, 'test_fixtures')


class TestParseWeather:
    def test_real_payload(self):
        with open(os.path.join(FIXTURES, 'openmeteo_current.json')) as f:
            assert parse_weather(json.load(f)) == {
                'temp_f': 48.6, 'code': 1, 'hi_f': 61.0, 'lo_f': 45.7, 'is_day': False}

    def test_is_day_defaults_to_day(self):
        data = {'current': {'temperature_2m': 50, 'weather_code': 0},
                'daily': {'temperature_2m_max': [55], 'temperature_2m_min': [40]}}
        assert parse_weather(data)['is_day'] is True

    @pytest.mark.parametrize('payload', [
        {},
        {'current': {'temperature_2m': 50, 'weather_code': 0}},  # no daily hi/lo
        {'current': {'temperature_2m': 50, 'weather_code': 0},
         'daily': {'temperature_2m_max': [], 'temperature_2m_min': []}},
        {'error': True, 'reason': 'Parameter latitude must be in range'},
    ])
    def test_malformed_payload_raises(self, payload):
        with pytest.raises(Exception):
            parse_weather(payload)


class TestMapCondition:
    # WMO weather codes as documented at open-meteo.com/en/docs
    @pytest.mark.parametrize('code,bitmap,label', [
        (0, 'weather-sun.bmp', 'Clear'),
        (1, 'weather-sun.bmp', 'Clear'),
        (2, 'weather-partly.bmp', 'Cloudy'),
        (3, 'weather-cloud.bmp', 'Overcast'),
        (45, 'weather-fog.bmp', 'Fog'),
        (48, 'weather-fog.bmp', 'Fog'),
        (51, 'weather-drizzle.bmp', 'Drizzle'),
        (55, 'weather-drizzle.bmp', 'Drizzle'),
        (56, 'weather-sleet.bmp', 'Sleet'),
        (61, 'weather-rain.bmp', 'Rain'),
        (65, 'weather-rain.bmp', 'Rain'),
        (67, 'weather-sleet.bmp', 'Sleet'),
        (71, 'weather-snow.bmp', 'Snow'),
        (77, 'weather-snow.bmp', 'Snow'),
        (80, 'weather-showers.bmp', 'Showers'),
        (82, 'weather-showers.bmp', 'Showers'),
        (86, 'weather-snow.bmp', 'Snow'),
        (95, 'weather-storm.bmp', 'Storm'),
        (99, 'weather-storm.bmp', 'Storm'),
    ])
    def test_codes(self, code, bitmap, label):
        assert map_condition(code) == (bitmap, label)

    @pytest.mark.parametrize('code,bitmap', [
        (0, 'weather-moon.bmp'),
        (1, 'weather-moon.bmp'),
        (2, 'weather-partly-night.bmp'),
        (3, 'weather-cloud.bmp'),   # no sun to swap out
        (63, 'weather-rain.bmp'),
    ])
    def test_night_icons(self, code, bitmap):
        assert map_condition(code, is_day=False)[0] == bitmap

    @pytest.mark.parametrize('code', [-1, 4, 50, 100])
    def test_unknown_code_falls_back(self, code):
        assert map_condition(code) == DEFAULT_CONDITION

    def test_every_icon_exists(self):
        for icon in {c[2] for c in CONDITIONS} | set(NIGHT.values()) | {DEFAULT_CONDITION[0]}:
            assert os.path.exists(os.path.join(ROOT, icon)), icon


class TestFormatHiLo:
    @pytest.mark.parametrize('hi,lo,expected', [
        (61.0, 45.4, 'H:61 L:45'),
        (-2, -15.4, 'H:-2 L:-15'),
        (104.4, 88, 'H:104 L:88'),
    ])
    def test_formatting(self, hi, lo, expected):
        assert format_hi_lo(hi, lo) == expected


class TestFormatTemperature:
    @pytest.mark.parametrize("temp,expected", [
        (42, '42°F'),
        (0, '0°F'),
        (-5, '-5°F'),
        (100, '100°F'),
        (72.6, '73°F'),
        (51.1, '51°F'),
    ])
    def test_formatting(self, temp, expected):
        assert format_temperature(temp) == expected
