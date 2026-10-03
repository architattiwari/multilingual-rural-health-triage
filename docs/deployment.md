# Deployment

This guide describes a sensible production setup. It does not make the deployment medically or legally certified. See
`docs/privacy.md` and `docs/triage-methodology.md` for the obligations that remain.

## Checklist

1. **Clinical sign off** of the rules and patient text by a qualified clinician and native speakers.
2. **HTTPS only.** Browsers refuse microphone access on plain HTTP except on localhost. Terminate TLS at a reverse proxy or load balancer and redirect HTTP.
3. **PostgreSQL 16** with a dedicated user. SQLite is rejected when `APP_ENV=production`.
4. **Secrets** from a secret manager or orchestrator, injected as environment variables. Required: `APP_SECRET_KEY` (32 or more characters, random), database credentials. Optional: `SPEECH_API_KEY`, `LLM_API_KEY`, `TTS_API_KEY`, `METRICS_TOKEN`.
5. **Emergency numbers.** Set `EMERGENCY_CONTACT_NUMBER`, `EMERGENCY_CONTACT_LABEL` and, if appropriate, `CRISIS_HELPLINE_NUMBER` for the region. The app never invents one.
6. **CORS.** Set `CORS_ORIGINS` to the exact frontend origin. If frontend and API share an origin through the provided nginx, no cross origin traffic exists.
7. **Proxy headers.** Set `TRUST_PROXY_HEADERS=true` only behind a proxy you control that overwrites `X-Forwarded-For`, otherwise clients can spoof rate limit identity.
8. **Migrations** with `alembic upgrade head` as a one off job before starting new replicas.
9. **Retention.** Schedule `scripts/purge_expired.py` hourly and set `CONVERSATION_RETENTION_HOURS`.

## Docker Compose (single host)

```bash
cp .env.example .env
# edit .env: POSTGRES_PASSWORD, APP_SECRET_KEY, emergency contact, provider keys, APP_ENV=production
docker compose up --build -d
```

Frontend: `http://localhost:8080` (nginx serves the static build and proxies `/api`). API docs: `http://localhost:8000/docs`.
Put a TLS terminating proxy in front for anything beyond local use. The compose file is development oriented: it publishes the
backend port directly and uses one container per service.

> The Docker files were written to the repository's conventions but were **not built in the authoring environment** because it
> had no Docker daemon. Build them in CI before relying on them.

## Without Docker

```bash
cd backend && pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app_factory --factory --host 0.0.0.0 --port 8000 --proxy-headers
cd ../frontend && npm ci && npm run build   # serve frontend/dist with any static server and proxy /api to the backend
```

## Logging and monitoring

* Logs are JSON on stdout with `request_id`, `component`, `level` and timings. Ship them with your platform agent. They contain no patient text or tokens.
* `GET /api/v1/health` for liveness and dependency flags. `degraded` means the database check failed.
* `GET /metrics` (bearer `METRICS_TOKEN`) exposes `http_requests_total`, `http_request_duration_seconds`, `triage_total{level}`,
  `llm_failures_total`, `speech_failures_total`, `tts_failures_total`, `validation_failures_total`, `unhandled_errors_total`,
  `prompt_injection_suspected_total`. Alert on rising speech, LLM and unhandled error counts, and on any change in the emergency share of `triage_total`.

## Scaling

* The API is stateless apart from in process rate limiting and metrics. Add replicas behind a load balancer.
* Provider calls are blocking and run in worker threads. Raise the thread pool or add replicas for higher concurrency.
* Database load is small: a few writes per patient turn.
* Move rate limiting to the gateway or a shared store when running more than one replica.

## Backups and retention

Back up PostgreSQL with point in time recovery. Remember that backups contain conversation text, so encrypt them, restrict
access and rotate them within your retention policy. Deleting a conversation does not remove it from existing backups.

## Security configuration

Run containers as non root (the backend image does), keep the base images patched, scan dependencies in CI, restrict database network
access to the backend, and keep `/metrics` and `/docs` off the public internet if you do not need them (`docs_url` can be disabled in `main.py`).
