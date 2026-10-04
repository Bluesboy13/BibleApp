"""Rebuild the 1909 Bikol New Testament (An Bagong Tipan, British and Foreign Bible Society, Manila;
public domain) from the OCR text of the University of Michigan scan on archive.org
(ajg9045.0001.001.umich.edu_djvu.txt), verse by verse, with automatic OCR corrections.

Usage: python bikol_ocr.py OUT_JSON OCR_TXT [OCR_TXT ...]   (e.g. the library's ABBYY text and a Tesseract re-read)
Chapters are found from "CAPITULO" headings and verse 1 restarts and laid out by the KJV's
chapter counts; every chapter's verse count is checked against the KJV and reported.
"""
import collections
import difflib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KJV = json.load(open(os.path.join(HERE, "..", "..", "data", "kjv.json"), encoding="utf-8"))
NT = list(range(39, 66))

DIGITLIKE = str.maketrans({"l": "1", "I": "1", "i": "1", "o": "0", "O": "0", "S": "5", "s": "5", "B": "8", "Z": "2"})


# Running heads name the book on every page (OCR spellings vary): book index in the NT.
def header_book(name):
    n = re.sub(r"[^A-Z ]", "", name.upper()).split()
    if not n:
        return None
    prefix = 0
    if n[0] in ("I", "II", "III", "IL", "IH", "HI", "U", "H", "N", "L"):
        prefix = {"I": 1, "L": 1, "II": 2, "IL": 2, "U": 2, "H": 2, "N": 2, "IH": 3, "HI": 3, "III": 3}[n[0]]
        n = n[1:]
    w = " ".join(n)
    keys = [("MATEO", 0), ("MARCOS", 1), ("MAECOS", 1), ("LUCAS", 2), ("APOSTOLES", 4), ("ROMA", 5),
            ("EOMA", 5), ("KOMA", 5), ("CORINTIOS", 6), ("COEINTIOS", 6), ("GALATAS", 8), ("EFESIOS", 9),
            ("FILIPOS", 10), ("COLOSAS", 11), ("TESALONICENSES", 12), ("TIMOTEO", 14), ("TITO", 16),
            ("FILEMON", 17), ("HEBREOS", 18), ("HEBEEOS", 18), ("SANTIAGO", 19), ("PEDRO", 20),
            ("JUDAS", 25), ("APOCALIPSIS", 26)]
    import difflib
    for word in n:
        hit = difflib.get_close_matches(word, [k for k, _ in keys], n=1, cutoff=0.75)
        if hit:
            b = dict(keys)[hit[0]]
            if b in (6, 12, 14, 20):
                b += 1 if prefix == 2 else 0
            return b
    if "JUAN" in w:
        return 3 if prefix == 0 else 21 + prefix   # 1-3 John are 22-24
    return None


def blocks(text):
    """Paragraph blocks (separated by blank lines), with running heads and page numbers removed."""
    out, cur = [], []
    for line in text.split("\n"):
        s = line.strip()
        # Running heads like "SAN MATEO 1 & 2. 3" / "264 SAN JUAN 1." and bare page numbers.
        hm = re.fullmatch(r"[\d\s.,]*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ .]{2,40}?)[\s.]*(\d+)[\d\s&.,lIoO]*", s)
        if hm and not re.match(r"CAP.TULO", s):
            book = header_book(hm.group(1))
            if book is not None:
                if cur:
                    out.append(cur)
                    cur = []
                out.append([("HDR", book, int(hm.group(2)))])
            continue
        if re.fullmatch(r"[\divxlIVXL.]{1,5}", s):
            continue
        if not s:
            if cur:
                out.append(cur)
                cur = []
            continue
        cur.append(s)
    if cur:
        out.append(cur)
    return out


def join(lines):
    t = ""
    for ln in lines:
        if t.endswith("-"):
            t = t[:-1] + ln
        else:
            t = (t + " " + ln).strip()
    return re.sub(r"\s+", " ", t)


def verse_number(tok, expected):
    """A printed verse number, allowing for common OCR misreadings (2 read as 9, a stray digit)."""
    d = tok.translate(DIGITLIKE)
    tries = [d, d.replace("9", "2", 1), d[1:], d[:-1], d.replace("8", "3", 1), d.replace("6", "5", 1)]
    for t in tries:
        if t.isdigit() and expected <= int(t) <= expected + 2:
            return int(t)
    return int(d) if d.isdigit() else None


def roman(s):
    s = s.upper().replace("1", "I").replace("L", "I").replace("T", "I").strip(" .")
    s = re.sub(r"[^IVX]", "", s)
    vals = {"I": 1, "V": 5, "X": 10}
    n = 0
    for i, ch in enumerate(s):
        v = vals[ch]
        n += -v if i + 1 < len(s) and vals[s[i + 1]] > v else v
    return n or None


def parse(text):
    """Returns {(book, chapter): {verse: text}}, following the printed CAPITULO numbers."""
    out = {}
    bi, ch, cur = -1, 0, None
    start = text.find("CAP")   # skip the title pages
    for blk in blocks(text[start:]):
        if isinstance(blk[0], tuple):
            _, hb, hc = blk[0]
            if hb < len(NT) and hc > len(KJV[NT[hb]][1]):
                hc = 1 if hb != bi else ch      # a page number, not a chapter (one-chapter books)
            # Resynchronise on the page's running head: right book, and at least its first chapter.
            # (OCR misreads digits in the heads, so within a book only step one chapter, and only
            # when the current chapter is nearly complete.)
            done = (cur is not None and 0 <= bi < len(NT) and 0 < ch <= len(KJV[NT[bi]][1])
                    and len(cur) >= 0.8 * len(KJV[NT[bi]][1][ch - 1]))
            if hb > bi or (hb == bi and hc == ch + 1 and done):
                if hb != bi:
                    bi, ch = hb, max(1, hc)
                else:
                    ch = hc
                if bi < len(NT):
                    cur = out.setdefault((bi, ch), {})
            continue
        first = re.sub(r"^[\W_]+", "", blk[0])
        mc = re.match(r"CAP.TULO\s+(\S+)", first)
        if mc:
            n = roman(mc.group(1))
            # "Chapter I" starts the next book only once this one is (nearly) complete; otherwise
            # it is a misread numeral.
            if bi >= len(NT):
                continue            # past Revelation (end matter)
            if bi < 0 or (n == 1 and ch >= len(KJV[NT[bi]][1]) - 1):
                bi, ch = bi + 1, 1
            else:
                # The page head may already have moved us to this chapter.
                ch = n if n and ch <= n <= ch + 2 else ch + 1
            cur = out.setdefault((bi, ch), {})
            blk = blk[1:]
            if not blk:
                continue
            first = re.sub(r"^[\W_]+", "", blk[0])
        if cur is None or bi >= len(NT):
            continue
        m = re.match(r"([0-9lIoOSsBZ]{1,3})\s+(.*)", first)
        expected = max(cur) + 1 if cur else 1
        num = verse_number(m.group(1), expected) if m and re.search(r"\d", m.group(1)) else None
        kc = KJV[NT[bi]][1]
        kjv_len = len(kc[ch - 1]) if ch <= len(kc) else 0
        if num is not None and num in (expected, expected + 1, expected + 2):
            cur[num] = join([m.group(2)] + blk[1:])
        elif num == 1 and cur and len(cur) >= 0.8 * kjv_len:
            # A chapter whose heading the OCR missed (one-chapter books have none at all).
            if ch >= len(kc):
                bi, ch = bi + 1, 1
            else:
                ch += 1
            cur = out.setdefault((bi, ch), {1: join([m.group(2)] + blk[1:])})
        elif len(blk) == 1 and len(first) < 70 and not cur.get(expected - 1, "").endswith(","):
            continue                                       # a section heading
        elif cur:
            last = max(cur)
            cur[last] = join([cur[last], *blk])
    return out


# --- OCR corrections ---
FIXES = [
    (r"(?<=[a-zA-Záéíóú])6\b", "ó"), (r"(?<=[a-z])6(?=[a-z])", "ó"),
    (r"(?<=[a-zA-Z])4(?=[a-z])", "q"), (r"\bmag(?:na|fia|iia|ña|ńa)\b", "magña"),
    (r"\bMag(?:na|fia|iia)\b", "Magña"), (r"(?<=[a-z])fi(?=[aeiou])", "ñ"), (r"\)'", "y"),
    (r"(?<=[a-z])£(?=[a-z])", "á"), (r"\^", ""), (r"\s+([,;:.?!])", r"\1"),
]


def correct(verses_all):
    for pat, rep in FIXES:
        verses_all = [re.sub(pat, rep, v) for v in verses_all]
    words = collections.Counter(w for v in verses_all for w in re.findall(r"[^\W\d_]+", v))

    def fix(w):
        if words[w] >= 3 or len(w) < 4:
            return w
        # A rare word one letter away from a common one is almost always an OCR slip.
        best = None
        for i in range(len(w)):
            for c in "abcdefghijklmnopqrstuvwyzáéíóúñ":
                for cand in (w[:i] + c + w[i + 1:], w[:i] + c + w[i:], w[:i] + w[i + 1:]):
                    if cand != w and words[cand] >= 25 and (best is None or words[cand] > words[best]):
                        best = cand
        return best or w
    cache = {}
    out = []
    for v in verses_all:
        out.append(re.sub(r"[^\W\d_]+", lambda m: cache.setdefault(m.group(0), fix(m.group(0))), v))
    return out, sum(1 for k, x in cache.items() if k != x)


def score(ch, lex):
    """Share of a chapter's words that are common in the book (OCR slips make rare words)."""
    words = [w for t in ch.values() for w in re.findall(r"[^\W\d_]+", t)]
    return sum(1 for w in words if lex[w] >= 3) / max(1, len(words))


def main(dst, *sources):
    """Each source is one OCR reading of the whole book; per chapter the best reading is kept."""
    parsed = [parse(open(src, encoding="utf-8", errors="replace").read()) for src in sources]
    for src, p in zip(sources, parsed):
        print(os.path.basename(src), "chapters found:", len(p))
    lex = collections.Counter(w for p in parsed for ch in p.values() for t in ch.values()
                              for w in re.findall(r"[^\W\d_]+", t))
    # A reading whose chapter starts like a *different* chapter of the first reading has lost its
    # place (e.g. Romans 5 filed as Revelation 21): never use it there.
    def opening(ch):
        return next((t for _, t in sorted(ch.items()) if t), "")[:120]
    starts = {k: opening(ch) for k, ch in parsed[0].items() if opening(ch)}

    def misplaced(key, ch):
        o = opening(ch)
        return bool(o) and any(k != key and difflib.SequenceMatcher(None, o, s0).ratio() > 0.8
                               for k, s0 in starts.items() if abs(len(s0) - len(o)) < 40)
    flat, keys, bad, used = [], [], 0, collections.Counter()
    for bi, b in enumerate(NT):
        for ci, kv in enumerate(KJV[b][1]):
            cands = [(p.get((bi, ci + 1), {}), si) for si, p in enumerate(parsed)
                     if si == 0 or not misplaced((bi, ci + 1), p.get((bi, ci + 1), {}))]
            ch, si = min(cands, key=lambda c: (abs((max(c[0]) if c[0] else 0) - len(kv)), -score(c[0], lex)))
            used[os.path.basename(sources[si])] += 1
            got = max(ch) if ch else 0
            if got != len(kv):
                bad += 1
                print(f"  {KJV[b][0]} {ci + 1}: {got} verses (KJV {len(kv)})")
            for v in range(1, max(got, len(kv)) + 1):
                keys.append((b, ci, v))
                flat.append(ch.get(v, ""))
    print("chapters taken from each reading:", dict(used))
    print("chapters not matching the KJV's verse count:", bad)
    fixed, n = correct(flat)
    print("words corrected:", n, "| empty verses:", sum(1 for t in fixed if not t))
    out = {}
    for (b, ci, v), t in zip(keys, fixed):
        out.setdefault(b, [])
        while len(out[b]) <= ci:
            out[b].append([])
        out[b][ci].append(t)
    json.dump({"books": out}, open(dst, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main(sys.argv[1], *sys.argv[2:])
