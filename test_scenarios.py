"""Every design the sign can show is a scenario (scenarios.py): reviewed on the real sign one
at a time (`make review`) and verified pixel for pixel (`make verify`). Keep the list complete."""
import os

import pytest

import layout
import scenarios
from simulate_display import font, glyph_metrics, ink_right, render_screen
from weather import CONDITIONS, map_condition

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
    designs = {map_condition(c[0], day) for c in CONDITIONS for day in (True, False)}
    assert shown == designs, 'missing: %s' % sorted(designs - shown)


def test_every_art_piece_has_a_scenario():
    shown = {scenarios.state(s)['bitmap'] for s in scenarios.SCENARIOS if 'art' in s}
    assert shown == set(layout.ART)


def test_every_train_state_has_a_scenario():
    states = {s['train'][3] if len(s['train']) > 3 else 'live' for s in scenarios.SCENARIOS if 'train' in s}
    assert states == {'live', 'stale', 'loading', 'offline'}


def test_every_screen_kind_has_a_scenario():
    kinds = {scenarios.state(s)['screen'] for s in scenarios.SCENARIOS}
    assert kinds == set(layout.LINES) | {'weather', 'art'}


@pytest.mark.parametrize('scenario', scenarios.SCENARIOS, ids=lambda s: s['name'])
def test_scenario_renders_and_fits(scenario):
    st = scenarios.state(scenario)
    assert os.path.exists(os.path.join(ROOT, st['bitmap']))
    for field, text in st['texts'].items():
        _, role, box, _ = FIELDS[field]
        x = layout.centered_x(text, glyph_metrics(role), box)
        assert ink_right(font(role), text, x) <= box[0] + box[1], '%s: %r leaves its box' % (field, text)
    assert render_screen(st).size == (layout.WIDTH, layout.HEIGHT)
