# API reference

Interactive OpenAPI documentation is served at `/docs` and the schema at `/openapi.json` while the backend runs.
Base path: `/api/v1`. All examples below are real responses captured from the running service (ids shortened or replaced).

> This service provides preliminary health triage guidance. It does not diagnose medical conditions and does not replace a
> qualified healthcare professional.

## Authentication

Patients are anonymous. `POST /conversations` returns a random 256 bit `access_token` once. Send it on every later call:

```
X-Conversation-Token: <access_token>
```

Only a keyed hash of the token is stored. A missing, wrong, foreign or expired token all return the same `401`, so conversation
ids cannot be probed. Tokens expire with the conversation (default 72 hours). There are no user accounts, see `docs/security.md`.

## Errors

```json
{"error": {"code": "unauthorized", "message": "Missing or invalid conversation token.", "error_id": "9c1f0a7d2b44"}}
```

| Status | `code` | Meaning |
|---|---|---|
| 401 | `unauthorized` | Token missing, wrong or conversation expired |
| 409 | `conversation_limit`, `triage_not_ready` | Message cap reached, or no final result yet |
| 413 | `payload_too_large` | JSON over 64 KB or audio over 5 MB |
| 415 | `unsupported_media` | Audio type not allowed or file signature does not match |
| 422 | `validation_failed` | Invalid body. The message lists field names only, never the submitted values |
| 429 | `rate_limited` | Too many requests |
| 503 | `provider_unavailable` | Speech or voice provider missing or failing. Typing still works |
| 500 | `internal_error` | Unexpected. Quote `error_id` to the operator. No stack trace is returned |

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness and dependency flags |
| GET | `/meta` | Versions, languages, limits, provider flags, emergency contact |
| POST | `/conversations` | Start a conversation |
| GET | `/conversations/{id}` | Messages, state summary, pending question |
| DELETE | `/conversations/{id}` | Delete the conversation and all stored messages (204) |
| POST | `/conversations/{id}/audio/transcribe` | Multipart upload `audio`, optional `language_hint`. Returns a transcript to review |
| POST | `/conversations/{id}/extract` | Preview entity extraction. Does not change state |
| POST | `/conversations/{id}/messages` | Submit a patient message or reviewed transcript |
| POST | `/conversations/{id}/answers` | Same, but names the question being answered (`question_id`) |
| GET | `/conversations/{id}/next-question` | The question awaiting an answer, or `null` |
| POST | `/conversations/{id}/triage` | Evaluate now with what is known (missing safety info yields `urgent`) |
| GET | `/conversations/{id}/triage` | Latest final result, or `409 triage_not_ready` |
| POST | `/conversations/{id}/speech` | MP3 of the latest assistant message |

`/metrics` (Prometheus text) is outside the versioned API. In production it requires `METRICS_TOKEN` as a bearer token.

## Example: start a conversation

`POST /api/v1/conversations` with `{"language": "hi"}`, response `201`:

```json
{
  "conversation_id": "3f8a1c52-7d0e-4b0a-9a55-6c1d2e8b9f10",
  "access_token": "<shown once>",
  "language": "hi",
  "assistant_message": "नमस्ते। मैं स्वास्थ्य जानकारी में मदद करने वाला सहायक हूं, डॉक्टर नहीं। आपको क्या तकलीफ है? कृपया अपनी बात बताइए।",
  "disclaimer": "यह टूल केवल शुरुआती स्वास्थ्य सलाह देता है। यह किसी बीमारी की पहचान नहीं करता और योग्य डॉक्टर की जगह नहीं ले सकता।",
  "expires_in_hours": 72,
  "emergency_contact": {
    "number": "EXAMPLE-NUMBER",
    "label": ""
  }
}
```

## Example: first message and follow up question

`POST /api/v1/conversations/{id}/messages`

```json
{"text": "Do din se bukhar hai aur sar bhaari lag raha hai.", "source": "text"}
```

Response `200` (abridged):

```json
{
  "conversation_id": "3f8a1c52-7d0e-4b0a-9a55-6c1d2e8b9f10",
  "triage_status": "information_gathering",
  "assistant_message": "Kya abhi saans lene mein dikkat, seene mein dard, ya behoshi jaisa kuch ho raha hai?",
  "question": {
    "question_id": "screen_critical_a",
    "kind": "yes_no",
    "text": "Kya abhi saans lene mein dikkat, seene mein dard, ya behoshi jaisa kuch ho raha hai?",
    "required_for_triage": true
  },
  "state": {
    "language": "hi-Latn",
    "detected_language": "hi-Latn",
    "age_years": null,
    "symptoms": [
      {
        "name": "fever",
        "original_text": "bukhar",
        "normalized_concept": "fever",
        "confidence": 0.92,
        "requires_clarification": false,
        "duration_days": 2.0,
        "severity": "unknown"
      },
      {
        "name": "head heaviness",
        "original_text": "sar bhaari",
        "normalized_concept": "head heaviness",
        "confidence": 0.82,
        "requires_clarification": true,
        "duration_days": 2.0,
        "severity": "unknown"
      }
    ],
    "missing_information": [
      "screen_critical_a",
      "screen_critical_b",
      "age"
    ],
    "red_flags": [],
    "followup_count": 1
  }
}
```

The patient's wording is preserved in `original_text`, the interpretation in `normalized_concept`, and the ambiguous phrase
is flagged with `requires_clarification`. The reply language follows the patient (here romanised Hindi).

## Example: emergency override

After `{"text": "mujhe saans lene mein bahut dikkat ho rahi hai"}` the response contains `"triage_status": "emergency"`,
`"question": null` and:

```json
{
  "assessment_id": "b7c3a0de-5f21-4e8a-8d6b-0a9c4f7e1d22",
  "triage_level": "emergency",
  "reason_codes": [
    "breathing_difficulty"
  ],
  "recommended_action": "seek_emergency_care_now",
  "confidence": null,
  "requires_human_review": false,
  "engine_version": "1.0.0",
  "rules_version": "2026.1",
  "patient": {
    "level": "emergency",
    "language": "hi-Latn",
    "headline": "Turant ilaaj ki zaroorat ho sakti hai",
    "message": "Aapne jo bataya uske aadhar par aapko abhi turant chikitsa sahayata ki zaroorat ho sakti hai. Kripya der na karein.",
    "next_steps": [
      "Nazdeeki aspatal ya swasthya kendra turant pahunchein, ya ambulance bulayein.",
      "Aapatkaleen number: EXAMPLE-NUMBER",
      "Mareez ko akela na chhodein.",
      "Agar sambhav ho to koi aur gaadi chalaye, mareez khud gaadi na chalaye."
    ],
    "warning_signs": [
      "Saans lene mein bahut dikkat",
      "Seene mein dard",
      "Behoshi ya bahut zyada uljhan",
      "Chehra tedha hona, ek taraf kamzori ya bolne mein dikkat",
      "Daura ya jhatke",
      "Bahut zyada khoon behna",
      "Chehre, honth ya gale mein sujan",
      "Lagataar ulti ya paani na pi paana"
    ],
    "disclaimer": "Yeh tool sirf shuruaati swasthya salah deta hai. Yeh kisi bimari ki pehchan nahi karta aur yogya doctor ki jagah nahi le sakta.",
    "emergency_contact": {
      "number": "EXAMPLE-NUMBER",
      "label": ""
    }
  }
}
```

`emergency_contact` comes from `EMERGENCY_CONTACT_NUMBER`. When it is not configured it is `null` and the guidance tells the
patient to contact local emergency services without inventing a number. `confidence` is always `null`.

## Example: voice

```
POST /api/v1/conversations/{id}/audio/transcribe   (multipart: audio=@recording.webm, language_hint=hi)
```

```json
{"text": "Do din se bukhar hai", "language": "hi", "confidence": 0.87, "low_confidence": false,
  "usable": true, "warnings": [], "duration_seconds": null}
```

When `usable` is false the client should ask the patient to correct the text or speak again. The patient always reviews the
transcript before it is submitted as a message with `"source": "voice"`.
