# eval/ — run locveil-bridge CLI & MQTT tests across the target axis.
# Design: ../../locveil-commons/eval/ARCHITECTURE.md (memory: test-run-axes). Mirrors locveil-voice/eval.
#
#   make cli                 # CLI contract tests — no service/broker/hardware (fastest)
#   make mqtt TARGET=local   # MQTT system tests against a local broker + running bridge
#   make mqtt TARGET=wb7     # ... against the WB7 controller's broker (remote)
#   make view                # open the promptfoo results UI
#
# Axis (external to the test YAML):
#   TARGET — where the SUT/broker is → profiles/targets/<TARGET>.env (MQTT_HOST, API_URL)
#
# CONFIG axis (which device/system config the bridge runs) is DEFERRED — see README.

TARGET    ?= local
PROMPTFOO ?= promptfoo

# The backend's uv-managed venv: has the console scripts; eval_commons gets installed here too.
# Code root is backend/ (pyproject lives there), so cwd for the CLI provider is ../backend.
VENV_BIN := $(abspath ../backend)/.venv/bin
export PROMPTFOO_PYTHON := $(VENV_BIN)/python
export PATH := $(VENV_BIN):$(PATH)

include profiles/targets/$(TARGET).env
export MQTT_HOST MQTT_PORT API_URL

.DEFAULT_GOAL := help
.PHONY: help setup cli mqtt view clean

help:
	@sed -n 's/^#   //p' $(MAKEFILE_LIST) | head -5
	@echo ""
	@echo "TARGET=$(TARGET)  ->  MQTT_HOST=$(MQTT_HOST)  API_URL=$(API_URL)"

setup:                        ## install the shared providers into the backend venv (uv)
	uv pip install --python $(PROMPTFOO_PYTHON) -e ../../locveil-commons/eval

cli:                          ## CLI contract tests (console scripts) — no service/broker needed
	$(PROMPTFOO) eval -c cli.promptfooconfig.yaml

mqtt:                         ## MQTT system tests (needs a broker + running bridge)
	$(PROMPTFOO) eval -c mqtt.promptfooconfig.yaml -o results-mqtt-$(TARGET).json

view:                         ## open the promptfoo results UI
	$(PROMPTFOO) view

clean:                        ## remove generated result files
	rm -f results-*.json
