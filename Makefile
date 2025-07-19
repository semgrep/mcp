# Semgrep MCP Makefile
# Development and deployment commands for the Semgrep MCP server

.PHONY: help install install-dev run test test-claude-integration lint format typecheck clean configure-claude-code check-claude-config dev-setup pre-commit-install check dev build

# Default target
help:
	@echo "Semgrep MCP - Security Analysis Server"
	@echo ""
	@echo "Available commands:"
	@echo "  install            Install project dependencies"
	@echo "  install-dev        Install with development dependencies"
	@echo "  run               Run the MCP server"
	@echo "  test              Run the test suite"
	@echo "  test-claude-integration  Run Claude Code integration tests"
	@echo "  lint              Check code style with ruff"
	@echo "  format            Format code with ruff"
	@echo "  typecheck         Run type checking with ruff"
	@echo "  configure-claude-code  Configure Claude Code integration globally"
	@echo "  check-claude-config    Check Claude Code configuration status"
	@echo "  pre-commit-install     Install pre-commit hooks"
	@echo "  clean             Clean build artifacts and cache"
	@echo "  dev-setup         Setup development environment"
	@echo "  check             Run all quality checks"
	@echo "  dev               Run development workflow"
	@echo "  build             Build distribution packages"

# Installation targets
install:
	@echo "Installing Semgrep MCP dependencies..."
	uv sync

install-dev:
	@echo "Installing Semgrep MCP with development dependencies..."
	uv sync --extra dev

# Run the server
run:
	@echo "Starting Semgrep MCP server..."
	uv run semgrep-mcp

# Testing targets
test:
	@echo "Running test suite..."
	uv run pytest tests/ -v

test-claude-integration:
	@echo "Running Claude Code integration tests..."
	uv run pytest tests/integration/test_claude_code_integration.py -v

# Code quality targets
lint:
	@echo "Checking code style with ruff..."
	uv run ruff check src/ tests/

format:
	@echo "Formatting code with ruff..."
	uv run ruff format src/ tests/
	uv run ruff check --fix src/ tests/

typecheck:
	@echo "Running type checking with ruff..."
	uv run ruff check src/ --select=F

# Configuration
configure-claude-code:
	@echo "Configuring Claude Code integration for user scope..."
	@python3 scripts/configure_semgrep_mcp.py

check-claude-config:
	@echo "Checking Claude Code MCP configuration..."
	@echo "Listing all configured MCP servers:"
	@claude mcp list
	@echo ""
	@echo "Getting details for semgrep-mcp server:"
	@claude mcp get semgrep-mcp || echo "❌ semgrep-mcp server not found"

# Pre-commit setup
pre-commit-install:
	@echo "Installing pre-commit hooks..."
	uv run pre-commit install
	@echo "✅ Pre-commit hooks installed"
	@echo "   Hooks will run automatically on git commit"
	@echo "   To run manually: uv run pre-commit run --all-files"

# Maintenance
clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

# Development workflow
dev-setup: install-dev pre-commit-install
	@echo "Development environment setup complete!"
	@echo "Run 'make run' to start the server"
	@echo "Run 'make test' to run tests"
	@echo "Pre-commit hooks are installed and will run on git commit"

# Build and quality check
check: lint typecheck test test-claude-integration
	@echo "All checks passed!"

# Complete development workflow
dev: format check
	@echo "Development workflow complete!"

# Release preparation
build:
	@echo "Building distribution packages..."
	uv build