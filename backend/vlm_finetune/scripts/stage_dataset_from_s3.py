from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import quote


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _extension(mime_type: str) -> str:
    return {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[mime_type]


def _preflight(records: list[dict], split: str) -> list[str]:
    errors: list[str] = []
    for row in records:
        if row.get("split") != split:
            errors.append(f"{row.get('sample_id')}: split mismatch")
        if row.get("consent", {}).get("training_allowed") is not True or row.get("consent", {}).get("withdrawn_at") is not None:
            errors.append(f"{row.get('sample_id')}: consent is not eligible")
        if row.get("review", {}).get("status") != "approved" or row.get("review", {}).get("disagreement") is True:
            errors.append(f"{row.get('sample_id')}: reviewer status is not eligible")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage only approved, consented StyleVLM images from the workload-identity S3 bucket.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", choices=["train", "eval", "test"], required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--execute-download", action="store_true", help="Without this switch, only validates the manifest and writes no data.")
    args = parser.parse_args()

    records = _records(args.manifest)
    errors = _preflight(records, args.split)
    if errors:
        raise SystemExit("\n".join(errors))
    if not args.execute_download:
        print(json.dumps({"ok": True, "mode": "dry_run", "split": args.split, "record_count": len(records)}, ensure_ascii=False))
        return

    bucket = os.getenv("AI_STYLIST_S3_BUCKET")
    if os.getenv("AI_STYLIST_STORAGE_BACKEND") != "s3" or not bucket:
        raise SystemExit("AI_STYLIST_STORAGE_BACKEND=s3 and AI_STYLIST_S3_BUCKET are required")
    import boto3
    client = boto3.client("s3", endpoint_url=os.getenv("AI_STYLIST_S3_ENDPOINT_URL"), region_name=os.getenv("AI_STYLIST_S3_REGION"))
    images = args.output_root / "images"
    images.mkdir(parents=True, exist_ok=True)
    prepared = []
    for row in records:
        image = row["image"]
        destination = images / f"{row['sample_id']}{_extension(image['mime_type'])}"
        client.download_file(bucket, image["s3_key"], str(destination))
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        if digest != image["sha256"]:
            destination.unlink(missing_ok=True)
            raise SystemExit(f"{row['sample_id']}: downloaded SHA-256 does not match approved manifest")
        prepared.append({"sample_id": row["sample_id"], "image_path": str(destination.relative_to(args.output_root)).replace("\\", "/"), "messages": row["messages"]})
    destination_manifest = args.output_root / f"{args.split}.jsonl"
    destination_manifest.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in prepared), encoding="utf-8")
    print(json.dumps({"ok": True, "mode": "staged", "split": args.split, "record_count": len(prepared), "prepared_manifest": str(destination_manifest)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
