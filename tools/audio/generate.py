"""Record Bible chapters with the Kokoro "Daniel" voice (bm_daniel, Apache-2.0, synthetic voice).

For each chapter writes:
  <out>/<book 01-66>/<chapter 001>.m4a   AAC mono audio
  <out>/<book>/<chapter>.json            {"s": verse start times, "e": verse end times, "d": duration}

Usage: python generate.py --out audio --only 19:23 43:3   (book:chapter, 1-based)
       python generate.py --out audio --books 1-66          (everything)
       python generate.py --out audio --books 1-66 --shard 3/20   (one of 20 equal slices, for parallel runs)
Needs kokoro-v1.0.onnx and voices-v1.0.bin (downloaded automatically) and ffmpeg.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TEXT = os.path.join(HERE, "..", "..", "data", "kjv.json")
MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
VOICE, SPEED, SR = "bm_daniel", 0.9, 24000
BITRATE = "24k"   # keeps the whole Bible (~70 h) under GitHub Pages' 1 GB site limit
GAP, PARA_GAP, INTRO_GAP = 0.3, 0.55, 0.6


def ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def spoken(t):
    t = t.replace("¶", "").replace("’", "'")
    return re.sub(r"\b([A-Z])([A-Z]+)\b", lambda m: m.group(1) + m.group(2).lower(), t)   # LORD -> Lord


def intro(book, c):
    return f"Psalm {c}." if book == "Psalms" else f"{book}, chapter {c}."


def load_kokoro(model_dir):
    from kokoro_onnx import Kokoro
    os.makedirs(model_dir, exist_ok=True)
    for f in ["kokoro-v1.0.onnx", "voices-v1.0.bin"]:
        p = os.path.join(model_dir, f)
        if not os.path.exists(p):
            urllib.request.urlretrieve(MODEL_URL + f, p)
    return Kokoro(os.path.join(model_dir, "kokoro-v1.0.onnx"), os.path.join(model_dir, "voices-v1.0.bin"))


def say(k, text):
    audio, sr = k.create(text, voice=VOICE, speed=SPEED, lang="en-gb")
    assert sr == SR
    return np.asarray(audio, dtype=np.float32)


def chapter(k, bible, b, c, out):
    name, chapters = bible[b - 1]
    verses = chapters[c - 1]
    silence = lambda s: np.zeros(int(s * SR), dtype=np.float32)
    parts = [say(k, intro(name, c)), silence(INTRO_GAP)]
    t = sum(len(p) for p in parts) / SR
    starts, ends = [], []
    for i, v in enumerate(verses):
        if i > 0:
            g = silence(PARA_GAP if v.startswith("¶") else GAP)
            parts.append(g)
            t += len(g) / SR
        a = say(k, spoken(v))
        starts.append(round(t, 3))
        parts.append(a)
        t += len(a) / SR
        ends.append(round(t, 3))
    audio = np.concatenate(parts + [silence(0.8)])
    audio = audio / max(1e-6, float(np.abs(audio).max())) * 0.89
    d = os.path.join(out, f"{b:02d}")
    os.makedirs(d, exist_ok=True)
    base = os.path.join(d, f"{c:03d}")
    pcm = (audio * 32767).astype("<i2").tobytes()
    subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-",
                    "-c:a", "aac", "-b:a", BITRATE, "-movflags", "+faststart", base + ".m4a"], input=pcm, check=True)
    with open(base + ".json", "w") as f:
        json.dump({"s": starts, "e": ends, "d": round(len(audio) / SR, 3)}, f, separators=(",", ":"))
    return len(audio) / SR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="audio")
    ap.add_argument("--models", default=os.path.join(HERE, ".models"))
    ap.add_argument("--only", nargs="*", default=[], help="book:chapter pairs")
    ap.add_argument("--books", default="", help="range like 1-66 or 40-43")
    ap.add_argument("--skip-in", default="", help="also skip chapters already recorded in this folder")
    ap.add_argument("--shard", default="", help="i/n: record only slice i (1-based) of n, balanced by text length")
    args = ap.parse_args()
    bible = json.load(open(TEXT, encoding="utf-8"))
    jobs = [tuple(map(int, x.split(":"))) for x in args.only]
    if args.books:
        lo, hi = (map(int, args.books.split("-")) if "-" in args.books else (int(args.books),) * 2)
        jobs += [(b, c) for b in range(lo, hi + 1) for c in range(1, len(bible[b - 1][1]) + 1)]
    if args.shard:
        i, n = map(int, args.shard.split("/"))
        load = [0] * n
        mine = []
        # Longest chapters first onto the least-loaded slice gives slices of similar length.
        for b, c in sorted(jobs, key=lambda j: -sum(len(v) for v in bible[j[0] - 1][1][j[1] - 1])):
            k_ = load.index(min(load))
            load[k_] += sum(len(v) for v in bible[b - 1][1][c - 1])
            if k_ == i - 1:
                mine.append((b, c))
        jobs = sorted(mine)
    k = load_kokoro(args.models)
    for b, c in jobs:
        done = [os.path.join(d, f"{b:02d}", f"{c:03d}.json") for d in (args.out, args.skip_in) if d]
        if any(os.path.exists(f) for f in done):
            continue   # already recorded: lets an interrupted run pick up where it stopped
        secs = chapter(k, bible, b, c, args.out)
        print(f"{bible[b - 1][0]} {c}: {secs:.0f}s", flush=True)


if __name__ == "__main__":
    main()
