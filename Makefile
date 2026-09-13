.PHONY: help install run-bot run-webapp test lint up down logs clean

help:
	@echo "Available commands:"
	@echo "  make install     - Install Python dependencies"
	@echo "  make run-bot     - Run aiogram bot locally"
	@echo "  make run-webapp  - Run FastAPI WebApp server locally"
	@echo "  make test        - Run automated unit tests with pytest"
	@echo "  make up          - Start all docker containers"
	@echo "  make down        - Stop all docker containers"
	@echo "  make logs        - Tail docker container logs"
	@echo "  make clean       - Remove cached files and pyc"

install:
	pip install -r requirements.txt

run-bot:
	python main.py

run-webapp:
	uvicorn webapp_server:app --host 0.0.0.0 --port 8080 --reload

test:
	pytest tests/ -v

up:
	docker-compose up -d --build

down:
	docker-compose down

logs:
	docker-compose logs -f

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage
