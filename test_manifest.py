"""The deploy list (tools/portal.py DEPLOY) must carry everything the board imports or opens.
A file missing from the board is an ImportError at boot, not something a desktop test sees."""
import ast
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from portal import DEPLOY  # noqa: E402

# Built into CircuitPython 10, frozen into the MatrixPortal M4 firmware, or in the board's /lib
ON_BOARD = {
    'binascii', 'board', 'digitalio', 'displayio', 'gc', 'json', 'microcontroller', 'os',
    'supervisor', 'sys', 'time', 'traceback', 'watchdog',
    'adafruit_bitmap_font', 'adafruit_debouncer', 'adafruit_display_text', 'adafruit_matrixportal',
    'adafruit_portalbase',
}
BOARD_MODULES = [p for p in DEPLOY if p.endswith('.py')]


def source(path):
    with open(os.path.join(ROOT, path)) as f:
        return f.read()


def test_deploy_files_exist():
    missing = [p for p in DEPLOY if not os.path.exists(os.path.join(ROOT, p))]
    assert not missing


@pytest.mark.parametrize('module', BOARD_MODULES)
def test_imports_resolve_on_board(module):
    names = set()
    for node in ast.walk(ast.parse(source(module))):
        if isinstance(node, ast.Import):
            names.update(a.name.split('.')[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module.split('.')[0])
    unresolved = sorted(n for n in names if n not in ON_BOARD and n + '.py' not in DEPLOY)
    assert not unresolved, '%s imports %s: add to DEPLOY or ON_BOARD' % (module, unresolved)


@pytest.mark.parametrize('module', BOARD_MODULES)
def test_assets_deployed(module):
    assets = set(re.findall(r"'([\w./-]+\.(?:bmp|bdf))'", source(module)))
    missing = sorted(a for a in assets if a not in DEPLOY)
    assert not missing, '%s references %s, which deploy would not copy' % (module, missing)


def test_desktop_only_files_not_deployed():
    assert not [p for p in DEPLOY if p.startswith(('test_', 'tools/', 'simulate_', 'generate_'))]
