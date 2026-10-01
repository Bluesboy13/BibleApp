"""Build the alternative texts used by the app's "Text" setting.

Inputs (public domain unless noted):
  --brenton-en DIR   eBible.org eng-Brenton USFM files (Brenton's English Septuagint)
  --brenton-gr DIR   eBible.org grcbrent XeTeX *_src.tex files (the Greek printed with Brenton)
  --tr FILE          tr1894.txt, accented Scrivener 1894 Textus Receptus ("id@code@BOOK.c.v@text")
  --kjva FILE        scrollmapper KJVA.json: the KJV (1769) with its Apocrypha
  --wlc FILE         scrollmapper WLC.json: the Westminster Leningrad Codex (Hebrew Bible)
  --tvtms FILE       STEPBible TVTMS versification table (CC BY 4.0) for Hebrew -> KJV numbering
Writes into data/:
  lxx-en.json, lxx-gr.json   {"books": {kjvIndex: [[verse, ...] per chapter]}, "labels": {kjvIndex: {chapter: [label, ...]}}}
  tr.json                    same shape, New Testament only (KJV numbering)
  wlc.json                   Hebrew OT in its own numbering, with "map" to KJV verses from STEPBible's table
  kjv-apocrypha.json         the KJV's Apocrypha, arranged by the app's extra-book index (66+)
  lxx-map.json               {kjvIndex: [[ [[kjvChapter, kjvVerse], ...] per LXX verse ] per LXX chapter]}
The map is made here by matching the words of Brenton's English against the KJV verse by verse,
so "KJV under" can show the matching KJV verse(s) under each LXX verse.
"""
import argparse
import collections
import glob
import json
import math
import os
import re

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "..", "data")

# KJV book order (index 0-38) and the USFM codes the Brenton files use.
OT_CODES = ["GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA", "1KI", "2KI", "1CH", "2CH",
            "EZR", "NEH", "ESG", "JOB", "PSA", "PRO", "ECC", "SNG", "ISA", "JER", "LAM", "EZK", "DAG",
            "HOS", "JOL", "AMO", "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL"]
NT_CODES = ["MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL", "1TH", "2TH",
            "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV"]
# The books of the Septuagint that the KJV doesn't have, shown after Revelation (app book index 66+).
EXTRA = [("1ES", "1 Esdras"), ("TOB", "Tobit"), ("JDT", "Judith"), ("1MA", "1 Maccabees"), ("2MA", "2 Maccabees"),
         ("3MA", "3 Maccabees"), ("4MA", "4 Maccabees"), ("WIS", "Wisdom of Solomon"), ("SIR", "Sirach"),
         ("MAN", "Prayer of Manasseh"), ("BAR", "Baruch"), ("LJE", "Letter of Jeremiah"), ("SUS", "Susanna"),
         ("BEL", "Bel and the Dragon")]
EXTRA_CODES = [c for c, _ in EXTRA]
# Chapters left out because they are separate books in English Bibles (Susanna, Bel and the Dragon).
SKIP_CHAPTERS = {"DAG": {"0", "13"}}


def clean_usfm(t):
    t = re.sub(r"\\f .*?\\f\*", "", t)
    t = re.sub(r"\\x .*?\\x\*", "", t)
    t = re.sub(r"\\\+?[a-z0-9]+\*?", " ", t)
    return " ".join(t.split())


def parse_brenton_en(d, codes=OT_CODES):
    books = {}
    for code in codes:
        f = glob.glob(os.path.join(d, f"*-{code}eng-Brenton.usfm"))[0]
        src = open(f, encoding="utf-8-sig").read()
        src = re.sub(r"\\vp (.*?)\\vp\*", lambda m: "\\vlabel " + m.group(1).strip() + " ", src)
        chapters, cur, para = collections.OrderedDict(), None, False
        verse = None
        for tok in re.split(r"(\\c \S+|\\v \S+|\\p\b|\\m\b|\\nb\b|\\d\b|\\vlabel \S+)", src):
            if not tok:
                continue
            if tok.startswith("\\c "):
                cur = tok[3:].strip()
                chapters[cur] = []
                verse = None
            elif tok.startswith("\\v "):
                verse = [tok[3:].strip(), "", para]
                para = False
                chapters[cur].append(verse)
            elif tok.startswith("\\vlabel "):
                if verse is not None:
                    verse[0] = tok[8:].strip()
            elif tok in ("\\p",):
                para = True
            elif tok in ("\\m", "\\nb", "\\d"):
                pass
            elif verse is not None:
                verse[1] += " " + tok
        books[code] = collections.OrderedDict(
            (c, [(lab, clean_usfm(txt), p) for lab, txt, p in vs if clean_usfm(txt)])
            for c, vs in chapters.items() if c not in SKIP_CHAPTERS.get(code, ()))
        books[code] = collections.OrderedDict((c, vs) for c, vs in books[code].items() if vs)   # e.g. Proverbs 30 is only a note
    return split_esdras(books) if "EZR" in books else books


def clean_tex(t):
    t = re.sub(r"\\[A-Za-z]+\s*", " ", t).replace("{", " ").replace("}", " ")
    return " ".join(t.split())


def parse_brenton_gr(d, codes=OT_CODES):
    books = {}
    for code in codes:
        name = {"NEH": None}.get(code, code)
        if name is None:
            continue
        src = open(os.path.join(d, f"{code}_src.tex"), encoding="utf-8-sig").read()
        chapters, cur, verse, para = collections.OrderedDict(), None, None, False
        for tok in re.split(r"(\\(?:ChapOne|Chap|PsalmChap)\{[^}]*\}|\\OneChap\b|\\(?:VerseOne|VS)\{[^}]*\}|\\PP\b)", src):
            if not tok:
                continue
            m = re.match(r"\\(?:ChapOne|Chap|PsalmChap)\{([^}]*)\}", tok)
            if m or tok == "\\OneChap":
                cur = m.group(1) if m else "1"
                chapters[cur] = []
                verse = None
                continue
            m = re.match(r"\\(?:VerseOne|VS)\{([^}]*)\}", tok)
            if m:
                verse = [m.group(1), "", para]
                para = False
                chapters[cur].append(verse)
            elif tok == "\\PP":
                para = True
            elif verse is not None:
                verse[1] += tok
        books[code] = collections.OrderedDict(
            (c, [(lab, clean_tex(txt), p) for lab, txt, p in vs if clean_tex(txt)])
            for c, vs in chapters.items() if c not in SKIP_CHAPTERS.get(code, ()))
        books[code] = collections.OrderedDict((c, vs) for c, vs in books[code].items() if vs)
    return split_esdras(books) if "EZR" in books else books


def split_esdras(books):
    """Brenton prints Ezra and Nehemiah as one book (2 Esdras); Nehemiah is its chapters 11-23."""
    ezr = books["EZR"]
    if len(ezr) == 23:
        books["NEH"] = collections.OrderedDict((str(int(c) - 10), v) for c, v in ezr.items() if int(c) > 10)
        books["EZR"] = collections.OrderedDict((c, v) for c, v in ezr.items() if int(c) <= 10)
    return books


def pack(books, codes, offset=0):
    """Position-indexed text plus the printed chapter/verse labels where they aren't simply 1, 2, 3..."""
    out, labels, chlabels, keys = {}, {}, {}, {}
    for i, code in enumerate(codes):
        b = i + offset
        chs = list(books[code].items())
        out[b] = [[("¶" if p and j else "") + t for j, (lab, t, p) in enumerate(vs)] for _, vs in chs]
        keys[b] = [[(cl, lab) for lab, _, _ in vs] for cl, vs in chs]
        lab = {}
        for ci, (_, vs) in enumerate(chs):
            got = [lab_ for lab_, _, _ in vs]
            if got != [str(j + 1) for j in range(len(vs))]:
                lab[ci + 1] = got
        if lab:
            labels[b] = lab
        cls = [cl for cl, _ in chs]
        if cls != [str(j + 1) for j in range(len(chs))]:
            chlabels[b] = cls
    return {"books": out, "labels": labels, "chapters": chlabels}, keys


STOP = set("the and of to in that he his for i unto a shall is be it not with they all them him my was thou thy which by as said lord god will me from have their on are thee but this ye upon you there were so when an at who o or".split())


def words(t):
    return [w for w in re.findall(r"[a-z]+", t.lower()) if w not in STOP and len(w) > 2]


def _keys_extra(t, b):
    """(chapter label, verse label) for each verse of a packed book."""
    chl = t["chapters"].get(b) or [str(i + 1) for i in range(len(t["books"][b]))]
    return [[(chl[ci], (t["labels"].get(b, {}).get(ci + 1) or [str(j + 1) for j in range(len(vs))])[vi])
             for vi in range(len(vs))] for ci, vs in enumerate(t["books"][b])]


def align(kjv_book, lxx_chapters):
    """For each KJV verse pick the Brenton verse that shares the most (rare) words, preferring nearby verses."""
    lxx = [(ci, vi, t) for ci, vs in enumerate(lxx_chapters) for vi, t in enumerate(vs)]
    kjv = [(ci, vi, t) for ci, vs in enumerate(kjv_book) for vi, t in enumerate(vs)]
    docs = [words(t) for _, _, t in lxx] + [words(t) for _, _, t in kjv]
    df = collections.Counter(w for d in docs for w in set(d))
    vocab = {w: i for i, w in enumerate(df)}
    n = len(docs)

    def vec(d):
        v = np.zeros(len(vocab), dtype=np.float32)
        for w, c in collections.Counter(d).items():
            v[vocab[w]] = (1 + math.log(c)) * math.log(n / df[w])
        nrm = np.linalg.norm(v)
        return v / nrm if nrm else v
    L = np.stack([vec(d) for d in docs[:len(lxx)]]) if lxx else np.zeros((0, len(vocab)))
    K = np.stack([vec(d) for d in docs[len(lxx):]])
    S = K @ L.T                                     # KJV x LXX similarity
    assign = []
    prev = -1
    for k in range(len(kjv)):
        expected = prev + 1
        dist = np.abs(np.arange(len(lxx)) - expected)
        score = S[k] - 0.0015 * np.minimum(dist, 200)
        best = int(np.argmax(score))
        if S[k, best] < 0.12 and 0 <= expected < len(lxx):
            best = expected                         # too little in common: keep the running order
        assign.append(best)
        prev = best
    m = [[[] for _ in vs] for vs in lxx_chapters]
    for k, l in enumerate(assign):
        ci, vi, _ = lxx[l]
        m[ci][vi].append([kjv[k][0] + 1, kjv[k][1] + 1])
    return m, [float(S[k, l]) for k, l in enumerate(assign)]


# KJV Apocrypha books (scrollmapper names) for the app's extra-book indices. 3 and 4 Maccabees aren't in it.
KJVA_BOOKS = {66: ("I Esdras", None), 67: ("Tobit", None), 68: ("Judith", None), 69: ("I Maccabees", None),
              70: ("II Maccabees", None), 73: ("Wisdom", None), 74: ("Sirach", None),
              75: ("Prayer of Manasses", None), 76: ("Baruch", range(1, 6)), 77: ("Baruch", [6]),
              78: ("Susanna", None), 79: ("Bel and the Dragon", None)}


def kjv_apocrypha(path):
    a = {b["name"]: b for b in json.load(open(path, encoding="utf-8"))["books"]}
    out = {}
    for idx, (name, chs) in KJVA_BOOKS.items():
        chapters = a[name]["chapters"]
        if chs:
            chapters = [c for c in chapters if c["chapter"] in chs]
        out[idx] = [[" ".join(v["text"].split()) for v in c["verses"]] for c in chapters]
    return out


TVTMS_BOOKS = ["Gen", "Exo", "Lev", "Num", "Deu", "Jos", "Jdg", "Rut", "1Sa", "2Sa", "1Ki", "2Ki", "1Ch", "2Ch",
               "Ezr", "Neh", "Est", "Job", "Psa", "Pro", "Ecc", "Sng", "Isa", "Jer", "Lam", "Ezk", "Dan",
               "Hos", "Jol", "Amo", "Oba", "Jon", "Mic", "Nam", "Hab", "Zep", "Hag", "Zec", "Mal"]


def hebrew_map(tvtms, wlc_books, kjv):
    """Map each Hebrew (WLC) verse to its KJV verse(s) using STEPBible's TVTMS 'Hebrew' rows."""
    lines = open(tvtms, encoding="utf-8").read().split("\n")
    start = next(i for i, l in enumerate(lines) if l.startswith("#DataStart(Expanded)"))
    end = next(i for i, l in enumerate(lines) if l.startswith("#DataEnd(Expanded)"))
    bidx = {b: i for i, b in enumerate(TVTMS_BOOKS)}

    def parse_std(book, txt):
        """'Gen.32:1' / 'Gen.5:32; 6:1' / 'Gen.2:25-3:1' / 'Psa.3:Title' -> [(c, v), ...] in KJV numbering."""
        refs, chap = [], None
        b = bidx[book]
        for part in txt.replace(book + ".", "").split(";"):
            part = part.strip()
            if not part or "Title" in part:
                continue
            m = re.match(r"^(?:(\d+):)?(\d+)(?:-(?:(\d+):)?(\d+))?$", part)
            if not m:
                continue
            c1 = int(m.group(1)) if m.group(1) else chap
            v1 = int(m.group(2))
            chap = c1
            if m.group(4):
                c2 = int(m.group(3)) if m.group(3) else c1
                v2 = int(m.group(4))
                c, v = c1, v1
                while (c, v) <= (c2, v2):
                    if c <= len(kjv[b][1]) and v <= len(kjv[b][1][c - 1]):
                        refs.append((c, v))
                        v += 1
                    else:
                        c, v = c + 1, 1
                    if c > len(kjv[b][1]):
                        break
            else:
                refs.append((c1, v1))
        return refs

    plain, parts = {}, collections.defaultdict(list)
    for l in lines[start + 1:end]:
        f = l.split("\t")
        if len(f) < 4 or "Hebrew" not in [t.strip() for t in f[0].split("+")]:
            continue
        m = re.match(r"^([1-3]?[A-Za-z]{2,3})\.(\d+):(\d+|Title)(!\w+)?$", f[1].strip())
        if not m or m.group(1) not in bidx or m.group(3) == "Title":
            continue
        key = (bidx[m.group(1)], int(m.group(2)), int(m.group(3)))
        refs = parse_std(m.group(1), f[2].strip())
        if m.group(4):
            parts[key] += refs
        else:
            plain[key] = refs
    out = {}
    for b in range(39):
        out[b] = []
        for ci, vs in enumerate(wlc_books[b]):
            row = []
            for vi in range(len(vs)):
                key = (b, ci + 1, vi + 1)
                refs = plain.get(key) if key in plain else parts.get(key)
                if refs is None:
                    refs = [(ci + 1, vi + 1)] if ci < len(kjv[b][1]) and vi < len(kjv[b][1][ci]) else []
                row.append([list(r) for r in dict.fromkeys(refs)])
            out[b].append(row)
    return out


def strip_cantillation(t):
    """Keep the vowel points, drop the cantillation marks (U+0591-U+05AF) and the paseq."""
    t = re.sub("[\u0591-\u05AF\u05BD\u05C0]", "", t)
    return " ".join(t.replace("/", "").split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brenton-en", required=True)
    ap.add_argument("--brenton-gr", required=True)
    ap.add_argument("--tr", required=True)
    ap.add_argument("--kjva", required=True)
    ap.add_argument("--wlc", required=True)
    ap.add_argument("--tvtms", required=True)
    a = ap.parse_args()
    kjv = json.load(open(os.path.join(DATA, "kjv.json"), encoding="utf-8"))

    en = parse_brenton_en(a.brenton_en)
    gr = parse_brenton_gr(a.brenton_gr)
    (en_p, en_keys), (gr_p, gr_keys) = pack(en, OT_CODES), pack(gr, OT_CODES)
    # Add the extra books after Revelation, with their names (they have no KJV to match against).
    for t, parsed in ((en_p, parse_brenton_en(a.brenton_en, EXTRA_CODES)), (gr_p, parse_brenton_gr(a.brenton_gr, EXTRA_CODES))):
        extra, _ = pack(parsed, EXTRA_CODES, offset=66)
        for k in ("books", "labels", "chapters"):
            t[k].update(extra[k])
        t["names"] = {66 + i: name for i, (_, name) in enumerate(EXTRA)}
    apoc = kjv_apocrypha(a.kjva)
    for b in apoc:
        m, _ = align(apoc[b], [[t.lstrip("¶") for t in vs] for vs in en_p["books"][b]])
        by_label = {key: m[ci][vi] for ci, ch in enumerate(_keys_extra(en_p, b)) for vi, key in enumerate(ch)}
        en_p.setdefault("map", {})[b] = m
        gr_p.setdefault("map", {})[b] = [[by_label.get(key, []) for key in ch] for ch in _keys_extra(gr_p, b)]

    # Match Brenton's English to the KJV, then give each text a map by Brenton's chapter:verse labels.
    sims = []
    for b in range(39):
        m, s_ = align(kjv[b][1], [[t.lstrip("¶") for t in vs] for vs in en_p["books"][b]])
        sims += s_
        by_label = {key: m[ci][vi] for ci, ch in enumerate(en_keys[b]) for vi, key in enumerate(ch)}
        en_p.setdefault("map", {})[b] = m
        gr_p.setdefault("map", {})[b] = [[by_label.get(key, []) for key in ch] for ch in gr_keys[b]]
        unmatched = sum(1 for ch in gr_keys[b] for key in ch if key not in by_label)
        if unmatched:
            print("Greek verses without an English label match:", OT_CODES[b], unmatched)
    print("alignment: KJV verses", len(sims), "weak matches (<0.12):", sum(x < 0.12 for x in sims))

    tr = collections.defaultdict(lambda: collections.defaultdict(dict))
    for line in open(a.tr, encoding="utf-8-sig"):
        parts = line.rstrip("\n").split("@")
        if len(parts) < 4 or not parts[0].isdigit():
            continue
        code, c, v = parts[2].split(".")
        tr[code][int(c)][int(v)] = parts[3].strip()
    trbooks = {}
    for i, code in enumerate(NT_CODES):
        kb = kjv[39 + i][1]
        trbooks[39 + i] = [[tr[code][c + 1].get(v + 1, "") for v in range(len(vs))] for c, vs in enumerate(kb)]
        missing = sum(1 for c, vs in enumerate(kb) for v in range(len(vs)) if not tr[code][c + 1].get(v + 1))
        if missing:
            print("TR missing verses", code, missing)

    def dump(name, obj):
        with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        print(name, os.path.getsize(os.path.join(DATA, name)) // 1024, "KB")
    dump("lxx-en.json", en_p)
    dump("lxx-gr.json", gr_p)
    dump("tr.json", {"books": trbooks})
    dump("kjv-apocrypha.json", {"books": apoc})

    # The WLC file is in Hebrew Bible order; match its books to KJV order by name.
    wlc = {re.sub(r"^III ", "3 ", re.sub(r"^II ", "2 ", re.sub(r"^I ", "1 ", x["name"]))): x
           for x in json.load(open(a.wlc, encoding="utf-8"))["books"]}
    wlc_books = {b: [[strip_cantillation(v["text"]) for v in c["verses"]] for c in wlc[kjv[b][0]]["chapters"]] for b in range(39)}
    hmap = hebrew_map(a.tvtms, wlc_books, kjv)
    # Check: every KJV verse should be reached from some Hebrew verse.
    hit = collections.Counter((b, c, v) for b in hmap for ch in hmap[b] for refs in ch for c, v in refs)
    missing = [(kjv[b][0], c + 1, v + 1) for b in range(39) for c, vs in enumerate(kjv[b][1]) for v in range(len(vs)) if (b, c + 1, v + 1) not in hit]
    print("Hebrew map: KJV verses not reached:", len(missing), missing[:12])
    print("Hebrew map: KJV verses reached more than once:", sum(1 for k, n in hit.items() if n > 1))
    dump("wlc.json", {"books": wlc_books, "map": hmap})


if __name__ == "__main__":
    main()
