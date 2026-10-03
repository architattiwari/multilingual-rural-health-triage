# Security

## Design summary

| Concern | Control | Where |
|---|---|---|
| Authentication | Anonymous patients. Random 256 bit conversation token, keyed hash stored, constant time compare, expiry | `core/security.py`, `ConversationService.authorize` |
| Authorization | Every conversation route depends on `current_conversation`. Missing, wrong, foreign or expired tokens give an identical 401 | `api/deps.py` |
| Input validation | Pydantic request models with `extra="forbid"`, length limits, enum fields, path id length | `api/schemas.py` |
| Text hygiene | Unicode NFC, removal of zero width and bidi override characters, control characters stripped, length cap | `sanitize_text` |
| SQL injection | SQLAlchemy ORM with bound parameters only. No string built SQL | `database/repository.py` |
| XSS | Frontend builds DOM with `textContent` and has no `innerHTML`. API returns JSON with `nosniff` and a `default-src 'none'` CSP. nginx sets a strict CSP | `frontend/src/dom.ts`, `nginx.conf` |
| CSRF | No cookies are used. The token is a custom header, which cross site forms cannot set. CORS allows only configured origins | `main.py` |
| Upload safety | Allow listed content type plus file signature check, 5 MB cap enforced while streaming, minimum size, WAV duration check, audio never written to disk | `speech/audio.py`, `BodyLimitMiddleware` |
| Request size | 64 KB for JSON, audio limit plus framing for uploads. Enforced on declared and streamed length | `api/middleware.py` |
| Rate limiting | Per client sliding window. Stricter limit on endpoints that call paid providers. Per conversation message cap | `core/security.py`, `api/deps.py` |
| Prompt injection | Constant system prompt, delimited untrusted text, heuristic screen that keeps suspicious text away from the model, strict output validation, evidence check, add only semantics, deterministic engine decides | `ai/`, `looks_like_prompt_injection` |
| Error disclosure | Central handlers return an error code and id. No stack traces, no echoed input in validation errors | `main.py` |
| Secrets | Environment only, `SecretStr` everywhere, never logged, production refuses weak `APP_SECRET_KEY` and SQLite | `core/config.py` |
| Logging | JSON logs of identifiers and timings. A formatter drops keys such as `text`, `token`. The httpx logger is silenced because it prints URLs | `core/logging.py` |
| Headers | `nosniff`, frame deny, no referrer, `no-store`, CSP, microphone permission policy | `RequestContextMiddleware`, `nginx.conf` |
| Containers | Non root user, no secrets in images, health checks | `backend/Dockerfile` |

## Why there are no user accounts

The workflow targets people with limited digital literacy and sometimes shared phones. Registration would add a barrier and
collect identity data the triage does not need. Instead each conversation is its own capability: possession of the token is the
authorization. The consequences are documented: anyone who has the token can read that conversation, the token cannot be
recovered if lost, and there is no cross device history. If a deployment needs clinician review of conversations, add
authenticated staff accounts with role based access, password hashing (Argon2id), short lived sessions and audit of reads. Do not
reuse the patient token for that.

The frontend keeps the token in `sessionStorage` so a refresh does not lose the conversation. It is cleared when the tab closes
or the conversation is deleted.

## Tests

`backend/tests/security/` covers authorization on every endpoint, uniform 401s, malformed and oversized bodies, invalid
fields, Unicode abuse, oversized and spoofed audio, prompt injection, rate limits, error disclosure, secret exposure in
settings, OpenAPI and logs, production configuration checks, metrics authentication and CORS.

## Residual risks and recommended hardening

* The rate limiter and metrics are per process. Add gateway level limits for multiple replicas.
* The prompt injection screen is heuristic. The real protection is architectural, because the model cannot decide urgency.
* Transport security is not handled by the app. Terminate HTTPS at the reverse proxy and redirect HTTP.
* Add dependency and image scanning to CI (for example `pip-audit`, `npm audit`, container scanning).
* Penetration testing and a threat model review by a security professional have not been performed.
* Third party AI providers receive patient speech and text. Review their terms, regions and retention before deployment.
