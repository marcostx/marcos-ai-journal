#!/usr/bin/env python3
"""Download UiPad screenshots listed in eval_set.json into eval_images/."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVAL = json.loads((ROOT / "eval_set.json").read_text())
IMG_DIR = ROOT / "eval_images"
IMG_DIR.mkdir(exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}


def main() -> None:
    for item in EVAL["items"]:
        dest = ROOT / item["image"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.stat().st_size > 0:
            continue
        hf_path = item["hf_path"]
        url = "https://huggingface.co/datasets/macpaw-research/UiPad/resolve/main/" + urllib.parse.quote(
            hf_path, safe="/"
        )
        print(f"download {item['row_id']} {hf_path}")
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req) as resp, dest.open("wb") as out:
            out.write(resp.read())
    print(f"ready: {len(list(IMG_DIR.glob('*.png')))} images in {IMG_DIR}")


if __name__ == "__main__":
    main()
