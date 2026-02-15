# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

CircuitPython app for an Adafruit MatrixPortal M4 LED matrix displaying real-time NYC MTA L train arrival times. Fetches from `wheresthefuckingtrain.com` API, shows next northbound (Manhattan) and southbound (Canarsie) arrivals at stop `L11`.

## Platform

- **Hardware**: Adafruit MatrixPortal M4 + 64x32 RGB LED matrix
- **Runtime**: CircuitPython (not CPython — no pip, no stdlib, limited memory)
- **No build step** — code runs directly on the microcontroller

## Development

**Deploy**: Copy `code.py`, `l-dashboard.bmp`, and `fonts/` to the CIRCUITPY USB drive. Board auto-runs `code.py` on save (auto-reload).

**Debug**: Connect serial console (e.g. `screen /dev/tty.usbmodem* 115200` or Mu editor) to see `print()` output and errors.

**WiFi config**: Board reads `settings.toml` on CIRCUITPY drive for `CIRCUITPY_WIFI_SSID` and `CIRCUITPY_WIFI_PASSWORD`. This file is on-device only, not in the repo.

**Libraries**: Adafruit CircuitPython Bundle libs required on device in `/lib`: `adafruit_matrixportal`, `adafruit_display_text`, `adafruit_bitmap_font`, `adafruit_datetime`. Install by copying `.mpy` files from the bundle.

## Architecture

- `code.py` — hardware-dependent main loop: fetch → parse → display. Runs on-device only.
- `logic.py` — pure functions (`get_arrival_in_minutes_from_now`, `filter_arrivals`, `format_arrival_pair`). Desktop-testable with stdlib `datetime`.
- Polls API every `UPDATE_DELAY` (15s), syncs NTP every `SYNC_TIME_DELAY` (30s)
- Filters arrivals < `MINIMUM_MINUTES_DISPLAY` (9 min) — too soon to catch
- Resets microcontroller after `ERROR_RESET_THRESHOLD` (3) consecutive failures
- WiFi reconnection: on error, checks `esp.is_connected`, attempts `connect_AP`, falls back to `esp.reset()`
- Structured serial logging: `[OK]`, `[ERR]`, `[RECONNECT]`, `[RESET]` prefixes

## Testing

**Unit tests** (run from `/tmp` to avoid `code.py` shadowing Python's `code` module):
```bash
cd /tmp && python3 -m pytest /path/to/mta-portal/test_logic.py -v
```
Run before every commit.

**Serial monitoring**: `screen /dev/tty.usbmodem* 115200` — watch structured logs during operation.

**Fault injection checklist** (for network changes):
1. Disable router WiFi 60s → verify `[RECONNECT]` logs, board recovers
2. Disable WiFi 5+ min → verify `[RESET]` after threshold, board reboots and recovers
3. Block API endpoint → verify `[ERR]` logs distinct from WiFi errors

## CircuitPython Constraints

- No threading, async limited — single main loop only
- Limited RAM (~200KB) — avoid large data structures, prefer `.mpy` compiled libs
- `adafruit_datetime` is a subset of Python's `datetime` (no full `timezone` support)
- Network calls can block and raise `RuntimeError` on connectivity issues
