# shared/testbed

Static HTML pages that serve as the controlled System Under Test (SUT) for this study.

No real build frameworks — control over which attributes are stable vs volatile
requires hand-authored HTML.

## Page tiers (§9)

| Tier | Shadow DOM | Framework fingerprints | Responsive duplication |
|------|-----------|----------------------|----------------------|
| S0   | none      | none                 | none                 |
| S1   | shallow   | 1–2 variants         | some                 |
| S2   | deep ≥2   | 2–3 variants         | full                 |

All three tiers are implemented. The corpus is 24 pages (`pages/page_01.html` …
`page_24.html`), each paired with a `page_NN.truth.json` declaring its targets,
volatile signals, and fingerprint variant. Shadow DOM is in active use — `page_20`
carries an S2 host, and double-shadow nesting is a reused pattern across the corpus.

## Serving

```
python -m http.server 8000 --directory shared/testbed
```

Set `BAR_TESTBED_BASE_URL=http://localhost:8000` in `.env` (it is the default).
