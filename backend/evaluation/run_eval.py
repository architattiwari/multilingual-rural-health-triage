"""Evaluate the rule based pipeline against evaluation/dataset.jsonl.

The dataset is small and hand written. It measures regressions and coverage of
the lexicon. It is NOT evidence of clinical accuracy. Real validation needs
recorded patient speech, native speaker annotation and clinician review.

Usage: python evaluation/run_eval.py [--min-safety-recall 1.0] [--json out.json]
Exit code is 1 when a threshold is missed.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clinical.concepts import CONCEPTS  # noqa: E402
from app.clinical.extractor import extract  # noqa: E402
from app.clinical.state import merge_extraction  # noqa: E402
from app.clinical.triage import evaluate  # noqa: E402
from app.clinical.questions import next_question, required_outstanding  # noqa: E402
from app.domain.clinical import ClinicalState, TriageLevel  # noqa: E402

DATASET = Path(__file__).with_name("dataset.jsonl")


def load() -> list[dict]:
    return [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]


def run() -> dict:
    rows = load()
    lang_ok = tp = fp = fn = 0
    dur_total = dur_ok = 0
    safety_total = safety_hit = false_alarm = non_emergency = 0
    amb_total = amb_ok = 0
    followup_total = followup_ok = 0
    by_category: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    failures: list[str] = []

    for row in rows:
        ex = extract(row["text"])
        found = {s.concept for s in ex.symptoms}
        want = set(row["symptoms"])

        lang_ok += ex.detected_language == row["language"]
        tp += len(found & want)
        fp += len(found - want)
        fn += len(want - found)
        exact = found >= want
        by_category[row["category"]][0] += 1
        by_category[row["category"]][1] += exact
        if not exact:
            failures.append(f"{row['id']}: wanted {sorted(want)} got {sorted(found)}")

        if row["duration_days"] is not None:
            dur_total += 1
            dur_ok += bool(ex.duration and abs(ex.duration.days - row["duration_days"]) < 0.01)

        state = ClinicalState(conversation_id="eval")
        merge_extraction(state, ex)
        result = evaluate(state, required_outstanding=required_outstanding(state))
        if row["emergency"]:
            safety_total += 1
            safety_hit += result.triage_level == TriageLevel.EMERGENCY
            if result.triage_level != TriageLevel.EMERGENCY:
                failures.append(f"SAFETY {row['id']}: expected emergency, got {result.triage_level.value}")
        else:
            non_emergency += 1
            false_alarm += result.triage_level == TriageLevel.EMERGENCY

        if row["ambiguous"]:
            amb_total += 1
            amb_ok += any(s.requires_clarification for s in state.symptoms)

        # Follow up relevance: the first question must be a safety screen or chief complaint
        # unless the utterance already established an emergency.
        if result.triage_level != TriageLevel.EMERGENCY:
            followup_total += 1
            q = next_question(state)
            followup_ok += bool(q and q.question_id in {"screen_critical_a", "chief_complaint"})

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "examples": len(rows),
        "language_detection_accuracy": round(lang_ok / len(rows), 3),
        "symptom_precision": round(precision, 3),
        "symptom_recall": round(recall, 3),
        "symptom_f1": round(2 * precision * recall / (precision + recall), 3) if precision + recall else 0.0,
        "duration_accuracy": round(dur_ok / dur_total, 3) if dur_total else None,
        "emergency_recall": round(safety_hit / safety_total, 3) if safety_total else None,
        "false_emergency_rate": round(false_alarm / non_emergency, 3) if non_emergency else None,
        "ambiguity_flag_rate": round(amb_ok / amb_total, 3) if amb_total else None,
        "followup_relevance": round(followup_ok / followup_total, 3) if followup_total else None,
        "per_category_symptom_coverage": {k: round(v[1] / v[0], 3) for k, v in sorted(by_category.items())},
        "failures": failures,
        "known_concepts": len(CONCEPTS),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-safety-recall", type=float, default=1.0)
    parser.add_argument("--min-symptom-f1", type=float, default=0.0)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = run()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    bad = (report["emergency_recall"] or 0) < args.min_safety_recall or report["symptom_f1"] < args.min_symptom_f1
    sys.exit(1 if bad else 0)
