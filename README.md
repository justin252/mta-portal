# mta-portal

Real-time NYC subway arrivals + weather on a 64x32 RGB LED matrix ([Adafruit MatrixPortal M4](https://learn.adafruit.com/adafruit-matrixportal-m4)). Auto-cycles between L train (Graham Av), G train (Metropolitan Av), and current weather. Buttons jump to a specific train screen.

## Setup

1. Install CircuitPython 10 on the board.
2. Create `settings.toml` on the CIRCUITPY drive with `CIRCUITPY_WIFI_SSID` and `CIRCUITPY_WIFI_PASSWORD`.
3. Install the libraries: `circup install -r device-requirements.txt`.
4. On your computer: `make setup`, then `make deploy` with the board on a USB data cable.

## Usage

Display auto-cycles **L train (4s) → G train (4s) → weather (3s)**. The weather screen joins once the first weather fetch succeeds.

- **Arrivals**: gold numbers are live. Dim numbers are over 90s old (network trouble). `Loading` and `Offline` mean no data yet; `No trains` means the API lists none.
- **Weather**: an icon for the condition (sun or moon, partly cloudy day or night, cloud, fog, drizzle, rain, showers, sleet, snow, storm), the condition, the temperature, and today's high and low (`H:61 L:45`).

- **UP**: art mode on/off (pixel art, a new piece every 10s: rooftop-disco train, Manhattan skyline, Williamsburg Bridge, pizza rat)
- **DOWN**: back to the transit screens (sports mode will live here)

## Architecture

- `code.py`: bootstrap that runs `app.py` and reloads the board instead of halting on an error
- `app.py`: main loop: buttons, screen cycle, fetches, display, watchdog
- `layout.py`: screen layout shared by the board and the simulator
- `logic.py`, `recovery.py`, `weather.py`: pure, desktop-tested logic
- `diag.py`: serial diagnostics (screen dumps, status, fault injection)
- `safemode.py`: automatic recovery from safe mode (brownouts)
- `simulate_display.py`: desktop renderer, pixel-exact against the board
- `tools/portal.py`: deploy and verify against the real board
- `*-dashboard.bmp`, `weather-*.bmp`, `art-*.bmp`: bitmaps, made by `generate_train_bitmap.py`, `generate_weather_bitmaps.py`, `generate_art.py`

Data sources: [wheresthefuckingtrain.com](https://www.wheresthefuckingtrain.com/) API (wraps MTA GTFS-RT) and [Open-Meteo](https://open-meteo.com/) current conditions and today's high/low (no key required).

## Design Decisions

**Polling (30s)**: MTA feeds update ~30s. Each fetch blocks the main loop for about a second (no threading in CircuitPython), so the screen showing during a fetch stays up about a second longer; polling more often would make that worse.

**Server time**: minutes are computed against the train API's own HTTP `Date` header, so the board needs no clock sync and no timezone setting.

**Error recovery**: a failed fetch retries after 5, 15, then 30s, rejoining WiFi if the link is down. If nothing succeeds for 3 minutes, the board reboots, which is the one reset that reliably clears ESP32 and socket state. Nothing ever gives up: outages just mean another retry or reboot until the network is back. Any unexpected exception soft-reloads the board instead of halting it, a 16s hardware watchdog catches hangs, and `safemode.py` resets out of safe mode after a brownout. Details: [docs/failure-modes.md](docs/failure-modes.md).

## Verification

```bash
make test        # desktop: logic, recovery policy, layout rules, simulator vs board captures
make test-live   # real train and weather APIs
make deploy      # copy changed files to the board, wait for the first good fetch
make verify      # show every design on the board, diff each against the simulator
make sim         # render every design (scenarios.py) to out/sim/, no board needed
make review      # walk every design on the real sign, Enter for the next; `make live` to go back
make inject      # drop WiFi, crash, hang: each must recover on its own
make soak        # optional: watch the board for hours (halts, data gaps, crashes, unexplained resets)
make sim LED=1   # render screens as the LEDs show them (2 bits per color channel)
```

`make verify` reads the board's actual framebuffer over USB serial, so "the simulator says it fits" and "the sign shows it" are the same claim. Serial log prefixes: `[BOOT]`, `[OK]`, `[ERR]`, `[RECONNECT]`, `[RESET]`, `[CRASH]`, `[WEATHER]`, `[BTN]`.
