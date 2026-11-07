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


if __name__ == '__main__':
    for letter, cfg in TRAINS.items():
        create_train_bitmap(letter, cfg['color'], cfg['file'])
