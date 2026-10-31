"""
Scope of the B_noVolatile leak and the B_noVolatileConsistent control cells (zero LLM).

Inputs: experiments/results/revision1/observations/ (DUMP_OBSERVATIONS=1 output: observation
texts, manifest.tsv, token_census.json, oracle_signals.json, guard_violations.txt), the corpus
experiments/runs/matrix_page_*.jsonl, shared/testbed/pages/*.truth.json, and the 22 class names
of BemDedupParityTests in shared/oracle.tests/LocatorVolatilityTests.cs.

Outputs: experiments/results/revision1/leak_scope.{md,json} and consistent_cells.json, the
(page, encoding) cells whose B_noVolatileConsistent observation differs from B_noVolatile.

leak_scope.json["gate"] passes only if
  (a) no stable id/class signal value of a target is flagged by the predicate (no CONFLICT),
  (b) condition 5 is identical for B_noVolatile and B_noVolatileConsistent on all 960
      (target × DOM encoding) events and equals the stored B_noVolatile records,
  (c) dumped B_noVolatile / B_full×F1 token counts equal the stored ones,
  (d) the dump guard reported zero violations and the Python re-parse agrees.
"""
from __future__ import annotations

import sys
import json
import pathlib
import re

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from load import load_dataframe, DOM_ENCODINGS as _DOM_ENC          # noqa: E402
from revision1_diagnostics import (                                  # noqa: E402
    REPO, OUT_DIR, TRUTH_DIR, protected_state, jsonable, md_table, parse_f2_keymap,
)
from revision1_volatile_nv import (                                  # noqa: E402
    _is_vol_class, _is_vol_id, _bem_base, _prefix_of, parse_observation,
)

OBS_DIR    = OUT_DIR / "observations"
CELLS_FILE = OUT_DIR / "consistent_cells.json"
PARITY_CS  = REPO / "shared" / "oracle.tests" / "LocatorVolatilityTests.cs"
NV, NVC    = "B_noVolatile", "B_noVolatileConsistent"
DOM_ENCODINGS = sorted(_DOM_ENC)                              # F0, F1, F2, F3
CSS_PLAIN  = re.compile(r"^-?[A-Za-z_][A-Za-z0-9_-]*$")   # usable as .tok / #id without escaping


def parity_class_names() -> tuple[list[str], list[str]]:
    """ClassNames and VolatileClasses of BemDedupParityTests, read from the test source."""
    src = PARITY_CS.read_text(encoding="utf-8")
    block = src[src.index("public class BemDedupParityTests"):]
    vol = re.findall(r'"([^"]+)"', block[block.index("VolatileClasses ="):block.index("};")])
    names_block = block[block.index("ClassNames ="):]
    names_block = names_block[:names_block.index("};")]
    names = re.findall(r'"([^"]+)"', names_block)
    assert len(names) == 22 and len(vol) == 4, f"parity test: {len(names)} names, {len(vol)} volatile"
    return names, vol


def labels(page: str) -> tuple[set, set]:
    t = json.loads((TRUTH_DIR / f"{page}.truth.json").read_text(encoding="utf-8"))
    vl = t["volatility_labels"]
    return set(vl["volatile_ids"]), set(vl["volatile_classes"])


def tokens_of(elements: list[dict]) -> tuple[list[str], list[str]]:
    """All class tokens and ids carried by parsed observation elements (with multiplicity)."""
    cls, ids = [], []
    for el in elements:
        c = el.get("class")
        if c:
            cls.extend(str(c).split())
        i = el.get("id")
        if i:
            ids.append(str(i))
    return cls, ids


def main():
    before = protected_state()
    df = load_dataframe(REPO)
    reverse = {v.lower(): k for k, v in parse_f2_keymap().items()}

    manifest = pd.read_csv(OBS_DIR / "manifest.tsv", sep="\t", dtype={"sha256": str})
    census = pd.DataFrame(json.loads((OBS_DIR / "token_census.json").read_text(encoding="utf-8")))
    signals = json.loads((OBS_DIR / "oracle_signals.json").read_text(encoding="utf-8"))
    guard_txt = (OBS_DIR / "guard_violations.txt").read_text(encoding="utf-8").strip()
    pages = sorted(manifest["page"].unique())
    assert len(pages) == 24 and len(manifest) == 24 * 9, f"manifest: {len(pages)} pages, {len(manifest)} rows"

    # 1. Fidelity: dumped token counts vs stored observation_tokens
    fid_rows, fid_bad = [], []
    for _, m in manifest[manifest["bundle"].isin(["B_full", NV])].iterrows():
        sel = df[(df.page == m.page) & (df.bundle == m.bundle) & (df.encoding == m.encoding)]
        stored = sorted(sel["observation_tokens"].unique())
        assert len(sel) == 10, f"{m.page} {m.bundle} {m.encoding}: {len(sel)} records"
        ok = stored == [int(m.tokens)]
        fid_rows.append({"page": m.page, "bundle": m.bundle, "encoding": m.encoding,
                         "dumped": int(m.tokens), "stored": stored, "match": ok})
        if not ok:
            fid_bad.append(fid_rows[-1])
    fidelity = {"cells": len(fid_rows), "mismatches": len(fid_bad), "mismatch_rows": fid_bad}

    # 2. Census classification
    lab = {p: labels(p) for p in pages}
    rows = []
    for _, c in census.iterrows():
        vids, vcls = lab[c.page]
        tok = c.token
        if c.kind == "class":
            regex = _is_vol_class(tok)
            listed = tok in vcls
            bem = _bem_base(tok, vcls)
        else:
            regex = _is_vol_id(tok)
            listed = tok in vids
            bem = False
        expected = regex or listed or bem
        rows.append({"page": c.page, "kind": c.kind, "token": tok, "listed": listed, "bem_base": bem,
                     "regex": regex, "predicate_flags": bool(c.predicate_flags),
                     "predicate_flags_with_empty_lists": bool(c.predicate_flags_with_empty_lists),
                     "python_port_agrees": expected == bool(c.predicate_flags)
                                           and regex == bool(c.predicate_flags_with_empty_lists),
                     "css_plain_identifier": bool(CSS_PLAIN.match(tok))})
    cen = pd.DataFrame(rows)
    assert bool(cen.listed.equals(census.listed.astype(bool))), "census 'listed' disagrees with truth labels"
    port_disagree = cen[~cen.python_port_agrees]
    leaks = cen[cen.predicate_flags & ~cen.listed & ~cen.bem_base].copy()
    special = cen[~cen.css_plain_identifier]

    # 3. Leak presence in B_noVolatile / B_noVolatileConsistent observations
    obs_tokens = {}   # (page, bundle, enc) -> (Counter-like dict class, dict id)
    for _, m in manifest[manifest["bundle"].isin([NV, NVC])].iterrows():
        text = (OBS_DIR / f"{m.page}__{m.bundle}__{m.encoding}.txt").read_text(encoding="utf-8")
        cls, ids = tokens_of(parse_observation(text, m.encoding, reverse))
        obs_tokens[(m.page, m.bundle, m.encoding)] = (pd.Series(cls, dtype=object).value_counts().to_dict(),
                                                      pd.Series(ids, dtype=object).value_counts().to_dict())

    nv_df = df[df.bundle == NV]
    leak_rows = []
    for _, lk in leaks.iterrows():
        idx = 0 if lk.kind == "class" else 1
        r = {"page": lk.page, "kind": lk.kind, "token": lk.token}
        for enc in DOM_ENCODINGS:
            r[f"NV_{enc}"] = obs_tokens[(lk.page, NV, enc)][idx].get(lk.token, 0)
            r[f"NVC_{enc}"] = obs_tokens[(lk.page, NVC, enc)][idx].get(lk.token, 0)
        used = nv_df[(nv_df.page == lk.page) & nv_df.locator_value.fillna("").str.contains(lk.token, regex=False)]
        r["NV_locators_using_token"] = int(len(used))
        r["NV_locators_using_token_by_enc"] = used.encoding.value_counts().sort_index().to_dict()
        leak_rows.append(r)
    leak_df = pd.DataFrame(leak_rows)

    # B_noVolatile records whose locator literally contains a leaked token, by outcome
    leak_by_page = leaks.groupby("page").token.apply(list).to_dict()
    nv_flags = nv_df[~nv_df.predicate_non_volatile.astype(bool)]
    uses = nv_df[nv_df.apply(lambda r: any(t in (r.locator_value or "")
                                           for t in leak_by_page.get(r.page, [])), axis=1)]
    usage = {
        "NV_records_predicate_non_volatile_false": int(len(nv_flags)),
        "NV_records_with_leaked_token_in_locator": int(len(uses)),
        "of_which_non_volatile_false": int((~uses.predicate_non_volatile.astype(bool)).sum()),
        "by_failure_mode": uses.failure_mode.fillna("success").value_counts().to_dict(),
        "by_page": uses.page.value_counts().sort_index().to_dict(),
    }

    # Python re-check of the guard: no predicate-flagged token in any NVC observation
    py_guard = []
    for (page, bundle, enc), (cls, ids) in obs_tokens.items():
        if bundle != NVC:
            continue
        flagged = set(cen[(cen.page == page) & cen.predicate_flags].apply(lambda x: (x.kind, x.token), axis=1))
        for t in cls:
            if ("class", t) in flagged:
                py_guard.append(f"{page} {enc} class={t}")
        for t in ids:
            if ("id", t) in flagged:
                py_guard.append(f"{page} {enc} id={t}")

    # Kept tokens that a prefix/substring form ([class^=], [class*=], [id^=], [id*=]) would flag
    prefix_rows = []
    for _, c in cen[~cen.predicate_flags].iterrows():
        vids, vcls = lab[c.page]
        if (c.kind == "class" and _prefix_of(c.token, vcls)) or (c.kind == "id" and _prefix_of(c.token, vids)):
            prefix_rows.append({"page": c.page, "kind": c.kind, "token": c.token})

    # 4. The 22 class names of §3.3
    names22, vol4 = parity_class_names()
    in_corpus = cen[(cen.kind == "class") & cen.token.isin(names22)]
    names22_info = {
        "names": names22, "test_volatile_classes": vol4,
        "intersection_with_leaked_tokens": sorted(set(names22) & set(leaks.token)),
        "names_present_in_corpus_dom": sorted(in_corpus.token.unique()),
        "names_matching_VolatileClassRe": sorted(n for n in names22 if _is_vol_class(n)),
    }

    # 5. CONFLICTS: stable id/class signal values flagged by the predicate
    sig = pd.DataFrame(signals)
    assert len(sig) == 24 * 10 * 4 * 2, f"oracle_signals: {len(sig)} rows"
    assert sig.oracle_found.all(), "oracle element missing in some DOM walk"
    conflicts = []
    for _, s in sig[sig.bundle == NVC].iterrows():
        for v in s.id_class_signals:
            if v["predicate_flags"]:
                conflicts.append({"page": s.page, "task_id": s.task_id, "encoding": s.encoding, **v})
    conflict_targets = sorted({(c["page"], c["task_id"], c["attr"], c["value"]) for c in conflicts})
    n_idclass_signal_targets = len({(s.page, s.task_id) for _, s in sig.iterrows() if s.id_class_signals})
    idclass_values = sorted({(s.page, s.task_id, v["attr"], v["value"], v["listed"], v["predicate_flags"])
                             for _, s in sig[sig.bundle == NVC].iterrows() for v in s.id_class_signals})

    # 6. Condition 5 identity (960) and vs stored records
    piv = sig.pivot_table(index=["page", "task_id", "encoding"], columns="bundle",
                          values="condition5", aggfunc="first")
    assert len(piv) == 960
    c5_diff = piv[piv[NV] != piv[NVC]].reset_index()
    stored = nv_df.set_index(["page", "task_id", "encoding"])["stable_signal_present_in_bundle"]
    joined = piv.join(stored, how="inner")
    assert len(joined) == 960
    c5_vs_stored = joined[joined[NV] != joined["stable_signal_present_in_bundle"]].reset_index()
    c5_counts = {NV: int(piv[NV].sum()), NVC: int(piv[NVC].sum()),
                 "stored_B_noVolatile": int(stored.sum())}

    # 7. Byte comparison NV vs NVC
    sha = manifest.set_index(["page", "bundle", "encoding"])
    cmp_rows, cells = [], []
    for page in pages:
        for enc in DOM_ENCODINGS:
            a = (OBS_DIR / f"{page}__{NV}__{enc}.txt").read_bytes()
            b = (OBS_DIR / f"{page}__{NVC}__{enc}.txt").read_bytes()
            same = a == b
            assert same == (sha.loc[(page, NV, enc), "sha256"] == sha.loc[(page, NVC, enc), "sha256"])
            cmp_rows.append({"page": page, "encoding": enc, "identical": same,
                             "tokens_NV": int(sha.loc[(page, NV, enc), "tokens"]),
                             "tokens_NVC": int(sha.loc[(page, NVC, enc), "tokens"])})
            if not same:
                cells.append({"page": page, "encoding": enc})
    cmp_df = pd.DataFrame(cmp_rows)
    diff_df = cmp_df[~cmp_df.identical].copy()
    diff_df["delta"] = diff_df.tokens_NVC - diff_df.tokens_NV
    leak_pages = sorted(leaks.page.unique())
    diff_pages = sorted(diff_df.page.unique())

    gate = {
        "conflicts_empty": len(conflicts) == 0,
        "condition5_identical_960": len(c5_diff) == 0,
        "condition5_matches_stored_960": len(c5_vs_stored) == 0,
        "token_fidelity": len(fid_bad) == 0,
        "dump_guard_clean": guard_txt == "" and not py_guard,
        "python_port_agrees_with_predicate": len(port_disagree) == 0,
        "differing_pages_equal_leak_pages": diff_pages == leak_pages,
    }
    gate["pass"] = all(gate.values())

    CELLS_FILE.write_text(json.dumps(cells, indent=2) + "\n", encoding="utf-8")

    # Report
    L = ["# Revision 1 — scope of the B_noVolatile leak and B_noVolatileConsistent controls", "",
         "Zero model calls. Observations rebuilt with `DUMP_OBSERVATIONS=1` "
         "(`Observation.BuildObservationAsync`, same DOM walk and encoders as the corpus run); "
         "predicate verdicts from `Oracle.LocatorUsesVolatileSignal` via "
         "`AttributeBundles.PredicateFlagsClassToken` / `PredicateFlagsId` "
         "(`[class~=\"tok\"]` / `[id=\"id\"]` forms).", "",
         f"**Gate: {'PASS' if gate['pass'] else 'FAIL'}** — "
         + ", ".join(f"{k}={'yes' if v else 'NO'}" for k, v in gate.items() if k != "pass"), "",
         "## 1. Fidelity of the rebuilt observations", "",
         f"Dumped token count vs stored `observation_tokens` for B_full×F1 and B_noVolatile×F0–F3: "
         f"{fidelity['cells']} cells, {fidelity['mismatches']} mismatches.", ""]
    if fid_bad:
        L += md_table(["page", "bundle", "enc", "dumped", "stored"],
                      [[r["page"], r["bundle"], r["encoding"], r["dumped"], r["stored"]] for r in fid_bad]) + [""]

    by_kind = cen.groupby("kind").agg(distinct=("token", "size"), predicate_flags=("predicate_flags", "sum"),
                                      listed=("listed", "sum"), bem_base=("bem_base", "sum"),
                                      regex=("regex", "sum"))
    L += ["## 2. Token census (raw DOM walk, per page distinct tokens, summed over 24 pages)", "",
          *md_table(["kind", "distinct (page,token)", "predicate flags", "listed", "BEM base", "regex"],
                    [[k, int(r.distinct), int(r.predicate_flags), int(r.listed), int(r.bem_base), int(r.regex)]
                     for k, r in by_kind.iterrows()]), "",
          f"Python port of the predicate vs C# verdict: {len(port_disagree)} disagreements.", "",
          "### 2a. Tokens flagged by the predicate, neither listed nor a BEM base (the leak)", "",
          f"Class tokens: {int((leaks.kind == 'class').sum())}; ids: {int((leaks.kind == 'id').sum())}; "
          f"pages: {', '.join(leak_pages)}.", ""]
    for kind in ("class", "id"):
        sub = leaks[leaks.kind == kind]
        L.append(f"- **{kind}**: " + ("; ".join(f"{p}: " + ", ".join(f"`{t}`" for t in g.token)
                                                 for p, g in sub.groupby("page")) if len(sub) else "none"))
    L += ["", "### 2b. Where the leaked tokens appear in the observations "
          "(element count carrying the token; NV = B_noVolatile, NVC = B_noVolatileConsistent)", "",
          *md_table(["page", "kind", "token"] + [f"NV {e}" for e in DOM_ENCODINGS]
                    + [f"NVC {e}" for e in DOM_ENCODINGS] + ["NV locators using it (by enc)"],
                    [[r.page, r.kind, f"`{r.token}`"] + [r[f"NV_{e}"] for e in DOM_ENCODINGS]
                     + [r[f"NVC_{e}"] for e in DOM_ENCODINGS]
                     + [f"{r.NV_locators_using_token} {r.NV_locators_using_token_by_enc or ''}"]
                     for _, r in leak_df.iterrows()]), "",
          f"B_noVolatile records with `predicate_non_volatile = false`: {usage['NV_records_predicate_non_volatile_false']}; "
          f"records whose locator literally contains a leaked token: {usage['NV_records_with_leaked_token_in_locator']} "
          f"(non_volatile=false: {usage['of_which_non_volatile_false']}); by failure mode "
          f"{usage['by_failure_mode']}; by page {usage['by_page']}. The earlier investigation "
          "(`volatile_in_noVolatile.md`) covered only the grabbed failures (84); the lacked ones lie outside it.",
          f"Leaked tokens used in at least one B_noVolatile locator: "
          f"{int((leak_df.NV_locators_using_token > 0).sum())} of {len(leak_df)}.", "",
          f"Leaked tokens absent from every B_noVolatile observation: "
          f"{int((leak_df[[f'NV_{e}' for e in DOM_ENCODINGS]].sum(axis=1) == 0).sum())} of {len(leak_df)}.",
          f"Leaked tokens present in any B_noVolatileConsistent observation: "
          f"{int((leak_df[[f'NVC_{e}' for e in DOM_ENCODINGS]].sum(axis=1) > 0).sum())}.", "",
          "### 2c. Prefix / substring forms", "",
          "Tokens kept by both bundles (not flagged in `~=`/`=` form) that are a prefix of a listed "
          "volatile token, i.e. would be flagged if the model wrote `[class^=…]`/`[class*=…]`/"
          f"`[id^=…]`/`[id*=…]`: {len(prefix_rows)}."
          + ("" if not prefix_rows else " " + "; ".join(f"{r['page']} {r['kind']} `{r['token']}`"
                                                           for r in prefix_rows)),
          "Fragments of a removed token cannot be written from the observation, since the token is absent.", "",
          "### 2d. Class/id tokens with CSS-special characters", "",
          f"Tokens in the DOM census that are not plain CSS identifiers: {len(special)}."
          + ("" if special.empty else " " + "; ".join(f"{r.page} {r.kind} `{r.token}` "
                                                       f"(flags={r.predicate_flags})"
                                                       for _, r in special.iterrows())),
          "The bundle consults the predicate only through `[class~=\"…\"]` / `[id=\"…\"]`; "
          "synthetic special-character tokens are covered by unit tests in `experiments/tests`.", "",
          "## 3. The 22 class names of §3.3", "",
          "Source: `BemDedupParityTests` (`shared/oracle.tests/LocatorVolatilityTests.cs`). "
          "It compares `Oracle.IsBemBaseOfVolatile` with the strip path of `ApplyBundleNoVolatile` "
          f"against {len(vol4)} hard-coded volatile classes ({', '.join(f'`{v}`' for v in vol4)}).", "",
          f"- Names: {', '.join(f'`{n}`' for n in names22)}.",
          f"- Names matching `VolatileClassRe`: {names22_info['names_matching_VolatileClassRe'] or 'none'}.",
          f"- Intersection with the leaked tokens: {names22_info['intersection_with_leaked_tokens'] or 'none'}.",
          f"- Names present in the testbed DOM: {len(names22_info['names_present_in_corpus_dom'])} of 22.",
          "- The test exercises only the BEM rule (each name is asserted not to be a literal volatile class), "
          "on a hand-written element, with no regex-matching name and no page DOM. A token flagged by "
          "`VolatileClassRe` but missing from `volatile_classes` is outside what the test can observe.", "",
          "## 4. Stable id/class signals vs the predicate (CONFLICT list)", "",
          f"Targets with an `id`/`class` entry in `signal_attrs`: {n_idclass_signal_targets}. "
          f"Distinct (target, attr, value): {len(idclass_values)}; listed: "
          f"{sum(1 for v in idclass_values if v[4])}; predicate-flagged: {sum(1 for v in idclass_values if v[5])}.", "",
          f"**CONFLICTS: {len(conflict_targets)}**"
          + ("" if not conflict_targets else " — " + "; ".join(f"{p} {t} {a}=`{v}`" for p, t, a, v in conflict_targets)),
          "",
          "## 5. Condition 5 (stable_signal_present_in_bundle)", "",
          f"B_noVolatile vs B_noVolatileConsistent over 960 (target × F0–F3): {len(c5_diff)} differences. "
          f"Rebuilt B_noVolatile vs stored records: {len(c5_vs_stored)} differences.",
          f"True counts: B_noVolatile {c5_counts[NV]}, B_noVolatileConsistent {c5_counts[NVC]}, "
          f"stored {c5_counts['stored_B_noVolatile']} (of 960). `lacked` is therefore unchanged.", "",
          "## 6. Byte comparison B_noVolatile vs B_noVolatileConsistent", "",
          f"Identical: {int(cmp_df.identical.sum())} of {len(cmp_df)}; differing: {len(diff_df)} "
          f"(pages {', '.join(diff_pages) or 'none'}).", "",
          *md_table(["page", "enc", "tokens NV", "tokens NVC", "Δ"],
                    [[r.page, r.encoding, r.tokens_NV, r.tokens_NVC, r.delta] for _, r in diff_df.iterrows()]), "",
          f"Cells file for the sensitivity run: `{CELLS_FILE.relative_to(REPO).as_posix()}` ({len(cells)} cells).", ""]

    after = protected_state()
    assert before == after, "protected files changed during the run"
    L += [f"Protected files (FINDINGS.md, 24 matrix, 71 axisc, 24 truth) unchanged: {len(before)} SHA-256 equal.", ""]

    (OUT_DIR / "leak_scope.md").write_text("\n".join(L), encoding="utf-8", newline="\n")
    (OUT_DIR / "leak_scope.json").write_text(json.dumps(jsonable({
        "gate": gate, "fidelity": fidelity,
        "census_by_kind": by_kind.reset_index().to_dict("records"),
        "python_port_disagreements": port_disagree.to_dict("records"),
        "leaked_tokens": leak_df.to_dict("records"), "leak_usage_in_NV_locators": usage,
        "prefix_form_tokens": prefix_rows,
        "special_character_tokens": special.to_dict("records"),
        "names22": names22_info,
        "idclass_signal_values": [dict(zip(["page", "task_id", "attr", "value", "listed", "predicate_flags"], v))
                                  for v in idclass_values],
        "conflicts": conflicts,
        "condition5": {"differences_NV_vs_NVC": c5_diff.to_dict("records"),
                       "differences_vs_stored": c5_vs_stored.to_dict("records"), "true_counts": c5_counts},
        "byte_comparison": cmp_df.to_dict("records"),
        "differing_cells": cells,
        "dump_guard_violations": guard_txt.splitlines(), "python_guard_violations": py_guard,
    }), indent=2) + "\n", encoding="utf-8", newline="\n")

    print("\n".join(L))
    if not gate["pass"]:
        print("\nGATE FAIL — stop before the dry-run.")
        sys.exit(3)


if __name__ == "__main__":
    main()
