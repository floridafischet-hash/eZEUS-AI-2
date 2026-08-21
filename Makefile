PYTHON ?= .venv/bin/python
UV_IMAGE ?= ghcr.io/astral-sh/uv:0.8.15-python3.12-bookworm-slim
HELM_IMAGE ?= alpine/helm:4.2.4
KUBECONFORM_IMAGE ?= ghcr.io/yannh/kubeconform:v0.8.0
HELM_CHART := deploy/helm/ezeus-ai-2
SMOKE_PROJECT ?= ezeus-ai-2-smoke
SMOKE_API_PORT ?= 18082
SMOKE_PAPERLESS_PORT ?= 18083

.PHONY: lock test lint format-check typecheck security helm-check container-smoke smoke-down

lock:
	docker run --rm --user "$(shell id -u):$(shell id -g)" -e UV_CACHE_DIR=/tmp/uv-cache \
		-v "$(CURDIR):/workspace" -w /workspace $(UV_IMAGE) \
		uv pip compile pyproject.toml --universal --python-version 3.12 \
		--generate-hashes --output-file requirements.lock
	docker run --rm --user "$(shell id -u):$(shell id -g)" -e UV_CACHE_DIR=/tmp/uv-cache \
		-v "$(CURDIR):/workspace" -w /workspace $(UV_IMAGE) \
		uv pip compile pyproject.toml --extra dev --universal --python-version 3.12 \
		--generate-hashes --output-file requirements-dev.lock

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

format-check:
	$(PYTHON) -m ruff format --check .

typecheck:
	$(PYTHON) -m mypy apps connectors core plugins webhooks

security:
	$(PYTHON) -m bandit -q -r apps connectors core plugins scripts webhooks
	$(PYTHON) -m pip_audit -r requirements.lock --strict

helm-check:
	docker run --rm -v "$(CURDIR):/work" -w /work $(HELM_IMAGE) lint $(HELM_CHART)
	mkdir -p build
	docker run --rm -v "$(CURDIR):/work" -w /work $(HELM_IMAGE) \
		template ezeus $(HELM_CHART) > build/helm-default.yaml
	docker run --rm -v "$(CURDIR):/work" -w /work $(HELM_IMAGE) \
		template ezeus $(HELM_CHART) -f $(HELM_CHART)/values-production.example.yaml \
		> build/helm-production.yaml
	docker run --rm -v "$(CURDIR):/work" -w /work $(KUBECONFORM_IMAGE) \
		-strict -summary /work/build/helm-default.yaml /work/build/helm-production.yaml

container-smoke:
	HOST_PORT=$(SMOKE_API_PORT) MOCK_PAPERLESS_PORT=$(SMOKE_PAPERLESS_PORT) \
		docker compose -p $(SMOKE_PROJECT) --env-file .env.example up -d --build --wait \
		--wait-timeout 180
	$(PYTHON) scripts/container_smoke_test.py \
		--base-url http://127.0.0.1:$(SMOKE_API_PORT) \
		--mock-url http://127.0.0.1:$(SMOKE_PAPERLESS_PORT)

smoke-down:
	HOST_PORT=$(SMOKE_API_PORT) MOCK_PAPERLESS_PORT=$(SMOKE_PAPERLESS_PORT) \
		docker compose -p $(SMOKE_PROJECT) --env-file .env.example down -v --remove-orphans
