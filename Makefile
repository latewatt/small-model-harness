SHELL := /bin/bash
PY := .venv/bin/python
MODEL ?= qwen3.5:4b-q4_K_M
AGENT ?= v0
SUBSET ?= mini10
BASE_URL ?= http://127.0.0.1:11435/v1
STEPS ?= 16
TASK_TIMEOUT ?= 240
MAX_TOKENS ?= 1024
export MODEL AGENT SUBSET BASE_URL STEPS TASK_TIMEOUT MAX_TOKENS
export UV_CACHE_DIR := $(CURDIR)/.cache/uv
export TMPDIR := $(CURDIR)/.cache/tmp
export PYTHONDONTWRITEBYTECODE := 1

.PHONY: setup setup-terminal bench ablate test serve stop status pull report view doctor terminal-plan
setup:
	mkdir -p .cache/tmp
	if [ ! -x .venv/bin/python ]; then uv venv --python 3.12 .venv; fi
	uv pip sync --python $(PY) requirements.lock

setup-terminal:
	mkdir -p .cache/tmp
	if [ ! -x .venv-harbor/bin/python ]; then uv venv --python 3.12 .venv-harbor; fi
	uv pip sync --python .venv-harbor/bin/python requirements-harbor.lock

bench:
	$(PY) -m harness.cli bench

ablate:
	$(PY) scripts/run_ablation.py

test:
	$(PY) -m pytest --basetemp=.cache/pytest-tmp

serve:
	$(PY) -m harness.server start

stop:
	$(PY) -m harness.server stop

status:
	$(PY) -m harness.server status

pull:
	$(PY) -m harness.server pull

report:
	$(PY) -m harness.cli report

view:
	$(PY) -m harness.cli view

doctor:
	$(PY) -m harness.cli doctor

terminal-plan:
	$(PY) -m harness.terminal --subset "$(SUBSET)"
