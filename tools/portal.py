#!/usr/bin/env python3
"""portal - verify the MatrixPortal sign against reality.

Usage:
  tools/portal.py deploy  [--dry-run] [--reload]   copy changed files to CIRCUITPY, watch the boot
  tools/portal.py verify  [--all] [-o DIR]         board framebuffer vs simulator; exit 1 on mismatch
  tools/portal.py shot    [-o DIR]                 save what the board shows (device.png, state.json)
  tools/portal.py status                           board status JSON
  tools/portal.py logs    [--minutes N]            serial log with timestamps
  tools/portal.py inject  wifi|crash|hang          fault injection; exit 0 if the board recovers
  tools/portal.py soak    --minutes N              log, then summarize errors, resets, gaps, memory

The board side is diag.py: one-letter commands on the USB console make it dump the RGB565
framebuffer plus the state that produced it, report status, or inject a fault.
"""

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import sys
import time

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

ADAFRUIT_VID = 0x239A
SCALE = 10
TEXT_X = 18  # labels start here; columns left of it are the line/weather bitmap
SHIFTS = range(-2, 3)
SCREENS = ('L', 'G', 'weather', 'train_art')
DRIVES = ('/Volumes/CIRCUITPY', '/media/%s/CIRCUITPY' % os.getenv('USER', ''),
          '/run/media/%s/CIRCUITPY' % os.getenv('USER', ''))
# Everything the board runs, in copy order: code.py last, so the auto-reload its write
# triggers starts the new code with every dependency already in place
DEPLOY = (
    'fonts/tom-thumb.bdf', 'fonts/spleen-5x8.bdf',
    'l-dashboard.bmp', 'g-dashboard.bmp', 'train.bmp',
    'weather-sun.bmp', 'weather-cloud.bmp', 'weather-rain.bmp',
    'weather-snow.bmp', 'weather-storm.bmp', 'weather-fog.bmp',
    'layout.py', 'logic.py', 'recovery.py', 'weather.py', 'diag.py', 'safemode.py', 'app.py',
    'code.py',
)
MAX_DATA_GAP_S = 300  # soak fails if the board goes this long without a successful fetch
HALT_AFTER_S = 30     # "Code done running" with no reload this long after it = halted board
# CircuitPython sets the terminal title (OSC) and clears lines (CSI) inline with output
ESCAPES = re.compile(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-9;?]*[A-Za-z]')


def die(msg, hint=None):
    print('error: %s' % msg, file=sys.stderr)
    if hint:
        print('  -> %s' % hint, file=sys.stderr)
    sys.exit(1)


def say(msg):
    print(msg, file=sys.stderr)


# --- pure helpers (tested in test_portal.py) ---

def clean_line(raw):
    """Decoded serial line without terminal escape codes or line endings."""
    return ESCAPES.sub('', raw.decode('utf-8', 'replace')).rstrip('\r\n')


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


def summarize(log):
    """Soak verdict from (seconds, line) pairs. Returns (summary dict, list of failures)."""
    s = {'ok': 0, 'errors': {}, 'reconnects': 0, 'resets': [], 'crashes': [], 'boots': [],
         'unexplained_resets': [], 'weather_ok': 0, 'weather_failed': 0, 'halted': [],
         'mem': [], 'fetch_s': []}
    oks = []
    last_reset_t = None
    done_at = None  # time of the last "Code done running" not yet followed by a reload
    for t, line in log:
        if done_at is not None and t - done_at > HALT_AFTER_S:
            s['halted'].append('Code done running at %ss, no reload after it' % done_at)
            done_at = None
        if line.startswith('[OK]'):
            s['ok'] += 1
            oks.append(t)
            m = re.search(r' mem=(\d+)', line)
            if m:
                s['mem'].append(int(m.group(1)))
        elif line.startswith('[ERR]'):
            kind = line[len('[ERR] '):].split(':', 1)[0]
            s['errors'][kind] = s['errors'].get(kind, 0) + 1
        elif line.startswith('[RECONNECT] ok'):
            s['reconnects'] += 1
        elif line.startswith('[RESET]'):
            s['resets'].append(line)
            last_reset_t = t
        elif line.startswith('[CRASH]'):
            s['crashes'].append(line)
        elif line.startswith('[BOOT] '):
            # explained: a guarded crash reload, or a hard reset right after a policy [RESET];
            # any other hard reset is the watchdog, a power drop, or the reset button
            if 'run=STARTUP' in line and not (s['resets'] and t - last_reset_t < 60):
                s['unexplained_resets'].append('%ss: %s' % (t, line))
            s['boots'].append(line)
            done_at = None
        elif line.startswith('[WEATHER] failed'):
            s['weather_failed'] += 1
        elif line.startswith('[WEATHER]'):
            s['weather_ok'] += 1
        elif 'Code done running' in line:
            done_at = t
        elif line.startswith('soft reboot'):
            done_at = None
        m = re.search(r' t=([\d.]+)s', line)
        if m:
            s['fetch_s'].append(float(m.group(1)))
    start = log[0][0] if log else 0
    end = log[-1][0] if log else 0
    if done_at is not None and end - done_at > HALT_AFTER_S:
        s['halted'].append('Code done running at %ss, no reload after it' % done_at)
    edges = [start] + oks + [end]
    s['max_gap_s'] = round(max(b - a for a, b in zip(edges, edges[1:])), 1) if log else 0
    s['minutes'] = round((end - start) / 60, 1)
    failures = []
    if s['halted']:
        failures.append('board halted: %s' % s['halted'][0])
    if s['max_gap_s'] > MAX_DATA_GAP_S:
        failures.append('no fresh data for %ds (limit %ds)' % (s['max_gap_s'], MAX_DATA_GAP_S))
    if not s['ok']:
        failures.append('no successful fetch')
    if s['unexplained_resets']:
        failures.append('%d hard reset(s) with no logged cause (watchdog, power or button): %s'
                        % (len(s['unexplained_resets']), s['unexplained_resets'][0]))
    if s['crashes']:
        failures.append('%d crash(es), recovered but a bug: %s' % (len(s['crashes']), s['crashes'][0]))
    return s, failures


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
        return clean_line(raw) or None

    def lines(self, seconds):
        """Yield lines for up to `seconds`."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            line = self.readline()
            if line is not None:
                yield line

    def wait_for(self, prefix, seconds, echo=True):
        """First line starting with prefix within `seconds`, else None. Echoes other lines."""
        for line in self.lines(seconds):
            if line.startswith(prefix):
                return line
            if echo:
                say('  | ' + line)
        return None

    def status(self):
        for _ in range(2):  # a byte sent right after (re)opening the port can be lost: ask twice
            self.ser.reset_input_buffer()
            self.send(b'i')
            line = self.wait_for('[STATUS] ', 10, echo=False)  # a fetch can block the loop a few seconds
            if line:
                return json.loads(line[len('[STATUS] '):])
        die('no status reply', 'is the board halted or at the REPL? check `tools/portal.py logs`')

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


def goto(console, screen, tries=8):
    """Drive the board to a screen with serial commands. False if it never shows."""
    for _ in range(tries):
        st = console.status()
        if st['screen'] == screen:
            return True
        if screen == 'train_art' or st['view'] == 'train_art':
            console.send(b'a')
        elif screen == 'weather' and not st['weather_ok']:
            return False
        else:
            console.send(b'n')
        time.sleep(0.5)  # let the display refresh before looking again
    return False


def capture_screen(console, screen, out_dir, bitmap=None):
    """goto + dump + verify, retrying when the 2s cycle moves on first. True if it matched."""
    for _ in range(4):
        if not goto(console, screen):
            print('%s: never shown%s' % (out_dir, ' (no weather data yet)' if screen == 'weather' else ''))
            return False
        lines = console.dump()
        state = parse_dump(lines)[0]
        if state['screen'] == screen and (bitmap is None or state['bitmap'] == bitmap):
            return verify_capture(lines, out_dir) == 0
    print('%s: cycled away before every capture' % out_dir)
    return False


def cmd_verify(args):
    if args.from_file or not args.all:
        return 1 if verify_capture(get_capture(args), args.output, not args.from_file) else 0
    console = Console(args.port)
    failed = [s for s in SCREENS if not capture_screen(console, s, os.path.join(args.output, s))]
    if console.status()['view'] == 'train_art':
        console.send(b'a')  # leave the sign cycling
    total = len(SCREENS)
    print('verified %d/%d screens%s' % (total - len(failed), total,
                                        ', FAILED: ' + ', '.join(failed) if failed else ''))
    return 1 if failed else 0


def cmd_status(args):
    print(json.dumps(Console(args.port).status(), indent=2))
    return 0


def cmd_logs(args):
    console = Console(args.port)
    start = time.monotonic()
    for line in console.lines(args.minutes * 60 if args.minutes else 10 ** 9):
        print('%7.1f %s' % (time.monotonic() - start, line), flush=True)
    return 0


INJECT = {
    # fault: (command byte, log prefixes that must appear in order, seconds allowed)
    'wifi': (b'w', ('[INJECT] dropping WiFi', '[RECONNECT] ok', '[OK]'), 120),
    'crash': (b'x', ('[CRASH] RuntimeError: injected crash', '[BOOT] run=SUPERVISOR_RELOAD', '[OK]'), 120),
    # a watchdog reset is a hard reset: the port drops and the board boots from scratch
    'hang': (b'h', ('[INJECT] hanging', '[BOOT] run=STARTUP', '[OK]'), 120),
}


def cmd_inject(args):
    cmd, steps, seconds = INJECT[args.fault]
    console = Console(args.port)
    console.ser.reset_input_buffer()
    sent = time.monotonic()
    console.send(cmd)
    deadline = sent + seconds
    for step in steps:
        # the [BOOT] line can print before the port reopens after a hard reset: don't wait it out
        wait = 45 if step.startswith('[BOOT]') else deadline - time.monotonic()
        line = console.wait_for(step, max(0, min(wait, deadline - time.monotonic())))
        if line is None and step.startswith('[BOOT]'):
            st = console.status()
            want = step[len('[BOOT] run='):]
            if st['up'] <= time.monotonic() - sent and st['run'] == want:
                print('  rebooted %ds ago (run=%s)' % (st['up'], st['run']))
                continue
        if line is None:
            print('FAILED: no "%s" within %ds' % (step, seconds))
            return 1
        print('  ' + line)
    print('recovered from %s' % args.fault)
    return 0


def cmd_soak(args):
    console = Console(args.port)
    os.makedirs(args.output, exist_ok=True)
    path = os.path.join(args.output, 'soak-%s.log' % time.strftime('%Y%m%d-%H%M%S'))
    start = time.monotonic()
    log = []
    say('soaking for %g min, logging to %s' % (args.minutes, path))
    with open(path, 'w') as f:
        for line in console.lines(args.minutes * 60):
            t = round(time.monotonic() - start, 1)
            log.append((t, line))
            f.write('%7.1f %s\n' % (t, line))
            f.flush()
    summary, failures = summarize(log)
    mem, fetch = summary.pop('mem'), summary.pop('fetch_s')
    summary['mem_min_max'] = [min(mem), max(mem)] if mem else None
    summary['fetch_s_max'] = max(fetch) if fetch else None
    print(json.dumps(summary, indent=2))
    print('FAIL: ' + '; '.join(failures) if failures else 'PASS')
    return 1 if failures else 0


def find_drive(arg):
    for d in ([arg] if arg else DRIVES):
        if d and os.path.isdir(d):
            return d
    die('CIRCUITPY drive not mounted', 'plug the board in with a data cable, or pass --drive')


def sha1(path):
    with open(path, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()


def cmd_deploy(args):
    drive = find_drive(args.drive)
    changed = [p for p in DEPLOY if not os.path.exists(os.path.join(drive, p))
               or sha1(os.path.join(ROOT, p)) != sha1(os.path.join(drive, p))]
    for p in changed:
        print(('would copy ' if args.dry_run else 'copy ') + p)
    stray = sorted(os.path.basename(p) for p in glob.glob(os.path.join(drive, '*.py'))
                   if os.path.basename(p) not in DEPLOY)
    if stray:
        say('warning: .py files on the board that deploy does not manage: %s' % ', '.join(stray))
    if args.dry_run:
        return 0
    console = Console(args.port) if (args.port or find_port()) else None
    if console:
        console.ser.reset_input_buffer()
    for p in changed:
        dst = os.path.join(drive, p)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(ROOT, p), dst)  # copyfile: no macOS ._ metadata files
        with open(dst, 'rb+') as f:
            os.fsync(f.fileno())
    os.sync()
    bad = [p for p in changed if sha1(os.path.join(ROOT, p)) != sha1(os.path.join(drive, p))]
    if bad:
        die('verification failed after copy: %s' % ', '.join(bad), 'eject and replug the board, retry')
    if not changed and not args.reload:
        print('board already up to date')
        return 0
    if console is None:
        say('copied; no serial port, so not watching the boot')
        return 0
    if args.reload:
        console.send(b'\x03')  # Ctrl-C stops the app...
        time.sleep(0.5)
        console.send(b'\x04')  # ...Ctrl-D soft-reloads it
    say('watching the boot (90s max)...')
    for line in console.lines(90):
        if line.startswith(('[BOOT]', '[OK]', '[ERR]', '[CRASH]', '[RECONNECT]', '[WEATHER]')):
            print(line)
        if line.startswith('[OK]'):
            return 0
        if line.startswith('[CRASH]') or 'Code done running' in line:
            print('the new code crashed on boot; see `tools/portal.py logs`')
            return 1
    print('no [OK] within 90s; see `tools/portal.py logs`')
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='portal', description='Verify the MatrixPortal sign against reality.',
        epilog='examples:\n  tools/portal.py deploy\n  tools/portal.py verify --all\n'
               '  tools/portal.py inject wifi\n  tools/portal.py soak --minutes 480',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', metavar='command')

    def add(name, fn, help_text):
        p = sub.add_parser(name, help=help_text, description=help_text)
        p.add_argument('--port', help='serial port (default: autodetect Adafruit USB VID)')
        p.set_defaults(fn=fn)
        return p

    p = add('deploy', cmd_deploy, 'copy changed files to CIRCUITPY, then watch the board boot')
    p.add_argument('--drive', help='CIRCUITPY mount point (default: autodetect)')
    p.add_argument('-n', '--dry-run', action='store_true', help='list what would be copied')
    p.add_argument('--reload', action='store_true', help='restart the app even if nothing changed')
    for name, fn, help_text in (
            ('shot', cmd_shot, 'save what the board is showing (device.png, state.json)'),
            ('verify', cmd_verify, 'diff the board framebuffer against the simulator; exit 1 on mismatch')):
        p = add(name, fn, help_text)
        p.add_argument('-o', '--output', default=os.path.join(ROOT, 'out'), help='output dir (default: out/)')
        p.add_argument('--from-file', metavar='CAPTURE', help='use a saved capture.txt instead of the board')
        if name == 'verify':
            p.add_argument('--all', action='store_true', help='drive the board through every screen')
    add('status', cmd_status, 'print the board status JSON')
    p = add('logs', cmd_logs, 'stream the serial log with timestamps')
    p.add_argument('--minutes', type=float, help='stop after N minutes (default: until Ctrl-C)')
    p = add('inject', cmd_inject, 'inject a fault; exit 0 if the board recovers on its own')
    p.add_argument('fault', choices=sorted(INJECT))
    p = add('soak', cmd_soak, 'log for N minutes, then pass/fail on halts, data gaps, crashes')
    p.add_argument('--minutes', type=float, required=True)
    p.add_argument('-o', '--output', default=os.path.join(ROOT, 'out'), help='log dir (default: out/)')

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
