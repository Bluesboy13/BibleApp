"""Record the Greek Bible (Septuagint + Textus Receptus NT) in modern Greek pronunciation with
Chatterbox Multilingual (MIT, resemble-ai) in its built-in Greek voice.

For each chapter writes, in the same layout the app uses for Daniel's English recordings:
  <out>/<book 01-80>/<chapter 001>.m4a   AAC mono audio
  <out>/<book>/<chapter>.json            {"s": verse start times, "e": verse end times, "d": duration}
Book numbers follow the app: 1-66 as in the KJV (Greek OT from lxx-gr.json, NT from tr.json),
67-80 the extra Septuagint books. Chapter numbers are positions in the text (1-based).

Usage: python generate.py --out new --skip-in . --shard 3/20 --minutes 320
Chapters already recorded (in --out or --skip-in) are skipped; --minutes stops cleanly before the
job time limit so the next run picks up where this one stopped.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import time
import unicodedata

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "..", "data")
BITRATE = "24k"
GAP, CHUNK_GAP, MAX_CHUNK = 0.35, 0.12, 200


def monotonic(t):
    """Polytonic -> modern monotonic Greek (one acute accent), which the model reads best."""
    t = unicodedata.normalize("NFD", t)
    t = t.replace("̀", "́").replace("͂", "́")
    t = "".join(ch for ch in t if ch not in "̣̓̔ͅ᾽᾿’ʼ")
    t = re.sub(r"[¶\[\]()“”]", "", t)
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", t)).strip()


def chunks(text):
    """Split long verses at punctuation so each piece stays within what the model reads well."""
    if len(text) <= MAX_CHUNK:
        return [text]
    parts = re.findall(r"[^·.;,]+[·.;,]?\s*", text)
    out, cur = [], ""
    for p in parts:
        if cur and len(cur) + len(p) > MAX_CHUNK:
            out.append(cur.strip())
            cur = ""
        cur += p
    if cur.strip():
        out.append(cur.strip())
    return out


def trim(a, sr):
    """Cut leading/trailing silence, keeping a short natural margin."""
    loud = np.where(np.abs(a) > 0.01)[0]
    if not len(loud):
        return a
    m = int(0.06 * sr)
    return a[max(0, loud[0] - m): loud[-1] + m]


def load_bible():
    g = json.load(open(os.path.join(DATA, "lxx-gr.json"), encoding="utf-8"))
    t = json.load(open(os.path.join(DATA, "tr.json"), encoding="utf-8"))
    books = {int(k) + 1: v for k, v in g["books"].items()}
    books.update({int(k) + 1: v for k, v in t["books"].items()})
    return books


def chapter(model, verses, b, c, out):
    sr = model.sr
    silence = lambda s: np.zeros(int(s * sr), dtype=np.float32)
    parts, starts, ends, t = [silence(0.3)], [], [], 0.3
    for i, v in enumerate(verses):
        if i > 0:
            parts.append(silence(GAP))
            t += GAP
        starts.append(round(t, 3))
        for j, piece in enumerate(chunks(monotonic(v))):
            if j:
                parts.append(silence(CHUNK_GAP))
                t += CHUNK_GAP
            torch.manual_seed(5)
            a = model.generate(piece, language_id="el").squeeze().cpu().numpy().astype(np.float32)
            a = trim(a, sr)
            parts.append(a)
            t += len(a) / sr
        ends.append(round(t, 3))
    audio = np.concatenate(parts + [silence(0.8)])
    audio = audio / max(1e-6, float(np.abs(audio).max())) * 0.89
    d = os.path.join(out, f"{b:02d}")
    os.makedirs(d, exist_ok=True)
    base = os.path.join(d, f"{c:03d}")
    pcm = (audio * 32767).astype("<i2").tobytes()
    subprocess.run([shutil.which("ffmpeg"), "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(sr), "-ac", "1",
                    "-i", "-", "-c:a", "aac", "-b:a", BITRATE, "-movflags", "+faststart", base + ".m4a"],
                   input=pcm, check=True)
    with open(base + ".json", "w") as f:
        json.dump({"s": starts, "e": ends, "d": round(len(audio) / sr, 3)}, f, separators=(",", ":"))
    return len(audio) / sr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="audio-el")
    ap.add_argument("--skip-in", default="")
    ap.add_argument("--only", nargs="*", default=[], help="book:chapter pairs")
    ap.add_argument("--shard", default="", help="i/n: record only slice i of n of what is still missing")
    ap.add_argument("--minutes", type=float, default=0, help="stop starting new chapters after this long")
    args = ap.parse_args()
    t0 = time.time()
    books = load_bible()
    size = lambda j: sum(len(v) for v in books[j[0]][j[1] - 1])
    done = lambda j: any(os.path.exists(os.path.join(d, f"{j[0]:02d}", f"{j[1]:03d}.json")) for d in (args.out, args.skip_in) if d)
    if args.only:
        jobs = [tuple(map(int, x.split(":"))) for x in args.only]
    else:
        jobs = [(b, c) for b in sorted(books) for c in range(1, len(books[b]) + 1)]
    jobs = [j for j in jobs if not done(j)]
    if args.shard:
        i, n = map(int, args.shard.split("/"))
        load, mine = [0] * n, []
        for j in sorted(jobs, key=lambda j: -size(j)):   # longest first onto the lightest slice
            k = load.index(min(load))
            load[k] += size(j)
            if k == i - 1:
                mine.append(j)
        jobs = mine
    # New Testament first, then the Old Testament and the extra books, each in Bible order.
    jobs.sort(key=lambda j: (not 40 <= j[0] <= 66, j))
    print(f"{len(jobs)} chapters to record", flush=True)
    if not jobs:
        return
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    torch.set_num_threads(os.cpu_count() or 4)
    model = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    for b, c in jobs:
        if args.minutes and time.time() - t0 > args.minutes * 60:
            print("Time budget reached; the next run continues from here.", flush=True)
            break
        s = time.time()
        secs = chapter(model, books[b][c - 1], b, c, args.out)
        print(f"{b:02d}/{c:03d}: {secs:.0f}s audio in {time.time() - s:.0f}s", flush=True)


if __name__ == "__main__":
    main()
