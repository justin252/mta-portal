# Failure modes

What can go wrong with the sign, what guards against it, and the check that proves the guard works.
"Board" checks need the MatrixPortal on a USB data cable (`make deploy verify inject soak`).

## Network and runtime

| Failure | Before | Guard | Verified by |
|---|---|---|---|
| Non-200 response (`HttpError`) or two socket failures (`OutOfRetries`) | Both subclass plain `Exception`, which `code.py` didn't catch: board halted at "Code done running" until reset | `recovery.attempt()` catches every `Exception` and counts it as a failed fetch | `test_recovery.py` feeds every exception type the board's network stack raises |
| Any other exception escaping the main loop | Same halt | `code.py` is a bootstrap: logs `[CRASH]`, records it in NVM, soft-reloads after 10s | `make inject` (crash): `[CRASH]` → `[BOOT] run=SUPERVISOR_RELOAD` → `[OK]` |
| WiFi drops | Library `connect()` retried 10× with 3s sleeps, freezing the display ~2 min per attempt | One bounded join per fetch attempt (10s max); retries scheduled by the policy so buttons and cycling stay live | `make inject` (wifi): `esp.disconnect()` → `[RECONNECT] ok` → `[OK]`, no reboot |
| Outage, wedged ESP32 or stale sockets | Reboot after 4 consecutive failures | Backoff 5/15/30s; reboot once ≥3 failures and no data for 180s (`recovery.py`). A reboot is the only reset that clears ESP32 and socket state | `test_recovery.py` scenarios: blip and 2 min outage ride through; outage from boot reboots at ~180s; flapping never reboots |
| Hang (a call that never returns) | Frozen display forever | Hardware watchdog, 16s (SAMD51 max), fed every loop pass and before each request | `make inject` (hang): loop stops feeding → hard reset → `[BOOT] run=STARTUP` → `[OK]` |
| Brownout or core fault | Safe mode, waits for the reset button | `safemode.py` resets automatically every time, after a 20s pause that keeps the USB drive usable for fixes | Logic only; a real brownout can't be injected |
| Time sync | Adafruit IO time request every 30s, inside the same `try` as trains: an AIO outage blocked arrivals and caused reboots. Timezone guessed from IP | Minutes computed against the train API's own `Date` header: no clock sync, no timezone, one less request per cycle | `test_logic.py` checks the date math against CPython `datetime`; `make test-live` checks the server clock is within 5 min |
| Weather: 404 + 13 KB JSON | NWS grid `OKX/35,35` is a marine zone (404), so the weather screen never showed; the 13 KB response was too big for a heap where a 4 KB allocation failed | Open-Meteo current conditions + today's high/low (~560 bytes); weather failures retry in 2 min and never count toward a reboot | `make test-live`; `make verify` captures the weather screen |
| Unexplained hard resets | Invisible | `[BOOT]` prints the run reason and the last event saved in NVM. A hard reset with no `[RESET]` before it is the watchdog, a power drop, or the button | `make soak` fails on any unexplained reset |
| Long uptime | `time.monotonic()` is a float that loses precision after days; long-press and the 2s G screen drift after ~2 weeks | Integer milliseconds from `time.monotonic_ns()` | Not automated |
| Memory pressure | 13 KB weather JSON; 4 KB copies failed | Small payloads, `gc.collect()` after each fetch, free memory logged on every `[OK]` | `make soak` reports the min/max free memory |

## Display

| Failure | Guard | Verified by |
|---|---|---|
| Simulator drifts from the board (it drew all text 1px low and its own reference images agreed with it) | Board framebuffer captures are the reference images (`test_fixtures/device/`) | `test_simulate_display.py::test_matches_board_capture`; `make verify` |
| Text clipped at the right edge (3-digit minutes) | Arrivals over 99 min are dropped | `test_layout.py` renders the widest strings with the real BDF metrics |
| Character drawn as a gap (the degree sign in `spleen-5x8.bdf` was blank: "49 F") | Glyph drawn; tests require ink, not just a glyph entry | `test_layout.py` |
| A design that never appears in testing (an icon only shown when it snows) | Every design is a scenario in `scenarios.py`; `tools/portal.py show NAME` holds it on the sign | `make verify` checks every scenario on the board; `test_scenarios.py` fails if a design has none |
| Color invisible on the LEDs (bit depth 2 keeps only the top 2 bits per channel) | Text colors checked | `test_layout.py`; `make sim LED=1` shows art details that go black (about a quarter of the train art's lit pixels) |
| Rows overlapping or off-screen | Rows computed from the Label placement formula | `test_layout.py` |
| Bitmap crowding the text | Train logos keep 2 clear columns before the text at x=18; weather icons keep 5 before x=21 | `test_layout.py` |
| Deploy missing a file (`weather.py` was missing on main) | `tools/portal.py deploy` copies the `DEPLOY` list; a boot crash reloads instead of halting | `test_manifest.py` checks every import and asset is deployed |

## Not covered

- `microcontroller.cpu.reset_reason` is always `UNKNOWN` on SAMD51, so watchdog, power and button resets look the same.
- Physical buttons, LED brightness and color accuracy: check by eye.
- Real brownouts: `safemode.py` can only be exercised by forcing safe mode from the REPL.
