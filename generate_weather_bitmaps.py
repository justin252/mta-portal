#!/usr/bin/env python3
"""Generate weather icon bitmaps for the LED matrix (64x32, icon in left 18px)."""
from PIL import Image, ImageDraw

WIDTH, HEIGHT = 64, 32
CX, CY = 8, 16  # icon center, same as train circle


def save(img, filename):
    img.save(filename, format='BMP')
    print("Generated %s" % filename)


def make_canvas():
    return Image.new('RGB', (WIDTH, HEIGHT), (0, 0, 0))


def generate_sun():
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    yellow = (255, 200, 0)
    # Sun circle
    draw.ellipse([CX - 4, CY - 4, CX + 4, CY + 4], fill=yellow)
    # Rays (8 directions)
    for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
        for dist in [6, 7]:
            px, py = CX + dx * dist, CY + dy * dist
            if 0 <= px < WIDTH and 0 <= py < HEIGHT:
                img.putpixel((px, py), yellow)
    save(img, 'weather-sun.bmp')


def generate_cloud():
    img = make_canvas()
    gray = (180, 180, 180)
    # Cloud blob — two overlapping ellipses
    draw = ImageDraw.Draw(img)
    draw.ellipse([CX - 6, CY - 3, CX + 2, CY + 4], fill=gray)
    draw.ellipse([CX - 2, CY - 5, CX + 7, CY + 3], fill=gray)
    # Flat bottom
    draw.rectangle([CX - 5, CY + 1, CX + 6, CY + 4], fill=gray)
    save(img, 'weather-cloud.bmp')


def generate_rain():
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    gray = (140, 140, 140)
    blue = (50, 120, 255)
    # Darker cloud (rainy)
    draw.ellipse([CX - 6, CY - 6, CX + 2, CY + 1], fill=gray)
    draw.ellipse([CX - 2, CY - 8, CX + 7, CY], fill=gray)
    draw.rectangle([CX - 5, CY - 2, CX + 6, CY + 1], fill=gray)
    # Rain drops
    for x_off in [-4, 0, 4]:
        for y_off in [4, 7]:
            px, py = CX + x_off, CY + y_off
            if 0 <= py < HEIGHT:
                img.putpixel((px, py), blue)
    save(img, 'weather-rain.bmp')


def generate_snow():
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    gray = (140, 140, 140)
    white = (220, 220, 255)
    # Cloud
    draw.ellipse([CX - 6, CY - 6, CX + 2, CY + 1], fill=gray)
    draw.ellipse([CX - 2, CY - 8, CX + 7, CY], fill=gray)
    draw.rectangle([CX - 5, CY - 2, CX + 6, CY + 1], fill=gray)
    # Snowflakes (dots in a scattered pattern)
    for x_off, y_off in [(-3, 4), (1, 5), (5, 4), (-1, 7), (3, 8), (-4, 9)]:
        px, py = CX + x_off, CY + y_off
        if 0 <= py < HEIGHT:
            img.putpixel((px, py), white)
    save(img, 'weather-snow.bmp')


def generate_storm():
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    dark = (100, 100, 100)
    yellow = (255, 255, 0)
    # Dark cloud
    draw.ellipse([CX - 6, CY - 6, CX + 2, CY + 1], fill=dark)
    draw.ellipse([CX - 2, CY - 8, CX + 7, CY], fill=dark)
    draw.rectangle([CX - 5, CY - 2, CX + 6, CY + 1], fill=dark)
    # Lightning bolt
    bolt = [(CX + 1, CY + 2), (CX - 1, CY + 5), (CX + 1, CY + 5),
            (CX - 2, CY + 9), (CX + 2, CY + 5), (CX, CY + 5), (CX + 2, CY + 2)]
    draw.polygon(bolt, fill=yellow)
    save(img, 'weather-storm.bmp')


def generate_fog():
    img = make_canvas()
    gray_light = (150, 150, 150)
    gray_dark = (100, 100, 100)
    # Horizontal fog lines
    for y_off, color in [(-4, gray_light), (-1, gray_dark), (2, gray_light), (5, gray_dark)]:
        for x in range(CX - 6, CX + 7):
            py = CY + y_off
            if 0 <= py < HEIGHT:
                img.putpixel((x, py), color)
    save(img, 'weather-fog.bmp')


if __name__ == '__main__':
    generate_sun()
    generate_cloud()
    generate_rain()
    generate_snow()
    generate_storm()
    generate_fog()
