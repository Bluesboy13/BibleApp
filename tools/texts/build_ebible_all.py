"""Build every freely shareable eBible.org Bible the app doesn't already carry, for the
FreeBiblos/BibleApp-texts repo (run there by its GitHub workflow).

Usage:
  python build_ebible_all.py pick TRANSLATIONS_CSV > wanted.tsv
      one translation per language not already in the app: public domain first, then the most
      literal (Unlocked Literal Bible), then any other freely licensed full Bible
  python build_ebible_all.py build TRANSLATIONS_CSV ZIP_DIR OUT_DIR
      converts each <id>_usfx.zip in ZIP_DIR to OUT_DIR/<id>.json.gz and writes OUT_DIR/index.json
"""
import csv
import gzip
import io
import json
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_langs as bl   # noqa: E402

# Languages the app already has (ISO 639-3, as eBible codes them).
HAVE = set("""eng grc heb hbo deu spa fra ita tgl cmn zho rus nld pol hun ces swe nob nor nno dan fin jpn vie tha
bul ell mal mya srp sqi als mri mlg plt arb arz ara kor pes fas prs ukr por hat haw ton hin ben tam tel mar guj
pan kan ory urd ind swh swa tur npi nep ceb ilo som yor hau ibo bcl""".split())
SKIP = {"ron1924"}   # printed in Cyrillic letters, which Romanian readers don't use
# BCP-47 codes for languages with device voices (eBible uses ISO 639-3).
BCP47 = {"afr": "af", "amh": "am", "hye": "hy", "aze": "az", "eus": "eu", "bel": "be", "bos": "bs", "cat": "ca",
         "hrv": "hr", "est": "et", "fil": "fil", "glg": "gl", "kat": "ka", "isl": "is", "gle": "ga", "kaz": "kk",
         "khm": "km", "lao": "lo", "lav": "lv", "lit": "lt", "mkd": "mk", "msa": "ms", "zsm": "ms", "mon": "mn",
         "ron": "ro", "slk": "sk", "slv": "sl", "sin": "si", "uzb": "uz", "uzn": "uz", "cym": "cy", "zul": "zu",
         "xho": "xh", "sot": "st", "tsn": "tn", "sna": "sn", "kin": "rw", "lug": "lg", "orm": "om", "tir": "ti",
         "jav": "jv", "sun": "su", "lin": "ln", "nya": "ny", "wol": "wo", "pus": "ps", "kur": "ku", "tgk": "tg",
         "tuk": "tk", "kir": "ky", "yid": "yi", "epo": "eo", "lat": "la", "fij": "fj", "smo": "sm"}


def rows(path):
    return list(csv.DictReader(open(path, encoding="utf-8-sig")))


def full(r):
    return r["downloadable"] == "True" and r["Redistributable"] == "True" and \
        int(r["OTbooks"] or 0) >= 39 and int(r["NTbooks"] or 0) >= 27


def rank(r):
    c = r["Copyright"].lower()
    if "public domain" in c:
        return 0
    if "ulb" in r["translationId"].lower() or "literal" in r["title"].lower():
        return 1
    if "biblica" in c:
        return 3      # Biblica's open Bibles are meaning-based: last resort
    return 2


def pick(csv_path):
    best = {}
    for r in rows(csv_path):
        lc = r["languageCode"]
        if lc in HAVE or not full(r) or r["translationId"] in SKIP:
            continue
        key = (rank(r), -int(r["OTverses"] or 0) - int(r["NTverses"] or 0))
        if lc not in best or key < best[lc][0]:
            best[lc] = (key, r)
    for lc, (_, r) in sorted(best.items()):
        print(f"{r['translationId']}\t{lc}\t{r['languageNameInEnglish']}")


def build(csv_path, zip_dir, out_dir):
    meta = {r["translationId"]: r for r in rows(csv_path)}
    kjv = json.load(open(os.path.join(bl.DATA, "kjv.json"), encoding="utf-8"))
    os.makedirs(out_dir, exist_ok=True)
    index = []
    for z in sorted(os.listdir(zip_dir)):
        if not z.endswith("_usfx.zip"):
            continue
        tid = z[:-len("_usfx.zip")]
        r = meta.get(tid)
        if not r:
            continue
        tmp = os.path.join(out_dir, "_tmp", tid)
        os.makedirs(tmp, exist_ok=True)
        with zipfile.ZipFile(os.path.join(zip_dir, z)) as zf:
            zf.extractall(tmp)
        usfx = [f for f in os.listdir(tmp) if f.endswith("_usfx.xml")]
        if not usfx:
            continue
        try:
            books = bl.load_usfx(os.path.join(tmp, usfx[0]))
            res = bl.pack(books, kjv)
        except Exception as e:   # one bad file shouldn't stop the rest
            print(f"{tid}: failed ({e})")
            continue
        names = bl.book_names(os.path.dirname(tmp), tid, r["languageCode"])
        if len(names) >= 60:
            res["bookNames"] = {b: names[b] for b in sorted(names) if b in res["books"]}
        report = bl.check(tid, res, kjv)
        verses = sum(len(ch) for chs in res["books"].values() for ch in chs)
        if len(res["books"]) < 60 or verses < 28000:
            print("skipped (incomplete):", report)
            continue
        print(report, flush=True)
        with gzip.open(os.path.join(out_dir, tid + ".json.gz"), "wt", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, separators=(",", ":"))
        lang = r["languageCode"]
        native, english = r["languageName"].strip(), r["languageNameInEnglish"].strip()
        index.append({
            "id": tid, "lang": BCP47.get(lang, lang),
            "group": native if native == english or not native else f"{native} ({english})",
            "name": r["title"].strip(), "short": (r["shortTitle"] or r["title"]).strip()[:24],
            "dir": "rtl" if r["textDirection"] == "rtl" else "ltr",
            "license": r["Copyright"].strip(),
        })
    index.sort(key=lambda e: e["group"].lower())
    json.dump(index, open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(len(index), "texts")


if __name__ == "__main__":
    if sys.argv[1] == "pick":
        pick(sys.argv[2])
    else:
        build(*sys.argv[2:5])
