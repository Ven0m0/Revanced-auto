.PHONY: help lint format check install-tools clean

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

lint: ## Run all linters (check only)
	@./scripts/lint.sh

format: ## Run all formatters (fix issues)
	@./scripts/lint.sh --fix

check: lint ## Alias for lint

install-tools: ## Install all required linting/formatting tools
	@echo "Installing linting and formatting tools..."
	@echo ""
	@echo "==> Python tools (ruff)"
	pip install --upgrade ruff
	@echo ""
	@echo "==> Shell tools"
	@command -v shellcheck >/dev/null 2>&1 || (echo "Please install shellcheck: https://github.com/koalaman/shellcheck#installing" && exit 1)
	@command -v shfmt >/dev/null 2>&1 || (echo "Installing shfmt..." && go install mvdan.cc/sh/v3/cmd/shfmt@latest)
	@command -v shellharden >/dev/null 2>&1 || (echo "Installing shellharden..." && cargo install shellharden)
	@echo ""
	@echo "==> YAML tools"
	pip install --upgrade yamllint
	@command -v yamlfmt >/dev/null 2>&1 || (echo "Installing yamlfmt..." && go install github.com/google/yamlfmt/cmd/yamlfmt@latest)
	@echo ""
	@echo "==> TOML tools (taplo)"
	@command -v taplo >/dev/null 2>&1 || (echo "Installing taplo..." && cargo install taplo-cli --locked)
	@echo ""
	@echo "==> Web tools (biome)"
	@command -v biome >/dev/null 2>&1 || (echo "Installing biome..." && npm install -g @biomejs/biome)
	@echo ""
	@echo "✓ All tools installed successfully!"

clean: ## Clean build artifacts
	@./build.sh clean

# Build targets
build: ## Build all apps from config.toml
	@./build.sh config.toml

# Testing targets
test-syntax: ## Check bash script syntax
	@echo "Checking bash syntax..."
	@for f in scripts/lib/*.sh build.sh extras.sh utils.sh check-env.sh scripts/*.sh; do \
		bash -n "$$f" && echo "$$f: OK"; \
	done

# Pre-commit setup
setup-pre-commit: ## Set up pre-commit hooks
	@pip install pre-commit
	@pre-commit install
	@echo "✓ Pre-commit hooks installed"
