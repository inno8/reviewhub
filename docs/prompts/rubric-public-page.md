# Design prompt: LEERA `/rubric` public page

> Self-contained design brief. Paste into a fresh Claude conversation
> or pass to a design agent. Carries all context, brand voice, and
> constraints so the output is on-brand without follow-up questions.

## Context

LEERA is a "Nakijken Copilot" (grading copilot) for Dutch MBO-4 ICT
teachers (docenten). MBO-4 is the highest level of Dutch vocational
education — students who graduate go into real software engineering
jobs or HBO. Teachers grade student GitHub PRs; LEERA drafts the
feedback in the docent's voice; the docent reviews + edits + sends.
v1 launches May 7 2026 at Media College Amsterdam Portfolio Day.
Pricing: €200/cohort/month.

You are designing **`/rubric`** — a **public, no-auth-required page**
that explains how LEERA grades code. This is the **MBO-4 readiness
signal**. Schools that visit the booth will scan this page before
signing a contract. It needs to communicate "we built this for the
Dutch vocational education context, we know what we're measuring, we
know how niveau 4 maps to professional engineering."

## Audience

Three reader profiles:

1. **School admin / curriculum director** (primary). Skeptical, doesn't
   code, needs to know if LEERA aligns with the MBO curriculum and
   Crebo werkprocessen. Will scan headers and skim. Rarely reads
   paragraphs.
2. **Docent (teacher)**. More technical, wants to know what
   categories are graded and at what level definitions. Will read
   examples and rubric levels closely.
3. **Student or parent**. Curious. Wants to know "what is my child
   being graded on, and is it fair?"

The page must work for all three without dumbing down for any.

## What the page must communicate

In rough priority order:

1. **The 6 Crebo 25604 rubric criteria LEERA grades on**, each with:
   - The canonical Dutch name from the Crebo werkproces (the docent-facing name)
   - A one-sentence description
   - 4 niveau levels with the official labels:
     1=Nog niet beheerst, 2=Gedeeltelijk beheerst, 3=Op opleidingsniveau,
     4=Boven niveau — same labels every Dutch MBO docent already knows
   - One realistic code example per category (short, in PHP or Python
     — the languages MBO-4 ICT students use most)
   - The Crebo werkproces code (B1-K1-W2, B1-K1-W3, etc.) so the
     curriculum coordinator can verify alignment with the
     kwalificatiedossier

2. **The grading philosophy**:
   - Rubric-aligned, not vibes-aligned. The teacher sets the rubric
     weights per course; LEERA grades against those weights.
   - Behavioral proof, not just correctness. LEERA tracks whether a
     student fixed a flagged issue *and didn't reintroduce it* across
     subsequent commits. This is the LearningProof system. Skill
     scores move based on observed behavior, not single-PR scores.
   - Docent voice. LEERA drafts feedback in the teacher's tone
     (calibrated from past examples), but the teacher has the final
     word. LEERA never sends comments without explicit Send.
   - Privacy-first. Student PII is redacted before any LLM call. The
     docent's name and the student's identity never reach the model.

3. **What LEERA does NOT grade**:
   - Aesthetics ("pretty code")
   - Cleverness for its own sake
   - Conformance to one specific framework or library version
   - Anything not in the rubric

   This negative framing matters because docenten worry about AI
   imposing American FAANG opinions on Dutch vocational students.

4. **How the rubric maps to MBO-4 expectations**:
   - Niveau 4 students should be capable of working independently as
     junior engineers
   - The rubric levels are calibrated against what a docent would
     expect at end-of-jaar 4
   - Niveau 1 = "onvoldoende voor diploma" (red); Niveau 4 = "klaar
     voor het werkveld" (green)

5. **A concrete invitation**:
   - "Wil je je vak inrichten met deze rubric? Plan een gesprek." →
     CTA to a contact form / email link
   - Or: "Probeer het gratis voor je klas tot 1 september" → link to
     org-signup

## The 6 Crebo criteria (canonical content)

These are defined in `grading/rubric_defaults.py:CREBO_RUBRIC_CRITERIA`
in the codebase — pull the canonical level definitions from there
rather than retyping. The Skill rows are seeded by `seed_skills`.

### 1. Code-ontwerp (`code_ontwerp`) — Crebo B1-K1-W2 "Ontwerpt software" — weight 15
**Wat we kijken:** Scheiding van verantwoordelijkheden, lagen,
abstracties, herbruikbaarheid.

| Niveau | Officiële label | Wat dat betekent |
|---|---|---|
| 1 | Nog niet beheerst | Geen duidelijke structuur; alles in één functie of bestand. |
| 2 | Gedeeltelijk beheerst | Basis-structuur, maar abstractie ontbreekt; veel herhaling. |
| 3 | Op opleidingsniveau | Logische opbouw, duidelijke scheiding van verantwoordelijkheden. |
| 4 | Boven niveau | Doordacht ontwerp; herbruikbaar, uitbreidbaar, minimale coupling. |

**Voorbeeld (PHP):** Een controller die een query bouwt, formatting doet
én de view rendert is niveau 1. Een dunne controller die delegeert naar
een service + een presenter is niveau 3.

### 2. Code-kwaliteit (`code_kwaliteit`) — Crebo B1-K1-W3 "Realiseert software" — weight 20
**Wat we kijken:** Leesbaarheid, naamgeving, consistentie, foutafhandeling.

| Niveau | Officiële label | Wat dat betekent |
|---|---|---|
| 1 | Nog niet beheerst | Moeilijk leesbaar; onduidelijke namen; geen foutafhandeling. |
| 2 | Gedeeltelijk beheerst | Werkt, maar inconsistent; cryptische namen; fouten worden geslikt. |
| 3 | Op opleidingsniveau | Leesbaar, idiomatic, fouten worden met context afgehandeld. |
| 4 | Boven niveau | Professioneel niveau; zelf-documenterend, robuust, edge cases afgedekt. |

### 3. Veiligheid (`veiligheid`) — Crebo B1-K1-W3 "Realiseert software (sub: veiligheid)" — weight 20
**Wat we kijken:** SQL-injectie, XSS, IDOR, hardcoded secrets,
authenticatie-fouten, input-validatie.

| Niveau | Officiële label | Wat dat betekent |
|---|---|---|
| 1 | Nog niet beheerst | Duidelijke kwetsbaarheden: hardcoded secrets, SQL-injectie, geen input-validatie. |
| 2 | Gedeeltelijk beheerst | Bewust van veiligheid, maar met gaten; inconsistente input-checks. |
| 3 | Op opleidingsniveau | Standaard praktijken: parameterized queries, input-validatie, geen secrets in code. |
| 4 | Boven niveau | Threat-modeled, least-privilege, defense in depth; edge cases doordacht. |

**Voorbeeld:** `DB::select("...title = '$search'")` is niveau 1.
`Book::where('title', $search)` is niveau 3.

### 4. Testen (`testen`) — Crebo B1-K1-W4 "Test software" — weight 20
**Wat we kijken:** Of er tests zijn, of ze de juiste dingen testen, of
edge cases gedekt zijn, of regressies gevangen worden.

| Niveau | Officiële label | Wat dat betekent |
|---|---|---|
| 1 | Nog niet beheerst | Geen tests aanwezig. |
| 2 | Gedeeltelijk beheerst | Alleen happy-path tests; edge cases en errors ongetest. |
| 3 | Op opleidingsniveau | Happy- en error-paden getest; redelijke dekking. |
| 4 | Boven niveau | Grondige dekking incl. edge cases en regressies; tests zijn zelf leesbaar. |

### 5. Verbetering (`verbetering`) — Crebo B1-K1-W5 "Doet verbetervoorstellen" — weight 10
**Wat we kijken:** Reactie op eerdere feedback, refactoring, performance,
documentatie, eigen initiatief.

| Niveau | Officiële label | Wat dat betekent |
|---|---|---|
| 1 | Nog niet beheerst | Geen reactie op eerdere feedback; TODOs blijven openstaan. |
| 2 | Gedeeltelijk beheerst | Past feedback deels toe, zonder onderliggende patronen te herkennen. |
| 3 | Op opleidingsniveau | Verwerkt feedback consistent; doet kleine verbeteringen uit eigen initiatief. |
| 4 | Boven niveau | Refactored proactief; stelt verbeteringen voor die verder gaan dan de opdracht. |

### 6. Samenwerking (`samenwerking`) — Crebo B1-K2-W1+W3 "Voert overleg & reflecteert" — weight 15
**Wat we kijken:** Commit messages, PR-beschrijvingen, reactie op review,
zelfreflectie.

| Niveau | Officiële label | Wat dat betekent |
|---|---|---|
| 1 | Nog niet beheerst | Commit-messages onduidelijk; PR-beschrijving ontbreekt; geen reactie op review. |
| 2 | Gedeeltelijk beheerst | Basis-beschrijving; reageert op reviews maar kort of defensief. |
| 3 | Op opleidingsniveau | Duidelijke commit-messages, PR-beschrijving toont context, constructieve reactie. |
| 4 | Boven niveau | PR-beschrijving documenteert keuzes en trade-offs; reflecteert zelfstandig. |

(All 6 criteria use the same Crebo niveau labels: Nog niet beheerst,
Gedeeltelijk beheerst, Op opleidingsniveau, Boven niveau. Pull the
canonical level descriptions from `grading/rubric_defaults.py` rather
than retyping — that file is the single source of truth.)

## Design system / brand voice

Read `docs/DESIGN.md` in the LEERA repo before designing — it defines
fonts, colors, spacing, motion. Do not deviate without explicit
approval. Specifics:

- Dark theme primary (the rest of LEERA is dark — the public rubric
  page should match, not look like a bright marketing site bolted onto
  a dark app)
- Typography: existing display + body fonts from DESIGN.md
- Color: each SkillCategory has a hex `color` field in
  `grading.models.SkillCategory`. Use those for the per-category
  accent. Do not invent new colors.
- Niveau 1 = error red, Niveau 4 = primary green. Match the existing
  severity treatment.
- No emoji. No stock illustrations. Code samples use the same
  monospace stack as the rest of the app.
- Material symbols for icons (already used everywhere)

**Voice (Dutch + Dunglish, like the rest of LEERA's copy):**

- Direct, concrete, sharp, encouraging.
- Builder talking to builder, not consultant to client. Not corporate,
  not academic.
- Avoid: "delve", "comprehensive", "robust", "leverage", "synergy",
  "transform", "innovative".
- Avoid: stock phrases like "the bottom line", "make no mistake",
  "let me break this down".
- Use real numbers and real examples. "5 min review per PR" beats
  "significant time savings".
- Short paragraphs. Mix one-sentence paragraphs with 2-3 sentence runs.
- End every section with what the reader can do next.

## Layout structure (suggestion)

```
┌─────────────────────────────────────────────────────────────┐
│ Top nav: LEERA logo, "Rubric", "Inloggen", "Praat met ons"  │
└─────────────────────────────────────────────────────────────┘

[Hero — half-viewport, dark]
  Headline (1 line, Dutch): "Hoe LEERA jouw code beoordeelt"
  Sub (1 paragraph): One-sentence positioning. "Acht skills. Vier
    niveaus. Eén docent met de eindstem."
  Two CTAs: "Bekijk de skills" (anchor scroll) | "Plan een gesprek"

[Philosophy strip — 3 columns or stacked]
  Three pillars (each: icon + 2-line claim + 1-line "wat dat
  betekent"):
    1. Rubric-aligned: "Geen vibe-cijfers." → Docent stelt de
       gewichten in.
    2. Behavioral proof: "Niet één PR, maar het patroon." → Skills
       bewegen op observatie, niet op één toets.
    3. Docent met eindstem: "AI doet het concept. De docent stuurt."
       → Geen LEERA-comment gaat naar GitHub zonder Send.

[Skills grid — primary content, 8 cards]
  Each card: category color accent + name + 1-line description +
  niveau bar (4 dots, hover for level definition) + "Bekijk niveaus"
  click expands inline detail panel with full level definitions and
  the code example.
  Allow vertical scroll within an expanded card so the page doesn't
  jump.

[Niveau-mapping section]
  Visual: 4 columns niveau 1-4. Each column shows what that niveau
  looks like across all 8 skills as small chips. Helps the school
  admin see "what does niveau 3 in onze klas look like".

[What we don't grade]
  Short list, defensive but confident. Three items max. Important
  for the docent skeptic.

[CTA — close]
  "Klaar om je vak in te richten?"
  Two buttons: "Probeer gratis tot 1 september" + "Plan een gesprek"

[Footer]
  Standard. Privacy, GDPR, contact, links to /login + /docs.
```

## Hard constraints

- **Public page, no auth required.** A school admin must be able to
  share the link before any account exists.
- **Mobile-friendly.** Docenten and admins read on phones during
  commute. Test on a 375px viewport.
- **Loads in <1.5s on 3G.** Don't ship hero videos. Static, accessible,
  fast.
- **Accessible (WCAG AA).** Color contrast on niveau levels matters —
  colorblind users must distinguish level 1 from level 4.
- **No tracking pixels.** GDPR-conscious docenten will check.

## Deliverable

A complete Vue 3 SFC at `frontend/src/views/RubricPublicView.vue` and
a route entry in `frontend/src/router/index.js` mounting it at
`/rubric` (no auth guard). Use Tailwind utilities and the existing
DESIGN.md tokens. Include a `<script setup lang="ts">` block, full
template, and any scoped CSS for the per-category color accents that
can't be done with utilities alone.

If a Django endpoint to serve the canonical rubric content
(categories, level definitions) doesn't exist yet, hardcode the
content in the SFC for now. v1.1 can swap to a fetched response once
the endpoint lands.

Use Dutch for all visible copy. English is fine in code comments. Get
the voice right — read existing LEERA copy in
`frontend/src/views/AcceptInviteView.vue` and
`frontend/src/views/LandingView.vue` for tone reference before writing
your own.
