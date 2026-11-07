"""Fake-device e2e for tools/portal.py: dumps are synthesized exactly as diag.py emits them."""
import binascii
import json
import os
import sys

import pytest
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import portal  # noqa: E402
from simulate_display import render_display, render_weather_display  # noqa: E402

STATES = {
    'L': ({'screen': 'L', 'bitmap': 'l-dashboard.bmp',
           'texts': {'north': 'Manhattan', 'north_times': '3,8,14', 'south': 'Canarsie', 'south_times': '1,5,12'}},
          lambda: render_display('L', '3,8,14', '1,5,12')),
    'G': ({'screen': 'G', 'bitmap': 'g-dashboard.bmp',
           'texts': {'north': 'Queens', 'north_times': '2,7,15', 'south': 'Church Av', 'south_times': '-,-,-'}},
          lambda: render_display('G', '2,7,15', '-,-,-')),
    'weather': ({'screen': 'weather', 'bitmap': 'weather-cloud.bmp',
                 'texts': {'condition': 'Cloudy', 'temp': '42°F'}},
                lambda: render_weather_display('cloud', '42°F', 'Cloudy')),
}


def fake_dump(img, state):
    """Lines diag.py would print for this image: RGB565 little-endian, one hex row per line."""
    w, h = img.size
    px = img.convert('RGB').load()
    lines = ['[FB] BEGIN ' + json.dumps(dict(state, w=w, h=h, src='memoryview'))]
    for y in range(h):
        row = bytearray()
        for x in range(w):
            v = portal.to_565(px[x, y])
            row += bytes((v & 0xFF, v >> 8))
        lines.append('[FB] %d %s' % (y, binascii.hexlify(row).decode()))
    lines.append('[FB] END')
    return lines


def shift_labels_up(img, n=1):
    """Copy of img with the text area (x >= TEXT_X) moved up n rows, bitmap area untouched."""
    out = img.copy()
    src = img.load()
    dst = out.load()
    w, h = img.size
    for y in range(h):
        for x in range(portal.TEXT_X, w):
            dst[x, y] = src[x, y + n] if y + n < h else (0, 0, 0)
    return out


def verify_lines(lines):
    state, rows = portal.parse_dump(lines)
    device_px = portal.decode_rgb565(rows)
    expected = portal.render_expected(state)
    return device_px, expected, portal.compare(device_px, expected)


def test_gold_encodes_like_displayio():
    assert portal.to_565((0xDD, 0x80, 0x00)) == 0xDC00
    row = fake_dump(Image.new('RGB', (1, 1), (0xDD, 0x80, 0x00)), {'screen': 'x'})[1]
    assert row == '[FB] 0 00dc'
    assert portal.decode_rgb565([b'\x00\xdc']) == [[0xDC00]]


@pytest.mark.parametrize('screen', sorted(STATES))
def test_fake_device_matches_sim(screen):
    state, render = STATES[screen]
    device_px, expected, mismatches = verify_lines(fake_dump(render(), state))
    assert mismatches == []
    assert portal.best_shift(device_px, expected)[0] == 0


def test_label_shift_detected():
    state, render = STATES['L']
    device_px, expected, mismatches = verify_lines(fake_dump(shift_labels_up(render()), state))
    assert len(mismatches) > 0
    assert portal.best_shift(device_px, expected)[0] == -1


def test_incomplete_dump_rejected():
    state, render = STATES['L']
    lines = fake_dump(render(), state)
    del lines[5]
    with pytest.raises(ValueError, match='missing rows'):
        portal.parse_dump(lines)


def test_device_error_surfaces():
    with pytest.raises(ValueError, match='device dump failed'):
        portal.parse_dump(["[FB] ERR OSError('boom')"])


def test_cli_verify_from_file(tmp_path, capsys):
    state, render = STATES['G']
    capture = tmp_path / 'capture.txt'
    capture.write_text('\n'.join(fake_dump(render(), state)) + '\n')
    assert portal.main(['verify', '--from-file', str(capture), '-o', str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip().endswith('match')
    for name in ('device.png', 'sim.png', 'diff.png', 'state.json'):
        assert (tmp_path / name).exists()


def test_cli_verify_mismatch_exit_code(tmp_path, capsys):
    state, render = STATES['L']
    capture = tmp_path / 'capture.txt'
    capture.write_text('\n'.join(fake_dump(shift_labels_up(render()), state)) + '\n')
    assert portal.main(['verify', '--from-file', str(capture), '-o', str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert 'mismatches' in out and 'best label shift -1' in out

