# Real-site pilot: site and target rule (pre-registered)

Status: committed **before** any processing of the sites (no HTML decoded, no page loaded, no
target computed). The rule does not change after the commit. If any part turns out to be
infeasible, the work stops and the author decides; the rule is not edited.

Purpose (reviewer R1 #2): B_full vs B_noVolatile on real pages, under F1 and F3. This file fixes
which sites and which targets enter the pilot. The analysis is fixed separately in
`pilot_analysis_plan.md` (same commit).

## 1. Source

- Domains: the 100 domains of the registered Common Crawl sample (`../cc_volatility/sampling_rule.md`,
  commit `4cb40ce`; list in `../cc_volatility/dry_run.json`, `qualified_domains`).
- Pages: the **May** snapshot, CC-MAIN-2026-21 (the chosen homepage record of each domain, already
  cached and integrity-checked, `../cc_volatility/fetch_integrity.md`).
- The September snapshot, CC-MAIN-2026-39, is used **only** for the secondary measure "survival"
  (`pilot_analysis_plan.md`).

## 2. Site eligibility

A site is eligible only if all four criteria hold, checked in the order (а) → (б) → (в) → (г).
The reported reason for an ineligible site is the first criterion that fails.

**(а) Volatile class present.** The May HTML contains at least one class token that the frozen
Oracle flags as volatile. Values: the WARC HTTP payload, decoded exactly as in
`../cc_volatility/analysis_plan.md` (gzip if `Content-Encoding: gzip`; charset from the HTTP
`Content-Type`, then `<meta charset>` in the first 4096 bytes, then UTF-8; `errors="replace"`),
parsed with Python `html.parser`, class values split on ASCII whitespace. Classifier: the same C#
CLI as cc_volatility (`../cc_volatility/oracle_cli/`, reflection on `Oracle.IsVolatileClass`, Oracle
source unchanged). Sites without such a token are counted as **"B_full ≡ B_noVolatile by
construction"** and are not loaded.

**(б) Offline load, walker and determinism.**

- Loading. The decoded payload is served as UTF-8 (`Content-Type: text/html; charset=utf-8`,
  status 200) by a Playwright route for the first main-frame navigation to the record's
  `WARC-Target-URI`. **Every other request is aborted** (all URLs, including the page's own
  origin); WebSockets are not connected; service workers are blocked; Chromium additionally runs
  with `--host-resolver-rules=MAP * ~NOTFOUND`, so no host name resolves. Scripts that cannot
  load a resource simply fail; this is by rule and is not repaired. Each load uses a new browser
  context, headless Chromium (the harness Playwright, Microsoft.Playwright 1.60.0), default
  viewport 1280×720, JavaScript enabled (as in the corpus).
- Readiness wait: identical to the corpus, `GotoAsync` (timeout 90 s) then
  `WaitForLoadStateAsync(NetworkIdle)` (timeout 90 s).
- Shims (determinism), part of this criterion:
  - Clock: `BrowserContext.Clock.SetFixedTimeAsync(<timestamp of the May WARC record, UTC>)`
    before navigation (`Date.now()` / `new Date()` fixed; timers keep running).
  - `Math.random`: replaced by an init script with a mulberry32 generator, seed 42 (verbatim
    below). The init script adds nothing to the DOM.
  - The shims must be byte-neutral on the corpus: the observation of every corpus page (24 pages,
    all six cells of §6) must be byte-identical with and without the shims. If not, the work
    stops before any site is processed.
- Walker: the unchanged harness pipeline (`Observation.BuildObservationAsync`, DOM walk +
  encoders) builds all six cells of §6 without an exception.
- Determinism: two consecutive dumps (separate processes, separate browser launches) give an
  identical observation sha256 for **all six cells**. A site that is not deterministic even with
  the shims is excluded and counted with its reason; there are no per-site fixes.

**(в) Targets.** The site has at least 5 eligible targets (§3).

**(г) Prompt size.** The prompt of the largest cell (system prompt + user prompt with the task
and the observation, o200k_base via `shared/tokenizer`, the count used by
`p1/batch/RevisionBatchRunner.cs`: `CountTokens(SystemPrompt) + CountTokens(BuildUserPrompt(obs,
task))`), maximised over the six cells and the site's selected tasks, is **≤ 128,000 tokens**.
Rationale: 128k is the standard context window of mainstream models; the threshold is fixed here,
before any page is measured. Excluded sites are counted and reported with their prompt size. If
fewer than 5 eligible sites remain after this exclusion, the work stops and the author decides;
the threshold is not changed.

**Cost cap.** If, after the dry run, the estimated cost of the eligible sites exceeds the cap,
the pilot takes the first N eligible sites by Tranco rank. N is fixed from the cap before any
model call.

## 3. Eligible target

Computed on the live DOM of the May page after loading (§2 (б), shims on), by the fixed function
`rp_candidates.js` (verbatim below). Only the light DOM of the main document is searched
(`document.querySelectorAll('*')`): elements inside shadow roots and iframes are not candidates
(they have no document XPath; this is a limitation).

An element is an eligible target if all of the following hold:

1. Kind: `a[href]`, `button`, `input` whose `type` (as the browser resolves it) is not `hidden`,
   `select`, `textarea`, or an element whose `role` attribute is exactly one of `button`, `link`,
   `tab`, `menuitem`, `checkbox` (the CSS `[role=…]` exact-value match).
2. DOM-only visibility (no CSS; this is a limitation): the element is in the HTML namespace and has
   no ancestor outside it (no svg/math ancestor); it has no ancestor `script`, `template`,
   `noscript` or `head`; it has no `hidden` attribute; neither the element itself nor any ancestor
   has `aria-hidden="true"` (exact value).
3. Accessible name: the first non-empty value of (i) the normalized visible text, i.e. the
   descendant text nodes, skipping `script`/`style`/`template`/`noscript` subtrees and subtrees
   with `hidden` or `aria-hidden="true"`; (ii) `aria-label`; (iii) `title`; (iv) the `alt` of the
   first descendant `img` with a non-empty `alt`; (v) `placeholder`; (vi) the `value` attribute.
   Normalization: JavaScript `\s+` collapsed to one space, trimmed. Length 1–80 Unicode code
   points.
4. The name is **unique** among the elements meeting 1–3 on the page (comparison: Python
   `str.casefold()` of the normalized name).

## 4. Target selection

From the site's eligible targets, take the 10 with the smallest
`SHA-256("<domain>|<xpath>")` (UTF-8, lowercase hex, compared as strings; `<domain>` as in the
Tranco list, `<xpath>` the absolute XPath in the May DOM). If there are fewer than 10, take all.

The XPath function is `xpathOf` in `rp_candidates.js`: `/html[1]/body[1]/…`, each step the
element's `localName` and its 1-based index among preceding element siblings with the same
`localName` in the HTML namespace. The function also checks that `document.evaluate` of the
XPath returns the same element; any failure is reported (none is expected).

## 5. Task (template, no manual writing)

`Click the <role> labelled '<name>'`; for a field, `Fill the <role> labelled '<name>'`.

Role, fixed table:

| element | role |
|---|---|
| any element with a non-empty `role` attribute | its first ASCII-whitespace token, lowercased |
| `a[href]` | link |
| `button` | button |
| `select` | listbox if `multiple` or `size` > 1, else combobox |
| `textarea` | textbox |
| `input` type button, submit, reset, image, file, color | button |
| `input` type checkbox | checkbox |
| `input` type radio | radio |
| `input` type range | slider |
| `input` type number | spinbutton |
| `input` type search | searchbox |
| any other `input` type | textbox |

"Fill" is used for the roles textbox, searchbox, spinbutton, combobox and listbox. "Click" is used
for every other role. `<name>` is the accessible name of §3, inserted as is.

Difference from the corpus, a limitation: corpus tasks are hand-written intents of the form
"Find the …" (`truth.json`, `intent`). The pilot uses this template instead. The template is not
changed after the selection.

## 6. Volatile values, cells

- The volatile values are determined automatically by the frozen Oracle: every class token
  (split on ASCII whitespace and on a single space, as the bundle code does) and every id value
  of the walked May DOM (`Observation.WalkDomAsync`) is classified by the CLI of §2 (а)
  (`IsVolatileClass` / `IsVolatileId`). The flagged values are the page's `volatile_classes` /
  `volatile_ids`.
- **B_noVolatile in this pilot is the existing `B_noVolatileConsistent` (NVC) bundle path**: it
  strips every class token and id that `Oracle.LocatorUsesVolatileSignal` flags, given these lists.
- Sensitivity, class only: the existing `B_full_minus_volClass` bundle path, with the same lists.
  The id branch is not removed in this cell because it failed validation in cc_volatility
  (`../cc_volatility/analysis_plan.md`, commit `d8f1bc9`; result in
  `../cc_volatility/volatility_analysis.md`).
- Six cells: {B_full, B_noVolatile (NVC), class-only} × {F1, F3}, built by the unchanged
  `Observation.BuildObservationAsync`.

## 7. Target stratum

- `signal_attrs` of a target = the attributes from the fixed list
  **{id, data-testid, aria-label, name, placeholder, href}** that the target actually has in the
  May DOM, with a non-empty value, whose value is not flagged as volatile by the frozen Oracle.
  Of these attributes, the Oracle has a value predicate only for `id`. An id flagged by
  `IsVolatileId` (e.g. `id="root"`) does not count. This is the same test that
  `Oracle.ComputeStableSignalPresence` applies with the §6 lists.
- Stratum: **"has stable signal"** if `signal_attrs` is non-empty, otherwise **"no stable signal"**.
- The list is fixed and does not change after target selection. `signal_attrs` is also the
  target's `signal_attrs` when P5 is computed (`pilot_analysis_plan.md`).

## 8. Oracle element and marker

- The oracle element is the target identified by its XPath in the May DOM.
- To evaluate locators, the marker `data-oracle-id="t_01"`… `"t_10"` is set on the targets by
  XPath after loading. The harness strips every `data-oracle-*` attribute before encoding
  (`AttributeBundles.StripOracleAnchors`).
- Check: the marker must not appear in any observation. The observation sha256 with markers must
  equal the sha256 without markers, and a search for `data-oracle` in every observation must
  return nothing.

## Limitations (declared in advance)

- External CSS, images, fonts and scripts are not loaded. The walker's `text` field is the
  rendering-dependent `innerText`, so the text can differ from the live site. Visibility in §3 is
  DOM-only.
- The pages are server HTML plus inline scripts run offline. They are not the hydrated live
  pages.
- Only the light DOM of the main document is searched (no shadow roots, no iframes).
- The task template differs from the corpus intent style (§5).

## Verbatim: `rp_candidates.js` (evaluated with `page.EvaluateAsync`)

```js
() => {
  const HTML_NS = 'http://www.w3.org/1999/xhtml';
  const ROLE_ATTR = new Set(['button', 'link', 'tab', 'menuitem', 'checkbox']);
  const EXCL_ANCESTOR = new Set(['script', 'template', 'noscript', 'head']);
  const SKIP_TEXT = new Set(['script', 'style', 'template', 'noscript']);
  const norm = s => (s == null ? '' : String(s)).replace(/\s+/g, ' ').trim();
  const isAriaHidden = n => n.getAttribute('aria-hidden') === 'true';

  // Rule 3, element kinds.
  const isKind = el => {
    const t = el.localName;
    if (t === 'input') return el.type !== 'hidden';
    if (t === 'a' && el.hasAttribute('href')) return true;
    if (t === 'button' || t === 'select' || t === 'textarea') return true;
    return ROLE_ATTR.has(el.getAttribute('role'));
  };

  // Rule 3, DOM-only visibility (no CSS). Returns the exclusion reason or null.
  const exclusion = el => {
    if (el.namespaceURI !== HTML_NS) return 'non_html_namespace';
    if (el.hasAttribute('hidden')) return 'hidden_attr';
    for (let n = el; n; n = n.parentElement) {
      if (n !== el && EXCL_ANCESTOR.has(n.localName)) return 'in_' + n.localName;
      if (n.namespaceURI !== HTML_NS) return 'non_html_ancestor';
      if (isAriaHidden(n)) return 'aria_hidden';
    }
    return null;
  };

  // Rule 3, visible text: descendant text nodes, skipping script/style/template/noscript
  // subtrees and subtrees with the hidden attribute or aria-hidden="true".
  const visibleText = el => {
    let out = '';
    const walk = n => {
      for (let c = n.firstChild; c; c = c.nextSibling) {
        if (c.nodeType === 3) { out += c.data; continue; }
        if (c.nodeType !== 1) continue;
        if (SKIP_TEXT.has(c.localName) || c.hasAttribute('hidden') || isAriaHidden(c)) continue;
        walk(c);
      }
    };
    walk(el);
    return norm(out);
  };

  // Rule 3, accessible name: first non-empty source in this order.
  const accName = el => {
    const txt = visibleText(el);
    if (txt) return [txt, 'text'];
    for (const a of ['aria-label', 'title']) {
      const v = norm(el.getAttribute(a));
      if (v) return [v, a];
    }
    for (const img of el.querySelectorAll('img')) {
      const v = norm(img.getAttribute('alt'));
      if (v) return [v, 'img_alt'];
    }
    for (const a of ['placeholder', 'value']) {
      const v = norm(el.getAttribute(a));
      if (v) return [v, a];
    }
    return ['', 'none'];
  };

  // Rule 4, absolute XPath: /html[1]/body[1]/..., each step = localName + 1-based index
  // among preceding element siblings with the same localName in the HTML namespace.
  const xpathOf = el => {
    const steps = [];
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      let i = 1;
      for (let s = n.previousElementSibling; s; s = s.previousElementSibling) {
        if (s.localName === n.localName && s.namespaceURI === HTML_NS) i++;
      }
      steps.unshift(n.localName + '[' + i + ']');
    }
    return '/' + steps.join('/');
  };

  const all = document.querySelectorAll('*');
  const excluded = {};
  const candidates = [];
  for (const el of all) {
    if (!isKind(el)) continue;
    const why = exclusion(el);
    if (why) { excluded[why] = (excluded[why] || 0) + 1; continue; }
    const [name, nameSource] = accName(el);
    const xpath = xpathOf(el);
    const back = document.evaluate(xpath, document, null,
      XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
    const attrs = {};
    for (const a of el.attributes) attrs[a.name] = a.value;
    candidates.push({
      xpath, xpathRoundTrip: back === el,
      tag: el.localName,
      type: el.localName === 'input' ? el.type : null,
      roleAttr: el.getAttribute('role'),
      multiple: el.localName === 'select' ? el.multiple : null,
      size: el.localName === 'select' ? el.size : null,
      name, nameSource, nameLength: [...name].length,
      attrs,
    });
  }
  return { elementCount: all.length, excluded, candidates };
}
```

## Verbatim: `rp_shim_random.js` (`BrowserContext.AddInitScriptAsync`)

```js
(() => {
  let s = 42 >>> 0;
  Math.random = function () {
    s = (s + 0x6D2B79F5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
})();
```

## Addendum (2026-10-13): observation protocol, fresh load per cell

Author's decision, committed before any model call.

- **Observation protocol.** Each cell is observed on a fresh load of the page, with the shims of §2 (б), by the
  same function the paid run uses (`PilotExecutor`, p1/batch, commit `99204d6`): fresh offline load → every
  target marker of the site set by XPath (§8) → the cell's observation as the first walk after that load.
- **Determinism, §2 (б).** Five independent full dumps must give an identical observation sha256 for all cells.
- **Reason.** A mismatch between the dump and the paid run, found during preparation, before any model call. The
  dump loaded each page once and walked the six cells one after another; the paid run loads the page afresh for
  every cell. On mobile.de five cells of the dump saw the DOM after a page timer had changed it.
- **Scope.** Rule §2 (б) is applied anew to every candidate that passed (а), (в) and (г), including the sites
  excluded so far under (б) (wikipedia.org, kaspersky.com).

## Addendum (2026-10-13): criterion (г) under the new observation protocol

Author's decision, committed before the measurement and before any model call.

- The change of the observation protocol (`1a16fa1`) affects every criterion measured on the observation. Therefore
  (г) (largest-cell prompt ≤ 128,000 tokens) is re-measured under the new protocol (fresh load per cell,
  `RealPilotOffline.ObserveCellAsync`) for every candidate excluded so far under (г): publicnode.com,
  tradingview.com, zendesk.com. The threshold does not change.
- A site that passes (г) under the new protocol is then subject to (б) (five identical dumps) and (в), and enters
  under the unchanged rules.
