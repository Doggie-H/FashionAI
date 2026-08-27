from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
INPUT = BACKEND_ROOT / "reports" / "style_session_10_item_scenario.json"
OUTPUT = BACKEND_ROOT.parent / "docs" / "CANDIDATE_OUTFIT_10_ITEM_SCORE_ANALYSIS.md"

RULE_LABELS = {
    "occasion_match": "Occasion match",
    "season_match": "Season match",
    "style_match": "Style match",
    "style_coherence": "Style coherence",
    "style_intensity_match": "Style intensity",
    "formality_match": "Formality",
    "fit_preference": "Fit preference",
    "mobility_match": "Mobility",
    "modesty_match": "Coverage/modesty",
    "functional_intent_support": "Functional intent",
    "outfit_intent_coverage": "Outfit intent coverage",
    "owned_wardrobe_available": "Owned wardrobe",
    "owned_wardrobe_preference": "Owned wardrobe preference",
    "skeleton_compatible": "Skeleton contract",
    "color_harmony": "Color harmony",
}


def cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def main() -> None:
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    candidates = data["candidates"]
    lines = [
        "# Phân tích candidate outfit và điểm số — scenario 10 item",
        "",
        "**Nguồn chạy:** `backend/reports/style_session_10_item_scenario.json`.  ",
        "**Chính sách:** `owned_only`; toàn bộ item candidate thuộc immutable wardrobe snapshot 10 item.",
        "",
        "## Bối cảnh quyết định",
        "",
        "| Tín hiệu | Giá trị |",
        "|---|---|",
    ]
    for key, value in data["context"].items():
        lines.append(f"| `{cell(key)}` | {cell(value)} |")

    lines.extend(["", "## Tổng quan candidate", "", "| Hạng | Candidate | Archetype | Điểm | Tổng evidence delta | Khớp total | Confidence |", "|---:|---|---|---:|---:|---|---:|"])
    for rank, candidate in enumerate(candidates, start=1):
        evidence_total = sum(float(item.get("score_delta", 0)) for item in candidate.get("evidence", []))
        total = float(candidate["score"])
        lines.append(
            f"| {rank} | {cell(', '.join(candidate['garment_ids']))} | {cell(', '.join(candidate.get('style_archetypes', [])))} | {total:.1f} | {evidence_total:.1f} | {'Có' if abs(total-evidence_total) < 0.001 else 'Không'} | {float(candidate['confidence']):.2f} |"
        )

    for rank, candidate in enumerate(candidates, start=1):
        rollup: dict[str, float] = defaultdict(float)
        examples: dict[str, list[str]] = defaultdict(list)
        for evidence in candidate.get("evidence", []):
            rule_id = evidence["rule_id"]
            rollup[rule_id] += float(evidence.get("score_delta", 0))
            if evidence["message"] not in examples[rule_id]:
                examples[rule_id].append(evidence["message"])
        lines.extend([
            "",
            f"## Candidate {rank}: `{candidate['outfit_id']}`",
            "",
            candidate.get("style_story", "Không có style story."),
            "",
            f"**Garments:** {', '.join(candidate['garment_ids'])}  ",
            f"**Tổng điểm:** {float(candidate['score']):.1f}; **confidence:** {float(candidate['confidence']):.2f}; **evidence delta:** {sum(rollup.values()):.1f}.",
            "",
            "| Rule | Điểm gộp | Evidence rút gọn |",
            "|---|---:|---|",
        ])
        for rule_id, score in sorted(rollup.items(), key=lambda pair: (-pair[1], pair[0])):
            lines.append(f"| {RULE_LABELS.get(rule_id, rule_id)} (`{rule_id}`) | {score:+.1f} | {cell(' / '.join(examples[rule_id]))} |")
        if candidate.get("functional_highlights"):
            lines.extend(["", f"**Functional highlights:** {', '.join(candidate['functional_highlights'])}."])
        if candidate.get("tradeoffs"):
            lines.extend(["", f"**Trade-offs:** {'; '.join(candidate['tradeoffs'])}."])
        if candidate.get("needs_user_confirmation"):
            lines.extend(["", f"**Cần xác nhận:** {'; '.join(candidate['needs_user_confirmation'])}."])

    lines.extend([
        "",
        "## Cách đọc điểm",
        "",
        "Điểm là tổng evidence của deterministic policy phiên bản hiện tại, không phải xác suất vật lý hoặc điểm tuyệt đối về gu thẩm mỹ. Confidence phản ánh tính đầy đủ/nhất quán của policy evidence; nó không chứng minh fit thật, chất liệu thật hay sự hài lòng của người dùng. Trade-off phải được hiển thị cho người dùng và là đầu vào cho feedback/reviewer workflow.",
        "",
        "> Scenario này là kiểm chứng workflow với kho đồ mô phỏng. Nó không thay thế bộ đánh giá có reviewer, ảnh thật, trang phục thật hoặc dữ liệu preference được cấp quyền.",
        "",
    ])
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
