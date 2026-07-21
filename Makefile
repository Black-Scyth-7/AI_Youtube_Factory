# AI YouTube Factory — developer task runner.
.DEFAULT_GOAL := help
.PHONY: help setup dev test lint format docker-up docker-down clean seed

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Install all dependencies (Node + Python)
	@bash scripts/setup.sh

dev: ## Run the full stack locally via Docker
	@bash scripts/dev.sh

test: ## Run all tests (Node + Python)
	@bash scripts/test.sh

lint: ## Lint all code
	@bash scripts/lint.sh

format: ## Auto-format all code
	@bash scripts/format.sh

docker-up: ## Start the Docker stack
	docker compose up --build

docker-down: ## Stop the Docker stack
	docker compose down

clean: ## Remove build artifacts and caches
	@bash scripts/reset.sh

seed: ## Seed placeholder data (no-op in Phase 01)
	@bash scripts/seed.sh
