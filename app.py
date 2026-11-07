"""MatrixPortal M4 subway sign: cycles L arrivals, G arrivals and current weather.

UP toggles art mode (full-screen pixel art, cycling). DOWN returns to the transit
screens (sports mode will live there).
code.py imports this module and soft-reloads the board if anything escapes it.
Every screen is drawn by apply(), from states built in screens.py: the same states the
simulator renders. How each failure mode is guarded and verified: docs/failure-modes.md.
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
import scenarios
import screens
from logic import TRAIN_URL, freshness, parse_station, server_time
from recovery import Recovery, attempt
from weather import WEATHER_URL, format_hi_lo, format_temperature, parse_weather

UPDATE_DELAY = 30           # train fetch interval (s); MTA feeds refresh about every 30s
WEATHER_UPDATE_DELAY = 900  # Open-Meteo current conditions change every 15 min
WEATHER_RETRY_DELAY = 120   # after a failed weather fetch
HOLD_TIMEOUT = 600          # a held scenario ends on its own if nobody releases it
# Long enough to read both directions (finding and reading six numbers takes ~2s), short
# enough that the L screen is never more than ~7s away
SCREEN_SECONDS = {'L': 4, 'G': 4, 'weather': 3}
ART_SECONDS = 10            # art is ambient: linger
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


def build_screen(state, fields):
    """Group with the bitmap at index 0 and one Label per field, in layout order."""
    group = displayio.Group()
    group.append(tile(state['bitmap']))
    labels = {}
    for field, role, x, y in fields:
        labels[field] = adafruit_display_text.label.Label(
            fonts[role], color=state['colors'][field], x=x, y=y, text=state['texts'][field])
        group.append(labels[field])
    return {'name': state['screen'], 'group': group, 'labels': labels, 'bitmap': state['bitmap']}


cycle = [build_screen(screens.train_state(line, [], [], 'loading'), layout.TRAIN_FIELDS)
         for line in layout.LINES]
cycle.append(build_screen(screens.weather_placeholder(), layout.WEATHER_FIELDS))
art = build_screen(screens.art_state(layout.ART[0]), ())
by_name = {s['name']: s for s in cycle + [art]}


def apply(state):
    """Draw a screen state (screens.py) onto its display group."""
    s = by_name[state['screen']]
    if s['bitmap'] != state['bitmap']:
        s['group'][0] = tile(state['bitmap'])  # swap in place; the old file closes when collected
        s['bitmap'] = state['bitmap']
    for field, text in state['texts'].items():
        label = s['labels'][field]
        if label.text != text:  # re-rendering a Label allocates; skip no-op updates
            label.text = text
        if label.color != state['colors'][field]:
            label.color = state['colors'][field]


idx = 0                 # position in the transit cycle
art_idx = 0             # position in layout.ART
mode = 'transit'        # 'transit' (L, G, weather) or 'art'
last_switch = now_ms()
display.root_group = cycle[0]['group']


def show(i):
    global idx, last_switch
    idx = i
    display.root_group = cycle[i]['group']
    last_switch = now_ms()


def next_screen():
    nxt = (idx + 1) % len(cycle)
    if cycle[nxt]['name'] == 'weather' and live_weather is None:
        nxt = 0  # the weather screen joins the cycle after its first good fetch
    show(nxt)


def set_mode(new):
    global mode, last_switch
    mode = new
    if mode == 'art':
        apply(screens.art_state(layout.ART[art_idx]))
        display.root_group = art['group']
        last_switch = now_ms()
    else:
        show(idx)
    print('[MODE] %s' % mode)


def next_art():
    global art_idx, last_switch
    art_idx = (art_idx + 1) % len(layout.ART)
    apply(screens.art_state(layout.ART[art_idx]))
    last_switch = now_ms()


def current_state():
    """What is on screen, read back from the live display objects (for diag dumps)."""
    s = art if mode == 'art' else cycle[idx]
    return {'screen': s['name'], 'bitmap': s['bitmap'],
            'texts': {f: label.text for f, label in s['labels'].items()},
            'colors': {f: label.color for f, label in s['labels'].items()}}


# --- Live data ---
live_trains = {}    # line -> (north, south) minutes from the last good fetch
live_weather = None
fresh = 'loading'   # logic.freshness() of live_trains, as last drawn


def render_live():
    for line in layout.LINES:
        apply(screens.train_state(line, *live_trains.get(line, ([], [])), fresh))
    apply(screens.weather_state(live_weather) if live_weather else screens.weather_placeholder())


# --- Scenarios: hold any design on the sign for review (diag 'v NAME', 'r') ---
held = None         # scenario name while one is held
held_until = 0


def update_freshness():
    """Redraw the arrival rows when they go stale, offline, or live again."""
    global fresh
    now = freshness(bool(live_trains), trains.age(now_s()), trains.failures)
    if now != fresh:
        fresh = now
        if held is None:
            render_live()


def hold(name):
    global held, held_until, mode
    scenario = scenarios.BY_NAME.get(name)
    if scenario is None:
        print('[SCENE] unknown %r' % name)
        return
    state = scenarios.state(scenario)
    apply(state)
    if state['screen'] == 'art':
        mode = 'art'
        display.root_group = art['group']
    else:
        mode = 'transit'
        show([s['name'] for s in cycle].index(state['screen']))
    held, held_until = name, now_s() + HOLD_TIMEOUT
    print('[SCENE] %s' % name)


def release():
    global held, mode
    if held is None:
        return
    held = None
    render_live()
    apply(screens.art_state(layout.ART[art_idx]))
    mode = 'transit'
    show(idx)
    print('[SCENE] back to live data')


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
    """{line: (north, south)} minutes for every line. Raises on any failure, so the
    display never shows one line fresh and the other stale without saying so."""
    arrivals = {}
    for line in layout.LINES:
        payload, headers = get_json(TRAIN_URL % layout.STATIONS[line]['stop_id'])
        arrivals[line] = parse_station(payload, line, server_time(headers, payload))
        payload = None
        gc.collect()
    return arrivals


# --- Diagnostics: serial commands from tools/portal.py ---
def status():
    gc.collect()  # so 'mem' is what's actually free, not what's awaiting collection
    s = now_s()
    diag.status({'mode': mode, 'screen': current_state()['screen'], 'held': held, 'fresh': fresh,
                 'weather_ok': live_weather is not None, 'failures': trains.failures,
                 'age': trains.age(s), 'mem': gc.mem_free(), 'up': (now_ms() - boot_ms) // 1000,
                 'wifi': wifi.is_connected, 'run': diag.run_reason(), 'last_event': diag.recall()})


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
    's': lambda arg: diag.dump(display, current_state()),
    'i': lambda arg: status(),
    'n': lambda arg: next_art() if mode == 'art' else next_screen(),
    'a': lambda arg: set_mode('transit' if mode == 'art' else 'art'),
    'v': hold,
    'r': lambda arg: release(),
    'w': lambda arg: drop_wifi(),
    'x': lambda arg: crash(),
    'h': lambda arg: hang(),
}

# --- Buttons (active-low with internal pull-up) ---
button_up_pin = digitalio.DigitalInOut(board.BUTTON_UP)
button_up_pin.switch_to_input(pull=digitalio.Pull.UP)
button_up = Debouncer(button_up_pin)
button_down_pin = digitalio.DigitalInOut(board.BUTTON_DOWN)
button_down_pin.switch_to_input(pull=digitalio.Pull.UP)
button_down = Debouncer(button_down_pin)

# --- Main loop ---
wdt = microcontroller.watchdog
wdt.timeout = WATCHDOG_TIMEOUT
wdt.mode = WatchDogMode.RESET

trains = Recovery(UPDATE_DELAY, now=now_s())
next_weather_s = now_s() + 15  # trains first

while True:
    wdt.feed()
    diag.poll(commands)
    button_up.update()
    button_down.update()

    if button_up.fell or button_down.fell:
        release()  # any press ends a held scenario
        if button_up.fell:
            set_mode('transit' if mode == 'art' else 'art')
        else:
            set_mode('transit')  # sports mode goes on this button

    if held is not None and now_s() >= held_until:
        release()
    if held is None:
        elapsed = now_ms() - last_switch
        if mode == 'transit' and elapsed > SCREEN_SECONDS[cycle[idx]['name']] * 1000:
            next_screen()
        elif mode == 'art' and elapsed > ART_SECONDS * 1000:
            next_art()
    update_freshness()

    if trains.due(now_s()):
        started = now_ms()
        arrivals, err = attempt(fetch_trains, trains, now_s)
        took = (now_ms() - started) / 1000
        if err is None:
            live_trains = arrivals
            update_freshness()  # before drawing, so new data never shows with the old state
            if held is None:
                render_live()
            texts = [(line, screens.train_state(line, *arrivals[line])['texts']) for line in layout.LINES]
            print('[OK] %s t=%.1fs mem=%d' % (' '.join(
                '%s N:%s S:%s' % (line, t['north_times'], t['south_times']) for line, t in texts),
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

    if now_s() >= next_weather_s:
        try:
            weather = parse_weather(get_json(WEATHER_URL)[0])
        except Exception as e:  # weather is optional: log, retry later, never escalate
            next_weather_s = now_s() + WEATHER_RETRY_DELAY
            print('[WEATHER] failed %s: %s' % (type(e).__name__, e))
            gc.collect()
        else:
            live_weather = weather
            if held is None:
                render_live()
            next_weather_s = now_s() + WEATHER_UPDATE_DELAY
            print('[WEATHER] %s %s code=%d' % (format_temperature(weather['temp_f']),
                                            format_hi_lo(weather['hi_f'], weather['lo_f']), weather['code']))

    time.sleep(0.1)
