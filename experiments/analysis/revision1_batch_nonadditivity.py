"""
Exploratory (not in batch_analysis_plan.md): why the F2 ablations are not additive.
B_full_minus_volClass×F1 gains more over B_full×F1 than B_noVolatile×F1 does, although
B_noVolatile removes volatile ids and classes.  Zero LLM, zero network.

1. Event level: gpt-4.1 F1 rep-1 cells B_full, B_full_minus_volClass and B_noVolatile paired
   on (page, task_id); P5 crosstab and every event on which minus_volClass and B_noVolatile
   disagree, with the volatile tokens of each locator (volatile_hits) and their presence in
   each observation.
2. Observation level: is B_noVolatile = B_full − volClass − volId?  The F1 dumps
   (batch_observations/) are composed per element and compared with B_noVolatile and
   B_noVolatileConsistent (key order included), and byte for byte.

Output: experiments/results/revision1/batch_exploratory_nonadditivity.md
"""
from __future__ import annotations

import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import collections   # noqa: E402
import hashlib       # noqa: E402
import json          # noqa: E402
import re            # noqa: E402

import pandas as pd  # noqa: E402

from load import load_dataframe                                                   # noqa: E402
from revision1_diagnostics import REPO, OUT_DIR, TRUTH_DIR, protected_state, md_table, mcnemar, fmt_p  # noqa: E402
from revision1_volatile_nv import volatile_hits                                   # noqa: E402

BATCH_DIR = OUT_DIR / "batch_runs"
DUMP = OUT_DIR / "batch_observations"
PLAN_JSON = OUT_DIR / "batch_plan.json"
PAGES_DIR = REPO / "shared" / "testbed" / "pages"
OUT_MD = OUT_DIR / "batch_exploratory_nonadditivity.md"
PAGES = [f"page_{n:02d}" for n in range(1, 25)]
NON_ATTRIBUTE_SIGNALS = {"text"}
NON_ATTR_KEYS = ("tag", "text", "is_shadow")   # F1 element keys that are not DOM attributes
MVC = "B_full_minus_volClass"
COLS = ["success", "failure_mode", "locator_raw", "predicate_unique_match", "predicate_matches_oracle",
        "predicate_non_volatile", "predicate_non_positional", "stable_signal_present_in_bundle"]
SHORT = {"observation_lacked_stable_signal": "lacked", "model_grabbed_brittle_signal": "grabbed",
         "output_format_unreachable": "unreachable"}


def page_of(s):
    return re.search(r"page_\d{2}", s).group(0)


def load_cells():
    mx = load_dataframe(REPO)
    mx = mx[mx["encoding"] == "F1"]
    cells = {}
    for b in ("B_full", "B_noVolatile"):
        c = mx[mx["bundle"] == b].set_index(["page", "task_id"])[COLS]
        assert len(c) == 240
        cells[b] = c
    recs = [json.loads(l) for f in sorted(BATCH_DIR.glob("batch_1_*.jsonl"))
            for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    called = pd.DataFrame([r for r in recs if r["bundle"] == MVC])
    called["page"] = called["page"].map(page_of)
    called = called.set_index(["page", "task_id"])[COLS]
    plan = json.loads(PLAN_JSON.read_text(encoding="utf-8"))
    reused_pages = sorted(r["page"] for r in plan["reused_block1"] if r["bundle"] == MVC)
    reused = cells["B_full"][cells["B_full"].index.get_level_values("page").isin(reused_pages)]
    cells[MVC] = pd.concat([called, reused]).sort_index()
    assert len(called) == 200 and len(cells[MVC]) == 240 and cells[MVC].index.is_unique
    origin = {k: ("reused (= B_full×F1 record)" if k[0] in reused_pages else "batch") for k in cells[MVC].index}
    return cells, reused_pages, origin


def load_truth():
    t = {}
    for tf in sorted(TRUTH_DIR.glob("*.truth.json")):
        tj = json.loads(tf.read_text(encoding="utf-8"))
        t[tj["page_id"]] = tj
    return t


def oracle_ids(page: str, task_id: str) -> list[str]:
    """id attribute values of every element carrying data-oracle-id=task_id in the page source
    (raw-text match, so markup inside template / script strings is included)."""
    html = (PAGES_DIR / f"{page}.html").read_text(encoding="utf-8")
    tag_re = re.compile(r"<[a-zA-Z][^<>]*data-oracle-id=\\?[\"']" + re.escape(task_id) + r"\\?[\"'][^<>]*>")
    ids = []
    for m in tag_re.finditer(html):
        idm = re.search(r"(?<![\w-])id=\\?[\"']([^\"'\\]+)", m.group(0))
        ids.append(idm.group(1) if idm else "")
    return ids


def observation(page, bundle):
    return json.loads((DUMP / f"{page}__{bundle}__F1.txt").read_text(encoding="utf-8"))


def field_tokens(elements):
    cls, ids = set(), set()
    for e in elements:
        cls.update(e.get("class", "").split())
        if e.get("id"):
            ids.add(e["id"])
    return cls, ids


def flags(r):
    return "".join(ch if r[c] else "·" for ch, c in (("U", "predicate_unique_match"), ("O", "predicate_matches_oracle"),
                                                     ("V", "predicate_non_volatile"), ("P", "predicate_non_positional"),
                                                     ("5", "stable_signal_present_in_bundle")))


def cell_md(s: str) -> str:
    return "`" + str(s).replace("|", "\\|").replace("`", "'") + "`"


def has_content(e: dict) -> bool:
    """ObservationEncoders.HasContent: an element is serialised iff it has an attribute or non-blank text.
    `tag`, `text` and the shadow marker `is_shadow` (IsInShadowRoot) are not attributes."""
    return any(k not in NON_ATTR_KEYS for k in e) or bool(str(e.get("text", "")).strip())


def align(full: list, other: list, own: tuple) -> list:
    """Map each B_full element to its counterpart in `other` (None if dropped by HasContent).
    `other` is an ordered subsequence of `full` that differs only in the keys in `own`."""
    strip = lambda e: {k: v for k, v in e.items() if k not in own}   # noqa: E731
    out, j = [], 0
    for e in full:
        if j < len(other) and strip(other[j]) == strip(e):
            out.append(other[j])
            j += 1
        else:
            assert not any(k not in (*NON_ATTR_KEYS, *own) for k in e) and not str(e.get("text", "")).strip(),                 "dropped element had content outside the stripped keys"
            out.append(None)
    assert j == len(other), "alignment did not consume every element"
    return out


def ordered(elements: list) -> list:
    """Element list with key order significant (plain dict equality ignores order)."""
    return [list(e.items()) for e in elements]


def compose_check():
    """B_full with class from minus_volClass and id from minus_volId, per element, vs B_noVolatile."""
    rows, diffs = [], collections.Counter()
    examples = collections.defaultdict(list)
    for p in PAGES:
        bf, mvc, mvi = observation(p, "B_full"), observation(p, MVC), observation(p, "B_full_minus_volId")
        nv, nvc = observation(p, "B_noVolatile"), observation(p, "B_noVolatileConsistent")
        a_mvc = align(bf, mvc, ("class",))      # asserts: minus_volClass differs from B_full only in class
        a_mvi = align(bf, mvi, ("id",))         # asserts: minus_volId differs from B_full only in id
        a_nv = align(bf, nv, ("class", "id"))   # asserts: B_noVolatile differs from B_full only in class / id
        composed_full = []
        for e_bf, e_c, e_i in zip(bf, a_mvc, a_mvi):
            c = {}
            for k, v in e_bf.items():
                src = e_c if k == "class" else e_i if k == "id" else e_bf
                if src is not None and k in src:
                    c[k] = src[k]
            composed_full.append(c if has_content(c) else None)
        composed = [c for c in composed_full if c is not None]
        page_diff = collections.Counter()
        for e_comp, e_nv in zip(composed_full, a_nv):
            if e_comp == e_nv:
                continue
            if (e_comp is None) != (e_nv is None):
                page_diff["element kept by B_noVolatile, dropped from the composition (no content left)"
                          if e_comp is None else "element dropped by B_noVolatile, kept in the composition"] += 1
            e_comp, e_nv = e_comp or {}, e_nv or {}
            for k in sorted(set(e_comp) | set(e_nv)):
                if k in ("tag", "is_shadow") and (not e_comp or not e_nv):
                    continue
                if e_comp.get(k) == e_nv.get(k):
                    continue
                if k == "class":
                    kept = set(e_nv.get(k, "").split()) - set(e_comp.get(k, "").split())
                    extra = set(e_comp.get(k, "").split()) - set(e_nv.get(k, "").split())
                    page_diff["class tokens kept by B_noVolatile, stripped by minus_volClass"] += len(kept)
                    page_diff["class tokens stripped by B_noVolatile, kept by minus_volClass"] += len(extra)
                    for t in sorted(kept):
                        if len(examples[p]) < 6 and t not in examples[p]:
                            examples[p].append(t)
                elif k == "id":
                    key = ("id kept by B_noVolatile, stripped by minus_volId" if k in e_nv
                           else "id stripped by B_noVolatile, kept by minus_volId")
                    page_diff[key] += 1
                    if k in e_nv and len(examples[p]) < 6:
                        examples[p].append("#" + e_nv[k])
                else:
                    page_diff[f"other key differs: {k}"] += 1
            page_diff["elements differing"] += 1
        diffs.update(page_diff)
        nv_bytes = (DUMP / f"{p}__B_noVolatile__F1.txt").read_bytes()
        nvc_bytes = (DUMP / f"{p}__B_noVolatileConsistent__F1.txt").read_bytes()
        rows.append({"page": p, "elements": len(bf), "elements_nv": len(nv), "elements_composed": len(composed),
                     "composed_eq_nv": ordered(composed) == ordered(nv),
                     "composed_eq_nvc": ordered(composed) == ordered(nvc),
                     "nv_bytes_eq_nvc": nv_bytes == nvc_bytes,
                     "elements_differing": page_diff["elements differing"],
                     "kept_class": page_diff["class tokens kept by B_noVolatile, stripped by minus_volClass"],
                     "kept_id": page_diff["id kept by B_noVolatile, stripped by minus_volId"],
                     "other": sum(v for k, v in page_diff.items() if k.startswith("other key")),
                     "dropped_comp": page_diff["element kept by B_noVolatile, dropped from the composition (no content left)"],
                     "reverse": page_diff["class tokens stripped by B_noVolatile, kept by minus_volClass"]
                                + page_diff["id stripped by B_noVolatile, kept by minus_volId"],
                     "examples": examples[p]})
    return rows, diffs


def main():
    print("[guard] protected files before")
    before = protected_state()
    cells, reused_pages, origin = load_cells()
    truth = load_truth()
    bf, mvc, nv = cells["B_full"], cells[MVC], cells["B_noVolatile"]
    idx = bf.index
    assert idx.equals(mvc.index) and idx.equals(nv.index)

    # crosstab
    combo = collections.Counter((bool(bf.loc[k, "success"]), bool(mvc.loc[k, "success"]), bool(nv.loc[k, "success"]))
                                for k in idx)
    yn = lambda b: "✓" if b else "✗"   # noqa: E731
    cross = [[yn(a), yn(b), yn(c), combo.get((a, b, c), 0)]
             for a in (True, False) for b in (True, False) for c in (True, False)]
    m_nv_mvc = mcnemar(nv["success"].to_numpy(bool), mvc["success"].to_numpy(bool))
    rates = {b: cells[b]["success"].mean() * 100 for b in ("B_full", MVC, "B_noVolatile")}

    # observation tokens present per page
    tokens = {}
    for p in PAGES:
        tokens[p] = {b: field_tokens(observation(p, b)) for b in ("B_full", MVC, "B_full_minus_volId", "B_noVolatile")}

    def event_row(k, direction):
        p, t = k
        tgt = next(x for x in truth[p]["targets"] if x["id"] == t)
        attrs = {a for a in tgt["signal_attrs"] if a not in NON_ATTRIBUTE_SIGNALS}
        vids = set(truth[p]["volatility_labels"].get("volatile_ids", []))
        vcls = set(truth[p]["volatility_labels"].get("volatile_classes", []))
        oids = oracle_ids(p, t)
        failing = nv.loc[k] if direction == "mvc_only" else mvc.loc[k]
        hits = volatile_hits(failing["locator_raw"], vids, vcls)
        hit_desc = []
        for h in hits:
            tok = h["token"]
            if h["rule"].startswith(("R1", "R2", "R3")):
                where = {b: tok in tokens[p][b][1] for b in ("B_noVolatile", MVC)}
            elif h["rule"].startswith(("R4", "R5", "R6", "R7", "R8")):
                where = {b: tok in tokens[p][b][0] for b in ("B_noVolatile", MVC)}
            else:
                where = {}
            hit_desc.append({"rule": h["rule"], "token": tok, "reason": h["reason"],
                             "in_NV_obs": where.get("B_noVolatile"), "in_mVC_obs": where.get(MVC)})
        return {"page": p, "task_id": t,
                "stratum": "has_attribute_signal" if attrs else "no_attribute_signal",
                "nv_failure": SHORT.get(nv.loc[k, "failure_mode"], "—") if direction == "mvc_only" else "— (success)",
                "mvc_failure": SHORT.get(mvc.loc[k, "failure_mode"], "—") if direction == "nv_only" else "— (success)",
                "bf_success": bool(bf.loc[k, "success"]),
                "signal_attrs": tgt["signal_attrs"], "oracle_ids": oids,
                "oracle_id_labelled_volatile": any(i in vids for i in oids if i),
                "nv_locator": nv.loc[k, "locator_raw"], "nv_flags": flags(nv.loc[k]),
                "mvc_locator": mvc.loc[k, "locator_raw"], "mvc_flags": flags(mvc.loc[k]),
                "mvc_origin": origin[k], "volatile_hits": hit_desc}

    mvc_only = [event_row(k, "mvc_only") for k in idx if mvc.loc[k, "success"] and not nv.loc[k, "success"]]
    nv_only = [event_row(k, "nv_only") for k in idx if nv.loc[k, "success"] and not mvc.loc[k, "success"]]

    # mechanism tallies for the minus_volClass-only events
    def mech(ev):
        hs = ev["volatile_hits"]
        if not hs:
            return "no volatile token in the B_noVolatile locator"
        cls = [h for h in hs if h["rule"].startswith(("R4", "R5", "R6", "R7", "R8"))]
        if cls and all(h["in_NV_obs"] and not h["in_mVC_obs"] for h in cls) and len(cls) == len(hs):
            labelled = any("truth volatile_classes" in h["reason"] or "BEM base" in h["reason"] for h in cls)
            return ("class token kept in B_noVolatile, stripped in minus_volClass"
                    + (" (labelled in truth.json)" if labelled else " (not labelled in truth.json; flagged by "
                                                                     "the predicate's VolatileClassRe)"))
        return "other: " + "; ".join(f"{h['rule']} {h['token']} [{h['reason']}] NV-obs={h['in_NV_obs']} "
                                     f"mVC-obs={h['in_mVC_obs']}" for h in hs)
    mech_counts = collections.Counter(mech(e) for e in mvc_only)
    for e in mvc_only:
        e["mechanism"] = mech(e)

    def mech_rev(ev):
        hs = ev["volatile_hits"]
        if not hs:
            return f"minus_volClass locator not volatile (flags {ev['mvc_flags']})"
        ids = [h for h in hs if h["rule"].startswith(("R1", "R2", "R3"))]
        if ids and len(ids) == len(hs) and all(h["in_mVC_obs"] and not h["in_NV_obs"] for h in ids):
            return "id kept in minus_volClass, stripped in B_noVolatile"
        return "other: " + "; ".join(f"{h['rule']} {h['token']} [{h['reason']}] NV-obs={h['in_NV_obs']} "
                                     f"mVC-obs={h['in_mVC_obs']}" for h in hs)
    for e in nv_only:
        e["mechanism"] = mech_rev(e)
    rev_counts = collections.Counter(e["mechanism"] for e in nv_only)

    comp_rows, comp_diffs = compose_check()

    after = protected_state()
    assert after == before, "[guard] protected files changed"

    # report
    L = ["# EXPLORATORY — non-additivity of the F2 ablations (minus_volClass vs B_noVolatile)", "",
         "**Exploratory**: not part of `batch_analysis_plan.md`; no model calls, no change to the plan, the "
         "predicate or the Oracle. Generated by `python experiments/analysis/revision1_batch_nonadditivity.py`.", "",
         "Cells: gpt-4.1, F1, rep 1. B_full×F1 and B_noVolatile×F1 are the original corpus records; "
         f"B_full_minus_volClass×F1 is the batch (200 events) plus the reused B_full×F1 records on "
         f"{', '.join(reused_pages)} (identical observation). n = 240 paired events (page, task_id).", "",
         f"P5 rates: B_full {rates['B_full']:.2f}%, minus_volClass {rates[MVC]:.2f}%, B_noVolatile "
         f"{rates['B_noVolatile']:.2f}%. vs B_full: minus_volClass {rates[MVC] - rates['B_full']:+.2f} pp, "
         f"B_noVolatile {rates['B_noVolatile'] - rates['B_full']:+.2f} pp (the +10.00 pp figure is the COP, "
         "B_noVolatile×**F3**; for ×F1 rep 1 the difference is +9.58 pp).", "",
         "## 1. P5 crosstab (✓ = success)", ""]
    L += md_table(["B_full", "minus_volClass", "B_noVolatile", "events"], cross)
    L += ["", f"minus_volClass vs B_noVolatile (exploratory McNemar, second − first = minus_volClass − B_noVolatile): "
          f"b = {m_nv_mvc['b_second_only']} (minus_volClass only), c = {m_nv_mvc['c_first_only']} (B_noVolatile "
          f"only), Δ {m_nv_mvc['delta_pp']:+.2f} pp, p exact {fmt_p(m_nv_mvc['p_exact'])}.", ""]

    L += ["## 2. Success under minus_volClass, failure under B_noVolatile "
          f"({len(mvc_only)} events)", "", "Mechanism tally:", ""]
    L += md_table(["mechanism", "events"], [[k, v] for k, v in mech_counts.most_common()])
    L += ["", "Flags = predicate conditions U unique, O oracle, V non-volatile, P non-positional, 5 stable signal "
          "present (· = false). Volatile tokens = Python port of `Oracle.LocatorUsesVolatileSignal` on the "
          "failing locator; NV-obs / mVC-obs = token present in that observation's class (or id) field.", ""]
    L += md_table(["page", "target", "stratum", "B_full P5", "NV failure", "signal_attrs", "oracle id (labelled volatile?)",
                   "B_noVolatile locator [flags]", "minus_volClass locator [flags]", "volatile tokens in NV locator",
                   "mechanism"],
                  [[e["page"], e["task_id"], e["stratum"], "✓" if e["bf_success"] else "✗", e["nv_failure"],
                    ", ".join(e["signal_attrs"]) or "(none)",
                    (", ".join(e["oracle_ids"]) or "(no id)") + (" — **yes**" if e["oracle_id_labelled_volatile"] else " — no"),
                    f"{cell_md(e['nv_locator'])} [{e['nv_flags']}]", f"{cell_md(e['mvc_locator'])} [{e['mvc_flags']}]",
                    "; ".join(f"{cell_md(h['token'])} {h['rule'].split()[0]} ({h['reason']}; NV-obs {h['in_NV_obs']}, "
                              f"mVC-obs {h['in_mVC_obs']})" for h in e["volatile_hits"]) or "—",
                    e["mechanism"]] for e in mvc_only])

    L += ["", "## 3. Success under B_noVolatile, failure under minus_volClass "
          f"({len(nv_only)} events)", "", "Mechanism tally:", ""]
    L += md_table(["mechanism", "events"], [[k, v] for k, v in rev_counts.most_common()])
    L += [""]
    L += md_table(["page", "target", "stratum", "B_full P5", "minus_volClass failure", "signal_attrs",
                   "oracle id (labelled volatile?)", "B_noVolatile locator [flags]", "minus_volClass locator [flags]",
                   "minus_volClass record", "volatile tokens in minus_volClass locator"],
                  [[e["page"], e["task_id"], e["stratum"], "✓" if e["bf_success"] else "✗", e["mvc_failure"],
                    ", ".join(e["signal_attrs"]) or "(none)",
                    (", ".join(e["oracle_ids"]) or "(no id)") + (" — **yes**" if e["oracle_id_labelled_volatile"] else " — no"),
                    f"{cell_md(e['nv_locator'])} [{e['nv_flags']}]", f"{cell_md(e['mvc_locator'])} [{e['mvc_flags']}]",
                    e["mvc_origin"],
                    "; ".join(f"{cell_md(h['token'])} {h['rule'].split()[0]} ({h['reason']}; NV-obs {h['in_NV_obs']}, "
                              f"mVC-obs {h['in_mVC_obs']})" for h in e["volatile_hits"]) or "—"] for e in nv_only])

    n_eq_nv = sum(r["composed_eq_nv"] for r in comp_rows)
    n_eq_nvc = sum(r["composed_eq_nvc"] for r in comp_rows)
    n_bytes = sum(r["nv_bytes_eq_nvc"] for r in comp_rows)
    L += ["", "## 4. Is B_noVolatile = B_full − volClass − volId in the observation?", "",
          "Composition per element: B_full with `class` from B_full_minus_volClass and `id` from "
          "B_full_minus_volId (F1 dumps in `batch_observations/`, parsed JSON, key order kept). Code: "
          "`ApplyBundleNoVolatile` strips only truth.json-labelled ids / class tokens and BEM bases of labelled "
          "classes; `ApplyBundleMinusVolatileClass` / `…Id` strip what the predicate flags "
          "(`PredicateFlagsClassToken` / `PredicateFlagsId`: the labels, BEM bases **and** the predicate's "
          "structural regexes) — the rule of B_noVolatileConsistent (AttributeBundles.cs).", "",
          f"- composition == B_noVolatile: **{n_eq_nv} / 24 pages**;",
          f"- composition == B_noVolatileConsistent: **{n_eq_nvc} / 24 pages**;",
          f"- B_noVolatile file == B_noVolatileConsistent file byte for byte: **{n_bytes} / 24 pages**;",
          "- alignment check: every single ablation and B_noVolatile differ from B_full only in their own "
          "key(s) (`class` / `id`); elements they drop are exactly those left without attribute or text "
          "(`ObservationEncoders.HasContent`) — asserted;",
          "- differences composition → B_noVolatile over all pages: "
          + ", ".join(f"{k} {v}" for k, v in sorted(comp_diffs.items())) + ".", ""]
    L += md_table(["page", "elements B_full / NV / composed", "elements differing", "of which kept by NV only (class-only elements)", "class tokens kept by NV only", "ids kept by NV only",
                   "reverse (stripped by NV only)", "other keys", "= NV", "= NVC", "NV bytes = NVC",
                   "examples kept by NV"],
                  [[r["page"], f"{r['elements']} / {r['elements_nv']} / {r['elements_composed']}", r["elements_differing"], r["dropped_comp"], r["kept_class"], r["kept_id"], r["reverse"],
                    r["other"], r["composed_eq_nv"], r["composed_eq_nvc"], r["nv_bytes_eq_nvc"],
                    ", ".join(cell_md(x) for x in r["examples"]) or "—"] for r in comp_rows])
    L += ["", f"Protected files (FINDINGS.md, 24 matrix, 71 axisc, 24 truth) unchanged: {len(after)} SHA-256 equal.", ""]
    OUT_MD.write_text("\n".join(L), encoding="utf-8")
    print(f"Wrote {OUT_MD.relative_to(REPO)}")
    print("crosstab", dict(combo))
    print("mvc_only", len(mvc_only), dict(mech_counts))
    print("nv_only", len(nv_only), dict(rev_counts))
    print("compose == NV", n_eq_nv, "== NVC", n_eq_nvc, "NV bytes == NVC", n_bytes, dict(comp_diffs))


if __name__ == "__main__":
    main()
