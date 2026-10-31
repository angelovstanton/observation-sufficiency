"""Holm family sensitivity: adjacent ladder steps (D3 Family A) vs a ladder referenced to B_full.

Rebuilds D3 Family A, stops on any control mismatch, then replaces only its five bundle
comparisons. Does not call diagnostics.main or modify existing results.
Run: python -B experiments/analysis/revision1_holm_bfull_family.py
"""

import copy
import hashlib
from itertools import combinations
import json
from math import comb
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
from revision1_diagnostics import (
    BUNDLE_LADDER_ORDER, KEY, build_encoding_pairs, build_pairs, cross_model,
    fmt_p, holm, load_dataframe, mcnemar, md_table,
)

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "experiments/results/revision1"
TITLE = ("# SENSITIVITY — Holm family definition (A: adjacent ladder steps, as in "
         "diagnostics.md D3; B: ladder referenced to B_full)")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_state():
    paths = {REPO / "experiments/FINDINGS.md"}
    paths.update(p for p in (REPO / "experiments/runs").rglob("*") if p.is_file())
    paths.update(p for p in OUT.rglob("*") if p.is_file())
    names = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "*truth.json"],
        cwd=REPO, check=True, capture_output=True).stdout.decode("utf-8").split("\0")
    paths.update(REPO / name for name in names if name)
    return {p.relative_to(REPO).as_posix(): sha256(p) for p in sorted(paths)}


def row(group, label, pairs, basis):
    r = mcnemar(pairs["success_bf"], pairs["success_nv"])
    return {"group": group, "comparison": label, "n_pairs": r["n"], "basis": basis,
            "delta_pp": r["delta_pp"], "b": r["b_second_only"], "c": r["c_first_only"],
            "chi2": r["chi2"], "p_raw": r["p"], "p_exact": r["p_exact"]}


def adjust(family):
    for r, p, exact in zip(family, holm([r["p_raw"] for r in family]),
                           holm([r["p_exact"] for r in family])):
        r.update(p_holm=p, p_holm_exact=exact)


def build_family_a(df):
    family = []
    for first, second in zip(BUNDLE_LADDER_ORDER[:-1], BUNDLE_LADDER_ORDER[1:]):
        pairs = build_pairs(df, first, second)
        assert len(pairs) == 960 and not pairs.duplicated(KEY).any()
        family.append(row("bundle ladder", f"{first} → {second}", pairs, "960 pairs, F0–F3"))
    for enc in ("F0", "F2", "F3"):
        pairs = build_encoding_pairs(df, "B_noVolatile", "F1", enc)
        assert len(pairs) == 240
        family.append(row("encoding vs F1", f"B_noVolatile: F1 → {enc}", pairs, "240 pairs"))
    pairs = build_pairs(df, "B_full", "B_noVolatile")
    for stratum in ("LOW", "HIGH"):
        sp = pairs[pairs["semantic_density"] == stratum]
        assert len(sp) == 480
        family.append(row("moderator", f"B_full → B_noVolatile, {stratum} pages", sp, "480 pairs"))
    # Independently enumerate exactly the same C(24,12) page label allocations as D3.
    page_order = list(pairs["page"].unique())
    by_page = pairs.groupby("page")[["success_bf", "success_nv"]].sum()
    delta = (by_page["success_nv"] - by_page["success_bf"]).astype(int)
    low = set(pairs.loc[pairs["semantic_density"] == "LOW", "page"])
    vals = [int(delta[p]) for p in page_order]
    assert len(vals) == 24 and len(low) == 12
    total = sum(vals)
    observed = sum(int(delta[p]) for p in page_order if p in low)
    threshold = abs(2 * observed - total)
    extreme = sum(abs(2 * sum(split) - total) >= threshold for split in combinations(vals, 12))
    p_perm = extreme / comb(24, 12)
    permutation = {"n_splits": comb(24, 12), "n_as_or_more_extreme": extreme,
                   "p_two_sided_exact": p_perm}
    family.append({"group": "moderator", "comparison": "LOW vs HIGH page-level Δ (exact permutation)",
                   "n_pairs": 24, "basis": "24 page deltas, C(24,12) splits",
                   "delta_pp": (observed / 12 - (total - observed) / 12) / 40 * 100,
                   "b": None, "c": None, "chi2": None, "p_raw": p_perm, "p_exact": p_perm})
    cm = cross_model.load_all()
    ptk, ek = cross_model._page_task_key, cross_model._event_key
    for model in ("gpt-4.1", "gpt-4.1-nano", "claude-sonnet-4-6"):
        bf = {ptk(r): bool(r["success"]) for r in cm[model]
              if r["bundle"] == "B_full" and r["encoding"] == "F1"}
        nv = {ptk(r): bool(r["success"]) for r in cm[model]
              if r["bundle"] == "B_noVolatile" and r["encoding"] == "F1"}
        keys = sorted(bf.keys() & nv.keys())
        family.append(row("cross-model", f"{model}: B_full×F1 → B_noVolatile×F1",
                          {"success_bf": [bf[k] for k in keys], "success_nv": [nv[k] for k in keys]},
                          f"{len(keys)} aligned events"))
    four = ["gpt-4.1", "gpt-4.1-nano", "claude-sonnet-4-6"]
    filt = {m: {ek(r): bool(r["success"]) for r in cm[m] if not cross_model._is_skip_page(r)} for m in four}
    keys = sorted(set(filt[four[0]]).intersection(*[set(filt[m]) for m in four[1:]]))
    for model in ("claude-sonnet-4-6", "gpt-4.1-nano"):
        family.append(row("cross-model", f"fair subset: gpt-4.1 → {model}",
                          {"success_bf": [filt["gpt-4.1"][k] for k in keys],
                           "success_nv": [filt[model][k] for k in keys]}, f"{len(keys)} common events"))
    gcop, ocop = [{ptk(r): bool(r["success"]) for r in cm[m]
                  if (r["bundle"], r["encoding"]) == (cross_model.COP_B, cross_model.COP_E)}
                 for m in ("gpt-4.1", "o4-mini")]
    keys = sorted(gcop.keys() & ocop.keys())
    family.append(row("cross-model", "COP cell: gpt-4.1 → o4-mini",
                      {"success_bf": [gcop[k] for k in keys], "success_nv": [ocop[k] for k in keys]},
                      f"{len(keys)} common events"))
    assert len(family) == 17
    adjust(family)
    return family, permutation


def control_family(family):
    saved = json.loads((OUT / "diagnostics.json").read_text(encoding="utf-8"))["D3"]["holm_family"]
    lines = (OUT / "diagnostics.md").read_text(encoding="utf-8").splitlines()
    start = lines.index("### Holm correction (family of 17 tests)")
    end = lines.index("### Token savings — bootstrap CIs", start)
    displayed = [[s.strip() for s in line.strip("|").split("|")]
                 for line in lines[start:end] if line.startswith("| ")][1:]
    failures = []
    if len(saved) != 17 or len(displayed) != 17:
        failures.append("Family A saved row count differs from 17")
    for i, (r, old, printed) in enumerate(zip(family, saved, displayed), 1):
        for field, value in r.items():
            if value != old.get(field):
                failures.append(f"row {i} {field}: recomputed={value!r}, saved={old.get(field)!r}")
        expected_display = [r["group"], r["comparison"], r["basis"], f"{r['delta_pp']:+.2f}",
                            "" if r["b"] is None else str(r["b"]), "" if r["c"] is None else str(r["c"]),
                            "" if r["chi2"] is None else f"{r['chi2']:.2f}",
                            *[fmt_p(r[k]) for k in ("p_raw", "p_holm", "p_exact", "p_holm_exact")]]
        if printed != expected_display:
            failures.append(f"row {i} differs from diagnostics.md D3: {printed!r} vs {expected_display!r}")
    if failures:
        raise SystemExit("Family A CONTROL FAILED; no outputs written:\n" + "\n".join(failures))


def main():
    before = protected_state()
    df = load_dataframe(REPO)
    assert set(df["model"]) == {"gpt-4.1"}
    family_a, permutation = build_family_a(df)
    control_family(family_a)
    print("Family A control PASS: all 17 full-precision rows and displayed D3 values match.")
    family_b = copy.deepcopy(family_a)
    expected_deltas = [9.48, .31, -19.48, -15.21, -54.79]
    crosschecks = []
    ref_keys = None
    for i, bundle in enumerate(BUNDLE_LADDER_ORDER[1:]):
        pairs = build_pairs(df, "B_full", bundle)
        keys = set(map(tuple, pairs[KEY].to_numpy()))
        assert len(pairs) == len(keys) == 960
        if ref_keys is None:
            ref_keys = keys
        assert keys == ref_keys, "B_full comparisons do not share identical 960 events"
        r = row("bundle ladder", f"B_full → {bundle}", pairs, "960 pairs, F0–F3")
        crosschecks.append({"comparison": r["comparison"], "expected_delta_pp": expected_deltas[i],
                            "actual_delta_pp": r["delta_pp"], "matches": round(r["delta_pp"], 2) == expected_deltas[i]})
        if i == 0:
            crosschecks[-1]["matches"] &= (r["b"], r["c"]) == (102, 11)
        if i == 4:
            crosschecks[-1]["matches"] &= r["b"] == 0
        family_b[i] = r
    assert family_a[5:] == family_b[5:], "Other 12 tests changed before adjustment"
    adjust(family_b)
    a = {r["comparison"]: r for r in family_a}
    b = {r["comparison"]: r for r in family_b}
    labels = list(a)[:5] + [label for label in list(b)[:5] if label not in a] + list(a)[5:]
    table_rows, joined, changed = [], [], []
    def pval(r, field):
        return "—" if r is None else fmt_p(r[field])
    def verdict(r, field):
        return "—" if r is None else ("yes" if r[field] < .05 else "no")
    for label in labels:
        ra, rb = a.get(label), b.get(label)
        r = ra if ra is not None else rb
        change = bool(ra and rb and (verdict(ra, "p_holm") != verdict(rb, "p_holm")
                                    or verdict(ra, "p_holm_exact") != verdict(rb, "p_holm_exact")))
        if change:
            changed.append(label)
        membership = "both" if ra and rb else ("A only" if ra else "B only")
        flag = "**VERDICT CHANGED**" if change else ("—" if membership == "both" else membership)
        sig = f"{verdict(ra, 'p_holm')} / {verdict(rb, 'p_holm')}"
        table_rows.append([label, f"{r['delta_pp']:+.2f}", *["—" if r[k] is None else r[k] for k in ("b", "c")],
                           "—" if r["chi2"] is None else f"{r['chi2']:.2f}", fmt_p(r["p_raw"]),
                           pval(ra, "p_holm"), pval(rb, "p_holm"), fmt_p(r["p_exact"]),
                           pval(ra, "p_holm_exact"), pval(rb, "p_holm_exact"), sig, flag])
        joined.append({"comparison": label, "family_membership": membership, "family_a": ra, "family_b": rb,
                       "significant_chi2_a": None if ra is None else ra["p_holm"] < .05,
                       "significant_chi2_b": None if rb is None else rb["p_holm"] < .05,
                       "significant_exact_a": None if ra is None else ra["p_holm_exact"] < .05,
                       "significant_exact_b": None if rb is None else rb["p_holm_exact"] < .05,
                       "verdict_changed": change})
    headers = ["comparison", "Δ pp", "b", "c", "χ²", "p raw", "p Holm (A)", "p Holm (B)",
               "p exact", "p Holm exact (A)", "p Holm exact (B)",
               "significant at 0.05 after Holm: A / B", "flag"]
    table = md_table(headers, table_rows)
    inputs = sorted(set((REPO / "experiments/runs").glob("matrix_page_*.jsonl"))
                    | set((REPO / "experiments/runs").glob("axisc_*.jsonl"))
                    | {OUT / "diagnostics.md", OUT / "diagnostics.json", OUT / "ladder_composition.md"}
                    | {REPO / "experiments/analysis" / name for name in (
                        "revision1_diagnostics.py", "load.py", "stats.py", "cross_model.py", "bundle_ladder.py")})
    hashes = {p.relative_to(REPO).as_posix(): sha256(p) for p in inputs}
    mismatches = [r for r in crosschecks if not r["matches"]]
    report = {"status": "SENSITIVITY — Holm family definition", "family_size_a": 17, "family_size_b": 17,
              "family_a_control": "PASS: all fields equal diagnostics.json; all displayed columns equal diagnostics.md D3",
              "unchanged_tests": 12, "permutation_control": permutation, "crosschecks": crosschecks,
              "crosscheck_mismatches": mismatches, "verdict_changed_rows": changed,
              "family_a": family_a, "family_b": family_b, "side_by_side": joined, "input_sha256": hashes}
    md = [TITLE, "", "Run: `python -B experiments/analysis/revision1_holm_bfull_family.py`.", "",
          "Family A control: **PASS**. All 17 raw and adjusted p-values (χ² and exact), and all other "
          "row fields, exactly reproduce diagnostics.json; every displayed D3 table value reproduces diagnostics.md. "
          "The exact moderator permutation p is independently recomputed by enumerating all 2,704,156 label splits.", "",
          "Each family contains 17 tests. Family B replaces only the five bundle comparisons; the other "
          "12 hypotheses, pair sets, effects and raw p-values remain unchanged. Holm is recomputed separately "
          "for χ² p-values and exact p-values using the imported diagnostics function.", "",
          "Bundles are not cumulative: B_noVolatile, B_noState and B_noSemantic each change B_full; "
          "B_identityCore and B_minimalCore are fixed sets (ladder_composition.md). Each B_full comparison "
          "uses the same 960 gpt-4.1 pairs across F0–F3, 24 pages × 10 tasks × 4 encodings.", "",
          "The table is the union of the two families (21 distinct hypotheses). “—” means not in that family "
          "or not applicable; it is not a nonsignificant verdict. Δ = second − first; b = second-only "
          "successes, c = first-only. The significance column uses χ² Holm p < 0.05. Flags check both "
          "χ² and exact Holm verdicts on shared hypotheses. Replacement rows are marked A only / B only.", ""]
    md += table + ["", "Shared-hypothesis verdict changes (χ² or exact): " + (", ".join(changed) if changed else "none") + ".",
                   "", "## Table 2 cross-check", ""]
    md += [f"- {r['comparison']}: {r['actual_delta_pp']:+.6f} pp; expected {r['expected_delta_pp']:+.2f}; "
           f"{'PASS' if r['matches'] else 'MISMATCH'}." for r in crosschecks]
    md += ["", "Additional controls: B_full→B_noVolatile b=102, c=11; B_full→B_minimalCore b=0. "
           f"Cross-check mismatches: {mismatches or 'none'}.", "",
           "This is sensitivity to hypothesis-family definition, not a new registered analysis. "
           "No LLM calls or network access occur in the script; all existing evidence and results are read-only.",
           "", "## Input SHA-256", "", "| Input | SHA-256 |", "|---|---|"]
    md += [f"| {path} | {digest} |" for path, digest in hashes.items()]
    payloads = {OUT / "holm_bfull_family.md": "\n".join(md) + "\n",
                OUT / "holm_bfull_family.json": json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"}
    for path, content in payloads.items():
        if path.exists() and path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"Refusing to change existing output: {path}")
    if protected_state() != before:
        raise RuntimeError("Protected file changed during computation")
    for path, content in payloads.items():
        if not path.exists():
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
    after = protected_state()
    assert all(after.get(path) == digest for path, digest in before.items()), "Existing protected file changed"
    print("\n".join(table))
    print(f"Verdict changes: {changed or 'none'}; Table 2 mismatches: {mismatches or 'none'}")
    print(f"Existing protected files unchanged: {len(before)}")


if __name__ == "__main__":
    main()
