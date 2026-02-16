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

STATIONS = {
    'L': {
        'stop_id': 'L11',
        'name': 'L-Graham Av',
        'north': 'Manhattan',
        'south': 'Canarsie',
        'bitmap': 'l-dashboard.bmp'
    },
    'G': {
        'stop_id': 'G29',
        'name': 'G-Metro Av',
        'north': 'Queens',
        'south': 'Church Av',
        'bitmap': 'g-dashboard.bmp'
    }
}
DATA_SOURCE = None  # Set dynamically
DATA_LOCATION = ["data"]
# MTA feeds update ~30s; matches that cadence while minimizing main loop blocking
UPDATE_DELAY = 30
SYNC_TIME_DELAY = 30
ERROR_RESET_THRESHOLD = 3

def get_arrival_times(route):
    stop_trains = network.fetch_data(DATA_SOURCE, json_path=(DATA_LOCATION,))
    stop_data = stop_trains[0]
    northbound_trains = [x['time'] for x in stop_data.get('N', []) if x.get('route') == route]
    southbound_trains = [x['time'] for x in stop_data.get('S', []) if x.get('route') == route]

    now = datetime.now()

    n = filter_arrivals(now, northbound_trains)
    s = filter_arrivals(now, southbound_trains)

    n0, n1, n2 = format_arrival_triple(n)
    s0, s1, s2 = format_arrival_triple(s)

    print("[OK] fetch success, next N: %s,%s,%s S: %s,%s,%s" % (n0, n1, n2, s0, s1, s2))
    return n0, n1, s0, s1, n2, s2

def update_text(n0, n1, s0, s1, n2, s2):
    text_lines[2].text = "%s,%s,%s" % (n0,n1,n2)
    text_lines[4].text = "%s,%s,%s" % (s0,s1,s2)
    display.root_group = group

def attempt_wifi_reconnect():
    esp = network._wifi.esp
    if esp.is_connected:
        return
    ssid = os.getenv("CIRCUITPY_WIFI_SSID")
    password = os.getenv("CIRCUITPY_WIFI_PASSWORD")
    print("[RECONNECT] wifi_connected=False, attempting esp.connect_AP...")
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

def switch_line(new_line):
    station = STATIONS[new_line]
    global DATA_SOURCE
    DATA_SOURCE = 'https://api.wheresthefuckingtrain.com/by-id/%s' % station['stop_id']

    global bitmap, _bitmap_file
    _bitmap_file.close()
    _bitmap_file = open(station['bitmap'], 'rb')
    bitmap = displayio.OnDiskBitmap(_bitmap_file)

    group.pop(0)
    tile_grid = displayio.TileGrid(bitmap, pixel_shader=getattr(bitmap, 'pixel_shader', displayio.ColorConverter()))
    group.insert(0, tile_grid)
    text_lines[0] = tile_grid

    text_lines[1].text = station['north']
    text_lines[3].text = station['south']
    text_lines[2].text = "-,-,-"
    text_lines[4].text = "-,-,-"

# --- Display setup ---
matrix = Matrix()
display = matrix.display
network = Network(status_neopixel=NEOPIXEL, debug=False)

# --- Drawing setup ---
group = displayio.Group()
colors = [0x444444, 0xDD8000]  # [dim white, gold]

font = bitmap_font.load_font("fonts/5x7.bdf")

# Load the L by default
current_line = 'L'
station = STATIONS[current_line]
DATA_SOURCE = 'https://api.wheresthefuckingtrain.com/by-id/%s' % station['stop_id']
_bitmap_file = open(station['bitmap'], 'rb')
bitmap = displayio.OnDiskBitmap(_bitmap_file)

text_lines = [
    displayio.TileGrid(bitmap, pixel_shader=getattr(bitmap, 'pixel_shader', displayio.ColorConverter())),
    adafruit_display_text.label.Label(font, color=colors[0], x=18, y=4, text=station['north']),
    adafruit_display_text.label.Label(font, color=colors[1], x=18, y=11, text="-"),
    adafruit_display_text.label.Label(font, color=colors[0], x=18, y=20, text=station['south']),
    adafruit_display_text.label.Label(font, color=colors[1], x=18, y=27, text="-"),
]
for x in text_lines:
    group.append(x)
display.root_group = group

# Button setup
button_up_pin = digitalio.DigitalInOut(board.BUTTON_UP)
button_up_pin.switch_to_input(pull=digitalio.Pull.UP)
button_up = Debouncer(button_up_pin)

button_down_pin = digitalio.DigitalInOut(board.BUTTON_DOWN)
button_down_pin.switch_to_input(pull=digitalio.Pull.UP)
button_down = Debouncer(button_down_pin)

error_counter = 0
last_time_sync = None
last_update = None

while True:
    # Poll buttons frequently
    button_up.update()
    button_down.update()

    if button_up.fell:
        print("[BTN] UP -> L")
        if current_line != 'L':
            switch_line('L')
            current_line = 'L'
            last_update = None
    elif button_down.fell:
        print("[BTN] DOWN -> G")
        if current_line != 'G':
            switch_line('G')
            current_line = 'G'
            last_update = None

    # API fetch on interval
    if last_update is None or time.monotonic() > last_update + UPDATE_DELAY:
        try:
            if last_time_sync is None or time.monotonic() > last_time_sync + SYNC_TIME_DELAY:
                network.get_local_time()
                last_time_sync = time.monotonic()
            arrivals = get_arrival_times(current_line)
            update_text(*arrivals)
            error_counter = 0
            last_update = time.monotonic()
        except (ValueError, RuntimeError, OSError, BrokenPipeError, ConnectionError) as e:
            print("[ERR] %s: %s - wifi_connected=%s" % (type(e).__name__, e, network._wifi.esp.is_connected))
            error_counter = error_counter + 1
            if error_counter > ERROR_RESET_THRESHOLD:
                print("[RESET] error_counter=%d, resetting microcontroller" % error_counter)
                microcontroller.reset()
            attempt_wifi_reconnect()
            last_update = time.monotonic()

    time.sleep(0.1)  # 100ms button polling rate
