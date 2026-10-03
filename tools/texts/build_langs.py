"""Build the app's other-language Bibles (data/texts/<id>.json) from public-domain sources.

Sources:
  scrollmapper/bible_databases  formats/json/<name>.json   (SWORD-derived, English book names)
  seven1m/open-bibles           <name>.osis.xml | .usfx.xml | .zefania.xml
Output shape matches the other texts: {"books": {kjvIndex: [[verse, ...] per chapter]}}, plus
"labels"/"map" for books whose chapters or verses don't line up with the KJV's, so places,
bookmarks and "KJV underneath" still work.

  eBible.org                    <id>_usfx.zip, unzipped to <id>/<id>_usfx.xml
Usage: python build_langs.py SCROLLMAPPER_JSON_DIR OPEN_BIBLES_DIR EBIBLE_DIR [id ...]
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "..", "data")

# id: (source, file, language, name)
TEXTS = {
    "de-elb": ("sm", "GerElb1905", "de", "Elberfelder 1905"),
    "de-lut": ("ob", "deu-luther1912.osis.xml", "de", "Luther 1912"),
    "es-rv": ("sm", "SpaRV", "es", "Reina-Valera 1909"),
    "fr-mar": ("sm", "FreBDM1744", "fr", "Martin 1744"),
    "it-riv": ("ob", "ita-riveduta.osis.xml", "it", "Riveduta 1927"),
    "tl-ab": ("sm", "TagAngBiblia", "tl", "Ang Biblia 1905"),
    "zh-cuv": ("ob", "chi-cuv-simp.usfx.xml", "zh-Hans", "和合本 (简体)"),
    "zh-cuvt": ("ob", "chi-cuv.usfx.xml", "zh-Hant", "和合本 (繁體)"),
    "ru-syn": ("sm", "RusSynodal", "ru", "Синодальный перевод"),
    "nl-sv": ("sm", "DutSVV", "nl", "Statenvertaling"),
    "pl-gd": ("sm", "PolGdanska", "pl", "Biblia Gdańska"),
    "hu-kar": ("sm", "HunKar", "hu", "Károli 1908"),
    "cs-bkr": ("sm", "CzeBKR", "cs", "Bible kralická"),
    "sv-1917": ("sm", "Swe1917", "sv", "Bibeln 1917"),
    "no-1930": ("sm", "Norsk", "nb", "Bibelen 1930"),
    "da-1871": ("sm", "DaOT1871NT1907", "da", "Bibelen 1871/1907"),
    "fi-1776": ("sm", "FinBiblia", "fi", "Biblia 1776"),
    "ja-kougo": ("sm", "JapKougo", "ja", "口語訳"),
    "vi-1934": ("ob", "vie-cadman.osis.xml", "vi", "Kinh Thánh 1934"),
    "th": ("ob", "tha-thai.osis.xml", "th", "พระคัมภีร์ไทย"),
    "bg": ("ob", "bul-bulgarian.osis.xml", "bg", "Библия"),
    "el-vam": ("sm", "GreVamvas", "el", "Βάμβας 1850"),
    "ml-1910": ("sm", "Mal1910", "ml", "സത്യവേദപുസ്തകം 1910"),
    "my-jud": ("sm", "BurJudson", "my", "Judson 1835"),
    "sr-dk": ("sm", "SrKDEkavski", "sr", "Даничић-Караџић"),
    "sq": ("ob", "sqi-albanian.osis.xml", "sq", "Bibla"),
    "mi": ("ob", "mri-maori.osis.xml", "mi", "Paipera Tapu"),
    "mg-1865": ("sm", "Mg1865", "mg", "Baiboly 1865"),
    # From eBible.org (fetched by the BibleApp-audio repo's ebible workflow), <id>/<id>_usfx.xml
    "it-dio": ("eb", "ita1885", "it", "Diodati 1885"),
    "ar-vd": ("eb", "arb-vd", "ar", "فاندايك (Van Dyck)"),
    "ko": ("eb", "kor", "ko", "한국어 성경"),
    "fa-opv": ("eb", "pesOPV", "fa", "ترجمه قدیم"),
    "uk-kul": ("eb", "ukr1871", "uk", "Куліш і Пулюй 1905"),
    "pt-bpm": ("eb", "porbrbsl", "pt", "Bíblia Portuguesa Mundial"),
    "ht": ("eb", "hat", "ht", "Bib La"),
    "haw": ("eb", "haw1868", "haw", "Baibala Hemolele 1868"),
    "to": ("eb", "ton", "to", "Ko e Tohi Tapu"),
    # Freely licensed (Creative Commons), for languages with no public-domain Bible available.
    "hi-irv": ("eb", "hin2017", "hi", "इंडियन रिवाइज्ड वर्जन (IRV)"),
    "bn-irv": ("eb", "benirv", "bn", "ইন্ডিয়ান রিভাইজড ভার্সন (IRV)"),
    "ta-irv": ("eb", "tam2017", "ta", "இண்டியன் ரிவைஸ்டு வெர்ஸன் (IRV)"),
    "te-irv": ("eb", "tel2017", "te", "ఇండియన్ రివైజ్డ్ వెర్షన్ (IRV)"),
    "mr-irv": ("eb", "mar", "mr", "इंडियन रीवाइज्ड वर्जन (IRV)"),
    "gu-irv": ("eb", "guj2017", "gu", "ઇન્ડિયન રીવાઇઝ્ડ વર્ઝન (IRV)"),
    "pa-irv": ("eb", "pan", "pa", "ਇੰਡਿਅਨ ਰਿਵਾਇਜ਼ਡ ਵਰਜ਼ਨ (IRV)"),
    "kn-irv": ("eb", "kanirv", "kn", "ಇಂಡಿಯನ್ ರಿವೈಜ್ಡ್ ವರ್ಸನ್ (IRV)"),
    "or-irv": ("eb", "ory", "or", "ଇଣ୍ଡିୟାନ ରିୱାଇସ୍ଡ୍ ୱରସନ୍ (IRV)"),
    "ur-geo": ("eb", "urdgvu", "ur", "اُردو جیو ورژن"),
    "id-ayt": ("eb", "indayt", "id", "Alkitab Yang Terbuka"),
    "sw-ulb": ("eb", "swhulb", "sw", "Biblia Takatifu (ULB)"),
    "tr-ytc": ("eb", "turytc", "tr", "Yorumsuz Türkçe Çeviri"),
    "ne-ulb": ("eb", "npiulb", "ne", "पवित्र बाइबल (ULB)"),
    "ceb-ulb": ("eb", "cebulb", "ceb", "Balaan nga Bibliya (ULB)"),
    "ilo-ulb": ("eb", "iloulb", "ilo", "Ti Biblia (ULB)"),
    "so": ("eb", "som", "so", "Kitaabka Quduuska Ah"),
    "yo": ("eb", "yor", "yo", "Bíbélì Mímọ́ (Open)"),
    "ha": ("eb", "hausa", "ha", "Littafi Mai Tsarki (Open)"),
    "ig": ("eb", "ibo", "ig", "Baịbụlụ Nsọ (Open)"),
}

# Book names in each language: from eBible's BookNames.xml of the text itself, or of another
# edition in the same language for texts from the other sources.
NAMES_FROM = {
    "de-elb": "deu1912", "de-lut": "deu1912", "es-rv": "spabll", "fr-mar": "fraLSG", "it-riv": "ita1927",
    "tl-ab": "tglulb", "zh-cuv": "cmn-cu89s", "zh-cuvt": "cmn-cu89t", "ru-syn": "russyn", "nl-sv": "nld",
    "pl-gd": "polubg", "cs-bkr": "ces1613", "sv-1917": "swe", "da-1871": "dan1931", "ja-kougo": "jpnm",
    "vi-1934": "vie1934", "th": "thaKJV", "ml-1910": "mal2015", "my-jud": "myajvb", "sr-dk": "srp1868",
    "mi": "mri2012",
}


def book_names(eb_dir, ebid, lang=""):
    path = os.path.join(eb_dir, ebid, "BookNames.xml")
    if not os.path.exists(path):
        return {}
    names = {}
    for m in re.finditer(r'<book code="(\w+)"([^>]*)/>', open(path, encoding="utf-8-sig").read()):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(2)))
        tidy = lambda x: re.sub(r"\s+", " ", re.sub("[\u200b\ufeff]", "", x).replace("~", " ")).strip()
        short, long_ = tidy(attrs.get("short", "")), tidy(attrs.get("long", ""))
        numbered = re.match(r"^([0-9]+|[IV]+)\.? ", short)
        if long_ and len(long_) <= 30 and not numbered and "." in short:
            short = long_   # an abbreviation such as "ગી.શા."
        # Some editions give an abbreviation as the short name; use the full name then.
        n = long_ if long_ and (not short or (long_.startswith(short.rstrip(".")) and len(long_) <= 20)) else short
        if m.group(1) in USFM and n:
            if n.isupper() and len(n) >= 3:
                low = (lambda x: x.replace("I", "ı").replace("İ", "i").lower()) if lang == "tr" else str.lower
                n = " ".join(w[:1] + low(w[1:]) for w in n.split(" "))
                n = re.sub(r"\b(Ii|Iii|Iv)\b", lambda w: w.group(1).upper(), n)
            names[USFM.index(m.group(1))] = n
    return names

OSIS = ("Gen Exod Lev Num Deut Josh Judg Ruth 1Sam 2Sam 1Kgs 2Kgs 1Chr 2Chr Ezra Neh Esth Job Ps Prov Eccl "
        "Song Isa Jer Lam Ezek Dan Hos Joel Amos Obad Jonah Mic Nah Hab Zeph Hag Zech Mal Matt Mark Luke John "
        "Acts Rom 1Cor 2Cor Gal Eph Phil Col 1Thess 2Thess 1Tim 2Tim Titus Phlm Heb Jas 1Pet 2Pet 1John 2John "
        "3John Jude Rev").split()
USFM = ("GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO ECC SNG ISA JER LAM "
        "EZK DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP "
        "COL 1TH 2TH 1TI 2TI TIT PHM HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV").split()


def norm_name(n):
    n = n.lower().replace("revelation of john", "revelation")
    n = re.sub(r"^(iii|ii|i) ", lambda m: {"i": "1 ", "ii": "2 ", "iii": "3 "}[m.group(1)], n)
    return re.sub(r"[^a-z0-9]", "", n.replace("song of songs", "song of solomon"))


def clean(t):
    # Some files carry Windows-1252 punctuation (’ “ ” –) as stray control characters.
    t = re.sub("[\x80-\x9f]", lambda m: m.group(0).encode("latin-1").decode("cp1252", "ignore"), t)
    t = re.sub(r"<note>.*?</note>", "", t, flags=re.S)
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"Retournez au Début.*?=+", "", t)          # web page debris in one source
    t = re.sub(r"\s*={3,}.*$", "", t)
    t = re.sub(r"\s*>\s*\d? ?[A-ZÅÄÖ][a-zåäö]+\.? \d+[,:]\d+.*$", "", t)   # trailing cross references
    return re.sub(r"\s+", " ", t).strip()


def load_sm(path, kjv):
    idx = {norm_name(n): i for i, (n, _) in enumerate(kjv)}
    books = {}
    for b in json.load(open(path, encoding="utf-8"))["books"]:
        i = idx.get(norm_name(b["name"]))
        if i is None:
            continue   # books outside the 66 (deuterocanon) are left out for now
        books[i] = [[(v["verse"], clean(v["text"])) for v in ch["verses"]] for ch in b["chapters"]]
    return books


def load_osis(path):
    ns = {"o": "http://www.bibletechnologies.net/2003/OSIS/namespace"}
    root = ET.parse(path).getroot()
    books = {}
    for v in root.iter("{%s}verse" % ns["o"]):
        oid = v.get("osisID")
        if not oid:
            continue
        bk, c, n = oid.split(" ")[0].split(".")[:3]
        if bk not in OSIS:
            continue
        # A note opening a psalm's first verse is its title (Scripture); other notes are footnotes.
        for note in v.findall(".//{%s}note" % ns["o"]):
            title = bk == "Ps" and n == "1" and len(v) and v[0] is note and not (v.text or "").strip()
            if not title:
                tail = note.tail
                note.clear()
                note.tail = tail
        text = clean("".join(v.itertext()))
        books.setdefault(OSIS.index(bk), {}).setdefault(int(c), []).append((int(re.sub(r"\D.*", "", n)), text))
    return {b: [chs[c] for c in sorted(chs)] for b, chs in books.items()}


def load_usfx(path):
    src = open(path, encoding="utf-8-sig").read()
    src = re.sub(r"<f\b.*?</f>|<x\b.*?</x>|<fe\b.*?</fe>", "", src, flags=re.S)
    # Headings added by editors (section titles, "Psalm 1", "Book 1"), not Scripture.
    src = re.sub(r"<s\b[^>]*>.*?</s>|<cl>.*?</cl>|<toc\b.*?</toc>|<h>.*?</h>|<id\b[^>]*/>|<id\b[^/>]*>.*?</id>|"
                 r"<p [^>]*sfm=\"(?:ms|mr|mt\d?|r|s\d?|sp)\"[^>]*>.*?</p>", "", src, flags=re.S)
    books = {}
    for m in re.finditer(r'<book id="(\w+)"(.*?)</book>', src, re.S):
        if m.group(1) not in USFM:
            continue
        b = USFM.index(m.group(1))
        chs = {}
        for cm in re.finditer(r'<c id="(\d+)"[^>]*/>(.*?)(?=<c id=|$)', m.group(2), re.S):
            vs = []
            # A psalm's title (<d>) comes before verse 1: it opens verse 1.
            pre = cm.group(2).split("<v id=", 1)[0]
            title = " ".join(clean(d) for d in re.findall(r"<d\b[^>]*>(.*?)</d>", pre, re.S))
            for vm in re.finditer(r'<v id="(\d+)[^"]*"[^>]*/>(.*?)(?=<v id=|<ve\s*/>|$)', cm.group(2), re.S):
                vs.append((int(vm.group(1)), clean(vm.group(2))))
            if title and vs:
                vs[0] = (vs[0][0], title + " " + vs[0][1])
            chs[int(cm.group(1))] = vs
        books[b] = [chs[c] for c in sorted(chs)]
    return books


def pack(books, kjv):
    """Lay the text out in the app's shape, with labels and a KJV map where numbering differs."""
    out, labels, maps = {}, {}, {}
    for b, chs in sorted(books.items()):
        kc = kjv[b][1]
        verses = [[t for _, t in ch] for ch in chs]
        nums = [[n for n, _ in ch] for ch in chs]
        out[b] = verses
        if any(ns != list(range(1, len(ns) + 1)) for ns in nums):
            labels[b] = {ci + 1: [str(n) for n in ns] for ci, ns in enumerate(nums) if ns != list(range(1, len(ns) + 1))}
        same = len(chs) == len(kc) and all(ns == list(range(1, len(kc[ci]) + 1)) for ci, ns in enumerate(nums))
        if not same:
            maps[b] = align(nums, kc)
    res = {"books": out}
    if labels:
        res["labels"] = labels
    if maps:
        res["map"] = maps
    return res


def align(nums, kc):
    """Map each verse to the KJV verse(s) it matches.

    Same number of verses in the book: only chapter breaks differ, so verses pair up in order.
    Otherwise chapter by chapter: one extra verse means a psalm title counted as verse 1 (it and
    verse 2 both go with KJV verse 1); anything else pairs verses by number."""
    kflat = [(ci + 1, vi + 1) for ci, ch in enumerate(kc) for vi in range(len(ch))]
    if sum(map(len, nums)) == len(kflat):
        it = iter(kflat)
        return [[[list(next(it))] for _ in ns] for ns in nums]
    m = []
    for ci, ns in enumerate(nums):
        c = ci + 1
        if c > len(kc):
            m.append([[] for _ in ns])
            continue
        k = len(kc[ci])
        shift = 1 if len(ns) == k + 1 else 0
        m.append([[[c, max(1, min(n - shift, k))]] for n in ns])
    return m


def check(tid, res, kjv):
    """Report anything that looks wrong: missing books, empty verses, stray markup."""
    probs = []
    missing = [kjv[b][0] for b in range(66) if b not in res["books"]]
    if missing:
        probs.append(f"missing books: {', '.join(missing)}")
    allv = [v for chs in res["books"].values() for ch in chs for v in ch]
    empty = sum(1 for v in allv if not v)
    if empty:
        probs.append(f"{empty} empty verses")
    junk = [v for v in allv if re.search(r"https?:|www\.|={3,}|<|>|@|\\", v)]
    if junk:
        probs.append(f"{len(junk)} verses with stray markup, e.g. {junk[0][:80]!r}")
    return f"{tid}: {len(allv)} verses, {len(res.get('map', {}))} books renumbered, names: {len(res.get('bookNames', {}))}" + ("; " + "; ".join(probs) if probs else "")


def main():
    sm_dir, ob_dir, eb_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    only = sys.argv[4:]
    kjv = json.load(open(os.path.join(DATA, "kjv.json"), encoding="utf-8"))
    os.makedirs(os.path.join(DATA, "texts"), exist_ok=True)
    for tid, (src, f, lang, name) in TEXTS.items():
        if only and tid not in only:
            continue
        if src == "sm":
            books = load_sm(os.path.join(sm_dir, f + ".json"), kjv)
        elif src == "eb":
            books = load_usfx(os.path.join(eb_dir, f, f + "_usfx.xml"))
        elif f.endswith(".osis.xml"):
            books = load_osis(os.path.join(ob_dir, f))
        else:
            books = load_usfx(os.path.join(ob_dir, f))
        res = pack(books, kjv)
        names = book_names(eb_dir, f if src == "eb" else NAMES_FROM.get(tid, ""), lang)
        if len(names) >= 60:
            res["bookNames"] = {b: names[b] for b in sorted(names) if b in res["books"]}
        print(check(tid, res, kjv), flush=True)
        with open(os.path.join(DATA, "texts", tid + ".json"), "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
