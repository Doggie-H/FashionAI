"""Evaluate AI Stylist outputs against a reviewed JSONL ground-truth file.

The benchmark intentionally separates simple evidence checks from human scoring.
It never treats fluent prose as proof of correctness.
"""
import argparse
import json
import re
from pathlib import Path


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def score_case(case, prediction):
    output = normalize(prediction.get("recommendation", ""))
    must_mention = case["decision_rubric"]["must_mention"]
    must_avoid = case["decision_rubric"]["must_avoid"]
    mentioned = sum(normalize(term) in output for term in must_mention)
    avoided = sum(normalize(term) not in output for term in must_avoid)
    mention_score = mentioned / max(len(must_mention), 1)
    avoid_score = avoided / max(len(must_avoid), 1)
    human_score = prediction.get("human_score")
    return {
        "case_id": case["case_id"],
        "mention_score": round(mention_score, 4),
        "avoidance_score": round(avoid_score, 4),
        "human_score": human_score,
        "evidence_complete": mention_score == 1.0 and avoid_score == 1.0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    cases = {json.loads(line)["case_id"]: json.loads(line) for line in args.ground_truth.read_text(encoding="utf-8").splitlines() if line.strip()}
    predictions = [json.loads(line) for line in args.predictions.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [score_case(cases[p["case_id"]], p) for p in predictions if p["case_id"] in cases]
    if not rows:
        raise SystemExit("No matching case IDs")

    report = {
        "cases": len(rows),
        "evidence_completeness": round(sum(row["evidence_complete"] for row in rows) / len(rows), 4),
        "mean_mention_score": round(sum(row["mention_score"] for row in rows) / len(rows), 4),
        "mean_avoidance_score": round(sum(row["avoidance_score"] for row in rows) / len(rows), 4),
        "mean_human_score": round(
            sum(row["human_score"] for row in rows if isinstance(row["human_score"], (int, float)))
            / max(sum(isinstance(row["human_score"], (int, float)) for row in rows), 1),
            4,
        ),
        "rows": rows,
        "limitations": [
            "Seed cases are draft until a human reviewer signs off.",
            "Keyword evidence is not a substitute for semantic or human evaluation.",
            "Human score must be supplied by an independent reviewer.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
