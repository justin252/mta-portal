#!/usr/bin/env python3
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 64, 32
CIRCLE_X, CIRCLE_Y = 8, 16
CIRCLE_RADIUS = 7
FONT_SIZE = 10
FONT_PATH = "/System/Library/Fonts/Helvetica.ttc"
LETTER_COLOR = (0, 0, 0)

TRAINS = {
    'G': {'color': (108, 190, 69), 'file': 'g-dashboard.bmp'},
    'L': {'color': (167, 169, 172), 'file': 'l-dashboard.bmp'},
}
TRAIN_ART_FILE = 'train.bmp'


def create_train_bitmap(letter, color, filename):
    img = Image.new('RGB', (WIDTH, HEIGHT), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.ellipse(
        [CIRCLE_X - CIRCLE_RADIUS, CIRCLE_Y - CIRCLE_RADIUS,
         CIRCLE_X + CIRCLE_RADIUS, CIRCLE_Y + CIRCLE_RADIUS],
        fill=color, outline=color,
    )

    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

    # Render at origin to find actual pixel bounds (textbbox includes advance width)
    tmp = Image.new('1', (WIDTH, HEIGHT), 0)
    ImageDraw.Draw(tmp).text((0, 0), letter, fill=1, font=font)
    xs = [x for y in range(HEIGHT) for x in range(WIDTH) if tmp.getpixel((x, y))]
    ys = [y for y in range(HEIGHT) for x in range(WIDTH) if tmp.getpixel((x, y))]
    px_cx = (min(xs) + max(xs)) / 2
    px_cy = (min(ys) + max(ys)) / 2
    text_x = round(CIRCLE_X - px_cx)
    text_y = round(CIRCLE_Y - px_cy)

    mask = Image.new('1', (WIDTH, HEIGHT), 0)
    ImageDraw.Draw(mask).text((text_x, text_y), letter, fill=1, font=font)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if mask.getpixel((x, y)):
                img.putpixel((x, y), LETTER_COLOR)

    img.save(filename, format='BMP')
    print(f"Generated {filename}")


def create_train_art(filename):
    """Draw a 64x32 side-view R160-style subway car."""
    img = Image.new('RGB', (WIDTH, HEIGHT), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Colors
    silver = (160, 165, 170)
    dark_silver = (100, 105, 110)
    window_blue = (20, 30, 50)
    wheel_gray = (80, 80, 80)
    rail_brown = (90, 70, 50)
    highlight = (190, 195, 200)

    # Track / rails (bottom rows)
    draw.line([(0, 29), (63, 29)], fill=rail_brown)
    draw.line([(0, 30), (63, 30)], fill=(70, 55, 40))
    for tx in range(2, 64, 8):
        draw.line([(tx, 29), (tx, 31)], fill=(60, 45, 35))

    # Car body — shorter, pushed down to make roof space
    car_top = 14
    car_bot = 26
    car_left = 3
    car_right = 60

    draw.rectangle([car_left, car_top, car_right, car_bot], fill=silver)
    draw.line([(car_left + 1, car_top), (car_right - 1, car_top)], fill=highlight)
    draw.line([(car_left, car_top + 1), (car_right, car_top + 1)], fill=highlight)
    draw.line([(car_left, car_bot), (car_right, car_bot)], fill=dark_silver)

    # Windows + center door
    win_top = 17
    win_bot = 22
    draw.rectangle([7, win_top, 27, win_bot], fill=window_blue)
    draw.line([(7, win_top), (27, win_top)], fill=(40, 50, 70))
    draw.rectangle([35, win_top, 55, win_bot], fill=window_blue)
    draw.line([(35, win_top), (55, win_top)], fill=(40, 50, 70))

    door_left = 29
    door_right = 33
    door_top = 16
    door_bot = car_bot - 1
    draw.rectangle([door_left, door_top, door_right, door_bot], fill=window_blue)
    draw.line([(31, door_top), (31, door_bot)], fill=(30, 40, 60))

    # Passenger heads in windows
    head_color = (180, 155, 120)
    for hx in [11, 17, 23]:
        draw.rectangle([hx, 19, hx + 1, 20], fill=head_color)
    for hx in [39, 46, 52]:
        draw.rectangle([hx, 19, hx + 1, 20], fill=head_color)

    # --- Rooftop disco scene ---
    skin = (220, 190, 140)
    pants = (60, 60, 100)
    roof_y = car_top - 1  # y=13, surface of roof

    # Disco ball hanging from above — 2 pink, 2 cyan, yellow center
    draw.line([(31, 0), (31, roof_y - 9)], fill=(100, 100, 100))  # string
    disco_pink = (255, 50, 150)
    disco_cyan = (50, 200, 255)
    disco_yellow = (255, 255, 100)
    draw.point((31, roof_y - 8), fill=disco_cyan)       # top
    draw.point((30, roof_y - 7), fill=disco_pink)       # left
    draw.point((31, roof_y - 7), fill=disco_yellow)     # center
    draw.point((32, roof_y - 7), fill=disco_cyan)       # right
    draw.point((31, roof_y - 6), fill=disco_pink)       # bottom

    # Left dancer (Uma) — red dress, arms out twist pose
    uma_dress = (220, 40, 40)
    ux = 26
    draw.rectangle([ux, roof_y - 6, ux + 1, roof_y - 5], fill=skin)      # head 2x2
    draw.rectangle([ux, roof_y - 4, ux + 1, roof_y - 2], fill=uma_dress) # body 2x3
    draw.point((ux - 1, roof_y - 4), fill=skin)     # L arm up
    draw.point((ux - 2, roof_y - 3), fill=skin)     # L arm out
    draw.point((ux + 2, roof_y - 3), fill=skin)     # R arm out
    draw.point((ux + 3, roof_y - 4), fill=skin)     # R arm up
    draw.point((ux - 1, roof_y - 1), fill=pants)    # L leg
    draw.point((ux + 2, roof_y - 1), fill=pants)    # R leg

    # Right dancer (Travolta) — white suit, arms out
    travolta_suit = (200, 200, 210)
    tx = 36
    draw.rectangle([tx, roof_y - 6, tx + 1, roof_y - 5], fill=skin)          # head 2x2
    draw.rectangle([tx, roof_y - 4, tx + 1, roof_y - 2], fill=travolta_suit) # body 2x3
    draw.point((tx + 2, roof_y - 4), fill=skin)     # R arm out
    draw.point((tx + 3, roof_y - 3), fill=skin)     # R arm extended
    draw.point((tx - 1, roof_y - 3), fill=skin)     # L arm out
    draw.point((tx - 2, roof_y - 2), fill=skin)     # L arm down
    draw.point((tx - 1, roof_y - 1), fill=pants)    # L leg
    draw.point((tx + 2, roof_y - 1), fill=pants)    # R leg

    # Lawn chair guy — back of train (right side)
    chair_color = (180, 100, 40)
    shirt = (80, 130, 180)
    # Chair: headrest, backrest, seat, footrest, legs
    draw.line([(47, roof_y - 5), (48, roof_y - 4)], fill=chair_color)
    draw.line([(48, roof_y - 4), (50, roof_y - 1)], fill=chair_color)
    draw.line([(50, roof_y - 1), (57, roof_y - 1)], fill=chair_color)
    draw.line([(57, roof_y - 1), (59, roof_y - 2)], fill=chair_color)
    draw.line([(51, roof_y - 1), (51, roof_y)], fill=chair_color)
    draw.line([(56, roof_y - 1), (56, roof_y)], fill=chair_color)
    # Person
    draw.rectangle([48, roof_y - 6, 49, roof_y - 5], fill=skin)   # head 2x2
    draw.point((49, roof_y - 4), fill=shirt)                       # neck
    draw.line([(50, roof_y - 4), (50, roof_y - 3)], fill=shirt)   # torso angled
    draw.line([(51, roof_y - 3), (54, roof_y - 3)], fill=shirt)   # torso flat
    draw.point((53, roof_y - 4), fill=skin)                        # arm on body
    draw.line([(55, roof_y - 3), (58, roof_y - 3)], fill=pants)   # legs
    draw.point((59, roof_y - 3), fill=skin)                        # feet

    # Wheels / trucks
    wheel_positions = [(10, 28), (18, 28), (44, 28), (52, 28)]
    for wx, wy in wheel_positions:
        draw.ellipse([wx - 2, wy - 2, wx + 2, wy + 2], fill=wheel_gray)
        draw.point((wx, wy), fill=(50, 50, 50))

    draw.line([(12, 27), (16, 27)], fill=dark_silver)
    draw.line([(20, 27), (42, 27)], fill=dark_silver)
    draw.line([(46, 27), (50, 27)], fill=dark_silver)

    # Couplers
    draw.rectangle([0, 22, car_left - 1, 24], fill=dark_silver)
    draw.rectangle([car_right + 1, 22, 63, 24], fill=dark_silver)

    img.save(filename, format='BMP')
    print(f"Generated {filename}")


if __name__ == '__main__':
    for letter, cfg in TRAINS.items():
        create_train_bitmap(letter, cfg['color'], cfg['file'])
    create_train_art(TRAIN_ART_FILE)
