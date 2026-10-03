"""Draft a translation of Bible verses into another language with Claude.

Every result is an AI DRAFT that needs review by a qualified human translator: the
output file says so at the top, every verse starts with review status "pending",
and nothing here touches the app's published texts in data/.

The model works from the original language (Greek Textus Receptus for the New
Testament, Hebrew WLC for the Old), with the KJV as an English anchor and,
optionally, an existing Bible in the target language for terminology. For each verse
it returns the draft, a literal English back-translation, a confidence level and
notes on the choices a reviewer should check.

Usage:
  pip install anthropic          # and set ANTHROPIC_API_KEY
  python translate.py "John 3:16-18" --to Swahili [--reference sw-ulb] [--out FILE]
  python translate.py "Genesis 1:1-3" --to "Bikol" --dry-run   # print the prompt only

Output goes to drafts/<language>/<book>-<chapter>-<verses>.json unless --out is given.
"""
import argparse
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
DATA = os.path.join(ROOT, "data")

MODEL = "claude-opus-5-5"
NOTICE = ("AI DRAFT - NOT REVIEWED. Machine-generated translation for a human translator "
          "to check, correct and approve. Do not publish or quote as Scripture.")

SYSTEM = """You are assisting a Bible translation team by drafting verses in a target language.
Your draft will be checked and corrected by a qualified human translator before anyone reads it as Scripture, so your job is to give them a faithful, natural starting point and to point out every place where they should look closely.

How to translate:
- Translate from the original-language text (Greek or Hebrew) when it is given. The KJV is an English anchor for verse boundaries and meaning, not the source to copy.
- If an existing Bible in the target language is given, use it only to match established terms (names, divine names, key theological words) and register. Do not copy its wording.
- Aim for meaning-based accuracy in natural, everyday language of the target language. Do not add explanation, commentary or harmonization inside the verse text.
- Keep proper names in the form established for the target language when you know it.

For each verse return:
- translation: the draft in the target language and its usual script.
- back_translation: a literal English rendering of your draft, so a reviewer who does not read the target language can check it.
- confidence: "high", "medium" or "low" for the draft as a whole.
- notes: short notes on choices the reviewer should check: key terms, ambiguities in the source, places where you were unsure of the target language. Use an empty list only when there is nothing worth checking.

If you do not know the target language well enough to draft reliably, still give your best attempt, mark it "low" confidence and say so in the notes."""

SCHEMA = {
    "type": "object",
    "properties": {
        "verses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "verse": {"type": "integer"},
                    "translation": {"type": "string"},
                    "back_translation": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "notes": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["verse", "translation", "back_translation", "confidence", "notes"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["verses"],
    "additionalProperties": False,
}


def load(path):
    with open(os.path.join(DATA, path), encoding="utf-8") as f:
        return json.load(f)


def clean(text):
    return text.replace("¶", "").strip()  # drop the KJV's paragraph marks


def parse_ref(ref, kjv):
    """'John 3:16-18' -> (book index, chapter, [verses]) in KJV numbering."""
    m = re.match(r"^\s*(.+?)\s+(\d+):(\d+)(?:-(\d+))?\s*$", ref)
    if not m:
        sys.exit(f"Can't read reference {ref!r}; use the form 'John 3:16' or 'John 3:16-18'.")
    name, ch, v1, v2 = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4) or m.group(3))
    names = [b[0].lower() for b in kjv]
    key = name.lower()
    hits = [i for i, n in enumerate(names) if n == key] or [i for i, n in enumerate(names) if n.startswith(key)]
    if len(hits) != 1:
        sys.exit(f"Unknown or ambiguous book {name!r}.")
    b = hits[0]
    chapters = kjv[b][1]
    if not 1 <= ch <= len(chapters):
        sys.exit(f"{kjv[b][0]} has {len(chapters)} chapters.")
    last = len(chapters[ch - 1])
    if not 1 <= v1 <= v2 <= last:
        sys.exit(f"{kjv[b][0]} {ch} has verses 1-{last}.")
    return b, ch, list(range(v1, v2 + 1))


def original(b, ch, verses):
    """The Greek (NT) or Hebrew (OT) text for each KJV verse, or None if it can't be lined up."""
    if b >= 39:
        books, label = load("tr.json")["books"], "Greek (Scrivener 1894 Textus Receptus)"
        chap = books.get(str(b), [])
        if ch > len(chap):
            return label, {}
        return label, {v: chap[ch - 1][v - 1] for v in verses if v <= len(chap[ch - 1])}
    wlc, label = load("wlc.json"), "Hebrew (Westminster Leningrad Codex)"
    chap_list, vmap = wlc["books"].get(str(b), []), wlc.get("map", {}).get(str(b))
    out = {}
    for v in verses:
        if not vmap:  # same numbering as the KJV
            if ch <= len(chap_list) and v <= len(chap_list[ch - 1]):
                out[v] = chap_list[ch - 1][v - 1]
            continue
        # map[chapter][verse] lists the KJV (chapter, verse) pairs each Hebrew verse covers
        parts = [chap_list[hc][hv] for hc, hverses in enumerate(vmap) for hv, refs in enumerate(hverses)
                 if [ch, v] in refs and hc < len(chap_list) and hv < len(chap_list[hc])]
        if parts:
            out[v] = " ".join(parts)
    return label, out


def reference_text(text_id, b, ch, verses):
    """Verses from an existing Bible in data/texts, when its numbering matches the KJV's here."""
    d = load(f"texts/{text_id}.json")
    if str(b) in d.get("map", {}):
        return {}  # numbering differs from the KJV in this book; skip rather than misalign
    chap = d["books"].get(str(b), [])
    if ch > len(chap):
        return {}
    return {v: chap[ch - 1][v - 1] for v in verses if v <= len(chap[ch - 1])}


def build_prompt(lang, title, verses, kjv_text, orig_label, orig, ref_id, ref):
    lines = [f"Target language: {lang}", f"Passage: {title}", ""]
    for v in verses:
        lines.append(f"Verse {v}")
        if v in orig:
            lines.append(f"  {orig_label}: {orig[v]}")
        lines.append(f"  KJV: {kjv_text[v]}")
        if v in ref:
            lines.append(f"  Existing {lang} Bible ({ref_id}), for terminology only: {ref[v]}")
        lines.append("")
    lines.append(f"Draft each verse above in {lang}.")
    return "\n".join(lines)


def call_claude(prompt):
    import anthropic  # imported here so --dry-run works without the SDK installed

    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            thinking={"type": "adaptive"},
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # if a safety classifier declines, retry on Anthropic's recommended model
        )
    except anthropic.AuthenticationError:
        sys.exit("The API key was rejected. Set ANTHROPIC_API_KEY to a valid key.")
    except anthropic.RateLimitError:
        sys.exit("Rate limited by the API. Wait a minute and try again.")
    except anthropic.APIStatusError as e:
        sys.exit(f"API error {e.status_code}: {e.message}")
    except anthropic.APIConnectionError:
        sys.exit("Couldn't reach the API. Check the network connection.")
    if response.stop_reason == "refusal":
        sys.exit("The model declined this request.")
    if response.stop_reason == "max_tokens":
        sys.exit("The draft was cut off; try fewer verses at a time.")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)["verses"], response.model


def main():
    ap = argparse.ArgumentParser(description="Draft verse translations with Claude (AI draft for human review).")
    ap.add_argument("ref", help="passage in KJV numbering, e.g. 'John 3:16-18'")
    ap.add_argument("--to", required=True, help="target language, e.g. 'Swahili'")
    ap.add_argument("--reference", help="id of an existing Bible in data/texts in the target language, e.g. sw-ulb")
    ap.add_argument("--out", help="output JSON path (default: drafts/<language>/...)")
    ap.add_argument("--dry-run", action="store_true", help="print the prompt and exit without calling the API")
    args = ap.parse_args()

    kjv = load("kjv.json")
    b, ch, verses = parse_ref(args.ref, kjv)
    book = kjv[b][0]
    title = f"{book} {ch}:{verses[0]}" + (f"-{verses[-1]}" if len(verses) > 1 else "")
    kjv_text = {v: clean(kjv[b][1][ch - 1][v - 1]) for v in verses}
    orig_label, orig = original(b, ch, verses)
    ref = reference_text(args.reference, b, ch, verses) if args.reference else {}
    prompt = build_prompt(args.to, title, verses, kjv_text, orig_label, orig, args.reference, ref)

    if args.dry_run:
        print("SYSTEM:\n" + SYSTEM + "\n\nUSER:\n" + prompt)
        return

    drafted, served_by = call_claude(prompt)
    by_verse = {d["verse"]: d for d in drafted}
    missing = [v for v in verses if v not in by_verse]
    if missing:
        print(f"Warning: no draft returned for verse(s) {missing}.", file=sys.stderr)

    result = {
        "status": "ai-draft",
        "needs_human_review": True,
        "notice": NOTICE,
        "passage": title,
        "target_language": args.to,
        "model": served_by,
        "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "sources": ["KJV (1769)"] + ([orig_label] if orig else []) + ([args.reference] if ref else []),
        "verses": [{
            "verse": v,
            "kjv": kjv_text[v],
            **{k: by_verse[v][k] for k in ("translation", "back_translation", "confidence", "notes")},
            "review": {"status": "pending", "reviewer": None, "approved_text": None, "comments": None},
        } for v in verses if v in by_verse],
    }

    slug = lambda s: re.sub(r"\W+", "-", s.lower()).strip("-")
    out = args.out or os.path.join(ROOT, "drafts", slug(args.to), f"{slug(book)}-{ch}-{verses[0]}-{verses[-1]}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"*** {NOTICE} ***\n\n{title} - {args.to}\n")
    for d in result["verses"]:
        print(f"{d['verse']}  {d['translation']}")
        print(f"    back-translation: {d['back_translation']}")
        print(f"    confidence: {d['confidence']}")
        for n in d["notes"]:
            print(f"    - {n}")
        print()
    print(f"Saved to {os.path.relpath(out)}")


if __name__ == "__main__":
    main()
