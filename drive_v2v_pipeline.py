#!/usr/bin/env python3
"""Dual-DB Driven Digital Human Dispatcher.

Connects `expression_db` + `gesture_db` directly to our Colab G4 pipelines:
  - Mode 1 (`--mode emotion-aroll`): Immediately upgrades existing `Wan2.1 + InfiniteTalk` renders by routing each
    segment's `emotion` preset (`warm_welcome`, `curious_hook`, `emphatic_explain`, `admiring_soft`,
    `surprised_contrast`, `sincere_cta`) into expressive facial-action prompts + tailored starting anchors.
  - Mode 2 (`--mode plan-storyboard`): Given a JSON script with segment texts + scene/emotion tags, automatically
    queries `db_index.json` + `emotion_presets.json` + `gesture_taxonomy.json` to emit a ready-to-render shot plan
    pairing each line with its optimal driving MP4 clip from `gesture_db` / `expression_db`!
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

HOME = Path.home()
DB_ROOT = HOME / "AI_Workstation/digital_human_db"
STEP3_IT = HOME / "AI_Workstation/pipelines/digital_human/step3_render_infinitetalk.py"


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def pick_best_clip(idx: dict, scene: str, emotion: str, aspect: str) -> dict | None:
    pool = idx.get("gesture_db", []) + idx.get("expression_db", [])
    best, best_score = None, -1
    for item in pool:
        score = 0
        if aspect and item.get("aspect") == aspect:
            score += 4
        if scene and item.get("scene") == scene:
            score += 3
        if emotion and item.get("emotion") == emotion:
            score += 2
        if score > best_score:
            best, best_score = item, score
    return best if best_score >= 3 else None


def cmd_render_emotion_aroll(args: argparse.Namespace) -> None:
    presets = load_json(DB_ROOT / "expression_db/emotion_presets.json")["emotions"]
    if args.emotion not in presets:
        raise ValueError(f"Unknown emotion '{args.emotion}'. Choose from: {', '.join(presets.keys())}")
    emo = presets[args.emotion]
    prompt = emo["wan_prompt"]
    print(f"[DUAL-DB EMOTION] {args.emotion} ({emo['label_zh']}) -> prompt:\n  {prompt}\n", flush=True)

    cmd = [
        "python3", "-u", str(STEP3_IT),
        "--url", args.url,
        "--aspect", args.aspect,
        "--steps", str(args.steps),
        "--image", args.image,
        "--audio", args.audio,
        "--out", args.out,
        "--prompt", prompt,
    ]
    if args.session:
        cmd += ["--session", args.session]
    subprocess.run(cmd, check=True)


def cmd_match(args: argparse.Namespace) -> None:
    idx = load_json(DB_ROOT / "db_index.json")
    presets = load_json(DB_ROOT / "expression_db/emotion_presets.json")["emotions"]
    emo = presets.get(args.emotion, presets["warm_welcome"])
    hit = pick_best_clip(idx, args.scene, args.emotion, args.aspect)
    out = {
        "query": {"scene": args.scene, "emotion": args.emotion, "aspect": args.aspect},
        "emotion_preset": emo,
        "matched_driving_clip": hit,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description="Dual-DB Digital Human Driver")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_em = sub.add_parser("emotion-aroll", help="Render InfiniteTalk A-Roll using a specific expression_db emotion preset")
    p_em.add_argument("--url", required=True)
    p_em.add_argument("--image", required=True)
    p_em.add_argument("--audio", required=True)
    p_em.add_argument("--out", required=True)
    p_em.add_argument("--emotion", default="emphatic_explain")
    p_em.add_argument("--aspect", choices=["9:16", "16:9"], default="9:16")
    p_em.add_argument("--steps", type=int, default=4, choices=[4, 6])
    p_em.add_argument("--session", default="")
    p_em.set_defaults(func=cmd_render_emotion_aroll)

    p_m = sub.add_parser("match", help="Query best-matching gesture/expression driving clip & prompt for a scene+emotion")
    p_m.add_argument("--scene", default="walking")
    p_m.add_argument("--emotion", default="warm_welcome")
    p_m.add_argument("--aspect", default="9:16")
    p_m.set_defaults(func=cmd_match)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
