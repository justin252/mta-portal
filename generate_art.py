#!/usr/bin/env python3
"""Generate the full-screen 64x32 pieces for art mode (art-*.bmp).

Colors use exact LED levels (0, 85, 170, 255): at bit depth 2 the matrix keeps only the top
2 bits of each channel, so anything with every channel below 64 is black on the board.
"""
from PIL import Image, ImageDraw

WIDTH, HEIGHT = 64, 32

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
SILVER = (170, 170, 170)
GRAY = (85, 85, 85)
NAVY = (0, 0, 85)
BLUE = (0, 0, 170)
SKY_BLUE = (85, 170, 255)
CYAN = (0, 255, 255)
TEAL = (0, 85, 170)
PURPLE = (85, 0, 85)
MAGENTA = (170, 0, 85)
PINK = (255, 0, 170)
RED = (255, 0, 0)
ORANGE = (255, 170, 0)
BROWN = (170, 85, 0)
OLIVE = (85, 85, 0)
YELLOW = (255, 255, 85)
PALE_YELLOW = (255, 255, 170)
SKIN = (255, 170, 85)
GREEN = (0, 170, 0)
LIGHT_GREEN = (85, 255, 85)
RAT_BROWN = (170, 85, 85)
LAVENDER = (170, 170, 255)


def canvas(color=BLACK):
    return Image.new('RGB', (WIDTH, HEIGHT), color)


def save(img, filename):
    img.save(filename, format='BMP')
    print('Generated %s' % filename)


def put(img, x, y, color):
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        img.putpixel((x, y), color)


def lit(x, y, seed):
    """Deterministic pseudo-random 0..99 per cell, so window patterns never change."""
    return (x * 73856093 ^ y * 19349663 ^ seed * 83492791) % 100


def create_train(filename='art-train.bmp'):
    """Side view of an R160-style subway car with a disco party on the roof."""
    img = canvas()
    draw = ImageDraw.Draw(img)

    # Track: rails with ties
    draw.line([(0, 29), (63, 29)], fill=BROWN)
    draw.line([(0, 30), (63, 30)], fill=BROWN)
    for tx in range(2, 64, 8):
        draw.line([(tx, 29), (tx, 31)], fill=OLIVE)

    # Car body
    car_top, car_bot, car_left, car_right = 14, 26, 3, 60
    draw.rectangle([car_left, car_top, car_right, car_bot], fill=SILVER)
    draw.line([(car_left + 1, car_top), (car_right - 1, car_top)], fill=WHITE)
    draw.line([(car_left, car_top + 1), (car_right, car_top + 1)], fill=WHITE)
    draw.line([(car_left, car_bot), (car_right, car_bot)], fill=GRAY)

    # Windows with a glare line, and the center door
    for x0, x1 in ((7, 27), (35, 55)):
        draw.rectangle([x0, 17, x1, 22], fill=TEAL)
        draw.line([(x0, 17), (x1, 17)], fill=SKY_BLUE)
    draw.rectangle([29, 16, 33, car_bot - 1], fill=BLUE)
    draw.line([(31, 16), (31, car_bot - 1)], fill=SKY_BLUE)

    # Passengers
    for hx in (11, 17, 23, 39, 46, 52):
        draw.rectangle([hx, 19, hx + 1, 20], fill=SKIN)

    # Rooftop disco: ball on a string, two dancers, a guy in a lawn chair
    roof_y = car_top - 1
    draw.line([(31, 0), (31, roof_y - 9)], fill=GRAY)
    for (dx, dy), color in (((0, -8), CYAN), ((-1, -7), PINK), ((0, -7), YELLOW),
                            ((1, -7), CYAN), ((0, -6), PINK)):
        put(img, 31 + dx, roof_y + dy, color)

    ux = 26  # dancer in a red dress, arms up
    draw.rectangle([ux, roof_y - 6, ux + 1, roof_y - 5], fill=SKIN)
    draw.rectangle([ux, roof_y - 4, ux + 1, roof_y - 2], fill=RED)
    for dx, dy in ((-1, -4), (-2, -3), (2, -3), (3, -4)):
        put(img, ux + dx, roof_y + dy, SKIN)
    put(img, ux - 1, roof_y - 1, BLUE)
    put(img, ux + 2, roof_y - 1, BLUE)

    tx = 36  # dancer in a white suit, one arm out
    draw.rectangle([tx, roof_y - 6, tx + 1, roof_y - 5], fill=SKIN)
    draw.rectangle([tx, roof_y - 4, tx + 1, roof_y - 2], fill=WHITE)
    for dx, dy in ((2, -4), (3, -3), (-1, -3), (-2, -2)):
        put(img, tx + dx, roof_y + dy, SKIN)
    put(img, tx - 1, roof_y - 1, BLUE)
    put(img, tx + 2, roof_y - 1, BLUE)

    for a, b in (((47, -5), (48, -4)), ((48, -4), (50, -1)), ((50, -1), (57, -1)),
                 ((57, -1), (59, -2)), ((51, -1), (51, 0)), ((56, -1), (56, 0))):
        draw.line([(a[0], roof_y + a[1]), (b[0], roof_y + b[1])], fill=BROWN)
    draw.rectangle([48, roof_y - 6, 49, roof_y - 5], fill=SKIN)
    put(img, 49, roof_y - 4, SKY_BLUE)
    draw.line([(50, roof_y - 4), (50, roof_y - 3)], fill=SKY_BLUE)
    draw.line([(51, roof_y - 3), (54, roof_y - 3)], fill=SKY_BLUE)
    put(img, 53, roof_y - 4, SKIN)
    draw.line([(55, roof_y - 3), (58, roof_y - 3)], fill=BLUE)
    put(img, 59, roof_y - 3, SKIN)

    # Wheels with bright hubs, undercarriage, couplers
    for wx in (10, 18, 44, 52):
        draw.ellipse([wx - 2, 26, wx + 2, 30], fill=GRAY)
        put(img, wx, 28, SILVER)
    for x0, x1 in ((12, 16), (20, 42), (46, 50)):
        draw.line([(x0, 27), (x1, 27)], fill=GRAY)
    draw.rectangle([0, 22, car_left - 1, 24], fill=GRAY)
    draw.rectangle([car_right + 1, 22, 63, 24], fill=GRAY)
    save(img, filename)


def create_skyline(filename='art-skyline.bmp'):
    """Manhattan at night: Empire State and Chrysler among lit towers, moon and stars."""
    img = canvas()
    draw = ImageDraw.Draw(img)

    for x, y, color in ((3, 2, LAVENDER), (9, 6, WHITE), (14, 1, LAVENDER), (29, 3, LAVENDER),
                        (36, 7, WHITE), (47, 2, LAVENDER), (61, 9, LAVENDER), (34, 1, LAVENDER)):
        put(img, x, y, color)
    # Moon: crescent, upper right
    for y in range(1, 10):
        for x in range(50, 60):
            if (x - 55) ** 2 + (y - 5) ** 2 <= 17 and not (x - 57) ** 2 + (y - 4) ** 2 <= 14:
                put(img, x, y, PALE_YELLOW)

    # (left, right, top) of the plain towers, back to front
    towers = ((0, 6, 20), (7, 13, 15), (28, 34, 18), (35, 38, 22), (47, 53, 13), (54, 59, 19),
              (60, 63, 16), (13, 16, 23))
    for x0, x1, top in towers:
        draw.rectangle([x0, top, x1, 31], fill=NAVY)
        for y in range(top + 2, 31, 2):
            for x in range(x0 + 1, x1, 2):
                if lit(x, y, 1) < 40:
                    put(img, x, y, ORANGE if lit(x, y, 2) < 70 else YELLOW)

    # Empire State: stepped setbacks, lit crown, antenna with a red light
    for x0, x1, top in ((17, 27, 12), (19, 25, 8), (21, 23, 5)):
        draw.rectangle([x0, top, x1, 31], fill=NAVY)
    draw.rectangle([21, 5, 23, 8], fill=PALE_YELLOW)
    draw.line([(22, 1), (22, 4)], fill=SILVER)
    put(img, 22, 0, RED)
    for y in range(14, 31, 2):
        for x in range(18, 27, 2):
            if lit(x, y, 3) < 45:
                put(img, x, y, YELLOW)

    # Chrysler: tower, then the silver crown of stacked arches and a spire
    draw.rectangle([40, 14, 46, 31], fill=NAVY)
    for i, (x0, x1) in enumerate(((40, 46), (41, 45), (42, 44))):
        y = 13 - i * 2
        draw.rectangle([x0, y - 1, x1, y], fill=SILVER)
        put(img, (x0 + x1) // 2, y - 1, WHITE)
    draw.line([(43, 3), (43, 7)], fill=WHITE)
    for y in range(16, 31, 2):
        for x in range(41, 46, 2):
            if lit(x, y, 4) < 45:
                put(img, x, y, ORANGE)
    save(img, filename)


def create_bridge(filename='art-bridge.bmp'):
    """Williamsburg Bridge at dusk: steel towers and cables cut out of the sky, river below."""
    img = canvas()
    draw = ImageDraw.Draw(img)

    # Dusk sky bands, sun setting on the horizon
    for y0, y1, color in ((0, 4, NAVY), (5, 8, PURPLE), (9, 12, MAGENTA), (13, 16, BROWN), (17, 19, ORANGE)):
        draw.rectangle([0, y0, 63, y1], fill=color)
    draw.ellipse([26, 8, 34, 16], fill=YELLOW)
    # River with the sun's reflection
    draw.rectangle([0, 20, 63, 31], fill=NAVY)
    for y, half in ((21, 5), (23, 4), (25, 3), (27, 2), (29, 1)):
        draw.line([(30 - half, y), (30 + half, y)], fill=ORANGE if y < 25 else BROWN)
    for y in (22, 26, 30):
        for x in range(2, 64, 9):
            draw.line([(x, y), (x + 2, y)], fill=TEAL)

    # Bridge in silhouette (black = LEDs off): deck, two lattice towers, cables, hangers
    draw.rectangle([0, 17, 63, 18], fill=BLACK)
    for tx in (12, 50):
        for x in (tx - 2, tx + 2):
            draw.line([(x, 3), (x, 31)], fill=BLACK)
        for y in range(3, 17, 4):
            draw.line([(tx - 2, y), (tx + 2, y + 4)], fill=BLACK)
            draw.line([(tx + 2, y), (tx - 2, y + 4)], fill=BLACK)
        draw.line([(tx - 2, 3), (tx + 2, 3)], fill=BLACK)
    # Main span cable sags between the tower tops; side spans run down to the deck
    for x in range(12, 51):
        t = (x - 31) / 19.0
        y = round(3 + 12 * (1 - t * t))
        put(img, x, y, BLACK)
        if x % 3 == 0:
            draw.line([(x, y), (x, 17)], fill=BLACK)
    for x0, x1 in ((0, 12), (50, 63)):
        for x in range(x0, x1 + 1):
            t = (x - x0) / float(x1 - x0)
            y = round(14 - 11 * t) if x0 == 0 else round(3 + 11 * t)
            put(img, x, y, BLACK)
    save(img, filename)


def create_rat(filename='art-rat.bmp'):
    """Pizza rat backing down the subway stairs, dragging a slice, under the green globe."""
    img = canvas()
    draw = ImageDraw.Draw(img)

    # Three wide steps down to the right: solid concrete, yellow safety nosing on each tread
    for x0, x1, y in ((0, 15, 10), (16, 31, 16), (32, 47, 22), (48, 63, 28)):
        draw.rectangle([x0, y, x1, 31], fill=GRAY)
        draw.line([(x0, y), (x1, y)], fill=YELLOW)

    # Green subway globe on the top landing
    draw.line([(6, 5), (6, 9)], fill=SILVER)
    draw.ellipse([3, 0, 9, 6], fill=GREEN)
    put(img, 5, 1, LIGHT_GREEN)
    put(img, 4, 2, LIGHT_GREEN)

    # The slice, crust up the stairs, tip hanging over the step edge into the rat's mouth
    draw.polygon([(17, 6), (21, 15), (33, 18)], fill=ORANGE)
    draw.line([(17, 6), (21, 15)], fill=BROWN)
    draw.line([(16, 7), (20, 15)], fill=BROWN)
    for x, y in ((21, 11), (25, 14), (21, 14)):
        put(img, x, y, RED)

    # Rat on the middle step, facing the slice: head left, tail trailing down the stairs
    draw.ellipse([37, 16, 45, 21], fill=RAT_BROWN)   # body
    draw.ellipse([33, 17, 38, 20], fill=RAT_BROWN)   # head
    put(img, 33, 18, PINK)                          # nose on the slice tip
    put(img, 36, 16, PINK)                          # ear
    put(img, 35, 18, WHITE)                         # eye
    for x in (38, 43):                              # feet on the tread
        put(img, x, 21, PINK)
    for x, y in ((46, 19), (47, 20), (48, 21), (49, 22), (50, 23), (51, 23), (52, 24)):
        put(img, x, y, PINK)                        # tail over the edge
    save(img, filename)


if __name__ == '__main__':
    create_train()
    create_skyline()
    create_bridge()
    create_rat()
