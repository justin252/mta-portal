"""Every design the sign can show is a scenario (scenarios.py): reviewed on the real sign one
at a time (`make review`) and verified pixel for pixel (`make verify`). Keep the list complete."""
import os

import pytest

import layout
import scenarios
from simulate_display import font, ink_right, render_screen
from weather import CONDITIONS

ROOT = os.path.dirname(os.path.abspath(__file__))
FIELDS = {f[0]: f for f in layout.TRAIN_FIELDS + layout.WEATHER_FIELDS}


def test_names_unique_and_indexed():
    names = [s['name'] for s in scenarios.SCENARIOS]
    assert len(names) == len(set(names))
    assert set(scenarios.BY_NAME) == set(names)
    assert all(s['about'] for s in scenarios.SCENARIOS)


def test_every_weather_design_has_a_scenario():
    shown = {(st['bitmap'], st['texts']['condition'])
             for st in map(scenarios.state, scenarios.SCENARIOS) if st['screen'] == 'weather'}
    assert shown == {(c[2], c[3]) for c in CONDITIONS}


def test_every_screen_kind_has_a_scenario():
    kinds = {scenarios.state(s)['screen'] for s in scenarios.SCENARIOS}
    assert kinds == set(layout.LINES) | {'weather', 'art'}


@pytest.mark.parametrize('scenario', scenarios.SCENARIOS, ids=lambda s: s['name'])
def test_scenario_renders_and_fits(scenario):
    st = scenarios.state(scenario)
    assert os.path.exists(os.path.join(ROOT, st['bitmap']))
    for field, text in st['texts'].items():
        _, role, x, _ = FIELDS[field]
        assert ink_right(font(role), text, x) <= layout.WIDTH, '%s: %r is clipped' % (field, text)
    assert render_screen(st).size == (layout.WIDTH, layout.HEIGHT)
