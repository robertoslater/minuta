.PHONY: help install dev dev-frontend dev-backend build clean test lint

SHELL := /bin/zsh
PROJECT_ROOT := $(shell pwd)
BACKEND_DIR := $(PROJECT_ROOT)/backend
FRONTEND_DIR := $(PROJECT_ROOT)/frontend
AUDIOCAP_DIR := $(PROJECT_ROOT)/audiocap
CONFIG_DIR := $(HOME)/.minuta
VENV := $(BACKEND_DIR)/.venv

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: install-backend install-frontend install-audiocap install-config ## Full installation
	@echo "\n✅ Installation complete. Run 'make dev' to start."

install-backend: ## Install Python backend
	cd $(BACKEND_DIR) && uv sync

install-frontend: ## Install Next.js frontend
	cd $(FRONTEND_DIR) && npm install

install-audiocap: ## Build Swift audio capture
	cd $(AUDIOCAP_DIR) && swift build -c release
	@cp $(AUDIOCAP_DIR)/.build/release/audiocap $(BACKEND_DIR)/.venv/bin/audiocap 2>/dev/null || true

install-config: ## Create default config
	@mkdir -p $(CONFIG_DIR)
	@if [ ! -f $(CONFIG_DIR)/config.toml ]; then \
		cp $(PROJECT_ROOT)/config.example.toml $(CONFIG_DIR)/config.toml; \
		echo "Created $(CONFIG_DIR)/config.toml"; \
	fi

dev: ## Start all services (backend + frontend)
	@echo "Starting Minuta..."
	@make dev-backend &
	@make dev-frontend &
	@wait

dev-backend: ## Start Python backend
	cd $(BACKEND_DIR) && uv run uvicorn minuta.server.app:create_app --factory --host 127.0.0.1 --port 8741 --reload

dev-frontend: ## Start Next.js frontend
	cd $(FRONTEND_DIR) && npm run dev

build-audiocap: ## Build Swift audiocap (release)
	cd $(AUDIOCAP_DIR) && swift build -c release

test: test-backend ## Run all tests

test-backend: ## Run Python tests
	cd $(BACKEND_DIR) && uv run pytest -v

lint: lint-backend lint-frontend ## Lint all code

lint-backend: ## Lint Python
	cd $(BACKEND_DIR) && uv run ruff check .

lint-frontend: ## Lint frontend
	cd $(FRONTEND_DIR) && npm run lint

clean: ## Clean build artifacts
	cd $(AUDIOCAP_DIR) && swift package clean 2>/dev/null || true
	rm -rf $(FRONTEND_DIR)/.next
	rm -rf $(BACKEND_DIR)/.venv
