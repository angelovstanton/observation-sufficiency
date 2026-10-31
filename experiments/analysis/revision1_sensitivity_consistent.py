"""
Sensitivity: B_noVolatileConsistent (NVC) vs B_full.

NVC event set, 24 pages × 10 targets × F0–F3 = 960 events:
  - "new_run": the 24 (page, encoding) cells whose NVC observation differs from
    B_noVolatile (consistent_cells.json), records from consistent_runs/consistent_<page>.jsonl
    (gpt-4.1, temperature 0, same prompt/regime/rep as the corpus);
  - "original_B_noVolatile": the other 72 cells, observation byte-identical, stored record reused.

Statistics as in revision1_diagnostics.py: McNemar (uncorrected χ², exact p), OR = b/c with
exact conditional CI, page-clustered percentile bootstrap (10,000, seed 42), Pareto walk, COP rule.

Output: experiments/results/revision1/sensitivity_consistent.md / sensitivity_consistent.json
"""
from __future__ import annotations

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import re
import json
import pathlib

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from load import load_dataframe, DOM_ENCODINGS as _DOM_ENC          # noqa: E402
from revision1_diagnostics import (                                  # noqa: E402
    REPO, OUT_DIR, TRUTH_DIR, KEY, PRED_COLS, protected_state, jsonable, md_table, state_of,
    mcnemar, page_bootstrap, pct_ci, pareto_walk, cop_of, build_pairs, fmt_p, fmt_or,
)

DOM_ENCODINGS = sorted(_DOM_ENC)
NVC, NV, BF, MCP = "B_noVolatileConsistent", "B_noVolatile", "B_full", "B_playwrightMCP"
RUNS_DIR   = OUT_DIR / "consistent_runs"
CELLS_FILE = OUT_DIR / "consistent_cells.json"
OBS_DIR    = OUT_DIR / "observations"
STATES = ["success", "grabbed", "lacked", "unreach"]
PREDS = {"P5": "original five-condition predicate (success field)",
         "P_now": "conditions 1+2 (unique match AND matches oracle)",
         "P_now_np": "conditions 1+2+4 (unique, oracle, non-positional)"}
COLS = {"P5": "P5", "P_now": "Pnow", "P_now_np": "Pnownp"}
AFFECTED = ["page_17", "page_18", "page_21", "page_22", "page_23", "page_24"]


def delta_stat(t):
    return (t["nv"] / t["n"] - t["bf"] / t["n"]) * 100


def add_relaxed(frame):
    for side in ("bf", "nv"):
        u = frame[f"predicate_unique_match_{side}"].astype(bool)
        o = frame[f"predicate_matches_oracle_{side}"].astype(bool)
        frame[f"P5_{side}"] = frame[f"success_{side}"].astype(bool)
        frame[f"Pnow_{side}"] = u & o
        frame[f"Pnownp_{side}"] = u & o & frame[f"predicate_non_positional_{side}"].astype(bool)
    return frame


def predicate_block(frame):
    """P5 / P_now / P_now_np on one paired frame (_bf first, _nv second); bootstrap over its pages."""
    order = list(frame["page"].unique())
    out = {}
    for name, col in COLS.items():
        res = mcnemar(frame[f"{col}_bf"], frame[f"{col}_nv"])
        g = frame.groupby("page", sort=False)
        arrays = {"bf": g[f"{col}_bf"].sum().reindex(order).to_numpy(dtype=float),
                  "nv": g[f"{col}_nv"].sum().reindex(order).to_numpy(dtype=float),
                  "n":  g[f"{col}_bf"].count().reindex(order).to_numpy(dtype=float)}
        res["boot_ci_lo_pp"], res["boot_ci_hi_pp"] = pct_ci(page_bootstrap(order, arrays, delta_stat))
        res["n_pages"] = len(order)
        res["definition"] = PREDS[name]
        out[name] = res
    return out


def pred_rows(block, first, second, label=None):
    rows = []
    for n, r in block.items():
        rows.append(([label] if label is not None else []) + [
            n, f"{r['success_first']}/{r['n']} ({r['rate_first_pct']:.2f}%)",
            f"{r['success_second']}/{r['n']} ({r['rate_second_pct']:.2f}%)", f"{r['delta_pp']:+.2f}",
            r["n11_both"], r["b_second_only"], r["c_first_only"], r["n00_neither"],
            "n/a" if np.isnan(r["chi2"]) else f"{r['chi2']:.2f}", fmt_p(r["p"]), fmt_p(r["p_exact"]),
            "n/a" if np.isnan(r["odds_ratio"]) else fmt_or(r["odds_ratio"]),
            "n/a" if np.isnan(r["or_ci_lo"]) else f"[{r['or_ci_lo']:.2f}, {fmt_or(r['or_ci_hi'])}]",
            f"[{r['boot_ci_lo_pp']:+.2f}, {r['boot_ci_hi_pp']:+.2f}]"])
    return rows


def pred_headers(first, second, label=None):
    return ([label] if label else []) + [
        "predicate", first, second, "Δ pp", "both", f"{second}-only (b)", f"{first}-only (c)", "neither",
        "χ² (uncorr.)", "p", "p exact", "OR = b/c", "OR 95% CI (exact cond.)", "bootstrap 95% CI Δ pp"]


def target_strata():
    none_t, text_only = set(), set()
    for tf in sorted(TRUTH_DIR.glob("*.truth.json")):
        tj = json.loads(tf.read_text(encoding="utf-8"))
        for t in tj["targets"]:
            sa = t["signal_attrs"]
            if not sa:
                none_t.add((tj["page_id"], t["id"]))
            elif all(a == "text" for a in sa):
                text_only.add((tj["page_id"], t["id"]))
    return none_t, text_only


def assemble_nvc(df):
    """The 960-event NVC set: 240 new_run records + the 720 stored B_noVolatile records of the
    72 byte-identical cells (relabelled NVC). Returns (nvc, nv, new, cells)."""
    cells = {(c["page"], c["encoding"]) for c in json.loads(CELLS_FILE.read_text(encoding="utf-8"))}
    new = pd.concat([pd.read_json(f, lines=True) for f in sorted(RUNS_DIR.glob("consistent_page_*.jsonl"))],
                    ignore_index=True)
    new["page"] = new["page"].str.extract(r"(page_\d{2})", expand=False)
    assert len(new) == 240, f"expected 240 new records, found {len(new)}"
    assert set(new.bundle) == {NVC} and set(new.model) == {"gpt-4.1"} and set(new.regime) == {"full_page"}
    assert set(new.repetition) == {0} and set(new.tokenizer_version) == {"o200k_base"}
    assert {(p, e) for p, e in zip(new.page, new.encoding)} == cells
    assert not new.duplicated(KEY).any()
    new["success"] = new["success"].astype(bool)
    new["stable_signal_present_in_bundle"] = new["stable_signal_present_in_bundle"].astype(bool)
    new["source"] = "new_run"

    nv = df[(df.bundle == NV) & df.encoding.isin(DOM_ENCODINGS)]
    orig = nv[[(p, e) not in cells for p, e in zip(nv.page, nv.encoding)]].copy()
    assert len(orig) == 720
    orig["bundle"] = NVC
    orig["source"] = "original_B_noVolatile (identical observation)"
    cols = list(dict.fromkeys(KEY + PRED_COLS + ["bundle", "model", "observation_tokens", "prompt_tokens_total",
                                                 "completion_tokens", "locator_raw", "source"]))
    nvc = pd.concat([new[cols], orig[cols]], ignore_index=True)
    assert len(nvc) == 960 and not nvc.duplicated(KEY).any()
    return nvc, nv, new, cells


def short_hash_tokens():
    """(page, token) class tokens of the CSS-module shape `Name_x__hash` with a 1–4 character
    middle segment that the predicate does not flag (DOM census of DUMP_OBSERVATIONS=1)."""
    census = json.loads((OBS_DIR / "token_census.json").read_text(encoding="utf-8"))
    short_rx = re.compile(r"^[A-Za-z]+_[A-Za-z0-9]{1,4}__[A-Za-z0-9]+$")
    return [(r["page"], r["token"]) for r in census
            if r["kind"] == "class" and short_rx.match(r["token"]) and not r["predicate_flags"]]


def main():
    before = protected_state()
    df = load_dataframe(REPO)
    nvc, nv, new, cells = assemble_nvc(df)

    # Run checks: observation tokens == dumped NVC tokens; condition 5 == stored B_noVolatile
    man = pd.read_csv(OBS_DIR / "manifest.tsv", sep="\t", dtype={"sha256": str})
    man_tok = man[man.bundle == NVC].set_index(["page", "encoding"])["tokens"]
    tok_mismatch = [f"{r.page} {r.encoding} {r.task_id}: {r.observation_tokens} vs {man_tok.loc[(r.page, r.encoding)]}"
                    for r in new.itertuples() if r.observation_tokens != man_tok.loc[(r.page, r.encoding)]]
    nv_idx = nv.set_index(KEY)
    c5_mismatch = [f"{r.page} {r.encoding} {r.task_id}" for r in new.itertuples()
                   if bool(r.stable_signal_present_in_bundle)
                   != bool(nv_idx.loc[(r.page, r.task_id, r.encoding, r.repetition), "stable_signal_present_in_bundle"])]
    checks = {"new_obs_tokens_equal_dump": len(tok_mismatch) == 0, "tok_mismatch": tok_mismatch,
              "new_condition5_equal_B_noVolatile": len(c5_mismatch) == 0, "c5_mismatch": c5_mismatch}

    df2 = pd.concat([df, nvc.assign(semantic_density=np.nan)], ignore_index=True)
    none_t, text_only = target_strata()
    no_attr = none_t | text_only

    def strata(frame):
        frame["stratum"] = ["NONE" if (p, k) in none_t else "text_only_signal" if (p, k) in text_only
                            else "has_attribute_signal" for p, k in zip(frame.page, frame.task_id)]
        frame["no_attr"] = [(p, k) in no_attr for p, k in zip(frame.page, frame.task_id)]
        return frame

    groups = {
        "all": lambda f: np.ones(len(f), dtype=bool),
        "has_attribute_signal": lambda f: f["stratum"] == "has_attribute_signal",
        "NONE": lambda f: f["stratum"] == "NONE",
        "text_only_signal": lambda f: f["stratum"] == "text_only_signal",
        "no_attribute_signal (NONE + text-only)": lambda f: f["no_attr"],
    }

    # Main 960 pairs: B_full vs NVC (and B_full vs NV for reference)
    pairs = strata(add_relaxed(build_pairs(df2, BF, NVC)))
    ref = strata(add_relaxed(build_pairs(df2, BF, NV)))
    assert len(pairs) == 960 and len(ref) == 960
    assert (pairs[KEY].values == ref[KEY].values).all()
    src = nvc.set_index(KEY)["source"]
    pairs["source"] = [src.loc[tuple(k)] for k in pairs[KEY].values]
    checks["no_attr_equals_cond5_false_NVC"] = bool(
        (pairs["no_attr"] == ~pairs["stable_signal_present_in_bundle_nv"].astype(bool)).all())

    main_blocks = {g: predicate_block(pairs[sel(pairs)]) for g, sel in groups.items()}
    ref_blocks = {g: predicate_block(ref[sel(ref)]) for g, sel in groups.items()}

    pairs["state_bf"] = [state_of(s, f) for s, f in zip(pairs.success_bf, pairs.failure_mode_bf)]
    pairs["state_nv"] = [state_of(s, f) for s, f in zip(pairs.success_nv, pairs.failure_mode_nv)]
    ref["state_nv"] = [state_of(s, f) for s, f in zip(ref.success_nv, ref.failure_mode_nv)]
    trans = pd.crosstab(pairs.state_bf, pairs.state_nv).reindex(index=STATES, columns=STATES, fill_value=0)
    trans_ref = pd.crosstab(pairs.state_bf, ref.state_nv).reindex(index=STATES, columns=STATES, fill_value=0)
    newmask = pairs.source == "new_run"
    trans_nv_nvc_new = pd.crosstab(ref.state_nv[newmask], pairs.state_nv[newmask]).reindex(
        index=STATES, columns=STATES, fill_value=0)
    vol_nv = int((~pairs.loc[:, "predicate_non_volatile_nv"].astype(bool)).sum())
    vol_ref = int((~ref.predicate_non_volatile_nv.astype(bool)).sum())
    grabbed_vol = {
        "NVC_grabbed": int((pairs.state_nv == "grabbed").sum()),
        "NVC_grabbed_volatile": int(((pairs.state_nv == "grabbed")
                                     & ~pairs.predicate_non_volatile_nv.astype(bool)).sum()),
        "NV_grabbed": int((ref.state_nv == "grabbed").sum()),
        "NV_grabbed_volatile": int(((ref.state_nv == "grabbed") & ~ref.predicate_non_volatile_nv.astype(bool)).sum()),
        "NVC_non_volatile_false_all": vol_nv, "NV_non_volatile_false_all": vol_ref,
    }

    # NV vs NVC on the 240 re-run events (first = NV, second = NVC)
    nn = ref[newmask][KEY + [c + "_nv" for c in PRED_COLS]].copy()
    nn.columns = KEY + [c + "_bf" for c in PRED_COLS]
    nn = nn.merge(pairs[newmask][KEY + [c + "_nv" for c in PRED_COLS]], on=KEY)
    nn = add_relaxed(nn)
    nv_vs_nvc_new = predicate_block(nn)

    # COP cell: NVC×F3 vs B_full×F1 (240)
    k3 = ["page", "task_id", "repetition"]
    cop = (df2[(df2.bundle == BF) & (df2.encoding == "F1")][k3 + PRED_COLS]
           .merge(df2[(df2.bundle == NVC) & (df2.encoding == "F3")][k3 + PRED_COLS], on=k3, suffixes=("_bf", "_nv")))
    cop_ref = (df2[(df2.bundle == BF) & (df2.encoding == "F1")][k3 + PRED_COLS]
               .merge(df2[(df2.bundle == NV) & (df2.encoding == "F3")][k3 + PRED_COLS], on=k3, suffixes=("_bf", "_nv")))
    assert len(cop) == 240 and len(cop_ref) == 240
    cop, cop_ref = strata(add_relaxed(cop)), strata(add_relaxed(cop_ref))
    cop_blocks = {g: predicate_block(cop[sel(cop)]) for g, sel in groups.items()}
    cop_ref_blocks = {g: predicate_block(cop_ref[sel(cop_ref)]) for g, sel in groups.items()}

    # Tokens and Pareto (25 cells)
    bundles = [BF, NV, "B_noState", "B_noSemantic", "B_identityCore", NVC]
    recs = df2[(df2.bundle.isin(bundles) & df2.encoding.isin(DOM_ENCODINGS)) | (df2.bundle == MCP)]
    assert len(recs) == 5040 + 960
    pc = recs.groupby(["bundle", "encoding"]).agg(
        n_success=("success", "sum"), n_records=("success", "count"),
        mean_obs_tokens=("observation_tokens", "mean"), mean_api_prompt_tokens=("prompt_tokens_total", "mean"))
    pc["success_rate"] = pc.n_success / pc.n_records
    walk_obs = pareto_walk(pc, "mean_obs_tokens")
    walk_api = pareto_walk(pc, "mean_api_prompt_tokens")
    cop_obs, cop_api = cop_of(walk_obs), cop_of(walk_api)
    walk21 = pareto_walk(pc.drop(index=[(NVC, e) for e in DOM_ENCODINGS]), "mean_obs_tokens")
    tok = pc.mean_obs_tokens
    tokens = {
        f"{b}×{e}": float(tok[(b, e)]) for b in (BF, NV, NVC) for e in DOM_ENCODINGS}
    tokens["B_playwrightMCP×F4"] = float(tok[(MCP, "F4")])
    reductions = {
        "NVC×F3 vs B_full×F1 %": (tok[(BF, "F1")] - tok[(NVC, "F3")]) / tok[(BF, "F1")] * 100,
        "NV×F3 vs B_full×F1 % (published COP)": (tok[(BF, "F1")] - tok[(NV, "F3")]) / tok[(BF, "F1")] * 100,
        "NVC×F3 vs NV×F3 %": (tok[(NV, "F3")] - tok[(NVC, "F3")]) / tok[(NV, "F3")] * 100,
        "NVC×F3 vs NVC×F1 %": (tok[(NVC, "F1")] - tok[(NVC, "F3")]) / tok[(NVC, "F1")] * 100,
    }

    # Per page (6 affected pages) and page_17 / page_18 vs F4
    def rate(b, p, e):
        s = df2[(df2.bundle == b) & (df2.page == p) & (df2.encoding == e)]
        return int(s.success.sum()), len(s)

    per_page = []
    for p in AFFECTED:
        for e in DOM_ENCODINGS:
            bf_s, _ = rate(BF, p, e)
            nv_s, _ = rate(NV, p, e)
            nvc_s, n = rate(NVC, p, e)
            src_e = nvc[(nvc.page == p) & (nvc.encoding == e)].source.iloc[0]
            per_page.append({"page": p, "encoding": e, "source": src_e, "B_full": bf_s, "B_noVolatile": nv_s,
                             NVC: nvc_s, "n": n,
                             "obs_tokens_NV": int(df2[(df2.bundle == NV) & (df2.page == p)
                                                      & (df2.encoding == e)].observation_tokens.iloc[0]),
                             "obs_tokens_NVC": int(df2[(df2.bundle == NVC) & (df2.page == p)
                                                       & (df2.encoding == e)].observation_tokens.iloc[0])})
    per_page_df = pd.DataFrame(per_page)
    page_tot = per_page_df.groupby("page")[[BF, NV, NVC, "n"]].sum().reset_index()

    # Per-target changes NV -> NVC on re-run events
    flips = []
    for r in nn.itertuples():
        if r.P5_bf != r.P5_nv:
            nvc_row = pairs[(pairs.page == r.page) & (pairs.task_id == r.task_id) & (pairs.encoding == r.encoding)].iloc[0]
            ref_row = ref[(ref.page == r.page) & (ref.task_id == r.task_id) & (ref.encoding == r.encoding)].iloc[0]
            flips.append({"page": r.page, "task_id": r.task_id, "encoding": r.encoding,
                          "NV_state": ref_row.state_nv, "NVC_state": nvc_row.state_nv,
                          "NV_locator": ref_row.locator_value_nv, "NVC_locator": nvc_row.locator_value_nv})

    crossover = []
    for p in ("page_17", "page_18"):
        f4_s, f4_n = rate(MCP, p, "F4")
        row = {"page": p, "F4_success": f4_s, "F4_n": f4_n}
        for b in (NV, NVC):
            per_enc = {e: rate(b, p, e)[0] for e in DOM_ENCODINGS}
            row[b] = {"per_encoding": per_enc, "total": sum(per_enc.values()), "n": 40,
                      "max_encoding_rate_pct": max(per_enc.values()) * 10, "mean_rate_pct": sum(per_enc.values()) / 40 * 100,
                      "encodings_below_F4": [e for e in DOM_ENCODINGS if per_enc[e] < f4_s],
                      "encodings_equal_F4": [e for e in DOM_ENCODINGS if per_enc[e] == f4_s],
                      "encodings_above_F4": [e for e in DOM_ENCODINGS if per_enc[e] > f4_s]}
        # per target: F4 vs NVC best-encoding / any-encoding
        tgt = []
        for t in sorted(df2[(df2.page == p)].task_id.unique()):
            f4 = bool(df2[(df2.bundle == MCP) & (df2.page == p) & (df2.task_id == t)].success.iloc[0])
            nvc_e = {e: bool(df2[(df2.bundle == NVC) & (df2.page == p) & (df2.task_id == t)
                                 & (df2.encoding == e)].success.iloc[0]) for e in DOM_ENCODINGS}
            nv_e = {e: bool(df2[(df2.bundle == NV) & (df2.page == p) & (df2.task_id == t)
                                & (df2.encoding == e)].success.iloc[0]) for e in DOM_ENCODINGS}
            tgt.append({"task_id": t, "F4": f4, "NV": nv_e, "NVC": nvc_e})
        row["targets"] = tgt
        crossover.append(row)

    # Report
    n_new, n_orig = int((nvc.source == "new_run").sum()), int((nvc.source != "new_run").sum())
    L = ["# Revision 1 — sensitivity: B_noVolatileConsistent vs B_full", "",
         "Facts only. B_noVolatileConsistent (NVC) removes every class/id token that the success predicate "
         "flags (`Oracle.LocatorUsesVolatileSignal`), in addition to what B_noVolatile (NV) removes "
         "(see `leak_scope.md`). Event set (960 = 24 pages × 10 targets × F0–F3):", "",
         f"- **new_run** — {n_new} records: the 24 (page, encoding) cells whose NVC observation differs from NV "
         "(page_17, page_18, page_21, page_22, page_23, page_24 × F0–F3); `SENSITIVITY_CONSISTENT=1`, gpt-4.1, "
         "temperature 0, full_page, repetition 0, canonical prompt; `experiments/results/revision1/consistent_runs/`.",
         f"- **original_B_noVolatile (identical observation)** — {n_orig} records: the 72 cells whose NVC "
         "observation is byte-identical to NV; the stored corpus NV record is used unchanged.", "",
         "Statistics: McNemar uncorrected χ² and exact binomial p; OR = b/c with exact conditional 95% CI; "
         "page-clustered percentile bootstrap of Δ (10,000 replicates, seed 42, draw sequence of `stats.py`). "
         "The NV columns repeat the corpus numbers for side-by-side reading.", "",
         "Run checks: new-record observation tokens equal the dumped NVC tokens: "
         f"{'yes' if checks['new_obs_tokens_equal_dump'] else 'NO ' + str(tok_mismatch[:5])}; "
         "new-record condition 5 equals the stored NV record: "
         f"{'yes' if checks['new_condition5_equal_B_noVolatile'] else 'NO ' + str(c5_mismatch[:5])}; "
         "no_attribute_signal events = condition-5-false events under NVC: "
         f"{'yes' if checks['no_attr_equals_cond5_false_NVC'] else 'NO'}.", "",
         "## 1. B_full vs B_noVolatileConsistent — 960 pairs", ""]
    L += md_table(pred_headers("B_full", "NVC"), pred_rows(main_blocks["all"], "B_full", "NVC"))
    L += ["", "Reference — B_full vs B_noVolatile (corpus), same 960 pairs:", ""]
    L += md_table(pred_headers("B_full", "NV"), pred_rows(ref_blocks["all"], "B_full", "NV"))
    L += ["", "### 1a. By target design stratum (D1b)", ""]
    rows = []
    for g in list(groups)[1:]:
        rows += pred_rows(main_blocks[g], "B_full", "NVC", label=f"{g} (n={main_blocks[g]['P5']['n']})")
    L += md_table(pred_headers("B_full", "NVC", label="stratum"), rows)
    L += ["", "Reference — B_full vs NV by stratum:", ""]
    rows = []
    for g in list(groups)[1:]:
        rows += pred_rows(ref_blocks[g], "B_full", "NV", label=f"{g} (n={ref_blocks[g]['P5']['n']})")
    L += md_table(pred_headers("B_full", "NV", label="stratum"), rows)
    L += ["", "### 1b. Transition matrices", "",
          "B_full state → NVC state (960):", ""]
    L += md_table(["B_full ↓ / NVC →"] + STATES + ["total"],
                  [[s] + [int(trans.loc[s, t]) for t in STATES] + [int(trans.loc[s].sum())] for s in STATES]
                  + [["total"] + [int(trans[t].sum()) for t in STATES] + [int(trans.values.sum())]])
    L += ["", "Reference — B_full state → NV state (960):", ""]
    L += md_table(["B_full ↓ / NV →"] + STATES + ["total"],
                  [[s] + [int(trans_ref.loc[s, t]) for t in STATES] + [int(trans_ref.loc[s].sum())] for s in STATES]
                  + [["total"] + [int(trans_ref[t].sum()) for t in STATES] + [int(trans_ref.values.sum())]])
    L += ["", f"NV state → NVC state on the {n_new} re-run events (the other {n_orig} are identical by construction):", ""]
    L += md_table(["NV ↓ / NVC →"] + STATES + ["total"],
                  [[s] + [int(trans_nv_nvc_new.loc[s, t]) for t in STATES] + [int(trans_nv_nvc_new.loc[s].sum())]
                   for s in STATES])
    L += ["", f"Volatile locators (`predicate_non_volatile = false`), all 960: NVC {grabbed_vol['NVC_non_volatile_false_all']}, "
          f"NV {grabbed_vol['NV_non_volatile_false_all']}. Grabbed: NVC {grabbed_vol['NVC_grabbed']} "
          f"(volatile {grabbed_vol['NVC_grabbed_volatile']}), NV {grabbed_vol['NV_grabbed']} "
          f"(volatile {grabbed_vol['NV_grabbed_volatile']}).", "",
          f"### 1c. NV vs NVC on the {n_new} re-run events", ""]
    L += md_table(pred_headers("NV", "NVC"), pred_rows(nv_vs_nvc_new, "NV", "NVC"))

    L += ["", "## 2. COP cell — NVC×F3 vs B_full×F1 (240 pairs)", ""]
    rows = []
    for g in groups:
        rows += pred_rows(cop_blocks[g], "B_full×F1", "NVC×F3", label=f"{g} (n={cop_blocks[g]['P5']['n']})")
    L += md_table(pred_headers("B_full×F1", "NVC×F3", label="stratum"), rows)
    L += ["", "Reference — NV×F3 (published COP) vs B_full×F1:", ""]
    rows = []
    for g in groups:
        rows += pred_rows(cop_ref_blocks[g], "B_full×F1", "NV×F3", label=f"{g} (n={cop_ref_blocks[g]['P5']['n']})")
    L += md_table(pred_headers("B_full×F1", "NV×F3", label="stratum"), rows)

    L += ["", "## 3. Tokens (mean observation tokens per event, o200k_base)", ""]
    L += md_table(["encoding", "B_full", "B_noVolatile", "NVC", "NVC − NV"],
                  [[e, f"{tok[(BF, e)]:,.1f}", f"{tok[(NV, e)]:,.1f}", f"{tok[(NVC, e)]:,.1f}",
                    f"{tok[(NVC, e)] - tok[(NV, e)]:+,.1f}"] for e in DOM_ENCODINGS])
    L += ["", f"B_playwrightMCP×F4: {tok[(MCP, 'F4')]:,.1f}.", ""]
    L += md_table(["reduction", "%"], [[k, f"{v:.1f}"] for k, v in reductions.items()])

    L += ["", "## 4. Pareto position (25 cells: the 21 published cells + 4 NVC cells)", "",
          "Frontier walk of `pareto.py` (sort by cost, keep strictly improving success); COP rule = first "
          "frontier cell with success > 50%.", ""]
    for label, w, copc, cost_col in (("observation tokens (o200k_base)", walk_obs, cop_obs, "mean_obs_tokens"),
                                     ("prompt tokens (`prompt_tokens_total`)", walk_api, cop_api,
                                      "mean_api_prompt_tokens")):
        L += [f"*Cost = {label}*", ""]
        L += md_table(["bundle", "enc", "success", "mean cost", "status"],
                      [[b, e, f"{r.n_success}/{r.n_records} ({r.success_rate * 100:.2f}%)",
                        f"{r[cost_col]:,.1f}",
                        r.pareto_status] for (b, e), r in w.iterrows()])
        L += ["", f"COP under this cost: {copc[0]}×{copc[1]}. Frontier: "
              + ", ".join(f"{b}×{e}" for (b, e), r in w.iterrows() if r.pareto_status == "FRONTIER") + ".", ""]
    L += ["Frontier without the NVC cells (21 cells, observation tokens): "
          + ", ".join(f"{b}×{e}" for (b, e), r in walk21.iterrows() if r.pareto_status == "FRONTIER")
          + f"; COP {cop_of(walk21)[0]}×{cop_of(walk21)[1]}.", ""]

    L += ["## 5. Per page — the six affected pages (successes out of 10 per cell)", ""]
    L += md_table(["page", "enc", "NVC source", "B_full", "NV", "NVC", "obs tokens NV", "obs tokens NVC"],
                  [[r.page, r.encoding, r.source, r.B_full, r.B_noVolatile, r[NVC], f"{r.obs_tokens_NV:,}",
                    f"{r.obs_tokens_NVC:,}"] for _, r in per_page_df.iterrows()])
    L += ["", "Page totals over F0–F3 (out of 40):", ""]
    L += md_table(["page", "B_full", "NV", "NVC"], [[r.page, r[BF], r[NV], r[NVC]] for _, r in page_tot.iterrows()])
    L += ["", f"Events that change P5 outcome NV → NVC ({len(flips)}):", ""]
    L += md_table(["page", "task", "enc", "NV state", "NVC state", "NV locator", "NVC locator"],
                  [[f["page"], f["task_id"], f["encoding"], f["NV_state"], f["NVC_state"],
                    f"`{str(f['NV_locator']).replace('|', '¦')}`", f"`{str(f['NVC_locator']).replace('|', '¦')}`"]
                   for f in flips])

    L += ["", "## 6. page_17 / page_18 — NVC vs B_playwrightMCP×F4", "",
          "FINDINGS.md line 55 states p17: F4 40% vs NV 20%; p18: F4 50% vs NV 30% (these NV figures equal "
          "the best NV encoding per page: p17 F2, p18 F1/F2/F3).", ""]
    rows = []
    for c in crossover:
        for b in (NV, NVC):
            d = c[b]
            rows.append([c["page"], b] + [d["per_encoding"][e] for e in DOM_ENCODINGS]
                        + [f"{d['total']}/40 ({d['mean_rate_pct']:.1f}%)", f"{d['max_encoding_rate_pct']:.0f}%",
                           f"{c['F4_success']}/{c['F4_n']} ({c['F4_success'] * 10}%)",
                           ", ".join(d["encodings_above_F4"]) or "none",
                           ", ".join(d["encodings_equal_F4"]) or "none"])
    L += md_table(["page", "bundle"] + DOM_ENCODINGS + ["total", "best encoding", "F4", "encodings > F4",
                                                         "encodings = F4"], rows)
    for c in crossover:
        L += ["", f"{c['page']} per target (1 = success):", ""]
        L += md_table(["task", "F4"] + [f"NV {e}" for e in DOM_ENCODINGS] + [f"NVC {e}" for e in DOM_ENCODINGS],
                      [[t["task_id"], int(t["F4"])] + [int(t["NV"][e]) for e in DOM_ENCODINGS]
                       + [int(t["NVC"][e]) for e in DOM_ENCODINGS] for t in c["targets"]])

    # 7. CSS-module-shaped class tokens that VolatileClassRe does not match
    # VolatileClassRe's second alternative needs ≥5 characters between "_" and "__"
    # (`[A-Za-z]+_[A-Za-z0-9]{5,}__`); tokens with a 1–4 character middle segment are not flagged.
    short = short_hash_tokens()
    short_by_page = {}
    for pg, t in short:
        short_by_page.setdefault(pg, []).append(t)

    def uses_short(frame, loc_col):
        return frame[[any(t in str(l or "") for t in short_by_page.get(pg, []))
                      for pg, l in zip(frame.page, frame[loc_col])]]
    short_use = {}
    for label, frame in (("NVC (960)", nvc), ("B_noVolatile (960)", nv),
                         ("B_full F0–F3 (960)", df[(df.bundle == BF) & df.encoding.isin(DOM_ENCODINGS)])):
        u = uses_short(frame, "locator_raw")
        short_use[label] = {"locators_using": int(len(u)), "of_which_success": int(u.success.astype(bool).sum())}
    L += ["", "## 7. CSS-module-shaped class tokens not matched by `VolatileClassRe`", "",
          "`VolatileClassRe` flags `Name_xxxxx__hash` only when the middle segment has ≥ 5 characters "
          "(`[A-Za-z]+_[A-Za-z0-9]{5,}__`). Class tokens of the form `Name_x__hash` with a 1–4 character middle "
          f"segment are not flagged by the predicate, so both NV and NVC keep them: {len(short)} distinct "
          f"(page, token) in the DOM census, pages "
          + ", ".join(f"{pg} {len(v)}" for pg, v in sorted(short_by_page.items()))
          + f". Examples: {', '.join(f'`{t}`' for _, t in short[:6])}.", ""]
    L += md_table(["event set", "locators containing such a token", "of which P5 success"],
                  [[k, v["locators_using"], v["of_which_success"]] for k, v in short_use.items()])

    after = protected_state()
    assert before == after, "protected files changed during the run"
    L += ["", f"Protected files (FINDINGS.md, 24 matrix, 71 axisc, 24 truth) unchanged: {len(before)} SHA-256 equal.", ""]

    (OUT_DIR / "sensitivity_consistent.md").write_text("\n".join(L), encoding="utf-8", newline="\n")
    (OUT_DIR / "sensitivity_consistent.json").write_text(json.dumps(jsonable({
        "event_set": {"new_run": n_new, "original_B_noVolatile": n_orig, "cells_new": sorted(map(list, cells))},
        "checks": checks,
        "main_960": main_blocks, "main_960_reference_NV": ref_blocks,
        "transitions_BF_to_NVC": trans.to_dict(), "transitions_BF_to_NV": trans_ref.to_dict(),
        "transitions_NV_to_NVC_rerun": trans_nv_nvc_new.to_dict(), "volatile_and_grabbed": grabbed_vol,
        "NV_vs_NVC_rerun_240": nv_vs_nvc_new,
        "cop_240": cop_blocks, "cop_240_reference_NV": cop_ref_blocks,
        "tokens_mean_obs": tokens, "token_reductions_pct": reductions,
        "pareto_obs": [{"bundle": b, "encoding": e, **r.to_dict()} for (b, e), r in walk_obs.iterrows()],
        "pareto_api": [{"bundle": b, "encoding": e, **r.to_dict()} for (b, e), r in walk_api.iterrows()],
        "cop_obs": list(cop_obs), "cop_api": list(cop_api),
        "per_page": per_page_df.to_dict("records"), "page_totals": page_tot.to_dict("records"),
        "nv_to_nvc_flips": flips, "crossover": crossover,
        "short_middle_css_module_tokens": {"tokens": short, "locator_use": short_use},
        "events": nvc.sort_values(KEY)[KEY + ["source", "success", "failure_mode", "locator_raw",
                                               "observation_tokens", "prompt_tokens_total"]].to_dict("records"),
    }), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
