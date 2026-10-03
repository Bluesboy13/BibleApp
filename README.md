# KJV Bible

A simple, book-like King James Bible reader. Plain HTML/CSS/JS, installable on phone or desktop, and it works offline.

- **Book layout:** serif type, paper-colored page, a large chapter number at the start of each chapter, and no verse numbers by default.
- **Verse numbers:** tap **¹²³** in the top bar to show or hide them.
- **Reading:** scrolls by default. Switch to **Pages** under **Aa** to turn pages like a Kindle (tap the edges or swipe).
- **Read aloud:** tap the speaker icon. By default the app plays its own recording in "Daniel", a British voice (Kokoro `bm_daniel`, Apache-2.0), streamed chapter by chapter and able to keep playing with the screen locked. Chapters not yet recorded, or offline listening, use the device's own voices, which can also be chosen under **Aa → Voice**. Words are highlighted and kept on screen, with play/pause, previous/next verse and speed.
  Recordings are made with `tools/audio/generate.py` and live in `audio/<book>/<chapter>.m4a` with verse timings in a matching `.json`.
- **Saved verses:** tap any verse to highlight it in one of four colours, or to copy or share it. Saved verses are listed under the bookmark icon and show in every text (KJV, LXX, Hebrew).
- **Ribbon:** remembers where you left off and reopens there. Tap the bookmark icon to save more spots.
- **Reading plan:** Genesis to Revelation in 365 days (about 3–4 chapters a day), with days to check off.
- **Septuagint (LXX):** under **Aa → Text**, switch to the Greek Old Testament (with the Textus Receptus for the New Testament) or Brenton's English translation of the Septuagint. The extra Septuagint books (1 Esdras, Tobit, Judith, 1–4 Maccabees, Wisdom, Sirach, Prayer of Manasseh, Baruch, Letter of Jeremiah, Susanna, Bel and the Dragon) appear at the bottom of the book list. Or choose the **Hebrew** Old Testament (Westminster Leningrad Codex, read right to left, with the Greek Textus Receptus for the New Testament). Turn on **KJV underneath** to see the matching KJV verse(s) under each verse — in the extra Septuagint books it shows the KJV's own Apocrypha. Your place, bookmarks and reading plan carry across (they're kept in KJV numbering).
- **Themes:** Paper, White and Night, with adjustable text size and font.

Data is kept on the device (localStorage). Optionally, sign in (under **Aa → Account**) with Google or with an email and password to sync your place, bookmarks, saved verses and reading plan across devices through Firebase. Email accounts must confirm their address before syncing. The KJV text is public domain: the 1769 standard text, cross-checked verse by verse against three independent KJV copies. Paragraph breaks follow the KJV's own ¶ marks.

## Sync setup (Firebase)
1. Create a Firebase project, add a Web app, and paste its config values into `js/firebase-config.js`.
2. Authentication → Sign-in method → enable **Google** and **Email/Password**. Under Settings → Authorized domains, add `bluesboy13.github.io`.
3. Create a Firestore database, then paste `firestore.rules` into its **Rules** tab and publish.
4. As written, anyone can create an account and each person can only reach their own data. To allow only people you approve, follow the note at the top of `firestore.rules`.

Each person's data lives in Firestore at `users/{their uid}`, never in this repo. `vendor/firebase.js` is a bundled copy of the Firebase JS SDK (app, auth, firestore/lite).

## Hosting on GitHub Pages
Repo **Settings → Pages → Build and deployment**: Source = *Deploy from a branch*, pick the branch and `/ (root)`, then Save.

## Install on your phone
- **iPhone (Safari):** Share → *Add to Home Screen*.
- **Android (Chrome):** ⋮ menu → *Add to Home screen* / *Install app*.

## Run locally
```
python3 -m http.server 8000
```
Then open http://localhost:8000.

## Texts and credits
- **KJV** — 1769 text, public domain.
- **Septuagint, Greek** — the Greek text printed with Brenton's Septuagint (1851), from eBible.org (`grcbrent`), public domain.
- **Septuagint, English** — Sir Lancelot C. L. Brenton's translation (1844/1851), from eBible.org (`eng-Brenton`), public domain.
- **Hebrew Old Testament** — Westminster Leningrad Codex (public domain), vowel points kept and cantillation marks removed for easier reading. Hebrew ↔ KJV verse numbering from STEPBible's TVTMS table ([STEPBible.org](https://www.stepbible.org), CC BY 4.0).
- **KJV Apocrypha** — from the 1769 KJV, public domain (shown under the Septuagint's extra books).
- **Other languages** (public domain; built by `tools/texts/build_langs.py` from [scrollmapper/bible_databases](https://github.com/scrollmapper/bible_databases) and [seven1m/open-bibles](https://github.com/seven1m/open-bibles)): German Elberfelder 1905 and Luther 1912, Spanish Reina-Valera 1909, French Martin 1744, Italian Riveduta 1927, Tagalog Ang Biblia 1905, Chinese Union Version (simplified and traditional), Russian Synodal, Dutch Statenvertaling, Polish Gdańska, Hungarian Károli 1908, Czech Kralice, Swedish 1917, Norwegian 1930, Danish 1871/1907, Finnish 1776, Japanese Kougo-yaku, Vietnamese 1934, Thai, Bulgarian, Modern Greek (Vamvas), Malayalam 1910, Burmese (Judson), Serbian (Daničić-Karadžić), Albanian, Māori and Malagasy 1865; and from [eBible.org](https://ebible.org) (public domain): Italian Diodati 1885, Arabic Van Dyck, Korean, Persian Old Version, Ukrainian Kulish–Pulyui 1905, Portuguese World Bible, Haitian Creole, Hawaiian 1868 and Tongan.
- **Bikol** — *An Bagong Tipan* (1909, British and Foreign Bible Society, Manila; public domain), New Testament only, rebuilt by `tools/texts/bikol_ocr.py` from two OCR readings of the University of Michigan scan on archive.org (the library's ABBYY text and a Tesseract re-read). Scanned text: some words have OCR errors and Acts 21, Ephesians 5 and Revelation 21 are incomplete; corrections welcome.
- **Freely licensed texts** (used only where no public-domain Bible is available; [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) unless noted, from eBible.org, unchanged apart from layout): Indian Revised Version in Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Punjabi, Kannada and Odia (© Bridge Connectivity Solutions); Unlocked Literal Bible in Swahili, Nepali, Cebuano and Ilokano (© Door43 World Missions Community); Biblica Open Bibles in Yoruba, Hausa and Igbo (© Biblica, Inc.); Urdu Geo Version (© Urdu Geo Version, CC BY-NC-ND 4.0); Alkitab Yang Terbuka (© YLSA-AYT, CC BY-ND 4.0); Yorumsuz Türkçe Çeviri (© İsmail Serinken and eBible.org, CC BY-ND 4.0); Somali Kitaabka Quduuska Ah (© Society for International Ministries, CC BY-NC-ND 4.0). Book names in each language come from eBible.org's book-name lists.
- **Greek New Testament** — Scrivener's 1894 Textus Receptus (accented), public domain; about 4,500 short words missing from that file (mostly ὁ and ἡ) restored from Dr. Maurice Robinson's Scrivener 1894 text, with accents from the Robinson-Pierpont Byzantine text (both public domain, [byztxt](https://github.com/byztxt)) — see `tools/texts/repair_tr.py`.
- The LXX ↔ KJV verse matching was made for this app by comparing the words of Brenton's English with the KJV (`tools/texts/build_texts.py`).
- **Audio** — "Daniel", Kokoro TTS voice `bm_daniel` (Apache-2.0). Greek read in modern Greek pronunciation by Chatterbox Multilingual's built-in voice (MIT, Resemble AI) — see `tools/greek/generate.py`.
