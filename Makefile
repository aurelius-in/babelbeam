.PHONY: setup dev migrate seed lint typecheck test test-e2e provider-check billing-test build

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
ifeq ($(wildcard $(ROOT)/.venv/bin/python),)
PY := python3
else
PY := $(ROOT)/.venv/bin/python
endif
export PYTHONPATH := $(ROOT)/services/backend:$(ROOT)/services/worker:$(ROOT)/packages/runtime

setup:
	python3 -m venv $(ROOT)/.venv
	$(ROOT)/.venv/bin/python -m pip install --upgrade pip
	$(ROOT)/.venv/bin/python -m pip install -e $(ROOT)/packages/runtime -r $(ROOT)/services/backend/requirements.txt -r $(ROOT)/services/worker/requirements.txt
	cd $(ROOT)/apps/web && npm install

dev:
	docker compose up -d postgres redis mailpit
	bash $(ROOT)/scripts/dev.sh

migrate:
	cd $(ROOT)/services/backend && PYTHONPATH=$(PYTHONPATH) $(PY) -m alembic upgrade head

seed:
	PYTHONPATH=$(PYTHONPATH) $(PY) $(ROOT)/scripts/seed.py

lint:
	PYTHONPATH=$(PYTHONPATH) $(PY) -m ruff check $(ROOT)/services $(ROOT)/packages $(ROOT)/scripts
	cd $(ROOT)/apps/web && npm run lint

typecheck:
	PYTHONPATH=$(PYTHONPATH) $(PY) -m mypy
	cd $(ROOT)/apps/web && npm run typecheck

test:
	PYTHONPATH=$(PYTHONPATH) $(PY) -m pytest -q
	cd $(ROOT)/apps/web && npm test

test-e2e:
	cd $(ROOT)/apps/web && npm run test:e2e

provider-check:
	PYTHONPATH=$(PYTHONPATH) $(PY) $(ROOT)/scripts/provider_check.py

billing-test:
	PYTHONPATH=$(PYTHONPATH) $(PY) $(ROOT)/scripts/billing_test.py

build:
	cd $(ROOT)/apps/web && npm run build
