# Reddit Ghost Publisher Makefile

.PHONY: help install install-dev test test-unit test-integration test-e2e test-load
.PHONY: lint format security-check clean build run run-dev stop logs
.PHONY: db-migrate db-upgrade db-downgrade docker-build docker-run docker-stop
.PHONY: monitoring-up monitoring-down

# Default target
help:
	@echo "Reddit Ghost Publisher - Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  install          Install production dependencies"
	@echo "  install-dev      Install development dependencies"
	@echo "  run-dev          Run development server"
	@echo "  format           Format code with black and isort"
	@echo "  lint             Run linting checks"
	@echo "  security-check   Run security checks"
	@echo ""
	@echo "Testing:"
	@echo "  test             Run all tests"
	@echo "  test-unit        Run unit tests"
	@echo "  test-integration Run integration tests"
	@echo "  test-e2e         Run end-to-end tests"
	@echo "  test-load        Run load tests"
	@echo ""
	@echo "Docker:"
	@echo "  build            Build Docker images"
	@echo "  run              Run with docker-compose"
	@echo "  stop             Stop docker-compose services"
	@echo "  logs             Show docker-compose logs"
	@echo ""
	@echo "Database:"
	@echo "  db-migrate       Create new migration"
	@echo "  db-upgrade       Apply migrations"
	@echo "  db-downgrade     Rollback migrations"
	@echo ""
	@echo "Monitoring:"
	@echo "  monitoring-up    Start monitoring stack"
	@echo "  monitoring-down  Stop monitoring stack"
	@echo ""
	@echo "Utilities:"
	@echo "  clean            Clean temporary files"

# Development
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt -r requirements-dev.txt

run-dev:
	uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload

format:
	black .
	isort .

lint:
	flake8 .
	mypy app/ workers/

security-check:
	bandit -r app/ workers/
	safety check

# Testing
test: test-unit test-integration

test-unit:
	pytest tests/unit/ -v --cov=app --cov=workers --cov-report=html

test-integration:
	pytest tests/integration/ -v

test-e2e:
	pytest tests/e2e/ -v

test-load:
	locust -f tests/load/locustfile.py --headless -u 10 -r 2 -t 60s --host=http://localhost:8000

# Docker
build:
	docker-compose build

run:
	docker-compose up -d

stop:
	docker-compose down

logs:
	docker-compose logs -f

# Database
db-migrate:
	alembic revision --autogenerate -m "$(MSG)"

db-upgrade:
	alembic upgrade head

db-downgrade:
	alembic downgrade -1

# Monitoring
monitoring-up:
	docker-compose up -d prometheus grafana

monitoring-down:
	docker-compose stop prometheus grafana

# Utilities
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf dist/
	rm -rf build/