# AI and language pipeline

## Speech to text

**Provider used:** `OpenAISpeechToText` calls an OpenAI compatible `/audio/transcriptions` endpoint with model `whisper-1`
and `verbose_json` output. It was selected because it supports Hindi, accepts common browser formats (WebM, Ogg, MP3, M4A, WAV),
returns segment level log probabilities that give a usable confidence signal, and has a simple REST interface. The abstraction
(`SpeechToTextProvider`) lets another engine replace it, including a self hosted model.

**Configuration:** `SPEECH_API_KEY`, `SPEECH_API_BASE_URL`, `SPEECH_MODEL`, `SPEECH_DEFAULT_LANGUAGE`. Without a key voice input is
disabled and typing works.

**Supported languages:** Hindi and English are requested explicitly through the language hint. Marwari is not a supported
recognition language. Marwari speakers are transcribed as Hindi, which loses dialect words.

**Known limitations**

* Rural accents, dialect vocabulary, background noise and cheap microphones reduce accuracy. No measurement on such audio has
  been made. Treat accuracy as unknown until tested with real recordings.
* Hindi speech is sometimes returned in Urdu script. The response flags `urdu_script_possible`. The extractor does not read Urdu script.
* Recognition can invent text for silence. The service uses `no_speech_prob` and average log probability to flag low quality
  audio, and the frontend always shows the transcript for correction before anything is submitted.
* Audio is sent to the provider's servers. It is not stored by this application.

**Audio handling:** the declared type must be on an allow list and the file signature must match. Maximum size is
`MAX_AUDIO_BYTES` (5 MB) and WAV duration is checked against `MAX_AUDIO_SECONDS`. The browser recorder uses mono Opus at about 16 kbps
and stops at the limit. Very quiet WAV files are flagged.

## Language detection

`clinical/language.py` classifies a message as Hindi (Devanagari), romanised Hindi, English or Marwari influenced Hindi and
reports code mixing. It uses script share, word counts and small marker word lists. It is built for short symptom phrases and
returns `und` when evidence is thin. The response language follows the patient: Devanagari gets Hindi, romanised input gets
romanised Hindi, English gets English, and Marwari influenced input is answered in Hindi.

## Normalisation

`clinical/text.py` folds spelling variation so one lexicon entry covers many spellings:
repeated letters collapse (`bukhaar` and `bukhar`), `z`/`j`, `w`/`v` and `q`/`k` unify, Devanagari nukta and nasal marks are
dropped and `ै`/`े` are unified so typical speech recognition spellings (`मे`, `हे`) still match. A fuzzy match with a high threshold
handles single word typos, at reduced confidence.

## Entity extraction

The rule based extractor (`clinical/extractor.py`) always runs and is the trusted baseline. It finds:

* symptoms with original wording, normalised concept, confidence, severity words and sudden onset
* negation scoped to a clause fragment (`bukhar hai lekin saans ki dikkat nahi`)
* duration (`do din se`, `teen hafte`, `kal se`, `do teen din`), age (`45 saal ka`, `6 mahine ki`), temperature
  (Fahrenheit converted to Celsius), pregnancy, sex terms and long term conditions

Ambiguous concepts (head heaviness, dizziness, weakness, palpitations, upset stomach) get lower confidence and
`requires_clarification`. The follow up engine asks one clarifying question for each instead of assuming a meaning.

Example (real output):

```json
{"name": "head heaviness", "original_text": "sar bhaari", "normalized_concept": "head heaviness",
 "confidence": 0.82, "requires_clarification": true, "duration_days": 2.0}
```

### Lexicon status

`clinical/lexicon.py` is a starter vocabulary written for engineering. Marwari entries in particular (`taav`, `matho`, `koni`,
`ghano`, `mhane`) need review by native speakers and dialect variation across Rajasthan is much wider than what is covered.
Review by clinicians and native speakers is required before real use.

## LLM usage

`LLMProvider` is implemented for the Anthropic Messages API. It is optional, and used for:

1. **Extra extraction** for phrases the lexicon does not know (`ai/extraction.py`).
2. **Translation** of reviewed English guidance into extra languages listed in `TRANSLATION_LANGUAGES` (`ai/translation.py`).

It is not used for triage, question wording, emergency handling, or free text responses.

**Safeguards**

* The system prompt is a constant (`ai/prompts.py`, `PROMPT_VERSION`). Patient text appears only in the user message inside
  `<patient_message>` tags and is described as data. Closing tags inside the text are removed.
* Text that matches the prompt injection screen is never sent to the model.
* Output must be a JSON object that validates against `LLMExtractionPayload`. Concept ids must exist. Each item's `evidence`
  must occur in the patient's message. Anything else is dropped and counted in `llm_failures_total` or `llm_rejected_items_total`.
  Raw model output is never logged or shown.
* The model can only add present symptoms. It cannot negate, downgrade or set a level. For ordinary symptoms a rule based negation in
  the same message wins. For red flags the model may still escalate, because a false alarm is safer than a miss.
* Translations are rejected if they contain markup, change any number or differ wildly in length, and fall back to Hindi.

## Follow up questions

Questions live in `clinical/questions.py` with `question_id`, `clinical_field`, `priority` (critical, high, medium, low),
`required_for_triage`, `trigger` and `language_templates`. The next question is the highest priority one whose trigger is true
and that is not yet answered. Critical screening always comes first. A reply that cannot be understood is asked again once
with an apology, then left unresolved, which leads to an `urgent` result with `insufficient_information` rather than reassurance.

## Text to speech

`OpenAITextToSpeech` calls an OpenAI compatible `/audio/speech` endpoint and returns MP3. The endpoint accepts only the latest
assistant message of the conversation, not arbitrary text, so it cannot be used as a free speech service. If it fails the frontend
uses the device speech synthesis, and if that is missing the text remains the primary output. The voice is not region or dialect tuned.

## Evaluation

See `backend/evaluation/`. `dataset.jsonl` has 49 hand written examples across standard Hindi, rural Hindi, code switching,
Marwari influenced text, ambiguous phrases, misspellings, simulated speech recognition errors and symptom variation.
`run_eval.py` reports language detection accuracy, symptom precision and recall, duration accuracy, emergency recall, false
emergency rate, ambiguity flagging and follow up relevance. It runs in the test suite as a regression gate.

Current result: emergency recall 1.0, false emergency rate 0.0, symptom F1 1.0, language detection 1.0 on these 49 examples.

**Read this number carefully.** The set is small and written by the same people who wrote the lexicon. One example
(`asr03`, a speech recognition spelling of chest pain) failed on first run and the folding rules were then fixed, so the
dataset was used for development. These figures show that known cases keep working. They say nothing about real world accuracy
on rural speech, which requires a held out set of recorded and annotated patient utterances.
