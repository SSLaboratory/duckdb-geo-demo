.PHONY: dev test build run lint format

dev:
	pip install -e ".[dev]"
	DATA_DIR=/tmp/geodata uvicorn geo_app.main:app --reload

test:
	pytest tests/ -v

build:
	docker build -t duckdb-geo-demo .

run:
	docker run --rm -p 8000:8000 -e READ_ONLY=false -v /tmp/data:/data duckdb-geo-demo

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/
