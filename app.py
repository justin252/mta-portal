"""MatrixPortal M4 subway sign: cycles L arrivals, G arrivals and current weather.

Buttons jump to L (UP) or G (DOWN); a long press toggles full-screen train art.
code.py imports this module and soft-reloads the board if anything escapes it.
How each failure mode is guarded and verified: docs/failure-modes.md.
"""

import gc
import os
import time
import board
import digitalio
import displayio
import microcontroller
import adafruit_display_text.label
from adafruit_bitmap_font import bitmap_font
from adafruit_debouncer import Debouncer
from adafruit_matrixportal.matrix import Matrix
from adafruit_portalbase.wifi_coprocessor import WiFi
from watchdog import WatchDogMode

import diag
import layout
from logic import TRAIN_URL, format_arrival_triple, parse_station, server_time
from recovery import Recovery, attempt
from weather import (DEFAULT_CONDITION, DEMO, WEATHER_URL, format_hi_lo, format_temperature,
                     map_condition, parse_weather)

UPDATE_DELAY = 30           # train fetch interval (s); MTA feeds refresh about every 30s
WEATHER_UPDATE_DELAY = 900  # Open-Meteo current conditions change every 15 min
WEATHER_RETRY_DELAY = 120   # after a failed weather fetch
DEMO_TIMEOUT = 600          # demo mode ends on its own if nobody ends it
CYCLE_SECONDS = 2           # every screen gets the same time
LONG_PRESS_MS = 1000
HTTP_TIMEOUT = 5            # per socket operation (s); keeps one request inside the watchdog window
WATCHDOG_TIMEOUT = 16       # SAMD51 maximum; if the loop stops feeding it, the board resets
HEADERS = {'User-Agent': 'mta-portal'}


def now_ms():
    # time.monotonic() is a float that loses precision after days of uptime; these are ints
    return time.monotonic_ns() // 1000000


def now_s():
    return now_ms() // 1000


diag.boot_report()
boot_ms = now_ms()

# --- Display ---
matrix = Matrix()
display = matrix.display
fonts = {role: bitmap_font.load_font(path) for role, path in layout.FONTS.items()}


def tile(path):
    # OnDiskBitmap(path) keeps its own file open while shown and closes it when collected
    bmp = displayio.OnDiskBitmap(path)
    return displayio.TileGrid(bmp, pixel_shader=bmp.pixel_shader)


def build_screen(name, bitmap, fields, texts):
    """Group with the bitmap at index 0 and one Label per field, in layout order."""
    group = displayio.Group()
    group.append(tile(bitmap))
    labels = {}
    for field, role, x, y in fields:
        labels[field] = adafruit_display_text.label.Label(
            fonts[role], color=layout.COLORS[role], x=x, y=y, text=texts[field])
        group.append(labels[field])
    return {'name': name, 'group': group, 'labels': labels, 'bitmap': bitmap}


screens = []
for line in layout.LINES:
    station = layout.STATIONS[line]
    screens.append(build_screen(line, station['bitmap'], layout.TRAIN_FIELDS, {
        'north': station['north'], 'north_times': '-,-,-',
        'south': station['south'], 'south_times': '-,-,-'}))
screens.append(build_screen('weather', DEFAULT_CONDITION[0], layout.WEATHER_FIELDS,
                            {'condition': '--', 'temp': '--', 'hi_lo': ''}))
by_name = {s['name']: s for s in screens}

screen_idx = 0
current_view = 'cycle'  # 'cycle' or 'train_art'
art_group = None
weather_ok = False      # the weather screen joins the cycle after its first good fetch
last_cycle_switch = now_ms()
display.root_group = screens[0]['group']


def show(idx):
    global screen_idx, last_cycle_switch
    screen_idx = idx
    display.root_group = screens[idx]['group']
    last_cycle_switch = now_ms()


def next_screen():
    nxt = (screen_idx + 1) % len(screens)
    if screens[nxt]['name'] == 'weather' and not weather_ok:
        nxt = 0
    show(nxt)


def toggle_art():
    global current_view, art_group
    if current_view == 'cycle':
        art_group = displayio.Group()
        art_group.append(tile(layout.TRAIN_ART))
        display.root_group = art_group
        current_view = 'train_art'
    else:
        current_view = 'cycle'
        show(screen_idx)
        art_group = None
    print('[BTN] view=%s' % current_view)


def set_text(label, text):
    if label.text != text:  # re-rendering a Label allocates; skip no-op updates
        label.text = text


def current_state():
    """What is on screen, read back from the live display objects (for diag dumps)."""
    if current_view == 'train_art':
        return {'screen': 'train_art', 'texts': {}, 'bitmap': layout.TRAIN_ART}
    s = screens[screen_idx]
    return {'screen': s['name'], 'bitmap': s['bitmap'],
            'texts': {field: label.text for field, label in s['labels'].items()}}


# --- Network ---
wifi = WiFi()  # resets the ESP32; the first fetch joins WiFi


def ensure_connected():
    """One bounded join attempt (connect_AP gives up after 10s). The recovery policy
    schedules the retry, so buttons and screen cycling stay live during outages."""
    if wifi.is_connected and wifi.requests:
        return
    print('[RECONNECT] joining WiFi')
    wdt.feed()
    wifi.connect(os.getenv('CIRCUITPY_WIFI_SSID'), os.getenv('CIRCUITPY_WIFI_PASSWORD'))
    print('[RECONNECT] ok')


def get_json(url):
    """GET url -> (payload, headers). Non-200 raises. Always releases the socket."""
    ensure_connected()
    wdt.feed()
    resp = wifi.requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)
    try:
        if resp.status_code != 200:
            raise RuntimeError('HTTP %d from %s' % (resp.status_code, url.split('/')[2]))
        return resp.json(), resp.headers
    finally:
        resp.close()


def fetch_trains():
    """{line: (n0, n1, n2, s0, s1, s2)} for every line. Raises on any failure, so the
    display never shows one line fresh and the other stale without saying so."""
    arrivals = {}
    for line in layout.LINES:
        payload, headers = get_json(TRAIN_URL % layout.STATIONS[line]['stop_id'])
        north, south = parse_station(payload, line, server_time(headers, payload))
        arrivals[line] = format_arrival_triple(north) + format_arrival_triple(south)
        payload = None
        gc.collect()
    return arrivals


def show_arrivals(arrivals):
    for line, (n0, n1, n2, s0, s1, s2) in arrivals.items():
        labels = by_name[line]['labels']
        set_text(labels['north_times'], '%s,%s,%s' % (n0, n1, n2))
        set_text(labels['south_times'], '%s,%s,%s' % (s0, s1, s2))


def show_weather(weather):
    global weather_ok
    if weather is None:  # no real reading yet: placeholders, and keep the screen out of the cycle
        s = by_name['weather']
        set_text(s['labels']['condition'], '--')
        set_text(s['labels']['temp'], '--')
        set_text(s['labels']['hi_lo'], '')
        weather_ok = False
        return
    bitmap, condition = map_condition(weather['code'])
    s = by_name['weather']
    if s['bitmap'] != bitmap:
        s['group'][0] = tile(bitmap)  # swap in place; the old bitmap's file closes when collected
        s['bitmap'] = bitmap
    set_text(s['labels']['condition'], condition)
    set_text(s['labels']['temp'], format_temperature(weather['temp_f']))
    set_text(s['labels']['hi_lo'], format_hi_lo(weather['hi_f'], weather['lo_f']))
    weather_ok = True


# --- Diagnostics: serial commands from tools/portal.py ---
def status():
    s = now_s()
    diag.status({'view': current_view, 'screen': current_state()['screen'], 'weather_ok': weather_ok,
                 'failures': trains.failures, 'age': trains.age(s), 'mem': gc.mem_free(),
                 'up': (now_ms() - boot_ms) // 1000, 'wifi': wifi.is_connected,
                 'run': diag.run_reason(), 'last_event': diag.recall()})


def demo_weather():
    """Hold the weather screen on the next fake reading from weather.DEMO (diag 'c')."""
    global demo_idx, demo_until
    demo_idx = (demo_idx + 1) % len(DEMO)
    reading = DEMO[demo_idx]
    show_weather(reading)
    if current_view == 'train_art':
        toggle_art()
    show(len(screens) - 1)
    demo_until = now_s() + DEMO_TIMEOUT
    print('[DEMO] %d/%d %s %s %s' % (demo_idx + 1, len(DEMO), map_condition(reading['code'])[1],
                                     format_temperature(reading['temp_f']),
                                     format_hi_lo(reading['hi_f'], reading['lo_f'])))


def live_weather():
    """Leave demo mode: real reading back, cycling resumes, fresh fetch now (diag 'r')."""
    global demo_until, next_weather_s, last_cycle_switch
    if demo_until is None:
        return
    demo_until = None
    show_weather(live_reading)
    next_weather_s = now_s()
    last_cycle_switch = now_ms()  # the current screen gets its full turn before cycling on
    print('[DEMO] back to live data')


def drop_wifi():
    print('[INJECT] dropping WiFi')
    try:
        wifi.esp.disconnect()
    except Exception as e:
        print('[INJECT] disconnect failed: %r' % (e,))


def crash():
    raise RuntimeError('injected crash')


def hang():
    print('[INJECT] hanging; the watchdog should reset the board within %ds' % WATCHDOG_TIMEOUT)
    while True:
        time.sleep(1)


commands = {
    's': lambda: diag.dump(display, current_state()),
    'i': status,
    'n': lambda: toggle_art() if current_view == 'train_art' else next_screen(),
    'a': toggle_art,
    'c': demo_weather,
    'r': live_weather,
    'w': drop_wifi,
    'x': crash,
    'h': hang,
}

# --- Buttons (active-low with internal pull-up) ---
button_up_pin = digitalio.DigitalInOut(board.BUTTON_UP)
button_up_pin.switch_to_input(pull=digitalio.Pull.UP)
button_up = Debouncer(button_up_pin)
button_down_pin = digitalio.DigitalInOut(board.BUTTON_DOWN)
button_down_pin.switch_to_input(pull=digitalio.Pull.UP)
button_down = Debouncer(button_down_pin)
button_press_ms = None

# --- Main loop ---
wdt = microcontroller.watchdog
wdt.timeout = WATCHDOG_TIMEOUT
wdt.mode = WatchDogMode.RESET

trains = Recovery(UPDATE_DELAY, now=now_s())
next_weather_s = now_s() + 15  # trains first
demo_idx = -1
demo_until = None   # set while demo mode holds the weather screen on a fake reading
live_reading = None

while True:
    wdt.feed()
    diag.poll(commands)
    button_up.update()
    button_down.update()

    if button_up.fell or button_down.fell:
        button_press_ms = now_ms()
    if (button_up.rose or button_down.rose) and button_press_ms is not None:
        held = now_ms() - button_press_ms
        button_press_ms = None
        live_weather()  # any press ends demo mode
        if held >= LONG_PRESS_MS or current_view == 'train_art':
            toggle_art()  # long press toggles; any press leaves the art view
        else:
            target = 0 if button_up.rose else 1
            if screen_idx != target:
                print('[BTN] %s -> %s' % ('UP' if button_up.rose else 'DOWN', screens[target]['name']))
                show(target)

    if demo_until is not None and now_s() >= demo_until:
        live_weather()
    if (current_view == 'cycle' and demo_until is None
            and now_ms() - last_cycle_switch > CYCLE_SECONDS * 1000):
        next_screen()

    if trains.due(now_s()):
        started = now_ms()
        arrivals, err = attempt(fetch_trains, trains, now_s)
        took = (now_ms() - started) / 1000
        if err is None:
            show_arrivals(arrivals)
            print('[OK] %s t=%.1fs mem=%d' % (' '.join(
                '%s N:%s,%s,%s S:%s,%s,%s' % ((line,) + arrivals[line]) for line in layout.LINES),
                took, gc.mem_free()))
        else:
            gc.collect()
            print('[ERR] %s: %s fails=%d age=%ds t=%.1fs mem=%d' % (
                type(err).__name__, err, trains.failures, trains.age(now_s()), took, gc.mem_free()))
            if trains.should_reboot(now_s()):
                reason = 'no data %ds, %d fails, last %s' % (
                    trains.age(now_s()), trains.failures, type(err).__name__)
                print('[RESET] ' + reason)
                diag.remember('reset: ' + reason)
                microcontroller.reset()

    if demo_until is None and now_s() >= next_weather_s:
        try:
            weather = parse_weather(get_json(WEATHER_URL)[0])
        except Exception as e:  # weather is optional: log, retry later, never escalate
            next_weather_s = now_s() + WEATHER_RETRY_DELAY
            print('[WEATHER] failed %s: %s' % (type(e).__name__, e))
            gc.collect()
        else:
            live_reading = weather
            show_weather(weather)
            next_weather_s = now_s() + WEATHER_UPDATE_DELAY
            print('[WEATHER] %s %s code=%d' % (format_temperature(weather['temp_f']),
                                            format_hi_lo(weather['hi_f'], weather['lo_f']), weather['code']))

    time.sleep(0.1)
