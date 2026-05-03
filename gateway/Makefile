.PHONY: install test smoke run docker-build docker-run

install:
	python3 -m pip install -r requirements.txt

test:
	pytest

smoke:
	python3 scripts/smoke_gateway.py

run:
	uvicorn app.main:app --reload

docker-build:
	docker build -t ai-deployment-service .

docker-run:
	docker run --rm -p 8000:8000 ai-deployment-service
