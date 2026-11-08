# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

CircuitPython app for an Adafruit MatrixPortal M4 + 64x32 RGB LED matrix. Auto-cycles L train arrivals (Graham Av, stop L11, 4s), G train arrivals (Metropolitan Av, stop G29, 4s) and weather (3s). Train data from `api.wheresthefuckingtrain.com`; weather (condition icon day/night + label, temperature, today's high/low) from Open-Meteo. UP toggles art mode (4 pieces, 10s each); DOWN returns to transit (sports mode will live there). Arrival rows show `Loading`/`Offline`/`No trains`, and dim when data is over 90s old: gold always means live.

## Verification loop (required)

Every change is checked against what the board actually renders, not just against the simulator.

| When | Run | Proves |
|---|---|---|
| Any change | `make test` | logic, recovery policy, layout rules, scenarios, simulator == board captures, deploy list complete |
| API or URL change | `make test-live` | endpoints answer 200 with the expected shape |
| Anything that runs on the board | `make deploy` | copies changed files, waits for the first `[OK]` |
| Design change | `make sim`, then review with the user on the sign (below) | the user approves every affected design on the real LEDs |
| Display change | `make verify` | every scenario in `scenarios.py`, shown on the board, matches the simulator pixel for pixel |
| Network or error-handling change | `make inject` | WiFi drop, crash and hang each recover on their own |
| Optional, after network changes | `make soak MINUTES=480` | hours without halts, data gaps, crashes or unexplained resets |

First time: `make setup`. Outputs go to `out/` (gitignored). Read the PNGs in `out/<screen>/` (`device_x10.png`, `sim_x10.png`, `diff.png`) when `verify` fails.

## Design review on the real sign

Every design state is a scenario in `scenarios.py` with fixed data (`make scenarios` lists them). For any change to how the sign looks:

1. Add or update a scenario for each state the change affects (`test_scenarios.py` fails if a weather condition or screen kind has none).
2. `make sim`: renders every scenario to `out/sim/` plus `sheet.png`, no board needed. For an idea that isn't built yet, render a 64x32 mockup PNG and put it on the sign with `tools/portal.py preview mockup.png` (held like a scenario) before writing the code.
3. `make deploy`, then walk the user through the affected scenarios on the sign one at a time: `tools/portal.py show NAME`, share `out/scenes/NAME/device_x10.png`, wait for the user to say next. (In a terminal: `make review`, Enter for next.)
4. Apply feedback and repeat. Then `make verify` and `make goldens`: reference images in `test_fixtures/device/` are board captures, one PNG per scenario with its state embedded. Commit them with the change.
5. `make live` puts the sign back on live data (any button press, or 10 min, does too).

Never commit raw serial logs (they can contain the WiFi SSID).

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
- `weather.py`: pure: Open-Meteo parsing (current + today's high/low), WMO code → icon/label.
- `screens.py`: pure: data → screen state (bitmap, texts, colors). `app.py` applies states; the simulator renders the same ones.
- `scenarios.py`: every design the sign can show, with fixed data, for review and verification.
- `diag.py`: board-side serial commands, one per line (`s` dump, `i` status, `n` next screen, `a` art, `v NAME` hold a scenario, `r` back to live, `w`/`x`/`h` fault injection) and the NVM event record.
- `safemode.py`: runs if CircuitPython enters safe mode (brownout, core fault); resets automatically after a 20s pause, every time.
- `simulate_display.py`: desktop renderer from `layout.py` + the same fonts/bitmaps. `--led` quantizes to LED colors.
- `generate_*.py`: make the bitmaps. Every lit pixel needs a channel ≥ 64 or it is black on the LEDs (`test_layout.py`); committed BMPs must match the generators (`test_bitmap.py`).
- `tools/portal.py`: host CLI behind the make targets (deploy, verify, show, review, live, goldens, status, logs, inject, soak).
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
