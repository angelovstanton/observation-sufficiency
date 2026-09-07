"""
test_signal_completeness.py — permanent guard against truth.json under-listing.

The bug class (diagnosed 2026-07-22): condition 5 (stable_signal_present_in_bundle)
is computed by Oracle.ComputeStableSignalPresence by iterating over the target's
`signal_attrs` from truth.json. If truth under-lists a stable signal the model
actually used, condition 5 goes FALSE while all four output predicates are TRUE —
an unearned failure (a false negative). The original occurrence: 123 records
(107 via `id`, 16 via a uniquely-resolving `href`) across 20 (target, signal)
pairs, where truth.json failed to enumerate a signal the model used — concentrated
in B_identityCore (58) and B_noSemantic (65).

This guard makes silent reintroduction impossible. It flags any non-NONE record
that is a false negative FIXABLE by completing signal_attrs — i.e.:

    recorded all-4-output-predicates TRUE
    AND recorded stable_signal_present_in_bundle FALSE
    AND there exists a recognized, non-volatile, identifying signal that
        (a) is present on the oracle element,
        (b) is a member of that record's bundle,
        (c) [href only] resolves uniquely on the page,
        (d) is NOT already in the target's signal_attrs.

Creditor set = {id, data-testid, name, aria-label, placeholder, href-if-unique}.
`type` and `role` are deliberately EXCLUDED: they are structural / non-identifying
(e.g. input[type="search"] is unique only incidentally); crediting them would
reward brittle resolution and contradict the stability thesis.

The check mirrors ComputeStableSignalPresence (Oracle.cs) + per-bundle membership
(Observation.cs) + volatile_ids filtering exactly, so a violation here means the
same thing the harness would score.

COVERAGE LIMITATION (and how it is made safe).
The oracle element's attributes are read from the STATIC HTML source. Eight
targets have their `data-oracle-id` assigned dynamically in JavaScript, so the
element is absent from the source and the parser cannot see its attributes
(page_08's data-testid cards are the only non-NONE cases). Rather than resolve
those from the rendered DOM — which would make this fast static guard depend on a
Playwright browser + the testbed server, as `--replay` does — the guard PINS that
set (KNOWN_DYNAMIC_ANCHORS) and enforces two invariants so an unanalysable target
is never invisible:
  1. test_oracle_anchor_visibility — the set of targets the parser cannot resolve
     must EQUAL the pinned set. A new dynamic anchor, or a parser regression that
     drops a previously-visible target, changes the set and fails the test.
  2. test_no_unanalysable_candidate — no pinned/dynamic target may carry a
     candidate false-negative record (all-4-true ∧ cond5-false ∧ non-NONE). If one
     ever does, it must be verified against the rendered DOM by hand; the guard
     fails loudly rather than skip it.

Run:      pytest experiments/analysis/test_signal_completeness.py -v
Inspect:  python  experiments/analysis/test_signal_completeness.py      (prints coverage + violations)
"""

import glob
import json
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[2]
PAGES = REPO / "shared" / "testbed" / "pages"
RUNS = REPO / "experiments" / "runs"

# Targets whose data-oracle-id is assigned dynamically in JS, so the oracle element
# is absent from static HTML and its attributes cannot be parsed here. PINNED so the
# unanalysable set is visible: test_oracle_anchor_visibility fails if it ever drifts.
# 5 are NONE targets (never false-negative candidates); the 3 non-NONE ones are
# page_08's data-testid cards. Closing this fully would require rendered-DOM
# resolution (Playwright + testbed server) — deliberately out of scope for a fast
# static guard; the two invariants below keep it safe instead.
KNOWN_DYNAMIC_ANCHORS = frozenset({
    ("page_03", "t_10"), ("page_06", "t_07"), ("page_08", "t_05"),
    ("page_08", "t_06"), ("page_08", "t_07"), ("page_08", "t_08"),
    ("page_09", "t_04"), ("page_23", "t_03"),
})

# ── bundle attribute-sets — mirror shared/harness/Observation.cs ──────────────
_identity = {"id", "data-testid"}
_semantic = {"text", "aria-label", "placeholder", "name"}
_accessibility = {
    "role", "aria-expanded", "aria-selected", "aria-checked", "aria-disabled",
    "aria-required", "aria-controls", "aria-haspopup", "aria-level", "tabindex",
    "aria-hidden", "aria-live", "aria-labelledby", "aria-describedby",
}
_structural = {"class", "src"}
_state = {"disabled", "checked", "selected", "value"}
_uncategorised = {"href", "type", "for", "alt", "title"}
_FULL = _identity | _semantic | _accessibility | _structural | _state | _uncategorised

_BUNDLES = {
    "B_full": _FULL,
    "B_noState": _FULL - _state,
    "B_noSemantic": _FULL - _semantic,
    "B_identityCore": {"id", "data-testid"},
    "B_minimalCore": set(),
}


def _bundle_set(bundle):
    # GroundingRunner uses AttributeBundles.ResolveBundleSetForSignalCheck to pass BundleFull for these two.
    if bundle in ("B_noVolatile", "B_playwrightMCP"):
        return _FULL
    return _BUNDLES[bundle]


# Recognized IDENTIFYING signals eligible to credit condition 5. type/role excluded.
_CREDITORS = {"id", "data-testid", "name", "aria-label", "placeholder", "href"}


def _load_truth(pages_dir):
    truth = {}
    for tf in sorted(glob.glob(str(pages_dir / "page_*.truth.json"))):
        d = json.load(open(tf, encoding="utf-8"))
        pid = d["page_id"]
        vl = d.get("volatility_labels", {})
        truth[pid] = {
            "vids": set(vl.get("volatile_ids", [])),
            "targets": {t["id"]: set(t.get("signal_attrs", [])) for t in d["targets"]},
        }
    return truth


# Match the oracle anchor and element attributes in all three value forms:
# double-quoted, single-quoted, and UNQUOTED (id=foo). Shadow DOM is embedded on
# some pages as JS string-array literals whose HTML attributes use single quotes
# (e.g. page_13: id='date-preset'); a double-quote-only parser silently captured no
# attributes for those and under-counted once already. The unquoted form is not
# present in the current testbed but is accepted defensively. Quoted alternatives are
# tried first, so a URL query string inside a quoted value (href="/x?fmt=csv") is
# consumed as one value and its "fmt=csv" is never mis-read as an attribute.
_ANCHOR_RE = re.compile(r"""data-oracle-id\s*=\s*(?:"(t_\d+)"|'(t_\d+)'|(t_\d+))""")
_ATTR_RE = re.compile(
    r"""([:a-zA-Z_][-:a-zA-Z0-9_]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))"""
)
_HREF_RE_TMPL = r"""href\s*=\s*(?:"{v}"|'{v}'|{v}(?=[\s/>]))"""


def _attr_value(m):
    """Pick whichever of the double/single/unquoted value groups matched."""
    return next((g for g in (m.group(2), m.group(3), m.group(4)) if g is not None), "")


def _load_elem_attrs(pages_dir):
    """
    Oracle element's HTML attributes, keyed by (page, target). Quote-agnostic.
    A key is present for every anchor FOUND in static HTML (even with no attributes);
    a target absent from the returned dict is one the parser could not resolve.
    """
    elattrs, hrefcount = {}, {}
    for hf in sorted(glob.glob(str(pages_dir / "page_*.html"))):
        pid = re.search(r"page_\d+", hf).group(0)
        html = open(hf, encoding="utf-8").read()
        for m in _ANCHOR_RE.finditer(html):
            tid = m.group(1) or m.group(2) or m.group(3)
            i = m.start()
            lt = html.rfind("<", 0, i)
            gt = html.find(">", i)
            attrs = {}
            for am in _ATTR_RE.finditer(html[lt + 1:gt]):
                attrs[am.group(1).lower()] = _attr_value(am)
            elattrs[(pid, tid)] = attrs
            if attrs.get("href"):
                v = attrs["href"]
                pat = _HREF_RE_TMPL.format(v=re.escape(v))
                hrefcount[(pid, tid)] = len(re.findall(pat, html))
    return elattrs, hrefcount


def _iter_candidates(runs_dir):
    """Yield (pid, tid, record) for every corpus record that is a candidate:
    all four output predicates TRUE and condition 5 FALSE."""
    for f in sorted(glob.glob(str(runs_dir / "matrix_page_*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if (
                r["success"] is False
                and r["predicate_unique_match"]
                and r["predicate_matches_oracle"]
                and r["predicate_non_volatile"]
                and r["predicate_non_positional"]
                and r["stable_signal_present_in_bundle"] is False
            ):
                pid = re.search(r"page_\d+", r["page"]).group(0)
                yield pid, r["task_id"], r


def unparseable_targets(pages_dir=PAGES):
    """Targets whose oracle anchor is not present in static HTML (JS-assigned)."""
    truth = _load_truth(pages_dir)
    elattrs, _ = _load_elem_attrs(pages_dir)
    all_targets = {(p, t) for p in truth for t in truth[p]["targets"]}
    return all_targets - set(elattrs)


def unanalysable_candidates(pages_dir=PAGES, runs_dir=RUNS):
    """Non-NONE targets that carry a candidate false-negative record but whose
    anchor the parser cannot resolve — so completeness cannot be checked here."""
    truth = _load_truth(pages_dir)
    unpars = unparseable_targets(pages_dir)
    out = set()
    for pid, tid, _r in _iter_candidates(runs_dir):
        if (pid, tid) in unpars and len(truth[pid]["targets"].get(tid, set())) > 0:
            out.add((pid, tid))
    return out


def find_violations(pages_dir=PAGES, runs_dir=RUNS):
    """Return the list of false-negative records fixable by completing signal_attrs."""
    truth = _load_truth(pages_dir)
    elattrs, hrefcount = _load_elem_attrs(pages_dir)
    violations = []
    for pid, tid, r in _iter_candidates(runs_dir):
        listed = truth[pid]["targets"].get(tid, set())
        if len(listed) == 0:
            continue  # NONE target — lacked by design (§36), not a false negative
        E = elattrs.get((pid, tid), {})  # {} for JS-assigned anchors — see coverage tests
        vids = truth[pid]["vids"]
        bs = _bundle_set(r["bundle"])
        for a in _CREDITORS:
            if a in listed or a not in bs:
                continue
            v = E.get(a)
            if not v:
                continue
            if a == "id" and v in vids:
                continue
            if a == "href" and hrefcount.get((pid, tid), 0) != 1:
                continue  # href must resolve uniquely to be a required signal
            violations.append({
                "page": pid, "task": tid, "bundle": r["bundle"],
                "encoding": r["encoding"], "signal_attrs": sorted(listed),
                "unlisted_creditor": a, "value": v,
            })
            break
    return violations


# ── tests ─────────────────────────────────────────────────────────────────────

def test_oracle_anchor_visibility():
    """
    Every target must be either statically parseable or a KNOWN dynamic anchor.
    Pinning the unanalysable set makes it visible: a new JS-assigned anchor, or a
    parser regression that drops a previously-visible target, trips this before it
    can hide from the completeness check.
    """
    unpars = unparseable_targets()
    assert unpars == KNOWN_DYNAMIC_ANCHORS, (
        "oracle-anchor visibility drift — the set of statically-unresolvable targets "
        f"changed. Newly invisible: {sorted(unpars - KNOWN_DYNAMIC_ANCHORS)}; "
        f"newly visible: {sorted(KNOWN_DYNAMIC_ANCHORS - unpars)}. Investigate and "
        "update KNOWN_DYNAMIC_ANCHORS deliberately — do not let a target skip the "
        "completeness check unnoticed."
    )


def test_no_unanalysable_candidate():
    """
    A JS-assigned (unparseable) target must never carry a candidate false-negative
    record. If one does, its signal_attrs completeness cannot be verified from static
    HTML and must be checked against the rendered DOM by hand — fail loudly, do not
    silently skip.
    """
    bad = unanalysable_candidates()
    assert not bad, (
        f"{sorted(bad)} have all-4-predicate-true + cond5-false records but their "
        "oracle anchor is assigned dynamically in JS (absent from static HTML), so "
        "signal_attrs completeness cannot be verified here. Resolve these against the "
        "rendered DOM (Playwright + testbed server) and re-check by hand."
    )


def test_no_underlisted_signal_false_negatives():
    """
    Zero non-NONE records may be a false negative fixable by completing signal_attrs.
    A failure here means truth.json under-lists a stable signal the model used — see
    the module docstring above.
    """
    v = find_violations()
    assert v == [], (
        f"{len(v)} under-listed-signal false negatives (truth.json incomplete). "
        f"First 10: {v[:10]}"
    )


if __name__ == "__main__":
    unpars = unparseable_targets()
    print(f"statically-unparseable targets: {len(unpars)} "
          f"(pinned: {len(KNOWN_DYNAMIC_ANCHORS)}; match: {unpars == KNOWN_DYNAMIC_ANCHORS})")
    for t in sorted(unpars):
        print(f"   {t[0]} {t[1]}")
    ua = unanalysable_candidates()
    print(f"unanalysable candidate false negatives (must be 0): {len(ua)} {sorted(ua)}")
    v = find_violations()
    print(f"\nunder-listed-signal false negatives: {len(v)}")
    by_attr, by_bundle, by_target = {}, {}, {}
    for x in v:
        by_attr[x["unlisted_creditor"]] = by_attr.get(x["unlisted_creditor"], 0) + 1
        by_bundle[x["bundle"]] = by_bundle.get(x["bundle"], 0) + 1
        by_target.setdefault((x["page"], x["task"], x["unlisted_creditor"]), 0)
        by_target[(x["page"], x["task"], x["unlisted_creditor"])] += 1
    print("by creditor attr:", by_attr)
    print("by bundle       :", by_bundle)
    print("distinct targets:", len(by_target))
    for (p, t, a), n in sorted(by_target.items()):
        print(f"   {p} {t:5s} via {a:11s} x{n}")
