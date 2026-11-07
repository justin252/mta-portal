# Verification loop for the MTA Portal sign. `make help` lists targets.
# Desktop targets need no board; deploy/verify/status/logs/inject/soak need it on a USB data cable.
PY ?= .venv/bin/python
PORTAL = $(PY) tools/portal.py
LED_FLAG = $(if $(LED),--led)

.PHONY: help setup test test-live sim deploy verify review show live scenarios goldens status logs inject soak

help: ## List targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-z-]+:.*## / {printf "  %-10s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Create .venv with the dev dependencies
	python3 -m venv .venv
	.venv/bin/pip install -q -r requirements-dev.txt

test: ## Desktop checks: logic, recovery policy, layout rules, simulator vs board captures
	$(PY) -m pytest

test-live: ## Contract checks against the real train and weather APIs
	$(PY) -m pytest -m live

sim: ## Render every scenario to out/sim/ plus sheet.png, no board needed (LED=1: LED colors)
	$(PY) simulate_display.py --all out/sim $(LED_FLAG)

deploy: ## Copy changed files to the board, watch it boot to its first good fetch
	$(PORTAL) deploy

verify: ## Show every scenario on the board, diff each against the simulator
	$(PORTAL) verify --all

review: ## Design review on the real sign: one scenario at a time, Enter for the next
	$(PORTAL) review

show: ## Hold one scenario on the sign: make show NAME=weather-rain
	$(PORTAL) show $(NAME)

live: ## End a held scenario: back to live data
	$(PORTAL) live

scenarios: ## List the scenarios
	$(PORTAL) scenarios

goldens: ## Capture every scenario from the board as a reference image (after a design change)
	$(PORTAL) goldens

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
