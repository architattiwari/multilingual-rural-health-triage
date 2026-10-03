# Privacy

> This document describes what the software does. It is not legal advice. The software has **not** been assessed for HIPAA, GDPR,
> India's DPDP Act or any other regime and makes no claim of compliance. Operators carry the obligations listed at the end.

## What is collected and why

| Data | Why | Where stored | Retention |
|---|---|---|---|
| Typed text or reviewed transcript of what the patient says | To understand symptoms | `conversation_messages` | Conversation expiry (default 72 h), or earlier on deletion |
| Structured state: symptoms, durations, age, sex if offered or needed, pregnancy if relevant, long term conditions, temperature | To apply triage rules | `conversations.state_json` | Same |
| Observation log of codes (for example `chest_pain: present`) | Traceability without wording | `clinical_observations` | Same |
| Assessment: level, rule ids, reason codes, versions | Audit of why a result was produced | `triage_assessments` | Same |
| Operational audit events with ids and codes, no wording | Operations and abuse detection | `audit_events` | 90 days, detached from the conversation on deletion |
| Hashed access token and timestamps | Authorization and expiry | `conversations` | Same as conversation |
| Audio | Transcription only | **Not stored** by this application | Held in memory during the request |

Name, phone number, address and national identifiers are never requested. A patient can still type them in free text. They would
be stored in `conversation_messages` like any other text, so the interface should discourage it and operators should treat the
table as sensitive.

## Who can access it

There are no staff accounts. The patient's device holds the token. Operators with database access can read stored messages.
Restrict that access, use encrypted disks and backups, and log operator reads in your own environment.

## Deletion

* Patient: `DELETE /conversations/{id}` (button "Delete my conversation") removes the conversation, messages, observations and
  assessments. Audit events are kept with the conversation id removed.
* Automatic: `scripts/purge_expired.py` deletes expired conversations. Schedule it hourly. Expired conversations are already
  refused by the API.
* Backups keep copies until they rotate. Set backup retention to match your policy.

## Third parties

| Provider | Receives | Notes |
|---|---|---|
| Speech to text (default OpenAI Whisper API) | The audio recording | Audio leaves your infrastructure. Review retention settings and region |
| LLM (default Anthropic API) | The single current patient message, only if the LLM is configured and the message passed the injection screen | No identifiers or history are sent |
| Text to speech (default OpenAI) | The latest assistant message text | Contains guidance, not patient wording |
| Browser speech synthesis | Text stays on the device | Used as fallback |

Disable voice by leaving `SPEECH_API_KEY` empty, and disable the LLM by leaving `LLM_API_KEY` empty. The application
then runs entirely on your own infrastructure with typed input.

## Frontend storage

`sessionStorage` holds the conversation id and token for the open tab. `localStorage` holds only the interface language. The
service worker caches static files, never API responses. There is no analytics or tracking.

## Compliance considerations that remain with the operator

* Identify the legal basis and obtain consent that is understandable to the user group, in their language.
* Assess regulation of health software and medical device rules in the deployment region.
* Data processing agreements, cross border transfer assessment and a data protection impact assessment for the AI providers.
* Breach response process, access logging, encryption at rest, and retention schedule.
* Special care when users may be minors or are describing another person.
* Clinical governance: ownership of the triage rules and an incident process for unsafe outputs.
