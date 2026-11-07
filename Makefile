.PHONY: up down test traffic latency errors kind smoke
up:
	bash scripts/init-env.sh
	docker compose up -d --build
down:
	docker compose down
test:
	python -m pytest -q
	docker run --rm -v "$(CURDIR):/work" -w /work --entrypoint promtool prom/prometheus:v3.5.0 test rules tests/prometheus/alerts.test.yml tests/prometheus/recording.test.yml
traffic:
	python3 scripts/traffic.py baseline --duration 600
latency:
	bash scripts/inject-latency.sh --duration 600
errors:
	bash scripts/inject-errors.sh --duration 600
kind:
	bash scripts/kind-up.sh
smoke:
	python3 scripts/smoke.py
