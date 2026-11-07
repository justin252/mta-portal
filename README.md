# mta-portal

Real-time NYC subway arrivals + weather on a 64x32 RGB LED matrix ([Adafruit MatrixPortal M4](https://learn.adafruit.com/adafruit-matrixportal-m4)). Auto-cycles between L train (Graham Av), G train (Metropolitan Av), and current weather. Buttons jump to a specific train screen.

## Setup

1. Install CircuitPython 10 on the board.
2. Create `settings.toml` on the CIRCUITPY drive with `CIRCUITPY_WIFI_SSID` and `CIRCUITPY_WIFI_PASSWORD`.
3. Install the libraries: `circup install -r device-requirements.txt`.
4. On your computer: `make setup`, then `make deploy` with the board on a USB data cable.

## Usage

Display auto-cycles **L train → G train → weather**, 2 seconds each. The weather screen joins once the first weather fetch succeeds.

The weather screen shows an icon for the current condition (sun, cloud, fog, rain, snow, storm), the condition name, the current temperature, and today's high and low (`H:61 L:45`).

- **Short press UP / DOWN**: jump to the L / G screen
- **Long press (1s) either button**: toggle full-screen pixel art train view
- **Any press in train view**: return to cycling

## Architecture

- `code.py`: bootstrap that runs `app.py` and reloads the board instead of halting on an error
- `app.py`: main loop: buttons, screen cycle, fetches, display, watchdog
- `layout.py`: screen layout shared by the board and the simulator
- `logic.py`, `recovery.py`, `weather.py`: pure, desktop-tested logic
- `diag.py`: serial diagnostics (screen dumps, status, fault injection)
- `safemode.py`: automatic recovery from safe mode (brownouts)
- `simulate_display.py`: desktop renderer, pixel-exact against the board
- `tools/portal.py`: deploy and verify against the real board
- `*-dashboard.bmp`, `weather-*.bmp`, `train.bmp`: bitmaps

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
make verify      # capture every screen (and every weather icon) from the board, diff against the simulator
make demo        # show every weather scenario on the sign with fake readings; `make live` to go back
make inject      # drop WiFi, crash, hang: each must recover on its own
make soak        # optional: watch the board for hours (halts, data gaps, crashes, unexplained resets)
make sim LED=1   # render screens as the LEDs show them (2 bits per color channel)
```

`make verify` reads the board's actual framebuffer over USB serial, so "the simulator says it fits" and "the sign shows it" are the same claim. Serial log prefixes: `[BOOT]`, `[OK]`, `[ERR]`, `[RECONNECT]`, `[RESET]`, `[CRASH]`, `[WEATHER]`, `[BTN]`.
