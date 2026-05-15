# Repository Guidelines

## Project Structure & Module Organization
This repo contains a small QR generation system split by deployment unit. `frontend/` holds the static Nginx-served UI (`index.html`, `script.js`, `style.css`). `gateway/` contains the Flask API gateway and its tests in `test_app.py`. `qr-service/` contains the QR worker and its tests. Root-level `docker-compose.yml` wires the services together

## Build, Test, and Development Commands
Use Docker first, since the images run tests during build.

- `docker build -t gateway-ci ./gateway` builds the gateway image and runs its pytest suite.
- `docker build -t qr-service-ci ./qr-service` builds the worker image and runs its pytest suite.
- `docker compose up --build` starts RabbitMQ, the worker, gateway, and frontend.
- `pytest gateway qr-service` runs both Python test modules from the repo root.
- `pytest gateway\test_app.py` or `pytest qr-service\test_app.py` runs a single service test file.

Create the external Docker network before `docker compose up` if it does not exist: `docker network create observability-shared`.

## Coding Style & Naming Conventions
Follow the existing style in each area: Python uses 4-space indentation, snake_case, and small module-level functions; JavaScript uses 4-space indentation with camelCase variables; CSS keeps kebab-case custom properties and selectors. Keep Flask routes explicit (`/api/generate`, `/api/status/<task_id>`), and prefer descriptive test names such as `test_generate_qr_gateway_success`. No formatter or linter is configured yet, so keep changes consistent with surrounding code.

## Testing Guidelines
Tests use `pytest` and `pytest-mock`; root `pytest.ini` disables the cache provider. Add or update tests in the same service directory as the code you touch. Cover happy-path and failure-path behavior for broker calls, HTTP responses, and QR processing. Keep test files named `test_*.py`.

## Commit & Pull Request Guidelines
Recent commits use short, imperative summaries like `add github action to test is containers are build`. Keep commit subjects concise, lowercase if practical, and focused on one change. For pull requests, include a short description, the affected service(s), local test coverage (`pytest`, `docker build`, or `docker compose up`), and screenshots when frontend behavior changes.

## Configuration Notes
Runtime settings are environment-driven: `RABBITMQ_HOST`, `QR_REQUEST_QUEUE`, `QR_RESULT_QUEUE`, and `METRICS_PORT`. Do not hardcode service endpoints; preserve the Docker service names used by `docker-compose.yml` and `frontend/nginx.conf`.
