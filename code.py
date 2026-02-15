import time
import microcontroller
from board import NEOPIXEL
import displayio
import adafruit_display_text.label
from adafruit_datetime import datetime
from adafruit_bitmap_font import bitmap_font
from adafruit_matrixportal.matrix import Matrix
from adafruit_matrixportal.network import Network

STOP_ID = 'L11'
DATA_SOURCE = 'https://api.wheresthefuckingtrain.com/by-id/%s' % (STOP_ID,)
DATA_LOCATION = ["data"]
UPDATE_DELAY = 15
SYNC_TIME_DELAY = 30
BACKGROUND_IMAGE = 'l-dashboard.bmp'
ERROR_RESET_THRESHOLD = 3

def get_arrival_in_minutes_from_now(now, date_str):
    train_date = datetime.fromisoformat(date_str).replace(tzinfo=None)
    return round((train_date-now).total_seconds()/60.0)

def filter_arrivals(now, time_strings):
    minutes = [get_arrival_in_minutes_from_now(now, t) for t in time_strings]
    return [m for m in minutes if m >= 0]

def format_arrival_triple(minutes_list):
    v0 = str(minutes_list[0]) if len(minutes_list) > 0 else '-'
    v1 = str(minutes_list[1]) if len(minutes_list) > 1 else '-'
    v2 = str(minutes_list[2]) if len(minutes_list) > 2 else '-'
    return v0, v1, v2

def get_arrival_times():
    stop_trains = network.fetch_data(DATA_SOURCE, json_path=(DATA_LOCATION,))
    stop_data = stop_trains[0]
    northbound_trains = [x['time'] for x in stop_data.get('N', [])]
    southbound_trains = [x['time'] for x in stop_data.get('S', [])]

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
    print("[RECONNECT] wifi_connected=False, attempting esp.connect_AP...")
    try:
        import os
        ssid = os.getenv("CIRCUITPY_WIFI_SSID")
        password = os.getenv("CIRCUITPY_WIFI_PASSWORD")
        esp.connect_AP(ssid, password)
        print("[RECONNECT] success")
    except Exception as e:
        print("[RECONNECT] connect_AP failed: %s - resetting ESP" % (e,))
        try:
            esp.reset()
            time.sleep(2)
            import os
            ssid = os.getenv("CIRCUITPY_WIFI_SSID")
            password = os.getenv("CIRCUITPY_WIFI_PASSWORD")
            esp.connect_AP(ssid, password)
            print("[RECONNECT] success after ESP reset")
        except Exception as e2:
            print("[RECONNECT] ESP reset failed: %s" % (e2,))

# --- Display setup ---
matrix = Matrix()
display = matrix.display
network = Network(status_neopixel=NEOPIXEL, debug=False)

# --- Drawing setup ---
group = displayio.Group()
bitmap = displayio.OnDiskBitmap(open(BACKGROUND_IMAGE, 'rb'))
colors = [0x444444, 0xDD8000]  # [dim white, gold]

font = bitmap_font.load_font("fonts/5x7.bdf")
text_lines = [
    displayio.TileGrid(bitmap, pixel_shader=getattr(bitmap, 'pixel_shader', displayio.ColorConverter())),
    adafruit_display_text.label.Label(font, color=colors[0], x=18, y=4, text="Manhattan"),
    adafruit_display_text.label.Label(font, color=colors[1], x=18, y=11, text="-"),
    adafruit_display_text.label.Label(font, color=colors[0], x=18, y=20, text="Canarsie"),
    adafruit_display_text.label.Label(font, color=colors[1], x=18, y=27, text="-"),
]
for x in text_lines:
    group.append(x)
display.root_group = group

error_counter = 0
last_time_sync = None
while True:
    try:
        if last_time_sync is None or time.monotonic() > last_time_sync + SYNC_TIME_DELAY:
            network.get_local_time()
            last_time_sync = time.monotonic()
        arrivals = get_arrival_times()
        update_text(*arrivals)
        error_counter = 0
    except (ValueError, RuntimeError, OSError, BrokenPipeError, ConnectionError) as e:
        print("[ERR] %s: %s - wifi_connected=%s" % (type(e).__name__, e, network._wifi.esp.is_connected))
        error_counter = error_counter + 1
        if error_counter > ERROR_RESET_THRESHOLD:
            print("[RESET] error_counter=%d, resetting microcontroller" % error_counter)
            microcontroller.reset()
        attempt_wifi_reconnect()

    time.sleep(UPDATE_DELAY)
