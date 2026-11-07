# Verification loop for the MTA Portal sign. `make help` lists targets.
# Desktop targets need no board; deploy/verify/status/logs/inject/soak need it on a USB data cable.
PY ?= .venv/bin/python
PORTAL = $(PY) tools/portal.py
LED_FLAG = $(if $(LED),--led)

.PHONY: help setup test test-live sim deploy verify status logs inject soak

help: ## List targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-z-]+:.*## / {printf "  %-10s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Create .venv with the dev dependencies
	python3 -m venv .venv
	.venv/bin/pip install -q -r requirements-dev.txt

test: ## Desktop checks: logic, recovery policy, layout rules, simulator vs board captures
	$(PY) -m pytest

test-live: ## Contract checks against the real train and weather APIs
	$(PY) -m pytest -m live

sim: ## Render every screen to out/sim/ (LED=1: only the colors the LEDs can show)
	@mkdir -p out/sim
	$(PY) simulate_display.py --line L $(LED_FLAG) -o out/sim/L.png
	$(PY) simulate_display.py --line G $(LED_FLAG) -o out/sim/G.png
	$(PY) simulate_display.py --weather $(LED_FLAG) -o out/sim/weather.png
	$(PY) simulate_display.py --train $(LED_FLAG) -o out/sim/train_art.png

deploy: ## Copy changed files to the board, watch it boot to its first good fetch
	$(PORTAL) deploy

verify: ## Capture every screen from the board and diff against the simulator
	$(PORTAL) verify --all

status: ## Board status JSON
	$(PORTAL) status

logs: ## Stream the board's serial log
	$(PORTAL) logs

inject: ## Drop WiFi, crash, hang: each must recover on its own
	$(PORTAL) inject wifi
	$(PORTAL) inject crash
	$(PORTAL) inject hang

soak: ## Optional: watch the board for MINUTES (default 480); fails on halts, gaps, crashes, unexplained resets
	$(PORTAL) soak --minutes $(or $(MINUTES),480)
