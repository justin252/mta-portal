# mta-portal

Real-time NYC subway arrivals on a 64x32 RGB LED matrix ([Adafruit MatrixPortal M4](https://learn.adafruit.com/adafruit-matrixportal-m4)). Shows next 3 arrivals in each direction for L (Graham Av — Manhattan / Canarsie) or G (Metropolitan Av — Queens / Church Av), toggled via hardware buttons.

## Setup

1. Create `settings.toml` on CIRCUITPY drive with `CIRCUITPY_WIFI_SSID` and `CIRCUITPY_WIFI_PASSWORD`
2. Copy [CircuitPython Bundle](https://circuitpython.org/libraries) libs to `/lib`: `adafruit_matrixportal`, `adafruit_display_text`, `adafruit_bitmap_font`, `adafruit_datetime`, `adafruit_debouncer`
3. Deploy to board:
```bash
cp boot.py code.py *.bmp /Volumes/CIRCUITPY/ && cp -r fonts /Volumes/CIRCUITPY/
```

Board auto-reloads on file save.

## Usage

- **UP** button: L train
- **DOWN** button: G train

## Architecture

- `code.py` — main loop: fetch → parse → display (on-device only)
- `logic.py` — pure functions for time parsing/filtering (desktop-testable)
- `boot.py` — enables filesystem writes for persistent train state
- `*-dashboard.bmp` — pre-rendered line name/color bitmaps

Data source: [wheresthefuckingtrain.com](https://www.wheresthefuckingtrain.com/) API (wraps MTA GTFS-RT).

## Design Decisions

**Polling (30s)**: MTA feeds update ~30s — polling matches that cadence. Display shows whole minutes, so sub-30s precision doesn't help. Each fetch blocks the main loop (no threading in CircuitPython), so less polling = better button responsiveness.

**Error recovery**: Network errors are common on microcontrollers. On failure, the board tries reconnecting WiFi, then resets the ESP32 chip, then reboots the entire board after 3 consecutive failures — recovering automatically without manual intervention.

## Testing

```bash
cd /tmp && python3 -m pytest /path/to/mta-portal/test_logic.py -v
```

Serial debug: `screen /dev/tty.usbmodem* 115200` — logs prefixed with `[OK]`, `[ERR]`, `[RECONNECT]`, `[RESET]`, `[BTN]`.
