"""
Exact composition of the bundle ladder (facts only, zero LLM).

Sources (no hand-written attribute lists):
  - batch_observations/bundle_composition.json: the attribute sets as the harness returns them
    (AttributeBundles.GetBundle / ResolveBundleSetForSignalCheck / AttributeCategories),
    written by DUMP_BATCH_OBSERVATIONS=1;
  - shared/harness/AttributeBundles.cs: the initializer and line of each set, and the line of
    each value-level filter function;
  - batch_observations/manifest.tsv: sha256 + o200k_base tokens of every page × bundle × F1
    observation, for the byte comparison of adjacent ladder steps.
Control: the dumped F1 token counts equal the stored corpus `observation_tokens`.

Outputs: experiments/results/revision1/ladder_composition.{md,json}
"""
from __future__ import annotations

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import re
import json
import pathlib

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from load import load_dataframe                                                    # noqa: E402
from revision1_diagnostics import REPO, OUT_DIR, protected_state, jsonable, md_table   # noqa: E402

DUMP = OUT_DIR / "batch_observations"
SRC = REPO / "shared" / "harness" / "AttributeBundles.cs"
OBS_SRC = REPO / "shared" / "harness" / "Observation.cs"
LADDER = ["B_full", "B_noVolatile", "B_noState", "B_noSemantic", "B_identityCore", "B_minimalCore"]
SET_VAR = {"B_full": "BundleFull", "B_noState": "BundleNoState", "B_noSemantic": "BundleNoSemantic",
           "B_identityCore": "BundleIdentityCore", "B_minimalCore": "BundleMinimalCore",
           "B_full_minus_aria": "BundleFullMinusAria"}
# Value-level filters: the function that builds the observation elements for the bundle.
VALUE_FN = {"B_noVolatile": "ApplyBundleNoVolatile", "B_noVolatileConsistent": "ApplyBundleNoVolatileConsistent",
            "B_full_minus_volClass": "ApplyBundleMinusVolatileClass",
            "B_full_minus_volId": "ApplyBundleMinusVolatileId"}
VALUE_RULE = {
    "B_noVolatile": "id ∈ truth.json volatile_ids; class token ∈ volatile_classes or a BEM base of one "
                    "(Oracle.IsBemBaseOfVolatile)",
    "B_noVolatileConsistent": "id / class token flagged by the predicate (Oracle.LocatorUsesVolatileSignal "
                              "on `[id=\"…\"]` / `[class~=\"…\"]`: labels + BEM base + structural regexes)",
    "B_full_minus_volClass": "class tokens flagged by the predicate (as B_noVolatileConsistent); id kept",
    "B_full_minus_volId": "id flagged by the predicate (as B_noVolatileConsistent); class kept",
}


def source_facts():
    lines = SRC.read_text(encoding="utf-8").splitlines()
    sets = {}
    for i, l in enumerate(lines):
        m = re.match(r"\s*public static readonly IReadOnlySet<string> (\w+) =", l)
        if m:
            j, expr = i + 1, []
            while True:
                expr.append(lines[j].strip())
                if lines[j].rstrip().endswith(";"):
                    break
                j += 1
            sets[m.group(1)] = {"line": i + 1, "initializer": " ".join(expr)}
    fns = {}
    for name in VALUE_FN.values():
        for i, l in enumerate(lines):
            if re.search(rf"public static ElementData {name}\(", l):
                fns[name] = i + 1
    obs_lines = OBS_SRC.read_text(encoding="utf-8").splitlines()
    aria_line = next(i + 1 for i, l in enumerate(obs_lines) if "BuildAriaObservationAsync(IPage page)" in l)
    return sets, fns, aria_line


def main():
    before = protected_state()
    comp = json.loads((DUMP / "bundle_composition.json").read_text(encoding="utf-8"))
    full = set(comp["bundle_full"])
    cats = {k: set(v) for k, v in comp["categories"].items()}
    sets, fns, aria_line = source_facts()

    def members(b):
        if b in comp["static_bundles"]:
            return set(comp["static_bundles"][b])
        return set(comp["condition5_sets"][b])          # value-level bundles: B_full membership

    def removed_by_category(b):
        rem = full - members(b)
        out = []
        for c, s in cats.items():
            hit = rem & s
            if hit:
                out.append(f"{c} ({'all' if hit == (s & full) else 'part'}: {', '.join(sorted(hit))})")
        return rem, out

    def defined_as(b):
        if b in SET_VAR:
            v = SET_VAR[b]
            ini = sets[v]["initializer"]
            rel = ("B_full" if "BundleFull" in ini else "B_noState set" if "BundleNoState" in ini
                   else "union of the six category sets" if "_identity.Concat" in ini else "literal set")
            return f"`{v}` = `{ini.rstrip(';')}` (AttributeBundles.cs:{sets[v]['line']})", rel
        if b in VALUE_FN:
            return (f"`{VALUE_FN[b]}` (AttributeBundles.cs:{fns[VALUE_FN[b]]}): B_full membership + value filter",
                    "B_full")
        if b == "B_full_minus_state":
            return "`_bundles[\"B_full_minus_state\"] = BundleNoState` (same set object as B_noState)", "B_noState set"
        if b == "B_playwrightMCP":
            return (f"`Observation.BuildAriaObservationAsync` (Observation.cs:{aria_line}): "
                    "`page.AriaSnapshotAsync()`, no DOM-walk bundle", "separate extraction path")
        raise KeyError(b)

    order = LADDER + ["B_playwrightMCP", "B_noVolatileConsistent", "B_full_minus_volClass",
                      "B_full_minus_volId", "B_full_minus_state", "B_full_minus_aria"]
    rows, comp_json = [], {}
    for b in order:
        d, rel = defined_as(b)
        if b == "B_playwrightMCP":
            rem_cats, rem, n_attr = ["n/a (ARIA snapshot, not an attribute projection)"], set(), "n/a"
            cond5 = sorted(comp["condition5_sets"].get(b, full)) if b in comp["condition5_sets"] else None
        else:
            rem, rem_cats = removed_by_category(b)
            n_attr = len(members(b))
        vol = VALUE_RULE.get(b, "no (every value of an admitted attribute is kept)" if b != "B_playwrightMCP"
                             else "n/a")
        rows.append([b, d, rel, n_attr, "; ".join(rem_cats) or "none", vol])
        comp_json[b] = {"defined_as": d, "defined_relative_to": rel,
                        "attributes": sorted(members(b)) if b != "B_playwrightMCP" else None,
                        "removed_vs_B_full": sorted(rem), "removed_by_category": rem_cats,
                        "value_level_filter": vol}

    # Byte comparison per page × F1
    man = pd.read_csv(DUMP / "manifest.tsv", sep="\t", dtype={"sha256": str})
    f1 = man[man.encoding == "F1"].set_index(["page", "bundle"])
    pages = sorted(man.page.unique())
    pairs = [("B_full", "B_noVolatile"), ("B_noVolatile", "B_noState"), ("B_noState", "B_noSemantic"),
             ("B_noSemantic", "B_identityCore"), ("B_identityCore", "B_minimalCore"),
             ("B_full", "B_noState"), ("B_full_minus_state", "B_noState"),
             ("B_full", "B_full_minus_volClass"), ("B_full", "B_full_minus_volId"), ("B_full", "B_full_minus_aria"),
             ("B_noVolatile", "B_noVolatileConsistent")]
    cmp_rows, cmp_json = [], []
    for a, b in pairs:
        ident = [p for p in pages if f1.loc[(p, a), "sha256"] == f1.loc[(p, b), "sha256"]]
        ta = [int(f1.loc[(p, a), "tokens"]) for p in pages]
        tb = [int(f1.loc[(p, b), "tokens"]) for p in pages]
        cmp_rows.append([f"{a} → {b}", f"{len(ident)}/24", f"{sum(ta) / 24:,.1f}", f"{sum(tb) / 24:,.1f}",
                         f"{sum(tb) / 24 - sum(ta) / 24:+,.1f}", ", ".join(ident) if 0 < len(ident) < 24 else
                         ("all" if len(ident) == 24 else "none")])
        cmp_json.append({"from": a, "to": b, "identical_pages": ident,
                         "tokens_from": dict(zip(pages, ta)), "tokens_to": dict(zip(pages, tb))})

    # Per page × adjacent ladder step: identical (=) or differing (≠)
    adj = pairs[:5]
    page_rows = [[p] + ["=" if f1.loc[(p, a), "sha256"] == f1.loc[(p, b), "sha256"] else "≠" for a, b in adj]
                 + [f"{int(f1.loc[(p, x), 'tokens']):,}" for x in LADDER] for p in pages]

    # Control: dumped F1 tokens == stored corpus observation_tokens (gpt-4.1 matrix)
    df = load_dataframe(REPO)
    stored = (df[(df.encoding == "F1") & df.bundle.isin(LADDER)]
              .groupby(["page", "bundle"]).observation_tokens.agg(["min", "max"]))
    mism = [f"{p} {b}: dump {int(f1.loc[(p, b), 'tokens'])} vs stored {r['min']}–{r['max']}"
            for (p, b), r in stored.iterrows()
            if not (r["min"] == r["max"] == int(f1.loc[(p, b), "tokens"]))]
    fidelity_ok = len(mism) == 0 and len(stored) == 24 * len(LADDER)

    L = ["# Revision 1 — bundle ladder composition", "",
         "Facts only. Attribute sets are read from the running harness code "
         "(`bundle_composition.json`, written by `DUMP_BATCH_OBSERVATIONS=1` from `AttributeBundles.GetBundle`, "
         "`ResolveBundleSetForSignalCheck` and `AttributeBundles.AttributeCategories`); initializer expressions and "
         "line numbers are parsed from `shared/harness/AttributeBundles.cs`. \"text\" is the virtual key for the "
         "visible text (Semantic-textual).", "",
         f"B_full = {len(full)} keys: {', '.join(sorted(full))}.", "",
         "Categories: " + "; ".join(f"**{c}** = {', '.join(sorted(s))}" for c, s in cats.items()) + ".", "",
         "## 1. Composition", ""]
    L += md_table(["bundle", "defined as (code)", "defined relative to", "attribute keys",
                   "removed vs B_full, by category", "value-level stripping"], rows)
    L += ["", "Static bundles apply `AttributeBundles.ApplyBundle` (keep an attribute iff its key is in the set; "
          "keep its full value). Value-level bundles keep B_full membership and filter id / class values in the "
          "function named above. Condition 5 (`ResolveBundleSetForSignalCheck`) uses B_full for B_noVolatile, "
          "B_playwrightMCP, B_noVolatileConsistent, B_full_minus_volClass and B_full_minus_volId.", "",
          "## 2. Byte comparison of F1 observations (24 pages)", "",
          "Identical = same sha256 of the observation text. Tokens = mean o200k_base observation tokens per page.", ""]
    L += md_table(["step", "identical pages", "mean tokens (from)", "mean tokens (to)", "Δ tokens",
                   "identical on"], cmp_rows)
    L += ["", "Per page, adjacent ladder steps (= identical, ≠ differs) and F1 tokens per ladder bundle:", ""]
    L += md_table(["page"] + [f"{a}→{b}" for a, b in adj] + LADDER, page_rows)
    L += ["", "B_playwrightMCP has F4 only (ARIA snapshot); an F1 byte comparison is not applicable.", "",
          f"Control — dumped F1 tokens equal the stored corpus `observation_tokens` for the {len(LADDER)} ladder "
          f"bundles × 24 pages: {'yes' if fidelity_ok else 'NO ' + str(mism[:10])}.", ""]

    after = protected_state()
    assert before == after, "protected files changed during the run"
    L += [f"Protected files (FINDINGS.md, 24 matrix, 71 axisc, 24 truth) unchanged: {len(before)} SHA-256 equal.", ""]
    (OUT_DIR / "ladder_composition.md").write_text("\n".join(L), encoding="utf-8", newline="\n")
    (OUT_DIR / "ladder_composition.json").write_text(json.dumps(jsonable({
        "bundle_full": sorted(full), "categories": {k: sorted(v) for k, v in cats.items()},
        "composition": comp_json, "byte_comparison_F1": cmp_json,
        "fidelity_F1_tokens_equal_corpus": fidelity_ok, "fidelity_mismatches": mism,
    }), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(L))
    if not fidelity_ok:
        sys.exit(3)


if __name__ == "__main__":
    main()
