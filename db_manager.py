#!/usr/bin/env python3
"""Unified Dual-Database Manager for Digital Human Facial Expressions (`expression_db`) & Body Gestures (`gesture_db`).

Supports:
  - `ingest`: Import any MP4 (real phone recording OR AI-generated reference clip), normalize cleanly to 25fps H.264,
              extract a 4-frame visual preview strip, and register searchable metadata into `db_index.json`.
  - `list` / `search`: Filter clips by db (`expression`/`gesture`), emotion, scene (`seated`/`standing`/`walking`),
              aspect (`9:16`/`16:9`), or tags.
  - `catalog`: Build a visual contact-sheet preview of all registered clips in the database.
  - `auto-plan`: Given a list of script segments with emotion/scene hints, return the best-matching DB clip IDs & prompts.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HOME = Path.home()
DB_ROOT = HOME / "AI_Workstation/digital_human_db"
INDEX_PATH = DB_ROOT / "db_index.json"
EMOTION_PRESETS = DB_ROOT / "expression_db/emotion_presets.json"
GESTURE_TAXONOMY = DB_ROOT / "gesture_db/gesture_taxonomy.json"
FFMPEG = str(HOME / ".local/bin/ffmpeg") if (HOME / ".local/bin/ffmpeg").exists() else "ffmpeg"


def load_index() -> dict:
    if INDEX_PATH.exists():
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return {"version": "1.0", "updated_at": "", "expression_db": [], "gesture_db": []}


def save_index(data: dict) -> None:
    data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    INDEX_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def probe_video(mp4: Path) -> tuple[int, int, float]:
    res = subprocess.run([FFMPEG, "-i", str(mp4)], capture_output=True, text=True).stderr
    m_dur = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res)
    dur = 0.0
    if m_dur:
        h, m_, s = map(float, m_dur.groups())
        dur = round(h * 3600 + m_ * 60 + s, 2)
    m_dim = re.search(r"Video:.*?,\s*(\d{3,4})x(\d{3,4})", res)
    w, h_ = (int(m_dim.group(1)), int(m_dim.group(2))) if m_dim else (0, 0)
    return w, h_, dur


def make_4frame_strip(mp4: Path, out_jpg: Path, dur: float, aspect: str) -> None:
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    tw, th = (240, 426) if aspect == "9:16" else (426, 240)
    grid = Image.new("RGB", (tw * 4, th), (14, 14, 18))
    times = [max(0.1, dur * r) for r in (0.12, 0.38, 0.64, 0.88)]
    for i, ts in enumerate(times):
        tmp = out_jpg.with_name(f"_tmp_{i}.jpg")
        subprocess.run(
            [FFMPEG, "-y", "-ss", f"{ts:.2f}", "-i", str(mp4), "-frames:v", "1", "-vf", f"scale={tw}:{th}:force_original_aspect_ratio=increase,crop={tw}:{th}", "-q:v", "2", str(tmp)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        grid.paste(Image.open(tmp), (i * tw, 0))
        tmp.unlink(missing_ok=True)
    grid.save(out_jpg, quality=88)


def cmd_ingest(args: argparse.Namespace) -> None:
    src = Path(args.src).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source clip not found: {src}")

    db_key = "expression_db" if args.db == "expression" else "gesture_db"
    clips_dir = DB_ROOT / db_key / "clips"
    thumbs_dir = DB_ROOT / db_key / "thumbs"
    clips_dir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    w0, h0, d0 = probe_video(src)
    aspect = args.aspect or ("9:16" if h0 > w0 else "16:9")
    tw, th = (720, 1280) if aspect == "9:16" else (1280, 720)
    dst_mp4 = clips_dir / f"{args.id}.mp4"

    # Normalize cleanly to 25fps silent driving master (strip audio so driving clips never leak background sound)
    cmd = [FFMPEG, "-y"]
    if args.start > 0:
        cmd += ["-ss", f"{args.start:.2f}"]
    cmd += ["-i", str(src)]
    if args.duration > 0:
        cmd += ["-t", f"{args.duration:.2f}"]
    cmd += [
        "-vf", f"scale={tw}:{th}:force_original_aspect_ratio=increase:flags=lanczos,crop={tw}:{th},fps=25",
        "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(dst_mp4),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    w, h, dur = probe_video(dst_mp4)
    thumb_jpg = thumbs_dir / f"{args.id}_strip.jpg"
    make_4frame_strip(dst_mp4, thumb_jpg, dur, aspect)

    idx = load_index()
    entry = {
        "id": args.id,
        "db": args.db,
        "label_zh": args.label,
        "emotion": args.emotion,
        "gesture_type": args.gesture_type,
        "scene": args.scene,
        "aspect": aspect,
        "resolution": f"{w}x{h}",
        "fps": 25,
        "duration_sec": dur,
        "source_type": args.source_type,
        "tags": [t.strip() for t in args.tags.split(",") if t.strip()],
        "clip_path": str(dst_mp4.relative_to(DB_ROOT)),
        "thumb_path": str(thumb_jpg.relative_to(DB_ROOT)),
        "added_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    arr = [e for e in idx[db_key] if e["id"] != args.id]
    arr.append(entry)
    idx[db_key] = arr
    save_index(idx)
    print(f"[INGEST OK] {db_key}/{args.id} ({w}x{h}, {dur}s, {args.scene}/{args.emotion}) -> {dst_mp4}")


def cmd_list(args: argparse.Namespace) -> None:
    idx = load_index()
    keys = ["expression_db", "gesture_db"] if args.db == "all" else [f"{args.db}_db"]
    for k in keys:
        items = idx.get(k, [])
        if args.scene:
            items = [i for i in items if i.get("scene") == args.scene]
        if args.emotion:
            items = [i for i in items if i.get("emotion") == args.emotion]
        if args.aspect:
            items = [i for i in items if i.get("aspect") == args.aspect]
        if args.tag:
            items = [i for i in items if args.tag in i.get("tags", []) or args.tag in i.get("label_zh", "")]
        print(f"\n=== {k} ({len(items)} items) ===")
        for it in items:
            print(f"  - [{it['id']}] {it['label_zh']} | {it['scene']} | emo={it['emotion']} | {it['aspect']} ({it['duration_sec']}s) | tags={','.join(it['tags'])}")


def cmd_catalog(_args: argparse.Namespace) -> None:
    idx = load_index()
    all_items = idx.get("expression_db", []) + idx.get("gesture_db", [])
    if not all_items:
        print("Database is empty.")
        return
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 22, index=2)
    except Exception:
        font = ImageFont.load_default()

    row_h = 340
    row_w = 1280
    canvas = Image.new("RGB", (row_w, row_h * len(all_items) + 40), (16, 18, 22))
    draw = ImageDraw.Draw(canvas)
    for i, it in enumerate(all_items):
        y0 = 20 + i * row_h
        title = f"[{it['db'].upper()}] {it['id']} — {it['label_zh']} ({it['scene']} / {it['emotion']} / {it['duration_sec']}s)"
        draw.text((24, y0), title, font=font, fill=(240, 210, 150))
        tp = DB_ROOT / it["thumb_path"]
        if tp.exists():
            im = Image.open(tp)
            im.thumbnail((row_w - 48, row_h - 56), Image.Resampling.LANCZOS)
            canvas.paste(im, (24, y0 + 38))
    out = DB_ROOT / "db_catalog_preview.jpg"
    canvas.save(out, quality=90)
    print(f"[CATALOG OK] {out} ({len(all_items)} items)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Digital Human Expression & Gesture Dual-DB Manager")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_in = sub.add_parser("ingest", help="Normalize and ingest a driving MP4 into expression_db or gesture_db")
    p_in.add_argument("--db", choices=["expression", "gesture"], required=True)
    p_in.add_argument("--id", required=True, help="Unique clip ID, e.g. gest_walk_zisha_01")
    p_in.add_argument("--src", required=True, help="Input MP4 path (real phone video or AI-generated clip)")
    p_in.add_argument("--label", required=True, help="Chinese human-readable label")
    p_in.add_argument("--scene", choices=["seated", "standing", "walking", "closeup"], default="seated")
    p_in.add_argument("--emotion", default="warm_welcome")
    p_in.add_argument("--gesture-type", default="seated_hand_open")
    p_in.add_argument("--source-type", choices=["real_capture", "ai_generated"], default="real_capture")
    p_in.add_argument("--aspect", choices=["9:16", "16:9", ""], default="")
    p_in.add_argument("--tags", default="")
    p_in.add_argument("--start", type=float, default=0.0)
    p_in.add_argument("--duration", type=float, default=0.0)
    p_in.set_defaults(func=cmd_ingest)

    p_ls = sub.add_parser("list", help="List or search clips in dual database")
    p_ls.add_argument("--db", choices=["all", "expression", "gesture"], default="all")
    p_ls.add_argument("--scene", default="")
    p_ls.add_argument("--emotion", default="")
    p_ls.add_argument("--aspect", default="")
    p_ls.add_argument("--tag", default="")
    p_ls.set_defaults(func=cmd_list)

    p_cat = sub.add_parser("catalog", help="Render visual contact-sheet catalog of all DB clips")
    p_cat.set_defaults(func=cmd_catalog)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
