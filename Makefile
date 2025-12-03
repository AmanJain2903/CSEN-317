.PHONY: help install test test-unit test-demos test-load test-stress test-all clean docker-build docker-up docker-down docker-logs run-node1 run-node2 run-node3 client

help:
	@echo "Distributed Chat System - Make Commands"
	@echo ""
	@echo "Development:"
	@echo "  make install       - Install dependencies"
	@echo "  make test          - Run unit tests only"
	@echo "  make test-all      - Run ALL tests (unit, demos, load, stress)"
	@echo "  make clean         - Clean temporary files"
	@echo ""
	@echo "Testing (requires nodes running):"
	@echo "  make test-unit     - Run unit tests (fast, no nodes needed)"
	@echo "  make test-demos    - Run demo scenarios (8 scenarios)"
	@echo "  make test-load     - Run load tests (performance)"
	@echo "  make test-stress   - Run stress tests (system limits)"
	@echo "  make test-coverage - Run tests with coverage report"
	@echo ""
	@echo "Local Nodes:"
	@echo "  make run-node1     - Start node 1"
	@echo "  make run-node2     - Start node 2"
	@echo "  make run-node3     - Start node 3"
	@echo "  make client        - Start client (connects to node 1)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build  - Build Docker images"
	@echo "  make docker-up     - Start cluster with docker compose"
	@echo "  make docker-down   - Stop cluster"
	@echo "  make docker-logs   - View cluster logs"
	@echo ""

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v -k "not demo_ and not load_test and not stress_test"

test-unit:
	pytest tests/ -v -k "not demo_ and not load_test and not stress_test"

test-demos:
	@echo "[WARNING] Ensure all 3 nodes are running before starting demos!"
	@echo "Press Ctrl+C to cancel, or wait 5 seconds to continue..."
	@sleep 5
	python tests/run_all_tests.py --demos

test-load:
	@echo "[WARNING] Ensure all 3 nodes are running before starting load tests!"
	@echo "Press Ctrl+C to cancel, or wait 5 seconds to continue..."
	@sleep 5
	python tests/load_test.py

test-stress:
	@echo "[WARNING] Ensure all 3 nodes are running before starting stress tests!"
	@echo "Press Ctrl+C to cancel, or wait 5 seconds to continue..."
	@sleep 5
	python tests/stress_test.py

test-all:
	python tests/run_all_tests.py --all

test-coverage:
	pytest tests/ --cov=src --cov-report=html --cov-report=term -k "not demo_ and not load_test and not stress_test"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage
	rm -rf data/logs/*.jsonl

run-node1:
	python -m src.node --config configs/node1.yml

run-node2:
	python -m src.node --config configs/node2.yml

run-node3:
	python -m src.node --config configs/node3.yml

client:
	python -m src.client_tui --host 127.0.0.1 --port 5001

docker-build:
	cd deploy && docker compose build

docker-up:
	cd deploy && docker compose up

docker-up-d:
	cd deploy && docker compose up -d

docker-down:
	cd deploy && docker compose down

docker-down-v:
	cd deploy && docker compose down -v

docker-logs:
	cd deploy && docker compose logs -f

docker-restart:
	cd deploy && docker compose restart

format:
	black src/ tests/

lint:
	pylint src/

setup-dev:
	python -m venv venv
	@echo "Virtual environment created. Activate with:"
	@echo "  source venv/bin/activate  (Linux/Mac)"
	@echo "  venv\\Scripts\\activate     (Windows)"
	@echo "Then run: make install"

