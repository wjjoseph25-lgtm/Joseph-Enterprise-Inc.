.PHONY: install ephe run test check docker-build

install:
	python -m pip install -r requirements.txt

ephe:
	python download_ephe.py

run:
	uvicorn app.main:app --reload --port 8000

test:
	python download_ephe.py
	python -m pytest -q

check:
	python -m compileall -q app tests download_ephe.py
	python download_ephe.py
	python -m pytest -q

docker-build:
	docker build -t orora-ephemeris .
