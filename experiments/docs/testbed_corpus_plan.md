# Testbed — 24-page master plan (initial)

**Design principle: realistic skin, controlled skeleton.** Every page looks and
weighs like a real production business page from a distinct domain; only the
factor *levels* and the *target placement* are deliberately set and labelled by
us. Realistic chrome (nav, footer, ads, decorative blocks) is wanted — it creates
authentic distractor density, which is part of what we measure.

This is an initial plan to lock the shape of the corpus before we build. Numbers
and domains are adjustable; the factor structure is not.

---

## Legend & invariants

**Factor groups (page-level):** Shadow DOM (S0 none / S1 shallow, 1 open root /
S2 deep, ≥2 nested) × semantic density (high = rich aria/role/data-testid/text /
low = div-soup, style-only classes) → 6 groups × 4 replica pages = **24 pages**.

**Element-level factors — present on EVERY page, not a column below:**
- *Volatility:* every page carries both stable targets and volatile ones (hashed
  ids / generated classes). The volatile attributes take the form of an imitated
  framework fingerprint (see column). These are the decoy the stability predicate
  punishes.
- *Ambiguity:* every page carries both uniquely-signalled targets and
  near-identical ones. "Special ambiguity" column flags only the *extra*,
  structural sources (responsive duplication, near-duplicate component cards).

**Size tiers (distributed across the 24):** Standard ~600–1500 el (×16) · Large
~2500–4000 el (×6) · Extreme 5000+ el (×2, near/over the context cap → truncation
behaviour).

**Fingerprint variants (the volatility vehicle, imitated in static HTML):**
`R` = React-style hashed classes · `A` = Angular-style `_ngcontent` markers ·
`V` = Vue-style `data-v-` scoped markers. Paper wording is always "pages imitating
characteristic framework DOM patterns", never "tested on React/Angular/Vue".

**Target intents (≈8–12 per page, roughly balanced across the corpus):**
click · input text · toggle · select option · submit · navigate.

---

## G1 — S0 (no shadow) · HIGH semantic density
*Server-rendered, accessible, rich aria/role/data-testid. Tests the easy-grounding
baseline and whether volatile decoys still trap the model when stable signal exists.*

| # | Tier | Domain & page | FP | Special ambiguity | Primary intents | What it stresses |
|---|------|---------------|----|-----|-----------------|------------------|
| 1 | Std | Online pharmacy — product detail | V | — | click(add to cart), select(dosage), input(qty), navigate(related) | semantic-rich grounding; volatile price/stock ids as decoy |
| 2 | Std | Government benefits portal — eligibility + apply | R | — | navigate, click(start application), toggle(language) | a11y-mandated realism; available-but-unused failures |
| 3 | Large | Retail bank — account overview | A | responsive dup (balance card mobile/desktop) | click(transaction), navigate(statements), toggle(hide balance) | large DOM + responsive multi-match |
| 4 | Std | Airline — flight search form | V | — | input(origin/dest), select(passengers), toggle(round trip), submit(search) | form-heavy, strong semantic labels |

## G2 — S0 (no shadow) · LOW semantic density
*div-soup, style-only classes, page-builder/legacy. Tests where removing semantic
attributes hurts most and where structure is the only remaining signal.*

| # | Tier | Domain & page | FP | Special ambiguity | Primary intents | What it stresses |
|---|------|---------------|----|-----|-----------------|------------------|
| 5 | Std | Real-estate listing (legacy portal) — property detail | R | — | click(gallery), click(save), navigate(contact agent) | div-soup; B_noSemantic should collapse here |
| 6 | Large | News/media homepage — article grid + ads | A | responsive dup (ad/promo slots) | navigate(articles), click(subscribe) | huge distractor density, low semantic |
| 7 | Std | Marketing landing (page-builder) — lead capture | V | — | input(email), click(CTA), submit(signup) | utility-class soup, style-only classes |
| 8 | **Extreme** | E-commerce mega-listing — product grid | R | responsive dup (grid/list view) + near-duplicate cards | navigate(product), click(filter), click(add to cart) | over the cap → truncation; high ambiguity among cards |

## G3 — S1 (shallow shadow, 1 open root) · HIGH semantic
*Accessible component-library pages. Tests whether structured encodings hold across
a single shadow boundary where flat encodings start to fray.*

| # | Tier | Domain & page | FP | Special ambiguity | Primary intents | What it stresses |
|---|------|---------------|----|-----|-----------------|------------------|
| 9 | Large | SaaS CRM — contact record page | A | — | click(edit), select(status), input(note), submit(save) | shallow shadow + structured-encoding payoff |
| 10 | Std | Hotel booking — room selection | V | — | select(room), toggle(breakfast), input(guests), submit(book) | shadow date/guest picker grounding |
| 11 | Std | Telecom — plan selector | R | near-duplicate plan cards | click(choose plan), toggle(add-ons), navigate(compare) | disambiguation among similar shadow cards |
| 12 | Std | LMS — course page + embedded player widget | V | — | click(play), toggle(mark complete), navigate(lesson) | accessible embedded shadow widget |

## G4 — S1 (shallow shadow) · LOW semantic
*Shadow boundary plus div-soup internals — the realistic "compiled widget" case.*

| # | Tier | Domain & page | FP | Special ambiguity | Primary intents | What it stresses |
|---|------|---------------|----|-----|-----------------|------------------|
| 13 | Large | Analytics dashboard — charts + filters | V | — | select(date range), toggle(metric), click(export) | shadow + low semantic = hardest shallow case |
| 14 | Std | Food delivery — menu + cart widget | R | near-duplicate menu items | click(add item), toggle(extras), input(qty), submit(checkout) | shadow cart over div-soup menu |
| 15 | Std | Job board — listings + filter sidebar widget | A | — | navigate(job), select(filter), click(apply) | shadow filter, style-only listings |
| 16 | Std | Customer support — help center + embedded chat | R | — | input(search), click(article), click(open chat) | third-party-style shadow widget |

## G5 — S2 (deep nested shadow, ≥2) · HIGH semantic
*Enterprise design systems (Lightning/UI5-style). Tests deep nesting where flat
encodings collapse and the COP must still hold.*

| # | Tier | Domain & page | FP | Special ambiguity | Primary intents | What it stresses |
|---|------|---------------|----|-----|-----------------|------------------|
| 17 | **Extreme** | Enterprise admin — user/role management console | A | near-duplicate rows | click(edit user), toggle(active), select(role), submit(save) | deep shadow + extreme size + truncation |
| 18 | Large | Project management — kanban board | R | near-duplicate cards across columns | click(card), toggle(filter), navigate(board) | deep shadow + structural ambiguity |
| 19 | Std | Insurance — multi-step quote flow | V | — | input(details), select(coverage), toggle(add-on), submit(next) | deep-shadow stepper, multi-form |
| 20 | Std | HR/payroll — employee self-service portal | A | — | click(payslip), toggle(direct deposit), navigate(benefits) | deep shadow + high semantic |

## G6 — S2 (deep nested shadow, ≥2) · LOW semantic
*Deep nesting with div-soup internals — the worst realistic case for grounding.*

| # | Tier | Domain & page | FP | Special ambiguity | Primary intents | What it stresses |
|---|------|---------------|----|-----|-----------------|------------------|
| 21 | Std | Video streaming — watch page + nested player | R | — | click(play/pause), toggle(captions), select(quality), navigate(next) | deep-shadow player, low-semantic internals |
| 22 | Large | Logistics — shipment tracking dashboard | V | — | input(tracking #), click(refresh), navigate(shipment) | deep shadow + low semantic + large |
| 23 | Std | Checkout — payment page + nested payment widget | R | responsive dup (order summary) | input(card), select(installments), toggle(save card), submit(pay) | deep-shadow payment widget; critical submit; responsive multi-match |
| 24 | Std | Settings — account preferences (nested toggles) | A | — | toggle(notifications), select(language), toggle(privacy), submit(save) | deep-shadow toggles, toggle-heavy, low semantic |

---

## Coverage check

- **Size tiers:** 16 Standard · 6 Large (#3, #6, #9, #13, #18, #22) · 2 Extreme (#8, #17). ✓
- **Fingerprints spread:** R on 1,2-no… R: 5,8,11,14,16,18,21,23 · A: 2,3,6,9,15,17,20,24 · V: 1,4,7,10,12,13,19,22. ✓
- **Responsive duplication:** #3, #6, #8, #23. ✓
- **Intent coverage:** submit on forms/checkout (4,7,9,14,17,19,23,24); toggle on settings/booking/media; select across booking/admin/checkout; navigate on listings/media; click + input everywhere. ✓
- **Special ambiguity sources:** responsive dup (4 pages) + near-duplicate component cards (8, 11, 14, 17, 18). ✓

---

## Next step — the per-target truth file (separate from the HTML)

Ground truth lives in a sibling file (`pages/page_NN.html` + `pages/page_NN.truth.json`),
**never** in the served DOM — otherwise the answer leaks into the observation the
model sees. Proposed truth-file shape, to lock on one page before building 24:

- page id, group, size tier, fingerprint variant
- per target: target id · intent · oracle element (a stable internal handle the
  harness can resolve, e.g. a private `data-truth-id` stripped before snapshotting,
  or an absolute path the oracle keeps) · is-ambiguous flag · expected-stable-signal
  (what a correct non-volatile locator could key on)
- per attribute/class label: volatile? (so the success predicate can check
  "non-volatile signals only" deterministically)

Open question to decide first: how the harness maps a returned XPath back to "the
oracle element" without that handle being visible in the snapshot. Cleanest is a
private attribute injected for the oracle, stripped from every bundle/encoding
before the observation is built.
