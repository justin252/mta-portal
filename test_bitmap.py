import os
from PIL import Image
import pytest

BMP_PATH = os.path.join(os.path.dirname(__file__), "l-dashboard.bmp")
L_COLOR = (167, 169, 172)
BLACK = (0, 0, 0)


@pytest.fixture
def img():
    return Image.open(BMP_PATH)


def test_dimensions(img):
    assert img.size == (64, 32)


def test_no_divider(img):
    for x in range(64):
        assert img.getpixel((x, 15)) == BLACK
        assert img.getpixel((x, 16)) == BLACK


def test_top_circle_present(img):
    assert img.getpixel((8, 0)) == L_COLOR
    assert img.getpixel((8, 14)) == L_COLOR


def test_bottom_circle_present(img):
    assert img.getpixel((8, 17)) == L_COLOR
    assert img.getpixel((8, 31)) == L_COLOR


def test_l_stroke_1px_top(img):
    # Vertical bar at x=6 is black
    assert img.getpixel((6, 5)) == BLACK
    # x=7 should NOT be black (1px stroke, not 2px)
    assert img.getpixel((7, 5)) == L_COLOR


def test_l_stroke_1px_bottom(img):
    assert img.getpixel((6, 22)) == BLACK
    assert img.getpixel((7, 22)) == L_COLOR
