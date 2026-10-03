# Triage methodology

Rules version `2026.1`, engine version `1.0.0` (see `backend/app/core/versions.py`).

## Status of this ruleset

This ruleset is an **engineering baseline** built from commonly cited symptom red flags. It has **not been clinically
validated, reviewed or approved**. Before any real patient use, a qualified clinician must review every rule, threshold and
patient facing sentence, and the deployment must be assessed under local medical device and health software regulation.
The software makes no claim of clinical accuracy.

## Principles

1. **Safety over reassurance.** Every ambiguity resolves toward escalation. A red flag that has been reported is never
   cleared by a later denial in the same conversation. The conflict is recorded and `requires_human_review` is set.
2. **Deterministic.** The engine (`clinical/triage.py`) is a pure function of the clinical state. It calls no network service
   and no LLM, so identical input always gives identical output and every result can be audited.
3. **No diagnosis.** Output is one of three levels plus a recommended action. Disease names are never produced.
4. **No false precision.** `confidence` is always `null` because no calibrated probability exists.
5. **Information before reassurance.** A non urgent result requires that all safety screening questions were answered. If the
   conversation ends with required information missing, the result is `urgent` with reason `insufficient_information`.

## Levels

| Level | Meaning | Recommended action key |
|---|---|---|
| `emergency` | Possible life threatening problem | `seek_emergency_care_now` |
| `urgent` | Needs prompt assessment, ideally the same day | `seek_medical_evaluation_promptly` |
| `non_urgent` | No emergency or urgent criteria met with the information given | `routine_consultation_and_monitoring` |

The `non_urgent` text never says the person is safe. It says the situation does not currently appear to need emergency
escalation and tells the person when to seek care.

### Emergency rules

| Rule | Reason code | Condition |
|---|---|---|
| E01 | `breathing_difficulty` | Difficulty breathing not described as mild |
| E02 | `chest_pain` | Chest pain of any severity |
| E03 | `loss_of_consciousness` | Fainting or unconsciousness |
| E04 | `new_confusion` | Confusion |
| E05 | `stroke_signs` | Face droop, one sided weakness or speech difficulty |
| E06 | `heavy_bleeding` | Heavy or uncontrolled bleeding |
| E07 | `gi_bleeding` | Vomiting blood or black stool |
| E08 | `severe_allergic_reaction` | Swelling of face, lips, tongue or throat |
| E09 | `seizure` | Seizure or convulsions |
| E10 | `snakebite` | Snake bite |
| E11 | `poisoning_or_overdose` | Poison, pesticide or overdose |
| E12 | `critical_symptom_reported` | Patient confirmed breathing, chest or fainting problem |
| E13 | `mental_health_crisis` | Thoughts of self harm |
| E14 | `fever_with_stiff_neck` | Fever with stiff neck |
| E15 | `very_high_fever` | Temperature at or above 41 C |
| E16 | `infant_fever` | Fever in a baby under 3 months |
| E17 | `dehydration_high_risk` | Dehydration signs with vomiting or diarrhoea in a high risk person |
| E18 | `pregnancy_bleeding_or_severe_pain` | Bleeding or severe abdominal pain in pregnancy |
| E19 | `worst_headache` | Sudden severe headache |
| E20 | `head_injury_with_vomiting` | Head injury with vomiting |
| E21 | `severe_burn` | Severe burn |

### Urgent rules

| Rule | Reason code | Condition |
|---|---|---|
| U01 | `high_fever` | Temperature at or above 39.5 C |
| U02 | `persistent_fever` | Fever for 3 days or more |
| U03 | `fever_young_or_old` | Fever in a child under 5 or adult 65 and over |
| U04 | `fever_in_pregnancy` | Fever during pregnancy |
| U05 | `fever_with_chronic_condition` | Fever with a chronic condition |
| U06 | `dehydration_signs` | Dehydration signs with vomiting or diarrhoea |
| U07 | `persistent_vomiting_or_diarrhea` | Vomiting or loose stools for 2 days or more, or in a young or old person |
| U08 | `blood_in_stool_or_urine` | Blood in stool or urine |
| U09 | `bleeding` | Bleeding that is not clearly minor |
| U10 | `severe_symptom` | A symptom described as severe |
| U11 | `abdominal_pain_with_fever_or_vomiting` | Abdominal pain with fever or vomiting |
| U12 | `persistent_cough` | Cough for 14 days or more |
| U13 | `prolonged_symptoms` | Any symptom for 7 days or more |
| U14 | `worsening` | Symptoms are getting worse |
| U15 | `stiff_neck` | Stiff neck |
| U16 | `injury` | Injury or burn |
| U17 | `jaundice_or_vision_change` | Yellow eyes or vision change |
| U18 | `mild_breathing_difficulty` | Breathing difficulty described as mild |
| U19 | `palpitations_high_risk` | Fast heartbeat in an older person or with heart disease |
| U20 | `symptoms_in_pregnancy` | Fever, vomiting, pain, dizziness or headache in pregnancy |
| U21 | `infant_unwell` | Any symptom in a child under 1 year |
| U99 | `insufficient_information` | Required safety information is missing |


## Information the engine needs

Required questions (`clinical/questions.py`, `required_for_triage = true`) must be answered before a non urgent result:

* Breathing, chest pain, fainting screen (always).
* Stroke, seizure, heavy bleeding, confusion screen (when headache, dizziness, weakness, injury, bleeding, vomiting, fever,
  neck stiffness or abdominal pain is present).
* Age (thresholds differ for infants, children under 5 and adults 65 and over).
* Dehydration signs (when vomiting or diarrhoea is present).
* Sex and pregnancy (only for ages 12 to 50 with abdominal pain, bleeding, vomiting or dizziness).
* Duration of symptoms.

Optional questions (fever temperature, long term illness, clarification of ambiguous words) are limited to two per conversation.

## Emergency override

When any emergency rule fires, `ConversationService._decide` stops asking questions, stores a final assessment and returns
emergency guidance. Later messages cannot lower the level because `max_level_reached` is retained and re applied.
A "yes" to the combined breathing, chest or fainting screen escalates immediately without asking which one.

## Known limitations

* Wording such as "pet kharab" (upset stomach) or "chakkar" (dizziness) is ambiguous. The system asks one clarifying question
  rather than assuming.
* Negation handling is rule based and scoped to a clause. Unusual sentence structures can be misread, which for red flags
  tends toward over escalation.
* The patient may be describing someone else. The system treats the described person as the patient and does not model
  the relationship.
* Thresholds (3 days of fever, 39.5 C, 14 days of cough and so on) are placeholders awaiting clinical review.
* Conditions such as mental health crises are only screened for an explicit statement of self harm.

## Changing the rules

1. Edit `clinical/rules.py` and add or update a test in `tests/unit/test_triage_and_questions.py` and
   `tests/safety/`.
2. Bump `RULES_VERSION` in `core/versions.py`.
3. Run `python evaluation/run_eval.py` and `scripts/verify.sh`.
4. Record the clinical reviewer and date in the pull request.

Every stored assessment carries `rules_version` and `engine_version`, so past results stay traceable.
