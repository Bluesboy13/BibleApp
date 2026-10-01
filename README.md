# KJV Bible

A simple, book-like King James Bible reader. Plain HTML/CSS/JS, installable on phone or desktop, and it works offline.

- **Book layout:** serif type, paper-colored page, a large chapter number at the start of each chapter, and no verse numbers by default.
- **Verse numbers:** tap **¹²³** in the top bar to show or hide them.
- **Reading:** scrolls by default. Switch to **Pages** under **Aa** to turn pages like a Kindle (tap the edges or swipe).
- **Read aloud:** tap the speaker icon. By default the app plays its own recording in "Daniel", a British voice (Kokoro `bm_daniel`, Apache-2.0), streamed chapter by chapter and able to keep playing with the screen locked. Chapters not yet recorded, or offline listening, use the device's own voices, which can also be chosen under **Aa → Voice**. Words are highlighted and kept on screen, with play/pause, previous/next verse and speed.
  Recordings are made with `tools/audio/generate.py` and live in `audio/<book>/<chapter>.m4a` with verse timings in a matching `.json`.
- **Ribbon:** remembers where you left off and reopens there. Tap the bookmark icon to save more spots.
- **Reading plan:** Genesis to Revelation in 365 days (about 3–4 chapters a day), with days to check off.
- **Septuagint (LXX):** under **Aa → Text**, switch to the Greek Old Testament (with the Textus Receptus for the New Testament) or Brenton's English translation of the Septuagint. The extra Septuagint books (1 Esdras, Tobit, Judith, 1–4 Maccabees, Wisdom, Sirach, Prayer of Manasseh, Baruch, Letter of Jeremiah, Susanna, Bel and the Dragon) appear at the bottom of the book list. Turn on **KJV underneath** to see the matching KJV verse(s) under each verse. Your place, bookmarks and reading plan carry across (they're kept in KJV numbering).
- **Themes:** Paper, White and Night, with adjustable text size and font.

Data is kept on the device (localStorage). Optionally, **Sign in with Google** (under **Aa**) syncs the ribbon, bookmarks and reading plan across devices through Firebase. Only Gmail addresses you approve can sync. The KJV text is public domain: the 1769 standard text, cross-checked verse by verse against three independent KJV copies. Paragraph breaks follow the KJV's own ¶ marks.

## Sync setup (Firebase)
1. Create a Firebase project, add a Web app, and paste its config values into `js/firebase-config.js`.
2. Authentication → Sign-in method → enable **Google**. Under Settings → Authorized domains, add `bluesboy13.github.io`.
3. Create a Firestore database, then paste `firestore.rules` into its **Rules** tab and publish.
4. To approve someone: in Firestore, add a collection `allowed` with one document per person; the document ID is their Gmail address in lowercase (no fields needed). Delete the document to remove them.

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
- **Greek New Testament** — Scrivener's 1894 Textus Receptus (accented), public domain.
- The LXX ↔ KJV verse matching was made for this app by comparing the words of Brenton's English with the KJV (`tools/texts/build_texts.py`).
- **Audio** — "Daniel", Kokoro TTS voice `bm_daniel` (Apache-2.0).
