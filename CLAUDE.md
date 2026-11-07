# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

CircuitPython app for an Adafruit MatrixPortal M4 + 64x32 RGB LED matrix. Auto-cycles L train arrivals (Graham Av, stop L11), G train arrivals (Metropolitan Av, stop G29) and weather, 2 seconds each. Train data from `api.wheresthefuckingtrain.com`; weather (current condition icon + label, temperature, today's high/low) from Open-Meteo. UP/DOWN buttons jump to L/G; a long press toggles full-screen train art.

## Verification loop (required)

Every change is checked against what the board actually renders, not just against the simulator.

| When | Run | Proves |
|---|---|---|
| Any change | `make test` | logic, recovery policy, layout rules, simulator == board captures, deploy list complete |
| API or URL change | `make test-live` | endpoints answer 200 with the expected shape |
| Anything that runs on the board | `make deploy` | copies changed files, waits for the first `[OK]` |
| Display change | `make verify` | each screen, plus every weather icon via fake readings (`weather.DEMO`), captured from the board matches the simulator pixel for pixel |
| Network or error-handling change | `make inject` | WiFi drop, crash and hang each recover on their own |
| Optional, after network changes | `make soak MINUTES=480` | hours without halts, data gaps, crashes or unexplained resets |

To look at weather scenarios on the sign: `make demo` (fake readings, one per icon/label), then `make live`. Demo mode also ends on any button press or after 10 min.

First time: `make setup`. Outputs go to `out/` (gitignored). Read the PNGs in `out/<screen>/` (`device_x10.png`, `sim_x10.png`, `diff.png`) when `verify` fails.

**Updating board captures**: after an intentional layout change, `make deploy`, then `tools/portal.py verify --all` and copy each `out/<screen>/capture.txt` to `test_fixtures/device/<screen>.txt`. Captures contain only `[FB]` lines; never commit raw serial logs (they can contain the WiFi SSID).

## The formulas (each pinned by a test)

- **Text placement** (`simulate_display.render_text`, matches `adafruit_display_text.Label`): glyph top = `y - bbx_h - bbx_yoff + font_ascent // 2`, x advances by DWIDTH. Fits iff `TEXT_X + sum(dwidth) <= 64`. Tested in `test_layout.py`, `test_simulate_display.py`.
- **LED color**: displayio truncates RGB888 to RGB565, then the Protomatter driver keeps the top `BIT_DEPTH` (2) bits per channel: `level = c8 >> (8 - BIT_DEPTH)`. Channels below 64 are off. `make sim LED=1` shows the result.
- **Minutes**: `round((t_train - t_server) / 60)` using the API's HTTP `Date` header as now; keep 0..99, soonest first, show 3. Epoch math stays in ints (CircuitPython floats have ~22 bits). Tested in `test_logic.py`.
- **Recovery**: retry after 5/15/30s; reboot when ≥3 failures in a row and no data for 180s; watchdog 16s. Tested in `test_recovery.py`.
- **Framebuffer dump**: RGB565 little-endian, one hex row per `[FB]` line (`diag.py`, decoded by `tools/portal.py`).

Failure modes and the guard/test for each: `docs/failure-modes.md`.

## Architecture

- `code.py`: bootstrap. Imports `app`; any exception that escapes is logged (`[CRASH]`), saved to NVM, and the board soft-reloads. Never halts at "Code done running".
- `app.py`: hardware main loop: buttons, screen cycle, fetch, display, watchdog, diag commands.
- `layout.py`: screen layout shared by `app.py` and the simulator (positions, fonts, colors, stations).
- `logic.py`: pure: date math, arrival parsing/formatting.
- `recovery.py`: pure: retry/reboot policy and `attempt()`, the catch-all fetch boundary.
- `weather.py`: pure: Open-Meteo parsing (current + today's high/low), WMO code → icon/label, `DEMO` readings covering every icon.
- `diag.py`: board-side serial commands (`s` dump, `i` status, `n` next screen, `a` art, `c` next fake weather reading, `w`/`x`/`h` fault injection) and the NVM event record.
- `safemode.py`: runs if CircuitPython enters safe mode (brownout, core fault); resets automatically after a 20s pause, every time.
- `simulate_display.py`: desktop renderer from `layout.py` + the same fonts/bitmaps. `--led` quantizes to LED colors.
- `tools/portal.py`: host CLI behind the make targets (deploy, verify, status, logs, demo, inject, soak).
- Serial log prefixes: `[BOOT]`, `[OK]`, `[ERR]`, `[RECONNECT]`, `[RESET]`, `[CRASH]`, `[WEATHER]`, `[BTN]`, `[INJECT]`.

## Board

- CircuitPython 10.0.3. `adafruit_portalbase`, `adafruit_requests`, `adafruit_esp32spi`, `adafruit_connection_manager` and `neopixel` are frozen into the firmware and load before `/lib`. Other libraries: `device-requirements.txt`.
- `settings.toml` on CIRCUITPY (not in the repo): `CIRCUITPY_WIFI_SSID`, `CIRCUITPY_WIFI_PASSWORD`.
- Serial: `/dev/cu.usbmodem*`. Never open it at 1200 baud (that reboots into the bootloader). Only one reader at a time: a running `soak` or `logs` blocks the other commands.
- `microcontroller.cpu.reset_reason` is always `UNKNOWN` on SAMD51; use the `[BOOT]` run reason and NVM `last_event` instead.

## Testing notes

- `pytest.ini` passes `-p no:debugging`: pdb imports the stdlib `code` module, which `code.py` would shadow. Run tests from the repo root.
- Board-only modules (`app.py`, `diag.py`, `code.py`, `safemode.py`) aren't imported by tests; `test_manifest.py` checks their imports resolve on the board, and `make deploy`/`make inject` exercise them.

## CircuitPython constraints

- Single main loop, no threading. Every network call blocks the loop; keep each one inside the 16s watchdog window (`HTTP_TIMEOUT` is per socket operation).
- Free heap is ~55-65 KB after a fetch and fragmented (a 4 KB contiguous allocation has failed). Keep payloads small and avoid large copies.
- One TLS socket at a time on the ESP32; requests to different hosts reuse it in turn.
- `time.monotonic()` loses precision after days of uptime; `app.py` uses integer ms from `time.monotonic_ns()`.
