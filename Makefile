# Minions Test & Coverage Makefile

.PHONY: test test-unit test-contract test-integration test-channel test-channel-contract coverage-full clean dev dev-server dev-build

# Python path
PYTHON := python
PYTEST := python -m pytest

# Default: run all tests
test:
	$(PYTEST) tests/ -v --tb=short -q

# Unit tests only
test-unit:
	$(PYTEST) tests/unit/ -v --tb=short

# Contract tests (interface compliance)
test-contract:
	$(PYTEST) tests/contract/ -v --tb=short

# Integration tests
test-integration:
	$(PYTEST) tests/integration/ -v --tb=short

# Full coverage (all modules)
coverage-full:
	$(PYTEST) tests/unit/ tests/integration/ -v \
		--cov=src/minions \
		--cov-report=term-missing \
		--cov-report=html

# Check contract coverage for all channels
check-contracts:
	$(PYTHON) scripts/check_channel_contracts.py

# Clean generated files
clean:
	rm -rf htmlcov/ .pytest_cache/
	rm -f coverage.xml coverage-sa.xml .coverage

# Quick check (fast feedback)
quick:
	$(PYTEST) tests/unit/ -x -q --tb=line

# Channel-specific tests
test-channel:
	@echo "Running Channel unit tests..."
	$(PYTEST) tests/unit/channels/ -v --tb=short

test-channel-contract:
	@echo "Running Channel contract tests..."
	$(PYTEST) tests/contract/channels/ -v --tb=short

# BaseChannel core unit tests (optional, not enforced)
test-base-core:
	$(PYTEST) tests/unit/channels/test_base_core.py -v

# ─── Development ───────────────────────────────────────────────────────────────
# Start backend (FastAPI :8088) + frontend Vite dev server (:5173) together.
# HMR: edit files under console/src and see changes instantly in the browser
# at http://localhost:5173 — no rebuild, no restart, no browser-cache issues.
# Requires macOS/Linux with built-in trap to stop both on Ctrl+C.
dev:
	@echo "Starting backend (:8088) + Vite dev server (:5173)..."
	@echo "Open http://localhost:5173  (Ctrl+C to stop both)"
	@trap 'kill 0' INT; \
	minions app & BACKEND=$$!; \
	cd console && npm run dev & FRONTEND=$$!; \
	wait $$BACKEND $$FRONTEND

# Start only the Vite dev server (assumes backend already running on :8088).
dev-server:
	@echo "Vite dev server on http://localhost:5173 (proxy /api -> :8088)"
	cd console && npm run dev

# Production-style rebuild of the console bundle into console/dist.
dev-build:
	cd console && npm run build
