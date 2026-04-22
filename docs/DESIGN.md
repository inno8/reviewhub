# Design System — Leera

Generated: 2026-04-22
Product: Leera (internal codename: Nakijken Copilot)
Stack: Vue 3 + Tailwind CSS (Stitch Material-3 palette)
Constraint: Always read this doc before any visual or UI decision. Flag deviations in QA.

---

## 1. Product Context

- **What Leera is:** AI-assisted code review + teacher intelligence platform. Reads student PRs, drafts rubric-based grading with evidence quotes, tracks each student's skill growth over time, surfaces class-wide patterns.
- **Who it's for:** Dutch MBO-4 ICT teachers (docenten) + teamleiders + their students. Primary teaching audience ages 45-60; student audience ages 16-20.
- **Space / industry:** Vocational software-education in NL. Adjacent to CodeGrade (autograding, university-focused), distinct from Moodle / Canvas / Blackboard (LMS administration).
- **Project type:** Multi-role web app (app UI) + marketing site (landing page at `leera.app`).

## 2. Positioning Thesis

**Leera is craftsman software for teachers, not edtech for administrators.**

Every design decision should push toward that thesis. When in doubt, look at Linear, Notion, Attio, Figma. Not Blackboard, Canvas, Instructure, Moodle.

The audience is time-pressed professionals evaluating young craftsmen's work. The interface should respect their time, make evidence visible, and feel like a tool.

## 3. Aesthetic Direction

**Primary aesthetic:** Brutally Minimal + Craftsman
- Typography and whitespace do the work
- Small amount of amber warmth where human feedback happens
- No decoration for decoration's sake
- No illustrations, mascots, or cartoon characters
- Dark-first (teachers grade at night)

**What this is NOT:**
- Not playful K-12 edtech ("bubbly buttons, rainbow gradients")
- Not enterprise LMS ("dense tabs, battleship grey")
- Not AI-generic ("purple gradient hero, 3-column icon grid, centered CTA")
- Not corporate SaaS ("trust badges, photo of diverse smiling workers")

**Mood words:** serious, honest, precise, warm-in-restraint, teacher-in-the-loop, code-as-craft

## 4. Color System

### 4.1 Foundation (existing Stitch palette — keep)

Source of truth: `frontend/tailwind.config.js`. Do NOT redefine elsewhere.

**Surface scale (dark-first):**

| Token | Hex | Usage |
|---|---|---|
| `background` / `surface` | `#10141a` | Page background, deepest level |
| `surface-container-lowest` | `#0a0e14` | Modal backdrops, input backgrounds |
| `surface-container-low` | `#181c22` | Cards, list rows, primary elevated surfaces |
| `surface-container` | `#1c2026` | Secondary elevated sections |
| `surface-container-high` | `#262a31` | Hover states, tertiary elevation |
| `surface-container-highest` | `#31353c` | Button surfaces, active states |
| `surface-bright` | `#353940` | Highest elevation |

**Accent colors:**

| Token | Hex | Semantic |
|---|---|---|
| `primary` | `#a2c9ff` | Primary actions, active states, links |
| `primary-container` | `#58a6ff` | Primary button gradients, focus rings |
| `secondary` | `#aec8ef` | Secondary actions, subtle accents |
| `tertiary` | `#ffba42` | Warmth, pending-review, warning-adjacent |
| `tertiary-container` | `#da9600` | Deeper amber for emphasis |
| `error` | `#ffb4ab` | Destructive actions, failed states, critical findings |
| `error-container` | `#93000a` | Error banner backgrounds |

**Text on surfaces:**

| Token | Hex | Usage |
|---|---|---|
| `on-surface` | `#dfe2eb` | Primary body text |
| `on-surface-variant` | `#c0c7d4` | Secondary text, labels |
| `outline` | `#8b919d` | Tertiary text, disabled |
| `outline-variant` | `#414752` | Borders, dividers |
| `on-primary` | `#00315c` | Text on primary-colored surfaces |

### 4.2 Usage rules

- **Blue (`primary`) = action.** Buttons, links, interactive chips. Never decorative.
- **Amber (`tertiary`) = teacher attention needed.** Pending review, new items in inbox, warning severity findings. Use sparingly — signal loses meaning when spammed.
- **Red (`error`) = destructive or critical only.** Delete actions, PR closed, critical security findings. Never for "warning-lite."
- **Greens are deliberately absent from the accent palette.** The category over-uses "success green"; we don't. Success is implied by absence of error + completeness.
- **Gradients:** allowed only on `primary-gradient` button class. Never on hero backgrounds, never on cards.

### 4.3 Semantic mapping

- Success → no chip or icon needed, or use `primary` if explicit confirmation required
- Warning → `tertiary` (amber)
- Error → `error` (soft red)
- Info → `secondary` (muted blue)
- Pending → `tertiary` (amber, lower opacity: `tertiary/40`)
- Discarded / archived → `outline` + reduced opacity (`opacity-60`)

### 4.4 Dark mode / light mode

**Dark-only for v1 and v1.1.** Teachers grade at night, interface is dark-forward. Light mode deferred. Do NOT bolt on a half-baked light theme; schedule it as a full redesign when time permits.

## 5. Typography

### 5.1 Families

| Role | Family | Fallback |
|---|---|---|
| **App UI (all)** | `Inter` | `system-ui, sans-serif` |
| **Marketing display** | `Fraunces` | `Georgia, serif` |
| **Marketing body** | `Inter` | `system-ui, sans-serif` |
| **Code / data tables** | `Fira Code` | `Consolas, monospace` |

**Why Inter for app:** best-in-class for dense data displays, tabular-nums for metrics, tight legibility at small sizes. Already in `tailwind.config.js`.

**Why Fraunces for marketing:** every edtech site uses a sans-serif display. A serif on the landing page signals editorial gravitas, books, craft. Fraunces specifically because it has a wide weight/optical-size range and doesn't read as "stuffy serif."

**Fonts blacklisted** (never use): Papyrus, Comic Sans, Lobster, Impact, Montserrat, Poppins, Raleway, Clash Display, Lato, Open Sans.

### 5.2 Scale (modular, 1.25 ratio)

App UI:

| Role | Size | Weight | Line height | Letter spacing |
|---|---|---|---|---|
| Display (hero) | 36px / 2.25rem | 700 | 1.1 | -0.02em |
| Page title | 28px / 1.75rem | 700 | 1.2 | -0.01em |
| Section heading | 20px / 1.25rem | 600 | 1.3 | -0.005em |
| Card title | 16px / 1rem | 600 | 1.4 | 0 |
| Body | 14px / 0.875rem | 400 | 1.5 | 0 |
| Body-small | 13px / 0.8125rem | 400 | 1.5 | 0 |
| Label | 12px / 0.75rem | 600 | 1.4 | 0.01em |
| Caption | 11px / 0.6875rem | 400 | 1.4 | 0.02em |
| Code | 13px / 0.8125rem | 400 | 1.5 | 0 |

Marketing display (hero, section leads): larger scale — 48px / 64px / 80px with Fraunces weight 500-700.

### 5.3 Bilingual rules

- **Primary language:** Dutch (nl-NL) for MBO-4 ICT audience
- **Technical terms stay English** in-line, unitalicized: PR, rubric, GitHub, commit, branch, pull request, webhook, merge
- **Never translate what doesn't translate:** "pull request" remains "PR" in Dutch copy, not "pul-verzoek"
- **Dutch product copy voice:** direct, second-person informal ("je" not "u" except in formal settings like invoices/legal)
- **English marketing copy** (for Belgium Flanders + future expansion): matches Dutch tone — direct, matter-of-fact, craftsman

## 6. Spacing

**Base unit:** 4px (standard Tailwind).

**Density:** comfortable (not compact, not spacious). Teachers scan inboxes at speed — compact feels clinical, spacious wastes vertical real estate.

**Scale** (using Tailwind tokens):

| Token | Value | Usage |
|---|---|---|
| `p-1` / `m-1` | 4px | Chip padding, icon margins |
| `p-2` / `m-2` | 8px | Tight groups |
| `p-3` / `m-3` | 12px | List row internal padding |
| `p-4` / `m-4` | 16px | Card internal padding (default) |
| `p-6` / `m-6` | 24px | Section padding |
| `p-8` / `m-8` | 32px | Page gutter (mobile) |
| `p-12` / `m-12` | 48px | Page gutter (desktop) |
| `p-16` / `m-16` | 64px | Major section separators |

**Vertical rhythm:** sections separated by 32px minimum on desktop, 24px on mobile.

## 7. Layout

### 7.1 App UI — grid-disciplined

- Sidebar: 240px fixed-width on desktop, collapsible drawer on tablet/mobile
- Main content: max-width `max-w-6xl` (1152px), centered
- Padding: `p-8` desktop, `p-4` mobile
- `AppShell` component wraps every authenticated route (sidebar + header + main slot)
- Tables use full content width; cards use comfortable max-width

### 7.2 Marketing site — editorial

- Asymmetric grid where useful
- Fraunces display sizes break the 8px grid intentionally (type wants to breathe)
- Max content width: `max-w-5xl` (1024px) for readability
- Hero can be full-bleed; body sections contained

### 7.3 Border radius

| Level | Value | Usage |
|---|---|---|
| DEFAULT | 4px (0.25rem) | Small inputs, chips |
| `rounded-lg` | 8px (0.5rem) | Buttons, form inputs |
| `rounded-xl` | 12px (0.75rem) | Cards, panels (most common) |
| `rounded-2xl` | 16px (1rem) | Hero cards, modals |
| `rounded-full` | 9999px | Circular avatars, pill buttons |

Consistency rule: within a single screen, radius variation must be purposeful. Don't mix `rounded-lg` and `rounded-2xl` side-by-side without hierarchy intent.

## 8. Motion

**Approach:** minimal-functional. Motion exists to aid comprehension, never to perform.

### 8.1 Durations

| Type | Duration | Usage |
|---|---|---|
| Micro | 50-100ms | Hover color shifts, icon fills |
| Short | 150-250ms | Button press, tab switch, dropdown open (default) |
| Medium | 250-400ms | Modal open, drawer slide, page transition |
| Long | 400-700ms | Marketing scroll reveals (rare) |

### 8.2 Easing

- Enter: `ease-out` (elements arriving decelerate)
- Exit: `ease-in` (elements leaving accelerate away)
- Move: `ease-in-out` (repositioning elements)

### 8.3 Rules

- **No entrance animations on app pages.** Dashboards don't bounce in.
- **Hover states transition color only**, never scale or transform. Scale-on-hover is toy-like.
- **Loading states are skeletons**, not spinners. Progress bars only for long operations (>2 sec).
- **Marketing site may use one scroll-triggered reveal per section.** More than that feels desperate.

## 9. Logo / Wordmark

**Status:** conceptual. To be executed by a designer or Claude Design in May.

### 9.1 Wordmark concept

**LEERA** rendered as a connected-E wordmark: the two Es joined by a subtle horizontal bar, symbolizing the connection between `leer-` (to learn) and `leraar` (teacher). Monospace-inspired letterform — clean geometric construction, no flourishes.

Weights: a single-weight logomark only. No italic, no bold variant. Scales from 16px favicon to 200px hero.

### 9.2 Lockups

- **Primary (white on dark):** `LEERA` wordmark in `#dfe2eb` on `#10141a`
- **Inverted (dark on light, for print/press):** wordmark in `#10141a` on white
- **Single-color (monochrome amber accent for special cases):** `LEERA` in `#ffba42` on `#10141a` — use sparingly (launch announcements, "we shipped" posts)

### 9.3 Favicon

16×16 and 32×32 — render the double-E motif cropped so only the joined-E shape is visible. Works at small size as a recognizable glyph.

### 9.4 Clear space

Minimum clear space around the wordmark: the width of one uppercase "E" on all sides.

## 10. Iconography

**Source:** Material Symbols (already in use). Rounded style, weight 300, fill optional per state.

**Rules:**

- Icons accompany labels on navigation; never icon-only for primary actions
- Icon size matches text: 16px for body, 20px for section headings
- Color inherits from text color (`on-surface` by default, `primary` when active)
- No custom illustration style in v1. If we need a spot illustration for marketing, commission it separately.

## 11. Component Patterns

Refer to the actual Vue components for canonical implementations. This section documents the conceptual patterns.

### 11.1 Cards

Pattern: `bg-surface-container-low border border-outline-variant/10 rounded-xl p-6`

Variants:
- Hover: `hover:border-primary/40 hover:bg-surface-container`
- Selected: `border-primary/60 bg-surface-container`
- Disabled: `opacity-60`

### 11.2 Buttons

| Variant | Class pattern | Usage |
|---|---|---|
| Primary | `primary-gradient text-on-primary font-bold px-5 py-2.5 rounded-lg shadow-lg shadow-primary/10 hover:shadow-primary/20 active:scale-95` | Main action per screen (one only) |
| Secondary | `bg-surface-container hover:bg-surface-container-high text-on-surface px-5 py-2.5 rounded-lg` | Secondary actions |
| Ghost | `text-on-surface-variant hover:text-on-surface px-4 py-2 rounded-lg` | Tertiary, "learn more" |
| Destructive | `border border-error/30 text-error hover:bg-error/10 px-4 py-2.5 rounded-lg` | Delete, discard, critical |

### 11.3 Form inputs

`bg-surface-container-lowest border border-outline-variant/30 rounded-lg text-on-surface focus:ring-1 focus:ring-primary/50 py-3 px-4`

### 11.4 Chips / badges

Small, pill-shaped, `rounded-full` + `bg-primary/15 text-primary px-3 py-1 text-xs font-medium`. Semantic color variants follow the color system.

### 11.5 Empty states

`glass-panel p-8 text-center rounded-xl` with:
- Material Symbol icon (40px, `text-outline`)
- Title (body-small weight 600)
- Body explaining what the user should do to populate (body-small, `text-on-surface-variant`)
- Optional primary button

### 11.6 Tables

Sortable columns, zebra-striping OFF (too noisy on dark), row hover `hover:bg-surface-container`, tabular-nums for numeric columns. Compact row height 40px, comfortable 48px.

## 12. Voice & Writing

### 12.1 Core rules

- **Lead with what it does, not how amazing it is.**
- **Address the teacher in second person direct.** "Je ziet elke student groeien" not "Teachers will see each student grow."
- **No jargon we invented.** If a term isn't in the teacher's vocabulary, rephrase.
- **Technical terms in English inline.** PR, rubric, webhook, commit — untranslated, unitalicized.
- **Numbers as digits, not words.** "3 keer sneller" not "drie keer sneller."
- **No em-dashes in product copy.** Use commas or periods. (Exception: technical docs.)

### 12.2 Banned words (AI-slop flags)

Avoid in all product, marketing, and doc copy:

`empower, unlock, transform, disrupt, revolutionize, seamless, delightful, robust, comprehensive, nuanced, multifaceted, furthermore, moreover, pivotal, landscape, tapestry, underscore, foster, showcase, intricate, vibrant, fundamental, significant, interplay, game-changer, world-class, best-in-class`

### 12.3 Tone by surface

| Surface | Tone |
|---|---|
| Onboarding / empty states | Warm, instructive, specific |
| Success confirmations | Brief, matter-of-fact, acknowledges what happened |
| Error messages | Direct, explains cause, suggests next action |
| Marketing (landing page) | Confident, data-backed, teacher-first |
| Legal / AVG copy | Formal "u", precise, no corporate hedging |
| Student-facing | Same register as teacher — we don't talk down |

### 12.4 The signature hero quote

The landing page and pitch deck both lead with this verified student quote:

> *"Tijdens de opdracht krijgen we eigenlijk geen feedback op de code. Ik zou wel na iedere push feedback willen krijgen."*
> — MBO-4 ICT student, Media College, April 2026

Use this exactly. Do not rewrite. Verbatim is the signal.

## 13. Marketing Site Aesthetic

Distinct from the app. Landing page (`leera.app`) is **editorial + typographic**, not dashboard-dense.

### 13.1 Key differences from app UI

- **Fraunces display** on hero headlines (app uses Inter)
- **Looser spacing** — scrolling page, not scan-dense interface
- **Full-bleed sections** allowed (app is contained)
- **One scroll-triggered animation per section** maximum
- **Long-form body copy** up to 65ch line length, not data-dense

### 13.2 Page structure (leera.app landing)

1. Hero: student quote (Fraunces, large) + one-line product description + single primary CTA
2. Problem section: 3 short paragraphs, no icon columns
3. How it works: 4-step vertical flow with real product screenshots
4. Proof: dogfood numbers + intern arc chart
5. Pricing: single card, one number (€200/cohort/month)
6. Footer: contact, legal, AVG/DPA link

### 13.3 Forbidden marketing patterns

- Hero photo of diverse smiling workers
- 3-column feature grid with icons in colored circles
- Trust badges ("as seen in X, Y, Z")
- Testimonial carousel with stock headshots
- "Trusted by" logo wall
- Gradient background mesh
- Hero CTA button in purple

## 14. Accessibility

- **Minimum contrast:** WCAG AA. All body text passes 4.5:1 minimum. Labels pass 3:1.
- **Focus visible:** always, via `focus:ring-1 focus:ring-primary/50`. Never remove outline globally.
- **Keyboard navigation:** all interactive elements reachable via Tab. Escape closes modals.
- **Screen reader:** Material Symbols have `aria-hidden="true"` when purely decorative; paired with visible label or `aria-label`.
- **Prefers-reduced-motion:** respect the media query. Disable the 150ms transitions, keep the color change.
- **Target size:** tap targets minimum 44×44px on mobile, 32×32px on desktop.

## 15. Future Work (v1.1+)

Not in v1 scope, documented so we don't forget:

- Light mode (full redesign, not inversion)
- Illustration system (spot illustrations for marketing, not the app)
- Motion system expansion (scroll-driven, signature product moments)
- Dutch/English localization toggle (currently Dutch-first hardcoded)
- High-contrast theme for accessibility-first teachers
- Print stylesheet (teachers sometimes print comment summaries for sprint reviews)
- Brand voice guidelines expansion (PR responses, support email templates, social posts)

## 16. Decisions Log

| Date | Decision | Rationale |
|---|---|---|
| 2026-04-22 | Initial DESIGN.md created | Codify existing Stitch palette + Inter/Fira Code, add marketing Fraunces, document voice and motion rules, define wordmark direction |
| 2026-04-22 | Dark-only for v1 | Teacher grading happens at night. Half-baked light mode is worse than none. |
| 2026-04-22 | Fraunces for marketing display | Contrast with app's sans, editorial gravitas, differentiates from generic edtech |
| 2026-04-22 | Double-E connected wordmark | Unique visual signature, symbolizes leer-leraar connection, scales well |
| 2026-04-22 | Greens absent from accent palette | Category over-uses "success green"; restraint signals craft |
| 2026-04-22 | No mascots, no illustrations in v1 | Every LMS has a cartoon robot. We don't. |

---

## Appendix A: Quick reference for developers

Before writing any UI code:

1. Read this file (DESIGN.md)
2. Check `frontend/tailwind.config.js` for exact hex values
3. Check an existing similar component for canonical patterns (e.g. GradingInboxView for list UI, OrgMembersView for table-with-tabs)
4. If no existing pattern fits, propose in the PR description + reference the relevant DESIGN.md section

Don't deviate without explicit user approval. Flag deviations in code review.

## Appendix B: For Claude Design (video + mockup generation)

When generating marketing assets via `claude.ai/design`, paste this summary block:

```
Leera brand:
- Dark near-black base #10141a
- Light blue accent #a2c9ff (primary)
- Amber accent #ffba42 (warmth)
- Inter for UI, Fraunces for marketing display, Fira Code for code
- Voice: direct, matter-of-fact, teacher-empathetic, NOT corporate
- No stock photos, no mascots, no gradient meshes, no purple
- Double-E wordmark with joined horizontal bar between the two Es
- Dutch primary language, English technical terms inline
```
