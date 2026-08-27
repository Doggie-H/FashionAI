from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "schemas" / "style_vlm_sample.schema.json"


def load_jsonl(path: Path) -> list[tuple[int, dict]]:
    rows: list[tuple[int, dict]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: every JSONL record must be an object")
        rows.append((line_number, value))
    return rows


def validate(manifests: dict[str, Path], schema_path: Path) -> dict[str, object]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    split_counts: dict[str, int] = {}
    owner_splits: dict[str, set[str]] = defaultdict(set)
    wardrobe_splits: dict[str, set[str]] = defaultdict(set)
    sample_ids: set[str] = set()

    for expected_split, manifest_path in manifests.items():
        rows = load_jsonl(manifest_path)
        split_counts[expected_split] = len(rows)
        for line_number, sample in rows:
            prefix = f"{manifest_path}:{line_number}"
            for error in sorted(validator.iter_errors(sample), key=lambda item: list(item.absolute_path)):
                location = ".".join(str(part) for part in error.absolute_path) or "<root>"
                errors.append(f"{prefix}: {location}: {error.message}")
            if sample.get("split") != expected_split:
                errors.append(f"{prefix}: record split must be {expected_split!r}")
            if sample.get("sample_id") in sample_ids:
                errors.append(f"{prefix}: duplicate sample_id {sample.get('sample_id')!r}")
            sample_ids.add(sample.get("sample_id", ""))
            consent = sample.get("consent", {})
            if consent.get("withdrawn_at") is not None:
                errors.append(f"{prefix}: withdrawn sample is forbidden")
            review = sample.get("review", {})
            if review.get("status") != "approved" or review.get("disagreement") is True:
                errors.append(f"{prefix}: only approved, non-disputed reviewer labels may enter fine-tune manifest")
            owner = sample.get("owner_group_id")
            wardrobe = sample.get("wardrobe_group_id")
            if owner:
                owner_splits[owner].add(expected_split)
            if wardrobe:
                wardrobe_splits[wardrobe].add(expected_split)

    for owner, splits in sorted(owner_splits.items()):
        if len(splits) > 1:
            errors.append(f"owner_group_id {owner!r} appears across splits {sorted(splits)}; split by owner to prevent leakage")
    for wardrobe, splits in sorted(wardrobe_splits.items()):
        if len(splits) > 1:
            errors.append(f"wardrobe_group_id {wardrobe!r} appears across splits {sorted(splits)}; split by wardrobe to prevent leakage")
    if not split_counts.get("train") or not split_counts.get("eval") or not split_counts.get("test"):
        errors.append("train, eval, and test manifests must each contain at least one approved sample")

    return {"ok": not errors, "split_counts": split_counts, "sample_count": len(sample_ids), "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate governed StyleVLM JSONL manifests before remote fine-tune staging.")
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--eval", dest="eval_path", type=Path, required=True)
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    report = validate({"train": args.train, "eval": args.eval_path, "test": args.test}, args.schema)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
