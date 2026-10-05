# FreeBiblos — to-do list

The running list of open work for the app and its FreeBiblos repos. Newest notes at the top of
each section; tick items off (and add the date) when done.

## Research: Bikol (Central Bikol / Bicolano) Bible

Goal: the full Bible in Bikol, public domain (printed before 1931), not just the 1909 New Testament.

**What we have:** *An Bagong Tipan* (1909, British and Foreign Bible Society, Manila), rebuilt
from the University of Michigan scan on archive.org (`ajg9045.0001.001.umich.edu`) by
`tools/texts/bikol_ocr.py` → `data/texts/bcl-1909.json`. 247/260 chapters match the KJV verse
count. Known gaps: Acts 21, Ephesians 5 and Revelation 21 incomplete (damaged pages);
Colossians 3's opening is filed under verse 3.

**What we're looking for:**
- *An Santa Biblia: na may laman kan mañga mahal na libros kan Daan asin Bagong Tipan*, c. 1914,
  BFBS (translators reportedly Julian Herras, OT; Juan Salazar, NT; possibly printed by Fukuin,
  Yokohama). Joshua Project lists a complete Bikol Bible from 1914.
- Its 1927 revision, *Manga Banal na Kasuratan na iyo an Daan asin an Bagong Tipan na Binicol*
  (reportedly American Bible Society; reprinted 1948, 1964, 1978, 1982 — use only a pre-1931
  printing).
- Any Bikol Old Testament book printed before 1931.

**Do not use:** *Marahay na Bareta Biblia* (1992, © Philippine Bible Society; archive.org item
`rosttaproject_bik_gen-1` is its Genesis); the 2021 Jehovah's Witnesses Bible (terms of use).

**Already searched (Oct 2026), nothing found:** archive.org by title, language, subject, date
range, Michigan scans and full text (only the 1909 NT exists there); eBible.org (no Bikol).

**Still to try** (need a normal browser — automated searches were blocked):
- [ ] HathiTrust catalog: search "Santa Biblia" + Bicol/Bikol, "Banal na Kasuratan", "Binicol",
      and the BFBS / ABS as authors; check for full-view copies.
- [ ] Google Books: same searches (the API hit its daily limit).
- [ ] WorldCat: find which libraries hold the 1914 and 1927 editions.
- [ ] Bible Society Library, Cambridge University Library (holds the BFBS archive, which should
      include the 1914 edition) — ask whether it is digitized or can be scanned.
- [ ] American Bible Society library (for the 1927 edition) — same question.
- [ ] Yale Divinity Library mission Bibles (guide:
      https://web.library.yale.edu/sites/default/files/files/Missionary_Bibles_in_Orbis_guide.pdf)
      and Boston University's mission collection.
- [ ] Scribd "Biblia 1914": https://www.scribd.com/document/100494576/Biblia-1914 (behind a
      browser check; see what edition it is).
- [ ] e-Sword module "An Biblia" (old Bikol text) from yirmeyah.net — password-protected,
      edition and permission unknown; use only if its source is a public-domain printing and the
      distributor gives permission.

**When a scan turns up:** fetch it with a GitHub workflow (archive.org-style), OCR with the
`bikol-ocr3.yml` approach (Tesseract Tagalog model, 8 parallel machines), rebuild with
`bikol_ocr.py` (extend it for the Old Testament book list), check chapter alignment against the
KJV, and replace `bcl-1909` with the full Bible.

**Also helpful:** a Bikol speaker proofreading the 1909 NT; a "report a typo" button in the app.

## Other open items

- [x] Firebase sign-in and sync (Oct 2026): Google + email sign-in, Firestore (`nam5`), rules published.
- [x] freebiblos.com: live (CNAME), added to Firebase's authorized domains.
- [ ] Greek audio (FreeBiblos/BibleApp-audio-el): recording; check it finishes and plays.
- [ ] Audio for Spanish, French, German, Italian, Portuguese and the other natural-voice languages,
      one language at a time (repos BibleApp-audio-<code>).
- [ ] New Testaments in ~800 more languages (eBible.org) in FreeBiblos/BibleApp-texts.
- [ ] Lithuanian (eBible `lit`) and Lukpa (`dop`) came out incomplete in the texts build — check
      their source files.
- [ ] Old public-domain Philippine Bibles on archive.org worth adding: Hiligaynon 1912
      (`lasantabibliaang00mani`), Ilocano OT 1919 (`tidaantulagngais00walk`), Ibanag 1911,
      Pampanga 1908.
- [ ] Book names still in English for Hungarian, Norwegian, Finnish, Bulgarian, Modern Greek,
      Albanian and Malagasy.
- [ ] About & credits section in the app (plain text, no links): the Creative Commons Bibles
      require their credit to be shown to readers. List each text's source and license, the voices,
      and Scourby if licensed.
- [ ] Alexander Scourby KJV audio: permission request emailed to Scourby Bible Media (Litchfield
      Associates, Tampa) — waiting for a reply. Use only with a written license.
