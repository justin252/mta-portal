#!/usr/bin/env python3
"""portal - capture what the MatrixPortal is actually showing and diff it against the simulator.

Usage:
  tools/portal.py verify [-o DIR] [--port PORT] [--from-file CAPTURE]   exit 1 on mismatch
  tools/portal.py shot   [-o DIR] [--port PORT] [--from-file CAPTURE]   save device.png, state.json

The board side is diag.py: sending 's' on the USB console makes it print the RGB565
framebuffer plus the state (screen, label texts, bitmap) that produced it. verify
re-renders that state with simulate_display.py and compares pixel by pixel.
"""

import argparse
import glob
import json
import os
import sys
import time

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

ADAFRUIT_VID = 0x239A
SCALE = 10
TEXT_X = 18  # labels start here; columns left of it are the line/weather bitmap
SHIFTS = range(-2, 3)


def die(msg, hint=None):
    print('error: %s' % msg, file=sys.stderr)
    if hint:
        print('  -> %s' % hint, file=sys.stderr)
    sys.exit(1)


def say(msg):
    print(msg, file=sys.stderr)


# --- pure helpers (tested in test_portal.py) ---

def to_565(rgb):
    """RGB888 tuple -> RGB565 int, truncating like displayio's ColorConverter."""
    r, g, b = rgb
    return (r >> 3) << 11 | (g >> 2) << 5 | b >> 3


def from_565(v):
    """RGB565 int -> RGB888 tuple, replicating high bits so full scale stays full scale."""
    r, g, b = v >> 11, (v >> 5) & 0x3F, v & 0x1F
    return (r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2)


def parse_dump(lines):
    """[FB] capture lines -> (state dict, list of row bytes). Raises ValueError if incomplete."""
    state, rows = None, {}
    for line in lines:
        if line.startswith('[FB] BEGIN '):
            state, rows = json.loads(line[len('[FB] BEGIN '):]), {}
        elif line.startswith('[FB] ERR'):
            raise ValueError('device dump failed: %s' % line[len('[FB] ERR'):].strip())
        elif line == '[FB] END':
            break
        elif line.startswith('[FB] ') and state is not None:
            y, hexrow = line[len('[FB] '):].split(' ', 1)
            rows[int(y)] = bytes.fromhex(hexrow)
    if state is None:
        raise ValueError('no [FB] BEGIN line in capture')
    bad = [y for y in range(state['h']) if len(rows.get(y, b'')) != state['w'] * 2]
    if bad:
        raise ValueError('incomplete dump, bad or missing rows: %s' % bad[:5])
    return state, [rows[y] for y in range(state['h'])]


def decode_rgb565(rows):
    """Little-endian RGB565 rows -> [[v, ...], ...] indexed [y][x]."""
    return [[row[i] | row[i + 1] << 8 for i in range(0, len(row), 2)] for row in rows]


def render_expected(state):
    """Render the device-reported state with the simulator. Returns a 64x32 RGB image."""
    import simulate_display as sim
    return sim.render_screen(state)


def text_diffs(state):
    """Station names the board shows that differ from layout.py (labels the board never rewrites)."""
    import layout
    texts = state.get('texts', {})
    station = layout.STATIONS.get(state['screen'])
    if not station:
        return []
    return ['%s: device %r, layout %r' % (f, texts.get(f), station[f])
            for f in ('north', 'south') if texts.get(f) != station[f]]


def compare(device_px, expected_img, shift=0, x0=0):
    """Mismatches (x, y, device565, expected565) between device pixels and an image.

    shift moves the expected image down by `shift` rows (negative = up) within columns >= x0,
    so a label drawn 1px higher on the device matches at shift=-1.
    """
    w, h = expected_img.size
    exp = expected_img.load()
    out = []
    for y in range(h):
        for x in range(x0, w):
            sy = y - shift if x >= TEXT_X else y
            want = to_565(exp[x, sy]) if 0 <= sy < h else 0
            if device_px[y][x] != want:
                out.append((x, y, device_px[y][x], want))
    return out


def best_shift(device_px, expected_img):
    """Vertical label offset (device vs sim) that minimizes mismatches in the text area."""
    counts = {s: len(compare(device_px, expected_img, shift=s, x0=TEXT_X)) for s in SHIFTS}
    return min(counts, key=lambda s: (counts[s], abs(s))), counts


def device_image(device_px):
    h, w = len(device_px), len(device_px[0])
    img = Image.new('RGB', (w, h))
    img.putdata([from_565(v) for row in device_px for v in row])
    return img


def diff_image(device_px, mismatches):
    """Device image dimmed, mismatched pixels red, scaled up."""
    img = device_image(device_px).point(lambda c: c // 3)
    for x, y, _, _ in mismatches:
        img.putpixel((x, y), (255, 0, 0))
    return scaled(img)


def scaled(img):
    return img.resize((img.width * SCALE, img.height * SCALE), Image.NEAREST)


# --- serial ---

def find_port():
    from serial.tools import list_ports
    for p in list_ports.comports():
        if p.vid == ADAFRUIT_VID:
            return p.device
    ports = sorted(glob.glob('/dev/cu.usbmodem*'))
    return ports[0] if ports else None


class Console:
    """The board's USB serial console. Reopens itself when a reset drops the port."""

    def __init__(self, port=None, wait=0):
        self.port = port
        self.ser = None
        self.open(wait)

    def open(self, wait):
        import serial
        deadline = time.monotonic() + wait
        while True:
            port = self.port or find_port()
            if port:
                try:
                    # USB CDC ignores the baud rate, but 1200 reboots the board into its bootloader
                    self.ser = serial.Serial(port, 115200, timeout=0.5)
                    return
                except (OSError, serial.SerialException):
                    pass
            if time.monotonic() >= deadline:
                die('no MatrixPortal serial port found',
                    'plug the board in with a data cable, or pass --port')
            time.sleep(0.5)

    def send(self, data):
        self.ser.write(data)

    def readline(self):
        """Next line, or None after 0.5s of silence. Survives the board resetting."""
        import serial
        try:
            raw = self.ser.readline()
        except (OSError, serial.SerialException):
            say('(port dropped: board is resetting; reopening)')
            self.ser = None
            self.open(wait=60)
            return None
        return raw.decode('utf-8', 'replace').rstrip('\r\n') or None

    def lines(self, seconds):
        """Yield lines for up to `seconds`."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            line = self.readline()
            if line is not None:
                yield line

    def dump(self):
        """Framebuffer dump lines."""
        self.ser.reset_input_buffer()
        self.send(b's')
        lines, halted = [], False
        for line in self.lines(20):
            if not line.startswith('[FB]'):
                halted = halted or 'Code done running' in line or line.startswith('>>>')
                continue
            lines.append(line)
            if line == '[FB] END' or line.startswith('[FB] ERR'):
                return lines
        die('no framebuffer dump within 20s',
            'board is halted or at the REPL; press reset' if halted else 'is diag.py deployed?')


# --- commands ---

def get_capture(args):
    if args.from_file:
        with open(args.from_file) as f:
            return [line.rstrip('\r\n') for line in f]
    return Console(args.port).dump()


def save_shot(lines, out_dir, keep_capture):
    try:
        state, rows = parse_dump(lines)
    except ValueError as e:
        die(str(e), 'retry; if it persists, check the serial log for [FB] ERR')
    os.makedirs(out_dir, exist_ok=True)
    if keep_capture:
        with open(os.path.join(out_dir, 'capture.txt'), 'w') as f:
            f.write('\n'.join(lines) + '\n')
    device_px = decode_rgb565(rows)
    img = device_image(device_px)
    img.save(os.path.join(out_dir, 'device.png'))
    scaled(img).save(os.path.join(out_dir, 'device_x10.png'))
    with open(os.path.join(out_dir, 'state.json'), 'w') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    return state, device_px


def cmd_shot(args):
    save_shot(get_capture(args), args.output, not args.from_file)
    for name in ('device.png', 'device_x10.png', 'state.json'):
        print(os.path.join(args.output, name))
    return 0


def verify_capture(lines, out_dir, keep_capture=True):
    """Diff one capture against the simulator; writes PNGs to out_dir. Returns mismatch count."""
    state, device_px = save_shot(lines, out_dir, keep_capture)
    expected = render_expected(state)
    expected.save(os.path.join(out_dir, 'sim.png'))
    scaled(expected).save(os.path.join(out_dir, 'sim_x10.png'))
    mismatches = compare(device_px, expected)
    diff_image(device_px, mismatches).save(os.path.join(out_dir, 'diff.png'))
    print('screen %s (src %s): %s' % (state['screen'], state.get('src'), out_dir))
    for d in text_diffs(state):
        print('text differs: %s' % d)
    if not mismatches:
        print('match')
        return 0
    x, y, got, want = mismatches[0]
    print('%d mismatches (first at %d,%d: device #%02x%02x%02x, sim #%02x%02x%02x)'
          % ((len(mismatches), x, y) + from_565(got) + from_565(want)))
    shift, counts = best_shift(device_px, expected)
    print('best label shift %+d (text-area mismatches by shift: %s)'
          % (shift, ', '.join('%+d:%d' % (s, counts[s]) for s in SHIFTS)))
    return len(mismatches)


def cmd_verify(args):
    return 1 if verify_capture(get_capture(args), args.output, not args.from_file) else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='portal', description='Capture the MatrixPortal framebuffer and diff it against the simulator.',
        epilog='examples:\n  tools/portal.py verify\n  tools/portal.py shot -o out/l-screen',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', metavar='command')

    def add(name, fn, help_text):
        p = sub.add_parser(name, help=help_text, description=help_text)
        p.add_argument('--port', help='serial port (default: autodetect Adafruit USB VID)')
        p.set_defaults(fn=fn)
        return p

    for name, fn, help_text in (
            ('shot', cmd_shot, 'save what the board is showing (device.png, state.json)'),
            ('verify', cmd_verify, 'diff the board framebuffer against the simulator; exit 1 on mismatch')):
        p = add(name, fn, help_text)
        p.add_argument('-o', '--output', default=os.path.join(ROOT, 'out'), help='output dir (default: out/)')
        p.add_argument('--from-file', metavar='CAPTURE', help='use a saved capture.txt instead of the board')

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help(sys.stderr)
        return 2
    try:
        return args.fn(args)
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    sys.exit(main())
