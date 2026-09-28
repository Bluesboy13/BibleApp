# KJV Bible

A simple, book-like King James Bible reader. Plain HTML/CSS/JS, installable on phone or desktop, and it works offline.

- **Book layout:** serif type, paper-colored page, a large chapter number at the start of each chapter, and no verse numbers by default.
- **Verse numbers:** tap **¹²³** in the top bar to show or hide them.
- **Reading:** scrolls by default. Switch to **Pages** under **Aa** to turn pages like a Kindle (tap the edges or swipe).
- **Ribbon:** remembers where you left off and reopens there. Tap the bookmark icon to save more spots.
- **Reading plan:** Genesis to Revelation in 365 days (about 3–4 chapters a day), with days to check off.
- **Themes:** Paper, White and Night, with adjustable text size and font.

All data stays on your device (localStorage). The KJV text is public domain.

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
