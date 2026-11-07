"""Device diagnostics over the USB serial console. Device-only.

Send 's' on the console to get the framebuffer plus the state that produced it:
    [FB] BEGIN {"w": 64, "h": 32, "src": "memoryview", "screen": "L", "texts": {...}, "bitmap": "..."}
    [FB] <y> <hex: one row, RGB565 little-endian, 2 bytes/px>
    [FB] END
tools/portal.py decodes the dump and diffs it against the simulator.
"""

import binascii
import json
import sys
import supervisor


def poll(display, state_fn):
    """Handle pending console commands without blocking the main loop."""
    while supervisor.runtime.serial_bytes_available:
        if sys.stdin.read(1) == 's':
            dump(display, state_fn)


def dump(display, state_fn):
    """Print the framebuffer and current state. Never raises into the caller."""
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
        info.update(state_fn())
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
