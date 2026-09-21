#!/usr/bin/env python3
"""Score one Cursor run and rebuild cumulative UiPad charts."""
from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import string
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GOLD_PATH = ROOT / "eval_gold.json"
RESULTS_PATH = ROOT / "results" / "uipad_results.jsonl"
SUMMARY_PATH = ROOT / "results" / "summary.csv"
CHARTS_DIR = ROOT / "charts"
IOU_THRESHOLD = 0.5
CANON_EFFORTS = ["none", "low", "medium", "high", "xhigh", "max"]
MODEL_ORDER = ["GPT-5.6 Sol", "Claude Opus 5", "Cursor Grok 4.6"]

_BOX_RE = re.compile(
    r"\[\s*\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]\s*,\s*"
    r"\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]\s*\]"
)
_TUPLE_BOX_RE = re.compile(
    r"\[\s*\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)\s*,\s*"
    r"\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)\s*\]"
)
_NUM_RE = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")
_YN_RE = re.compile(r"\b(yes|no)\b", re.I)


def _norm_type(answer_type: str) -> str:
    at = (answer_type or "").strip().lower()
    return {"yes-no": "yes/no", "text": "string"}.get(at, at)


def _gold_number(gold):
    try:
        return float(str(gold).strip().replace(",", ""))
    except Exception:
        return None


def _yn(s):
    if s is None:
        return None
    s = str(s).strip().lower()
    if s.startswith("y"):
        return "yes"
    if s.startswith("n"):
        return "no"
    return None


def _as_box(val):
    try:
        if val is None:
            return None
        if isinstance(val, str):
            val = ast.literal_eval(val.strip())
        if len(val) == 2 and all(hasattr(p, "__len__") and len(p) == 2 for p in val):
            (x1, y1), (x2, y2) = val
        elif len(val) == 4:
            x1, y1, x2, y2 = val
        else:
            return None
        x1, y1, x2, y2 = float(x1), float(y1), float(x2), float(y2)
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
    except Exception:
        return None


def _iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    denom = area_a + area_b - inter
    return inter / denom if denom > 0 else 0.0


def _norm_string(s: str) -> str:
    s = str(s).strip().lower()
    s = s.translate(str.maketrans("", "", string.punctuation))
    return " ".join(s.split())


def parse_answer(raw_text: str, answer_type: str):
    at = _norm_type(answer_type)
    text = (raw_text or "").strip()
    if not text:
        return None
    if at == "coordinates":
        matches = list(_BOX_RE.finditer(text)) + list(_TUPLE_BOX_RE.finditer(text))
        if matches:
            m = matches[-1]
            return [[float(m.group(1)), float(m.group(2))], [float(m.group(3)), float(m.group(4))]]
        try:
            return ast.literal_eval(text.splitlines()[-1].strip())
        except Exception:
            return None
    last = next((ln.strip() for ln in reversed(text.splitlines()) if ln.strip()), text)
    if at == "number":
        found = list(_NUM_RE.finditer(last)) or list(_NUM_RE.finditer(text))
        return float(found[-1].group(0).replace(",", "")) if found else None
    if at == "yes/no":
        found = list(_YN_RE.finditer(last)) or list(_YN_RE.finditer(text))
        return found[-1].group(1).lower() if found else None
    return last


def judge(parsed, gold, answer_type: str) -> tuple[bool, str]:
    at = _norm_type(answer_type)
    if at == "number":
        g = _gold_number(gold)
        if g is None:
            return False, "bad gold number"
        if parsed is None:
            return False, "no number parsed"
        ok = abs(float(parsed) - g) <= max(0.01, abs(g) * 0.01)
        return ok, f"number pred={parsed} gold={g}"
    if at == "yes/no":
        p, g = _yn(parsed), _yn(gold)
        return (p is not None and p == g), f"yes/no pred={p} gold={g}"
    if at == "coordinates":
        pb, gb = _as_box(parsed), _as_box(gold)
        if gb is None:
            return False, "bad gold box"
        if pb is None:
            return False, "no box parsed"
        iou = _iou(pb, gb)
        return iou >= IOU_THRESHOLD, f"iou={iou:.2f}"
    if parsed is None:
        return False, "no string parsed"
    ok = _norm_string(parsed) == _norm_string(gold)
    return ok, f"string pred={parsed!r} gold={str(gold)!r}"


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    recs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            recs.append(json.loads(line))
    return recs


def key_of(rec: dict) -> tuple:
    return (rec["model"], rec["reasoning_effort"], rec["row_id"])


def write_jsonl(path: Path, recs: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in recs:
            f.write(json.dumps(rec) + "\n")


def summarize(recs: list[dict]) -> list[dict]:
    grouped: dict[tuple, list] = defaultdict(list)
    for rec in recs:
        if rec.get("error"):
            continue
        grouped[(rec["model"], rec["reasoning_effort"])].append(rec)
    rows = []
    for (model, effort), items in grouped.items():
        n = len(items)
        correct = sum(1 for x in items if x.get("correct"))
        by_type: dict[str, list] = defaultdict(list)
        for x in items:
            by_type[x["answer_type"]].append(x)
        row = {
            "model": model,
            "reasoning_effort": effort,
            "n": n,
            "pass_at_1": correct / n if n else 0.0,
            "n_correct": correct,
        }
        for t in ("number", "yes/no", "string", "coordinates"):
            subset = by_type.get(t, [])
            row[f"pass_{t.replace('/', '_')}"] = (
                sum(1 for x in subset if x.get("correct")) / len(subset) if subset else ""
            )
        rows.append(row)
    def sort_key(r):
        m = MODEL_ORDER.index(r["model"]) if r["model"] in MODEL_ORDER else 99
        e = CANON_EFFORTS.index(r["reasoning_effort"]) if r["reasoning_effort"] in CANON_EFFORTS else 99
        return (m, e)
    return sorted(rows, key=sort_key)


def write_summary_csv(rows: list[dict]) -> None:
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else ["model", "reasoning_effort", "n", "pass_at_1"]
    with SUMMARY_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            out = dict(row)
            if isinstance(out.get("pass_at_1"), float):
                out["pass_at_1"] = f"{out['pass_at_1']:.4f}"
            w.writerow(out)


def _svg_line_chart(series: dict[str, list[tuple[str, float]]], title: str, ylabel: str) -> str:
    width, height = 820, 360
    left, right, top, bottom = 56, 24, 36, 48
    plot_w, plot_h = width - left - right, height - top - bottom
    colors = {
        "GPT-5.6 Sol": "#2563eb",
        "Claude Opus 5": "#c2410c",
        "Cursor Grok 4.6": "#0f766e",
    }
    x_labels = []
    for pts in series.values():
        for lab, _ in pts:
            if lab not in x_labels:
                x_labels.append(lab)
    x_labels = [e for e in CANON_EFFORTS if e in x_labels] or x_labels
    n = max(len(x_labels), 1)

    def x_pos(label: str) -> float:
        i = x_labels.index(label) if label in x_labels else 0
        return left + (plot_w * (i / max(n - 1, 1)))

    def y_pos(v: float) -> float:
        return top + plot_h * (1 - v)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        f'<text x="{left}" y="22" font-size="14" font-family="sans-serif">{title}</text>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_h}" stroke="#ccc"/>',
        f'<line x1="{left}" y1="{top+plot_h}" x2="{left+plot_w}" y2="{top+plot_h}" stroke="#ccc"/>',
    ]
    for tick in (0, 0.25, 0.5, 0.75, 1.0):
        y = y_pos(tick)
        parts.append(f'<line x1="{left}" y1="{y}" x2="{left+plot_w}" y2="{y}" stroke="#f0f0f0"/>')
        parts.append(
            f'<text x="{left-8}" y="{y+4}" font-size="10" text-anchor="end" font-family="sans-serif">{tick:.2f}</text>'
        )
    for lab in x_labels:
        parts.append(
            f'<text x="{x_pos(lab)}" y="{top+plot_h+20}" font-size="11" text-anchor="middle" font-family="sans-serif">{lab}</text>'
        )
    legend_x = left
    for name, pts in series.items():
        color = colors.get(name, "#444")
        coords = " ".join(f"{x_pos(lab)},{y_pos(v)}" for lab, v in pts if lab in x_labels)
        if coords:
            parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{coords}"/>')
            for lab, v in pts:
                if lab in x_labels:
                    parts.append(f'<circle cx="{x_pos(lab)}" cy="{y_pos(v)}" r="3.5" fill="{color}"/>')
        parts.append(
            f'<rect x="{legend_x}" y="{height-18}" width="10" height="10" fill="{color}"/>'
            f'<text x="{legend_x+14}" y="{height-9}" font-size="11" font-family="sans-serif">{name}</text>'
        )
        legend_x += 160
    parts.append(f'<text x="8" y="{top+plot_h/2}" font-size="10" font-family="sans-serif" transform="rotate(-90 8 {top+plot_h/2})">{ylabel}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def write_charts(rows: list[dict]) -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    series: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in rows:
        series[row["model"]].append((row["reasoning_effort"], float(row["pass_at_1"])))
    (CHARTS_DIR / "pass_at_1_vs_effort.svg").write_text(
        _svg_line_chart(dict(series), "pass@1 vs reasoning effort", "pass@1"),
        encoding="utf-8",
    )
    for t, key in (
        ("number", "pass_number"),
        ("yes/no", "pass_yes_no"),
        ("string", "pass_string"),
        ("coordinates", "pass_coordinates"),
    ):
        typed: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for row in rows:
            val = row.get(key)
            if val == "" or val is None:
                continue
            typed[row["model"]].append((row["reasoning_effort"], float(val)))
        (CHARTS_DIR / f"pass_at_1_{t.replace('/', '_')}.svg").write_text(
            _svg_line_chart(dict(typed), f"pass@1 vs effort ({t})", "pass@1"),
            encoding="utf-8",
        )


def print_table(rows: list[dict], current: tuple[str, str] | None) -> None:
    print("\nCumulative pass@1 by model / effort\n")
    print(f"{'model':<18} {'effort':<10} {'n':>4} {'pass@1':>8}  number  yes/no  string  coords")
    for row in rows:
        mark = " <--" if current and (row["model"], row["reasoning_effort"]) == current else ""
        def fmt(v):
            return f"{float(v):.2f}" if v != "" and v is not None else "  - "
        print(
            f"{row['model']:<18} {row['reasoning_effort']:<10} {row['n']:>4} {row['pass_at_1']:>8.3f}  "
            f"{fmt(row.get('pass_number')):>6}  {fmt(row.get('pass_yes_no')):>6}  "
            f"{fmt(row.get('pass_string')):>6}  {fmt(row.get('pass_coordinates')):>6}{mark}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, help="JSONL of raw answers for one model+effort")
    args = parser.parse_args()
    run_path = Path(args.run)
    if not run_path.is_absolute():
        run_path = ROOT / run_path

    gold = {g["row_id"]: g for g in json.loads(GOLD_PATH.read_text())["items"]}
    raw_recs = load_jsonl(run_path)
    if not raw_recs:
        raise SystemExit(f"no records in {run_path}")

    scored = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for rec in raw_recs:
        g = gold[rec["row_id"]]
        parsed = parse_answer(rec["raw_response"], g["answer_type"])
        correct, reason = judge(parsed, g["gold_answer"], g["answer_type"])
        scored.append(
            {
                "row_id": rec["row_id"],
                "screen_id": rec.get("screen_id", g["screen_id"]),
                "question": rec.get("question", ""),
                "answer_type": g["answer_type"],
                "gold_answer": g["gold_answer"],
                "model": rec["model"],
                "reasoning_effort": rec["reasoning_effort"],
                "raw_response": rec["raw_response"],
                "parsed_answer": parsed,
                "correct": correct,
                "reason": reason,
                "input_tokens": rec.get("input_tokens"),
                "reasoning_tokens": rec.get("reasoning_tokens"),
                "output_tokens": rec.get("output_tokens"),
                "latency_ms": rec.get("latency_ms"),
                "run_timestamp": rec.get("run_timestamp") or now,
                "error": rec.get("error"),
            }
        )

    existing = load_jsonl(RESULTS_PATH)
    by_key = {key_of(r): r for r in existing}
    added = 0
    for rec in scored:
        k = key_of(rec)
        if k not in by_key:
            added += 1
        by_key[k] = rec
    merged = list(by_key.values())
    write_jsonl(RESULTS_PATH, merged)

    rows = summarize(merged)
    write_summary_csv(rows)
    write_charts(rows)

    model, effort = scored[0]["model"], scored[0]["reasoning_effort"]
    n = len(scored)
    acc = sum(1 for r in scored if r["correct"]) / n
    print(f"scored {n} answers for {model} / {effort}: pass@1={acc:.3f} ({added} new rows)")
    print(f"wrote {RESULTS_PATH}")
    print(f"wrote {SUMMARY_PATH}")
    print(f"wrote {CHARTS_DIR}/pass_at_1_vs_effort.svg")
    print_table(rows, (model, effort))


if __name__ == "__main__":
    main()
