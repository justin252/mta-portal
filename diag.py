"""Board-side diagnostics over the USB serial console. Device-only.

tools/portal.py sends one command per line; app.py maps them to handlers and poll()
runs them between main-loop passes:
    s         screen dump    [FB] BEGIN {state} / [FB] <y> <hex RGB565 LE row> / [FB] END
    i         status         [STATUS] {json}
    n         next screen    a  toggle train art
    v NAME    hold a scenario from scenarios.py on the sign    r  back to live data
    w         drop WiFi      x  crash the main loop    h  hang (stop feeding the watchdog)
The last three are fault injection: each must end in recovery, never a halted board.

NVM is flash that survives resets (write only on rare events): [1] event length, [2:] text.
safemode.py writes the same record.
"""

import binascii
import gc
import json
import sys
import traceback
import microcontroller
import supervisor

_EVENT_MAX = 60
_line = ''  # command characters received so far


def poll(commands):
    """Run each complete command line ("s", "v weather-rain") as handler(arg). Never blocks."""
    global _line
    while supervisor.runtime.serial_bytes_available:
        ch = sys.stdin.read(1)
        if ch not in '\r\n':
            if len(_line) < 64:
                _line += ch
            continue
        cmd, _, arg = _line.partition(' ')
        _line = ''
        handler = commands.get(cmd)
        if handler:
            handler(arg)


def dump(display, state):
    """Print the framebuffer and the state that produced it. Never raises into the caller."""
    try:
        w, h = display.width, display.height
        row_bytes = w * 2
        mv_err = None
        try:
            # RGBMatrix exposes the RGB565 buffer the LEDs are driven from. Slice it, don't
            # copy it: a 4 KB copy fails on this heap.
            buf = memoryview(display.framebuffer)
            items_per_row = len(buf) // h
            if items_per_row not in (w, row_bytes) or len(buf) % h:
                raise ValueError('framebuffer has %d items, expected %d or %d'
                                 % (len(buf), w * h, row_bytes * h))
            src = 'memoryview'
        except Exception as e:
            buf = None
            src = 'fill_row'
            mv_err = repr(e)
        info = {'w': w, 'h': h, 'src': src, 'mv_err': mv_err}
        info.update(state)
        print('[FB] BEGIN ' + json.dumps(info))
        row = bytearray(row_bytes)
        for y in range(h):
            if buf is None:
                display.fill_row(y, row)
                data = row
            else:
                data = buf[y * items_per_row:(y + 1) * items_per_row]
            print('[FB] %d %s' % (y, binascii.hexlify(data).decode()))
        print('[FB] END')
    except Exception as e:
        print('[FB] ERR %r' % (e,))


def status(info):
    print('[STATUS] ' + json.dumps(info))


def remember(event):
    """Record the last notable event (reboot reason, crash) so the next boot can report it."""
    record = bytes([min(len(event.encode()), _EVENT_MAX)]) + event.encode()[:_EVENT_MAX]
    nvm = microcontroller.nvm
    if bytes(nvm[1:1 + len(record)]) != record:  # skip identical rewrites: flash wears out
        nvm[1:1 + len(record)] = record


def recall():
    n = microcontroller.nvm[1]
    if not 0 < n <= _EVENT_MAX:  # 0xFF: never written
        return None
    try:
        return bytes(microcontroller.nvm[2:2 + n]).decode()
    except Exception:  # truncated mid-character
        return None


def _name(enum_value):
    return str(enum_value).split('.')[-1]


def run_reason():
    """STARTUP after a hard reset (power, button, watchdog), SUPERVISOR_RELOAD after a crash.
    (microcontroller.cpu.reset_reason would say which hard reset, but SAMD51 always reports UNKNOWN.)"""
    return _name(supervisor.runtime.run_reason)


def boot_report():
    print('[BOOT] run=%s last_event=%r mem=%d' % (run_reason(), recall(), gc.mem_free()))
    tb = supervisor.get_previous_traceback()
    if tb:
        print('[BOOT] previous traceback:\n' + tb)


def on_crash(e):
    """code.py calls this when an exception escapes app.py, before it reloads."""
    microcontroller.watchdog.mode = None  # the crash pause must not end in a watchdog reset
    print('[CRASH] %s: %s' % (type(e).__name__, e))
    traceback.print_exception(e)
    remember('crash: %s: %s' % (type(e).__name__, e))
