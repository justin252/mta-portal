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



# Newer icons use exact LED levels (0, 85, 170, 255): at bit depth 2 the matrix keeps only
# the top 2 bits per channel, so these render on the board exactly as designed.
CLOUD = (170, 170, 170)
RAIN_BLUE = (0, 85, 255)
LIGHT_BLUE = (85, 170, 255)
SNOW_WHITE = (255, 255, 255)
SUN_YELLOW = (255, 200, 0)  # same as generate_sun
MOON = (255, 255, 170)
STAR = (170, 170, 255)


def rain_cloud(draw, color):
    """The cloud shape rain/snow/storm use, upper part of the icon."""
    draw.ellipse([CX - 6, CY - 6, CX + 2, CY + 1], fill=color)
    draw.ellipse([CX - 2, CY - 8, CX + 7, CY], fill=color)
    draw.rectangle([CX - 5, CY - 2, CX + 6, CY + 1], fill=color)


def small_cloud(draw, color, dx=0, dy=0):
    """A smaller cloud for the partly-cloudy icons, lower left."""
    draw.ellipse([1 + dx, 15 + dy, 8 + dx, 22 + dy], fill=color)
    draw.ellipse([5 + dx, 13 + dy, 13 + dx, 21 + dy], fill=color)
    draw.rectangle([2 + dx, 18 + dy, 12 + dx, 22 + dy], fill=color)


def crescent(img, cx, cy, r, cut_dx, cut_dy, color):
    """Disc of radius r minus the same disc shifted by (cut_dx, cut_dy)."""
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            inside = (x - cx) ** 2 + (y - cy) ** 2 <= r * r + r
            cut = (x - cx - cut_dx) ** 2 + (y - cy - cut_dy) ** 2 <= r * r + r
            if inside and not cut and 0 <= x < 16 and 0 <= y < HEIGHT:
                img.putpixel((x, y), color)


def star(img, x, y, color, big=False):
    img.putpixel((x, y), color)
    if big:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            img.putpixel((x + dx, y + dy), color)


def generate_moon():
    img = make_canvas()
    crescent(img, 7, 17, 6, 3, -3, MOON)
    star(img, 13, 9, SNOW_WHITE, big=True)
    star(img, 14, 20, STAR)
    star(img, 2, 8, STAR)
    save(img, 'weather-moon.bmp')


def generate_partly():
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    sx, sy = 10, 11
    draw.ellipse([sx - 3, sy - 3, sx + 3, sy + 3], fill=SUN_YELLOW)
    for dx, dy in ((0, -1), (1, 0), (1, -1), (-1, -1), (-1, 0)):
        dist = 4 if dx and dy else 5
        img.putpixel((sx + dx * dist, sy + dy * dist), SUN_YELLOW)
    small_cloud(draw, CLOUD, dy=2)
    save(img, 'weather-partly.bmp')


def generate_partly_night():
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    crescent(img, 9, 11, 5, 3, -2, MOON)
    star(img, 14, 6, SNOW_WHITE)
    star(img, 2, 7, STAR)
    small_cloud(draw, CLOUD, dy=2)
    save(img, 'weather-partly-night.bmp')


def generate_drizzle():
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    rain_cloud(draw, CLOUD)
    for x_off, y_off in ((-3, 4), (3, 5), (0, 8)):  # sparse, light
        img.putpixel((CX + x_off, CY + y_off), LIGHT_BLUE)
    save(img, 'weather-drizzle.bmp')


def generate_showers():
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    rain_cloud(draw, CLOUD)
    # Slanted streaks, two staggered rows: heavier than rain's dots
    for x0, y0 in ((5, 19), (9, 19), (13, 19), (7, 23), (11, 23)):
        for i in range(3):
            img.putpixel((x0 - i, y0 + i), RAIN_BLUE)
    save(img, 'weather-showers.bmp')


def generate_sleet():
    img = make_canvas()
    draw = ImageDraw.Draw(img)
    rain_cloud(draw, CLOUD)
    for x, y in ((4, 20), (10, 20), (7, 24), (13, 24)):  # drops: 2px tall
        img.putpixel((x, y), RAIN_BLUE)
        img.putpixel((x, y + 1), RAIN_BLUE)
    for x, y in ((7, 20), (13, 20), (4, 24), (10, 24)):  # flakes: small crosses
        star(img, x, y + 1, SNOW_WHITE, big=False)
    save(img, 'weather-sleet.bmp')


if __name__ == '__main__':
    generate_sun()
    generate_cloud()
    generate_rain()
    generate_snow()
    generate_storm()
    generate_fog()
    generate_moon()
    generate_partly()
    generate_partly_night()
    generate_drizzle()
    generate_showers()
    generate_sleet()
