# mta-portal

Real-time NYC subway arrivals + weather on a 64x32 RGB LED matrix ([Adafruit MatrixPortal M4](https://learn.adafruit.com/adafruit-matrixportal-m4)). Auto-cycles between L train (Graham Av), G train (Metropolitan Av), and current weather. Buttons jump to a specific train screen.

## Setup

1. Create `settings.toml` on CIRCUITPY drive with `CIRCUITPY_WIFI_SSID` and `CIRCUITPY_WIFI_PASSWORD`
2. Copy [CircuitPython Bundle](https://circuitpython.org/libraries) libs to `/lib`: `adafruit_matrixportal`, `adafruit_display_text`, `adafruit_bitmap_font`, `adafruit_datetime`, `adafruit_debouncer`
3. Deploy to board:
```bash
cp boot.py code.py logic.py weather.py *.bmp /Volumes/CIRCUITPY/ && cp -r fonts /Volumes/CIRCUITPY/
```

Board auto-reloads on file save.

## Usage

Display auto-cycles: **L train → G train → weather → repeat** (10s per screen).

- **Short press UP**: jump to L train screen
- **Short press DOWN**: jump to G train screen
- **Long press (1s) either button**: toggle full-screen pixel art train view
- **Short press in train view**: return to cycling
- Cycling resumes automatically after button press

## Architecture

- `code.py` — main loop: fetch → parse → display (on-device only)
- `logic.py` — pure functions for time parsing/filtering (desktop-testable)
- `weather.py` — pure functions for NWS weather parsing (desktop-testable)
- `simulate_display.py` — desktop display simulator (outputs scaled PNG)
- `boot.py` — enables filesystem writes for persistent train state
- `*-dashboard.bmp` — pre-rendered line name/color bitmaps
- `weather-*.bmp` — weather icon bitmaps (sun/cloud/rain/snow/storm/fog)
- `train.bmp` — full-screen pixel art subway car bitmap (rooftop disco scene)

Data sources: [wheresthefuckingtrain.com](https://www.wheresthefuckingtrain.com/) API (wraps MTA GTFS-RT), [NWS forecast API](https://api.weather.gov/) (no key required).

## Design Decisions

**Polling (30s)**: MTA feeds update ~30s — polling matches that cadence. Display shows whole minutes, so sub-30s precision doesn't help. Each fetch blocks the main loop (no threading in CircuitPython), so less polling = better button responsiveness.

**Error recovery**: Network errors are common on microcontrollers. On failure, the board tries reconnecting WiFi, then resets the ESP32 chip, then reboots the entire board after 3 consecutive failures — recovering automatically without manual intervention.

## Display Simulator

Renders the LED matrix output as a PNG on desktop (requires Pillow):
```bash
python3 simulate_display.py                          # L train, placeholder times
python3 simulate_display.py --line G --north 2,7,15 --south 4,9,20
python3 simulate_display.py --weather --condition sun --temp 72
```

## Testing

```bash
cd /tmp && python3 -m pytest ~/code/mta-portal/test_logic.py ~/code/mta-portal/test_simulate_display.py ~/code/mta-portal/test_weather.py -v
```

Serial debug: `screen /dev/tty.usbmodem* 115200` — logs prefixed with `[OK]`, `[ERR]`, `[WEATHER]`, `[RECONNECT]`, `[RESET]`, `[BTN]`.
