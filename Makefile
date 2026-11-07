# Verification loop for the MTA Portal sign. `make help` lists targets.
# Desktop targets need no board; verify needs it on a USB data cable.
PY ?= .venv/bin/python
LED_FLAG = $(if $(LED),--led)

.PHONY: help setup test sim verify

help: ## List targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-z-]+:.*## / {printf "  %-10s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Create .venv with the dev dependencies
	python3 -m venv .venv
	.venv/bin/pip install -q -r requirements-dev.txt

test: ## Desktop checks: simulator vs board captures, layout rules, harness
	$(PY) -m pytest

sim: ## Render every screen to out/sim/ (LED=1: only the colors the LEDs can show)
	@mkdir -p out/sim
	$(PY) simulate_display.py --line L $(LED_FLAG) -o out/sim/L.png
	$(PY) simulate_display.py --line G $(LED_FLAG) -o out/sim/G.png
	$(PY) simulate_display.py --weather $(LED_FLAG) -o out/sim/weather.png
	$(PY) simulate_display.py --train $(LED_FLAG) -o out/sim/train_art.png

verify: ## Capture what the board shows now and diff it against the simulator
	$(PY) tools/portal.py verify
