## Main loop for MatrixPortal M4 LED sign. Cycles between L train arrivals,
## G train arrivals, and current weather. Buttons jump to L (UP) or G (DOWN).
## Long press toggles full-screen train pixel art view.

import os
import time
import microcontroller
import board
import digitalio
from adafruit_debouncer import Debouncer
from board import NEOPIXEL
import displayio
import adafruit_display_text.label
from adafruit_datetime import datetime
from adafruit_bitmap_font import bitmap_font
from adafruit_matrixportal.matrix import Matrix
from adafruit_matrixportal.network import Network
from logic import filter_arrivals, format_arrival_triple
from weather import parse_nws_forecast, map_condition, format_temperature

STATIONS = {
    'L': {
        'stop_id': 'L11',
        'north': 'Manhattan',
        'south': 'Canarsie',
        'bitmap': 'l-dashboard.bmp',
    },
    'G': {
        'stop_id': 'G29',
        'north': 'Queens',
        'south': 'Church Av',
        'bitmap': 'g-dashboard.bmp',
    }
}
API_BASE = 'https://api.wheresthefuckingtrain.com/by-id/%s'
DATA_LOCATION = ["data"]
WEATHER_URL = 'https://api.weather.gov/gridpoints/OKX/35,35/forecast'

UPDATE_DELAY = 30           # train fetch interval (seconds)
WEATHER_UPDATE_DELAY = 300  # weather fetch interval (5 min)
SCREEN_CYCLE_DELAY = 10    # seconds between screen switches
SYNC_TIME_DELAY = 30
ERROR_RESET_THRESHOLD = 3
LONG_PRESS_THRESHOLD = 1.0  # seconds


def fetch_train(line):
    """Fetch arrivals for one line. Returns (n0,n1,n2,s0,s1,s2) display strings."""
    url = API_BASE % STATIONS[line]['stop_id']
    stop_trains = network.fetch_data(url, json_path=(DATA_LOCATION,))
    stop_data = stop_trains[0]
    northbound = [x['time'] for x in stop_data.get('N', []) if x.get('route') == line]
    southbound = [x['time'] for x in stop_data.get('S', []) if x.get('route') == line]
    now = datetime.now()
    n = filter_arrivals(now, northbound)
    s = filter_arrivals(now, southbound)
    n0, n1, n2 = format_arrival_triple(n)
    s0, s1, s2 = format_arrival_triple(s)
    print("[OK] %s N:%s,%s,%s S:%s,%s,%s" % (line, n0, n1, n2, s0, s1, s2))
    return n0, n1, n2, s0, s1, s2


def update_train_display(line, arrivals):
    """Write arrival times into the display group for a train line."""
    n0, n1, n2, s0, s1, s2 = arrivals
    labels = train_labels[line]
    labels['north_times'].text = "%s,%s,%s" % (n0, n1, n2)
    labels['south_times'].text = "%s,%s,%s" % (s0, s1, s2)


def fetch_weather():
    """Fetch weather from NWS. Returns parsed dict or None on error."""
    try:
        resp = network._wifi.requests.get(WEATHER_URL, headers={"User-Agent": "mta-portal"})
        data = resp.json()
        resp.close()
        weather = parse_nws_forecast(data)
        print("[WEATHER] %s %d°F" % (weather['short_forecast'], weather['temp_f']))
        return weather
    except Exception as e:
        print("[WEATHER] fetch failed: %s" % e)
        return None


def update_weather_display(weather):
    """Update weather display group with new data."""
    global _weather_bitmap_file
    icon_file, label = map_condition(weather['icon_url'])
    _weather_bitmap_file.close()
    _weather_bitmap_file = open(icon_file, 'rb')
    new_bmp = displayio.OnDiskBitmap(_weather_bitmap_file)
    weather_group.pop(0)
    tile = displayio.TileGrid(new_bmp, pixel_shader=getattr(new_bmp, 'pixel_shader', displayio.ColorConverter()))
    weather_group.insert(0, tile)
    weather_labels['condition'].text = label
    weather_labels['temp'].text = format_temperature(weather['temp_f'])


def show_train_art():
    """Switch display to full-screen train pixel art."""
    global current_view, _train_art_file
    _train_art_file = open('train.bmp', 'rb')
    bmp = displayio.OnDiskBitmap(_train_art_file)
    grp = displayio.Group()
    grp.append(displayio.TileGrid(bmp, pixel_shader=getattr(bmp, 'pixel_shader', displayio.ColorConverter())))
    display.root_group = grp
    current_view = 'train_art'
    print("[BTN] show train art")


def exit_train_art():
    """Return from train pixel art to cycling mode."""
    global current_view, _train_art_file, last_cycle_switch
    if _train_art_file:
        _train_art_file.close()
        _train_art_file = None
    display.root_group = screens[screen_idx][1]
    current_view = 'cycle'
    last_cycle_switch = time.monotonic()
    print("[BTN] exit train art")


def attempt_wifi_reconnect():
    """Try reconnecting WiFi; if connect_AP fails, hard-reset the ESP32 coprocessor."""
    esp = network._wifi.esp
    if esp.is_connected:
        return
    ssid = os.getenv("CIRCUITPY_WIFI_SSID")
    password = os.getenv("CIRCUITPY_WIFI_PASSWORD")
    print("[RECONNECT] attempting esp.connect_AP...")
    try:
        esp.connect_AP(ssid, password)
        print("[RECONNECT] success")
    except Exception as e:
        print("[RECONNECT] connect_AP failed: %s - resetting ESP" % (e,))
        try:
            esp.reset()
            time.sleep(2)
            esp.connect_AP(ssid, password)
            print("[RECONNECT] success after ESP reset")
        except Exception as e2:
            print("[RECONNECT] ESP reset failed: %s" % (e2,))


# --- Display setup ---
matrix = Matrix()
display = matrix.display
network = Network(status_neopixel=NEOPIXEL, debug=False)

colors = [0x444444, 0xDD8000]  # [dim white, gold]
font_label = bitmap_font.load_font("fonts/tom-thumb.bdf")
font_time = bitmap_font.load_font("fonts/spleen-5x8.bdf")


def build_train_group(line):
    """Create a display group for a train line. Returns (group, labels_dict, bitmap_file)."""
    station = STATIONS[line]
    bmp_file = open(station['bitmap'], 'rb')
    bmp = displayio.OnDiskBitmap(bmp_file)
    grp = displayio.Group()
    tile = displayio.TileGrid(bmp, pixel_shader=getattr(bmp, 'pixel_shader', displayio.ColorConverter()))
    north_label = adafruit_display_text.label.Label(font_label, color=colors[0], x=18, y=4, text=station['north'])
    north_times = adafruit_display_text.label.Label(font_time, color=colors[1], x=18, y=11, text="-,-,-")
    south_label = adafruit_display_text.label.Label(font_label, color=colors[0], x=18, y=20, text=station['south'])
    south_times = adafruit_display_text.label.Label(font_time, color=colors[1], x=18, y=27, text="-,-,-")
    for el in [tile, north_label, north_times, south_label, south_times]:
        grp.append(el)
    labels = {'north_times': north_times, 'south_times': south_times}
    return grp, labels, bmp_file


# Build train display groups
l_group, l_labels, _l_bitmap_file = build_train_group('L')
g_group, g_labels, _g_bitmap_file = build_train_group('G')
train_labels = {'L': l_labels, 'G': g_labels}

# Build weather display group
_weather_bitmap_file = open('weather-cloud.bmp', 'rb')
_weather_bmp = displayio.OnDiskBitmap(_weather_bitmap_file)
weather_group = displayio.Group()
_weather_tile = displayio.TileGrid(_weather_bmp, pixel_shader=getattr(_weather_bmp, 'pixel_shader', displayio.ColorConverter()))
weather_labels = {
    'condition': adafruit_display_text.label.Label(font_label, color=colors[0], x=18, y=10, text="--"),
    'temp': adafruit_display_text.label.Label(font_time, color=colors[1], x=18, y=22, text="--"),
}
for el in [_weather_tile, weather_labels['condition'], weather_labels['temp']]:
    weather_group.append(el)

# Screen cycling: L → G → weather → L → ...
screens = [('L', l_group), ('G', g_group), ('weather', weather_group)]
screen_idx = 0
display.root_group = l_group

# Hardware buttons
button_up_pin = digitalio.DigitalInOut(board.BUTTON_UP)
button_up_pin.switch_to_input(pull=digitalio.Pull.UP)
button_up = Debouncer(button_up_pin)

button_down_pin = digitalio.DigitalInOut(board.BUTTON_DOWN)
button_down_pin.switch_to_input(pull=digitalio.Pull.UP)
button_down = Debouncer(button_down_pin)

# State
error_counter = 0
last_time_sync = None
last_train_update = None
last_weather_update = None
last_cycle_switch = time.monotonic()
cached_weather = None
current_view = 'cycle'  # 'cycle' or 'train_art'
_train_art_file = None
button_press_time = None

# Main loop: poll buttons at 100ms, fetch trains every 30s, weather every 5min,
# cycle display every 10s. Long press toggles train pixel art view.
while True:
    button_up.update()
    button_down.update()

    # Button press start — record time
    if button_up.fell or button_down.fell:
        button_press_time = time.monotonic()

    # Button release — short vs long press
    if button_up.rose or button_down.rose:
        if button_press_time is not None:
            held = time.monotonic() - button_press_time
            button_press_time = None

            if held >= LONG_PRESS_THRESHOLD:
                # Long press: toggle train pixel art
                if current_view == 'cycle':
                    show_train_art()
                else:
                    exit_train_art()
            else:
                # Short press
                if current_view == 'train_art':
                    exit_train_art()
                else:
                    target = 0 if button_up.rose else 1  # L=0, G=1
                    if screen_idx != target:
                        print("[BTN] %s -> %s" % ("UP" if button_up.rose else "DOWN", screens[target][0]))
                        screen_idx = target
                        display.root_group = screens[screen_idx][1]
                        last_cycle_switch = time.monotonic()

    now_mono = time.monotonic()

    # Screen cycling — only when in cycle mode
    if current_view == 'cycle' and now_mono > last_cycle_switch + SCREEN_CYCLE_DELAY:
        next_idx = (screen_idx + 1) % len(screens)
        # Skip weather screen if no data yet
        if next_idx == 2 and cached_weather is None:
            next_idx = 0
        screen_idx = next_idx
        display.root_group = screens[screen_idx][1]
        last_cycle_switch = now_mono

    # Periodic train fetch — both L and G
    if last_train_update is None or now_mono > last_train_update + UPDATE_DELAY:
        try:
            if last_time_sync is None or now_mono > last_time_sync + SYNC_TIME_DELAY:
                network.get_local_time()
                last_time_sync = time.monotonic()
            for line in ('L', 'G'):
                arrivals = fetch_train(line)
                update_train_display(line, arrivals)
            error_counter = 0
            last_train_update = time.monotonic()
        except (ValueError, RuntimeError, OSError, BrokenPipeError, ConnectionError) as e:
            print("[ERR] %s: %s - wifi=%s" % (type(e).__name__, e, network._wifi.esp.is_connected))
            error_counter = error_counter + 1
            if error_counter > ERROR_RESET_THRESHOLD:
                print("[RESET] error_counter=%d" % error_counter)
                microcontroller.reset()
            attempt_wifi_reconnect()
            last_train_update = time.monotonic()

    # Periodic weather fetch
    if last_weather_update is None or now_mono > last_weather_update + WEATHER_UPDATE_DELAY:
        weather = fetch_weather()
        if weather:
            cached_weather = weather
            update_weather_display(weather)
        last_weather_update = time.monotonic()

    time.sleep(0.1)
