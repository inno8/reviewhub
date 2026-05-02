# Booth A6 card — Media College Amsterdam Portfolio Day, 7 mei 2026

**Status:** copy + design ready. Print-ready HTML at `booth-a6-card.html`.
**Audience:** Dutch MBO-4 ICT docenten + schooladmins walking past the booth.
**Goal:** they take it, read it on the train home, scan the QR, land on `/welcome`.

## Voice decisions

- Dutch throughout. Audience is docenten — English copy reads as "American product with a Dutch sticker."
- Lead with the magic moment, not the product features. Their pain is **time**: "20 minuten per PR × 25 studenten × 4 vakken = ze komen er niet doorheen."
- The hero claim mirrors the landing page H1 so card → site is one consistent voice: **"Nakijken in 5 minuten — niet 20."**
- "Copilot" not "AI tool" — "tool" reads transactional; "copilot" carries the "jij houdt het stuur" framing that's central to the product's pitch.
- Crebo 25604 namedrop on back: every MBO-4 ICT docent recognises this; it answers "is this compliant?" before they ask.

## Front

```
┌──────────────────────────────────┐
│                                  │
│        [LEERA wordmark]          │
│                                  │
│  Nakijken in 5 minuten           │
│  — niet 20.                      │
│                                  │
│  Een AI-copilot voor             │
│  MBO-4 ICT-docenten.             │
│  Jij houdt het laatste woord.    │
│                                  │
│           [QR code]              │
│       leera.nl/welcome           │
│                                  │
└──────────────────────────────────┘
```

## Back

```
┌──────────────────────────────────┐
│  Hoe het werkt                   │
│                                  │
│  1. Student pusht commit         │
│     → AI schrijft een            │
│     rubric-concept in jouw stem  │
│                                  │
│  2. Jij reviewt, tweakt,         │
│     klikt Verzenden              │
│                                  │
│  3. Student leest binnen         │
│     seconden de feedback —       │
│     in GitHub                    │
│                                  │
│  ✓ Crebo 25604 native            │
│  ✓ AVG-compliant, EU-data        │
│  ✓ GitHub-native, geen uploads   │
│                                  │
│  Pilot tot 1 september:          │
│  gratis, geen creditcard         │
│                                  │
│  inno8techs@gmail.com            │
│  © 2026 Leera                    │
└──────────────────────────────────┘
```

## QR target

Point the QR at `https://leera.nl/welcome` (or whatever your production
domain resolves to for the LandingView). The closing CTA shipped earlier
today (commit `f22c41e`) routes them from `/welcome` → `/org-signup` for
the pilot.

The existing QR PNG at `docs/pitch/leera-form-qr-branded.png` points at
the **student research Google Form**, not the pilot signup. Generate a
fresh QR for `/welcome` before printing — recommend
[qrcode-monkey.com](https://www.qrcode-monkey.com/) with brand colour
`#5b8dee` on transparent background to match the wordmark.

## Print specs

- **Size:** A6 (105mm × 148mm), portrait
- **Bleed:** 3mm on each side (final 111×154mm)
- **Stock:** 350gsm matte coated; matte not glossy so the dark blue
  background doesn't fingerprint
- **Front:** dark navy `#0a0e1a` with the wordmark + hero in `#a3c8ff` /
  white
- **Back:** lighter navy `#1a1f2e` with white text + `#5b8dee` accent on
  the checkmarks and the "Pilot tot 1 september" line
- **Quantity:** 250 for a half-day booth, 500 if you expect heavy traffic

## Co-branding

If the booth wants the Media College Amsterdam logo as a courtesy
host-credit, drop it in the bottom corner of the back at 12mm height.
Otherwise keep the back clean — Leera owns the surface.

## Two-line elevator if asked

> "Wij maken nakijken voor MBO-ICT-docenten draagbaar. AI schrijft het
> concept, docent houdt het laatste woord. PR-review in vijf minuten in
> plaats van twintig."
