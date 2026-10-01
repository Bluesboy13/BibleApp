"""Restore words missing from the accented TR (tr1894.txt drops many short words such as ὁ and ἡ)
by aligning each verse with Dr. Maurice Robinson's complete, public-domain Scrivener 1894 text
(github.com/byztxt/greektext-scrivener, textonly/*.SCV, unaccented transliteration).

Words present in Robinson's text but missing here are inserted with the accents they carry at
that spot in the Robinson-Pierpont Byzantine text (github.com/byztxt/byzantine-majority-text,
csv-unicode/ccat/no-variants, public domain), which tells ἡ "the" from ἢ "or"; failing that,
in their usual accented form from the rest of the NT. Nothing else is changed.
Usage: python repair_tr.py SCV_DIR BYZ_CSV_DIR data/tr.json
"""
import collections
import difflib
import json
import os
import re
import sys
import unicodedata

FILES = ["MT", "MR", "LU", "JOH", "AC", "RO", "1CO", "2CO", "GA", "EPH", "PHP", "COL", "1TH", "2TH", "1TI",
         "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE", "1JO", "2JO", "3JO", "JUDE", "RE"]
BYZ = ["MAT", "MAR", "LUK", "JOH", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL", "1TH", "2TH", "1TI",
       "2TI", "TIT", "PHM", "HEB", "JAM", "1PE", "2PE", "1JO", "2JO", "3JO", "JUD", "REV"]
BETA = dict(zip("abgdezhyiklmnxoprstufcqwv", "αβγδεζηθικλμνξοπρστυφχψωσ"))


def base(w):
    w = unicodedata.normalize("NFD", w.lower())
    return "".join(ch for ch in w if "α" <= ch <= "ω").replace("ς", "σ")


def fix_breathing(word, forms):
    """A few words lost their breathing mark (ημῶν): use the marked spelling seen elsewhere."""
    d = unicodedata.normalize("NFD", word)
    if not d or d[0].lower() not in "αεηιουω" or "\u0313" in d[:4] or "\u0314" in d[:4]:
        return word
    core = re.sub(r"[^\w\u0300-\u036f]", "", d)
    for cand, _ in forms[base(word)].most_common():
        c = unicodedata.normalize("NFD", cand)
        if c.replace("\u0313", "").replace("\u0314", "").lower() == core.lower() and c != core:
            fixed = unicodedata.normalize("NFC", c)
            if word[0].isupper():
                fixed = fixed[0].upper() + fixed[1:]
            return word.replace(unicodedata.normalize("NFC", core), fixed)
    return word


def scv(path):
    verses, cur = {}, None
    text = re.sub(r"\[[^\]]*\]", " ", open(path, encoding="latin-1").read())
    for tok in text.split():
        m = re.fullmatch(r"(\d+):(\d+)", tok)
        if m:
            cur = (int(m[1]), int(m[2]))
            verses[cur] = []
        elif cur and re.fullmatch(r"[a-z]+", tok):
            verses[cur].append("".join(BETA[ch] for ch in tok))
    return verses


def byz(path):
    import csv
    return {(int(r["chapter"]), int(r["verse"])): r["text"].split() for r in csv.DictReader(open(path, encoding="utf-8"))}


def accent_from(out, inserted, ref):
    """Give each inserted word the accents of the same word at the same spot in the reference text."""
    if not ref:
        return out
    clean = [re.sub(r"[^\w]", "", w) for w in ref]
    sm = difflib.SequenceMatcher(None, [base(w) for w in out], [base(w) for w in clean], autojunk=False)
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            if a + k in inserted and clean[b + k]:
                w = clean[b + k]
                out[a + k] = w[0].lower() + w[1:] if a + k else w
    return out


def main(scv_dir, byz_dir, tr_path):
    tr = json.load(open(tr_path, encoding="utf-8"))
    forms = collections.defaultdict(collections.Counter)
    for chs in tr["books"].values():
        for vs in chs:
            for v in vs:
                for w in v.split():
                    w = re.sub(r"[^\w]", "", w)
                    if w:
                        forms[base(w)][w if not w[0].isupper() else w] += 1
    best = lambda b: next((w for w, _ in forms[b].most_common() if not w[0].isupper()), None) or b
    added = missing_verses = 0
    for i, f in enumerate(FILES):
        ref = scv(os.path.join(scv_dir, f + ".SCV"))
        acc = byz(os.path.join(byz_dir, BYZ[i] + ".csv"))
        chs = tr["books"][str(39 + i)]
        for c, vs in enumerate(chs):
            for v, text in enumerate(vs):
                want = ref.get((c + 1, v + 1))
                if want is None:
                    missing_verses += 1
                    continue
                words = text.split()
                have = [base(w) for w in words]
                out, inserted = [], set()
                for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, have, want, autojunk=False).get_opcodes():
                    if op == "insert":
                        inserted.update(range(len(out), len(out) + b2 - b1))
                        out += [best(w) for w in want[b1:b2]]
                        added += b2 - b1
                    out += words[a1:a2]
                out = accent_from(out, inserted, acc.get((c + 1, v + 1)))
                out = [fix_breathing(w, forms) for w in out]
                vs[v] = re.sub(r"\bπρὶν ἡ\b", "πρὶν ἢ", " ".join(out))
    json.dump(tr, open(tr_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"restored {added} words; {missing_verses} verses not in the reference")


if __name__ == "__main__":
    main(*sys.argv[1:4])
