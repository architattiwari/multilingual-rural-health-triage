# Multilingual Rural Health Triage Assistant

Voice first, low bandwidth preliminary health triage for people who describe symptoms in Hindi, Hindi mixed with English,
rural colloquial Hindi and Marwari influenced Hindi.

> **Medical safety notice.** This tool provides preliminary health triage guidance. It does not diagnose medical conditions and
> does not replace a qualified healthcare professional. The triage rules in this repository are an engineering baseline that
> has **not been clinically validated**. Do not use it for real patient care until clinicians have reviewed and approved the
> rules, text and deployment.

## Problem statement

People in rural areas often live far from a clinic, describe illness in dialect rather than medical terms, and have limited
literacy or connectivity. Deciding "is this an emergency, do I need a doctor soon, or can it wait" is the hardest step and is
often made late. This project helps with that single decision, in the patient's own words and language, and never claims more.

## Product objectives

Understand a spoken or typed description, ask only the questions that matter, apply deterministic safety rules, explain the
next step in simple language, escalate dangerous symptoms at once, and never diagnose or falsely reassure.

## Key features

* Browser microphone recording and upload with validation, plus typing, in a large button, high contrast, mobile first interface
* Hindi, romanised Hindi, English and Marwari influenced input, with code mixing detection
* Rule based entity extraction with original wording, normalised meaning, confidence and clarification of ambiguous phrases
* Question engine driven by clinical state with priorities, one question at a time, emergency screening first
* Deterministic, versioned triage rules with an audit trail. LLMs can never set or lower a level
* Optional LLM assisted extraction with schema validation, evidence checking and prompt injection defences
* Replaceable providers for speech to text, LLM, text to speech and translation
* Read aloud with server voice and device voice fallback. Fully usable without voice
* Privacy by default: no accounts, no stored audio, expiring conversations, one click deletion
* Structured logs, metrics, health checks, OpenAPI docs, Docker setup, 175 backend tests plus frontend tests

## Screenshots



## Architecture

See `docs/architecture.md` for the full diagram, trust boundaries and data flow. In short:

```
Frontend → API (auth, limits) → Conversation service
   → audio validation → speech to text (optional)
   → language detection → rule extractor (+ optional validated LLM)
   → clinical state → red flag rules → deterministic triage engine
   → question engine (if more information is needed)
   → localization (reviewed templates) → frontend (+ optional speech)
```

## Technology stack

| Area | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, httpx |
| Database | PostgreSQL 16 (production), SQLite (development and tests) |
| Frontend | TypeScript, Vite, no UI framework (22 KB JavaScript, 8 KB gzipped) |
| AI providers | OpenAI compatible speech to text and text to speech, Anthropic Messages API for the LLM (all optional) |
| Quality | pytest, ruff, mypy, vitest |
| Packaging | Docker, Docker Compose, nginx |

## Project structure

```
backend/app/        api, services, domain, clinical (rules, triage, questions), ai, speech, database, models, core
backend/tests/      unit, integration, safety, security
backend/evaluation/ dataset.jsonl and run_eval.py
frontend/src/       dom, i18n, api, recorder, speech, screens
database/migrations Alembic environment and versions
docs/               architecture, api, ai-pipeline, triage-methodology, security, privacy, deployment
scripts/            verify.sh, secret_scan.sh, purge_expired.py
```

## Installation

Requirements: Python 3.12 or newer, Node.js 20 or newer, optionally Docker.

```bash
unzip multilingual-rural-health-triage.zip && cd multilingual-rural-health-triage
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-dev.txt
(cd frontend && npm ci)
cp .env.example .env
```

## Environment variables

`.env.example` lists every variable the code reads, with comments. Essentials:

| Variable | Purpose |
|---|---|
| `APP_ENV` | `development`, `test` or `production`. Production demands a strong secret and PostgreSQL |
| `DATABASE_URL` | SQLAlchemy URL. `sqlite:///./triage.db` for local, `postgresql+psycopg://...` otherwise |
| `APP_SECRET_KEY` | 32 or more random characters. Keys the token hashes |
| `EMERGENCY_CONTACT_NUMBER` | Region specific. Left empty, the app tells users to contact local services and shows no number |
| `SPEECH_API_KEY`, `LLM_API_KEY`, `TTS_API_KEY` | Optional. Empty disables that provider |

## Database setup

```bash
cd backend
alembic upgrade head          # creates all tables (uses DATABASE_URL from .env)
```

## Local development

Backend, from `backend/`:

```bash
uvicorn app.main:app_factory --factory --reload --port 8000
```

Frontend, from `frontend/`:

```bash
npm run dev                   # http://localhost:5173, proxies /api to localhost:8000
```

With no provider keys the app runs with typed input and the rule engine. Voice and read aloud become available when you set the keys.

## Running the tests

```bash
./scripts/verify.sh           # lint, types, all backend tests, evaluation gate, frontend tests and build, secret scan
# or individually
cd backend && pytest -q && ruff check app tests evaluation && mypy app
cd frontend && npm test && npm run build
```

## API documentation

Run the backend and open `http://localhost:8000/docs`. Real example requests and responses are in `docs/api.md`.

## Speech processing pipeline

Browser records mono Opus (about 16 kbps, 60 s limit), the API validates type, signature, size and duration, a
`SpeechToTextProvider` transcribes, and the patient reviews and corrects the transcript before sending it. Details and limits
including Marwari and accent caveats are in `docs/ai-pipeline.md`.

## NLP and LLM pipeline

Rules first, optional LLM second, and the deterministic engine last. The LLM only adds validated findings. See `docs/ai-pipeline.md`.

## Medical entity extraction

Symptoms, severity words, sudden onset, duration, age, temperature, pregnancy, sex terms and long term conditions are extracted
with negation handling. Each symptom keeps `original_text`, `normalized_concept`, `confidence` and `requires_clarification`.

## Follow up engine

`backend/app/clinical/questions.py`. Critical screening is always first, then age and condition specific safety questions, then at most two
optional questions. Unclear answers are asked once more and then lead to a cautious result.

## Triage methodology

Three levels (`emergency`, `urgent`, `non_urgent`) from versioned rules listed in `docs/triage-methodology.md`.

## Safety architecture

Deterministic engine, sticky red flags, emergency override that stops questioning, non urgent only after screening, no
probability claims, LLM add only with evidence checks, fixed reviewed patient text, never "you are safe", and an audit record
of rules, versions and information used for every assessment.

## Privacy considerations

No accounts or contact details, audio not stored, conversations expire (72 h default) and can be deleted on demand, third party
data flows are documented. See `docs/privacy.md`. No compliance claim is made.

## Security considerations

See `docs/security.md` for the control matrix, test coverage and residual risks.

## Deployment

See `docs/deployment.md`. Docker Compose files are included.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Microphone button missing | Browser lacks `MediaRecorder`, or the page is not on HTTPS or localhost. Typing still works |
| "Voice is not available" | `SPEECH_API_KEY` not set, or the provider is failing. Check `/api/v1/health` and the logs for `speech provider failure` |
| 401 on every call | Token missing or expired. Start a new conversation |
| Production start fails with `APP_SECRET_KEY` error | Use 32 or more characters and PostgreSQL |
| `alembic` cannot find the database | Run from `backend/` and check `DATABASE_URL` |
| CORS error in the browser | Add the frontend origin to `CORS_ORIGINS` |
| 429 responses | Rate limit reached. Adjust `RATE_LIMIT_*` if legitimate |

## Limitations

* **Not clinically validated.** Rules and thresholds need clinician review. Patient wording needs native speaker review.
* **Marwari support is partial.** A small starter vocabulary and Hindi speech recognition. Dialect variation is wide.
* **Accuracy on real rural speech is unmeasured.** The evaluation set is small, hand written and was used during development.
* **Offline.** Only the cached welcome and safety information work offline. Triage needs the server. There is no on device AI.
* **Described person.** Triage assumes the person described is the patient. Relationships are not modelled.
* **Docker files unbuilt and browser UI untested here.** They were authored but the environment had no Docker daemon or real
  browser. Frontend logic is covered by jsdom unit tests, type checking and a production build only.
* **Not tested against live providers.** Provider integrations are tested with fakes and request shaping only, since no credentials were available.
* In process rate limiting suits one replica.

## Future improvements

Clinician reviewed rule set and sign off workflow, annotated recorded speech corpus for evaluation, dialect specific
recognition, more regional languages with reviewed templates, authenticated clinician review console, shared rate limiting
store, end to end browser tests, offline symptom checklist, and SMS or IVR channels for feature phones.

## Contribution guidelines

1. Open an issue for any change to triage rules or patient text and involve a clinician reviewer.
2. Keep clinical logic in `backend/app/clinical`, free of network and database imports.
3. Every rule change needs a unit test, a safety test, a `RULES_VERSION` bump and a clean `./scripts/verify.sh`.
4. Never log patient text, tokens or provider payloads. Never commit credentials.
5. Prefer small, reviewed pull requests. Explain why in comments, not what.

## License

MIT for the software, see `LICENSE`. The license does not extend any warranty of clinical safety.
