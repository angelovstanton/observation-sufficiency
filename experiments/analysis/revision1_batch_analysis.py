"""
Analysis of the batch run (Blocks 1–4); zero LLM, zero network.

Implements experiments/results/revision1/batch_analysis_plan.md (committed before any batch
outcome was read); only the section labelled Exploratory goes beyond it.

Inputs
  - experiments/results/revision1/batch_runs/: journal.jsonl, batch_*.jsonl (4,500 records),
    released_keys.md (plan batch_plan.json, sha256 567c370855a2…).
  - Rep 1 / reference arms from the corpus: gpt-4.1 experiments/runs/matrix_page_*.jsonl;
    gpt-4.1-nano and o4-mini experiments/runs/axisc_*_page_*.jsonl.  Block-1 reused cells are
    rebuilt from the corpus records they reuse.

Outcomes: P5 = success (primary); P_now = condition 1 ∧ 2 (secondary).  Pairs are matched on
(page, task_id) within the plan's (encoding, rep).  McNemar (uncorrected χ², exact p),
OR = b/c with exact conditional CI, page-clustered percentile bootstrap (10,000, seed 42),
Holm sets as in the plan's Multiplicity section.

Guard: SHA-256 of FINDINGS.md, 24 matrix, 71 axisc, 24 truth files before and after.
Output: experiments/results/revision1/batch_analysis.md / batch_analysis.json
"""
from __future__ import annotations

import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import collections   # noqa: E402
import hashlib       # noqa: E402
import json          # noqa: E402
import math          # noqa: E402
import re            # noqa: E402

import numpy as np    # noqa: E402
import pandas as pd   # noqa: E402

from load import load_dataframe                                             # noqa: E402
from revision1_diagnostics import (                                         # noqa: E402
    REPO, OUT_DIR, RUNS, TRUTH_DIR, N_BOOT, SEED, LACKED, GRABBED, UNREACHABLE,
    Controls, protected_state, jsonable, md_table, fmt_p, fmt_or, mcnemar,
    page_bootstrap, pct_ci, holm,
)

BATCH_DIR = OUT_DIR / "batch_runs"
PLAN_JSON = OUT_DIR / "batch_plan.json"
PLAN_MD   = OUT_DIR / "batch_analysis_plan.md"
DUMP_MANIFEST = OUT_DIR / "batch_observations" / "manifest.tsv"
OBS_MANIFEST  = OUT_DIR / "observations" / "manifest.tsv"
OUT_MD   = OUT_DIR / "batch_analysis.md"
OUT_JSON = OUT_DIR / "batch_analysis.json"

PLAN_SHA_PREFIX = "567c370855a2"
JOURNAL_SHA = "e7984c9f4388d23b42006a12c04ad7cae2e7073500b62c1e4bb720b07dac93f9"
BLOCK_COUNTS = {"1": 660, "2": 720, "3": 2880, "4": 240}
PAGES = [f"page_{n:02d}" for n in range(1, 25)]
REPS = [1, 2, 3]
PREDS = {"P5": "P5", "P_now": "Pnow"}
STRATA = ["has_attribute_signal", "no_attribute_signal"]
NON_ATTRIBUTE_SIGNALS = {"text"}       # as D1b in revision1_diagnostics
GPT, NANO, O4 = "gpt-4.1", "gpt-4.1-nano", "o4-mini"
ABLATIONS = ["B_full_minus_volClass", "B_full_minus_volId", "B_full_minus_state", "B_full_minus_aria"]

# Published corpus values reproduced as controls (sources: revision1_diagnostics D1b COP
# check; cross_model.REPORT nano_nvF1_ok / nano_nvF2_ok / o4mini_cop_ok).
CTRL = {"gpt_cop_delta_pp": 10.00, "nano_nvF1_ok": 163, "nano_nvF2_ok": 70, "o4_cop_ok": 181,
        "cond5_true": {"B_full_minus_aria": 147, "B_full_minus_volClass": 192,
                       "B_full_minus_volId": 192, "B_full_minus_state": 192},
        "aria_flip": 45, "f2l_minus_f2_tokens": 151}

delta_stat = lambda t: (t["nv"] / t["n"] - t["bf"] / t["n"]) * 100   # noqa: E731
rate_stat = lambda t: t["s"] / t["n"] * 100                         # noqa: E731


def page_of(s: str) -> str:
    m = re.search(r"page_\d{2}", s)
    assert m, f"no page_NN in {s!r}"
    return m.group(0)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: pathlib.Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# Loading

def standardise(recs: pd.DataFrame, model: str, origin: str) -> pd.DataFrame:
    out = pd.DataFrame({
        "model": model,
        "bundle": recs["bundle"].to_numpy(),
        "encoding": recs["encoding"].to_numpy(),
        "rep": (recs["repetition"].astype(int) + 1).to_numpy(),
        "page": [page_of(p) for p in recs["page"]],
        "task_id": recs["task_id"].to_numpy(),
        "P5": recs["success"].astype(bool).to_numpy(),
        "Pnow": (recs["predicate_unique_match"].astype(bool)
                 & recs["predicate_matches_oracle"].astype(bool)).to_numpy(),
        "cond5": recs["stable_signal_present_in_bundle"].astype(bool).to_numpy(),
        "obs_tokens": recs["observation_tokens"].astype(int).to_numpy(),
        "failure_mode": recs["failure_mode"].to_numpy(),
        "origin": origin,
    })
    for c in ("event_key", "block", "finish_reason", "llm_attempts"):
        out[c] = recs[c].to_numpy() if c in recs else None
    return out


def load_plan():
    plan = json.loads(PLAN_JSON.read_text(encoding="utf-8"))
    plan_sha = sha256(PLAN_JSON)
    assert plan_sha.startswith(PLAN_SHA_PREFIX), f"batch_plan.json sha256 {plan_sha} != {PLAN_SHA_PREFIX}…"
    key = lambda e: f"{e['model']}|{e['bundle']}|{e['encoding']}|{e['page']}|{e['task_id']}|{e['repetition']}"  # noqa: E731
    events = {key(e): e for e in plan["events"]}
    assert len(events) == 4500
    assert dict(collections.Counter(e["block"] for e in events.values())) == BLOCK_COUNTS
    return plan, plan_sha, events


def load_journal(plan_sha, events):
    path = BATCH_DIR / "journal.jsonl"
    assert sha256(path) == JOURNAL_SHA, "journal.jsonl sha256 mismatch"
    entries = read_jsonl(path)
    last, types, released = {}, collections.Counter(), set()
    per_block = collections.defaultdict(collections.Counter)
    for e in entries:
        assert e["plan_sha256"] == plan_sha and e["key"] in events
        last[e["key"]] = e["type"]
        types[e["type"]] += 1
        per_block[events[e["key"]]["block"]][e["type"]] += 1
        if e["type"] == "released":
            released.add(e["key"])
    assert set(last) == set(events) and set(last.values()) == {"response"}, \
        "every plan key must end in a response"
    md = (BATCH_DIR / "released_keys.md").read_text(encoding="utf-8")
    md_keys = {k.replace("\\|", "|") for k in re.findall(r"`([^`]*\\\|[^`]*)`", md)}
    return {"lines": len(entries), "types": dict(types),
            "per_block": {b: dict(c) for b, c in sorted(per_block.items())},
            "released": sorted(released), "released_md": sorted(md_keys),
            "released_md_equal": md_keys == released}


def load_batch(plan_sha, events) -> pd.DataFrame:
    manifest = {}
    for m in (OBS_MANIFEST, DUMP_MANIFEST):        # dump overrides; repeated cells only in observations/
        t = pd.read_csv(m, sep="\t", dtype={"sha256": str})
        manifest.update({(r.page, r.bundle, r.encoding): r.sha256 for r in t.itertuples()})
    recs = []
    for f in sorted(BATCH_DIR.glob("batch_*.jsonl")):
        recs += read_jsonl(f)
    df = pd.DataFrame(recs)
    assert len(df) == 4500 and df["event_key"].is_unique and set(df["event_key"]) == set(events)
    assert (df["plan_sha256"] == plan_sha).all()
    for r in df.itertuples():
        e = events[r.event_key]
        assert (page_of(r.page), r.bundle, r.encoding, r.task_id, int(r.repetition), int(r.rep), str(r.block),
                r.model) == (e["page"], e["bundle"], e["encoding"], e["task_id"], e["repetition"], e["rep"],
                             e["block"], e["model"]), f"{r.event_key}: record disagrees with plan"
        assert r.observation_sha256 == manifest[(e["page"], e["bundle"], e["encoding"])], \
            f"{r.event_key}: observation sha256 differs from manifest"
    assert dict(collections.Counter(df["block"].astype(str))) == BLOCK_COUNTS
    assert set(df["tokenizer_version"]) == {"o200k_base"}
    out = pd.concat([standardise(g, m, "batch") for m, g in df.groupby("model", sort=True)], ignore_index=True)
    return out


def load_corpus() -> pd.DataFrame:
    mx = load_dataframe(REPO)
    parts = [standardise(mx, GPT, "corpus")]
    for model, pat in ((NANO, "axisc_gpt-4-1-nano_page_*.jsonl"), (O4, "axisc_o4-mini_page_*.jsonl")):
        recs = [r for f in sorted(RUNS.glob(pat)) for r in read_jsonl(f)]
        assert len(recs) in (960, 240), f"{model}: {len(recs)} axisc records"
        parts.append(standardise(pd.DataFrame(recs), model, "corpus"))
    return pd.concat(parts, ignore_index=True)


def rebuild_reused(plan, corpus) -> pd.DataFrame:
    """Block-1 reused cells: the batch writes no record; the stored record is the event."""
    parts = []
    for r in plan["reused_block1"]:
        src_bundle = "B_noState" if r["source"].startswith("original_B_noState") else "B_full"
        assert r["source"].startswith(f"original_{src_bundle}")
        src = corpus[(corpus["model"] == GPT) & (corpus["bundle"] == src_bundle) & (corpus["encoding"] == "F1")
                     & (corpus["rep"] == 1) & (corpus["page"] == r["page"])].copy()
        assert len(src) == 10
        src["bundle"], src["origin"] = r["bundle"], "reused"
        parts.append(src)
    return pd.concat(parts, ignore_index=True)


def load_truth():
    strata, attr_signals = {}, {}
    for tf in sorted(TRUTH_DIR.glob("*.truth.json")):
        tj = json.loads(tf.read_text(encoding="utf-8"))
        for t in tj["targets"]:
            attrs = {a for a in t["signal_attrs"] if a not in NON_ATTRIBUTE_SIGNALS}
            strata[(tj["page_id"], t["id"])] = "has_attribute_signal" if attrs else "no_attribute_signal"
            attr_signals[(tj["page_id"], t["id"])] = attrs
    assert len(strata) == 240
    return strata, attr_signals


# Statistics

class Data:
    def __init__(self, frame: pd.DataFrame, strata: dict):
        self.f = frame
        self.strata = strata

    def cell(self, model, bundle, enc, rep) -> pd.DataFrame:
        c = self.f[(self.f["model"] == model) & (self.f["bundle"] == bundle)
                   & (self.f["encoding"] == enc) & (self.f["rep"] == rep)]
        assert len(c) == 240 and not c.duplicated(["page", "task_id"]).any(), \
            f"cell {model} {bundle} {enc} rep{rep}: {len(c)} records"
        return c.set_index(["page", "task_id"]).sort_index()

    def majority(self, model, bundle, enc) -> pd.DataFrame:
        cells = [self.cell(model, bundle, enc, r) for r in REPS]
        out = cells[0][["obs_tokens"]].copy()
        for col in PREDS.values():
            out[col] = sum(c[col].astype(int) for c in cells) >= 2
        return out


def compare(first: pd.DataFrame, second: pd.DataFrame, strata: dict, keep=None) -> dict:
    """Paired comparison, second − first; overall and by stratum, P5 and P_now."""
    idx = first.index.intersection(second.index)
    assert len(idx) == len(first) == len(second), "arms are not matched event-for-event"
    if keep is not None:
        idx = pd.MultiIndex.from_tuples([k for k in idx if k in keep], names=idx.names)
    a, b = first.loc[idx], second.loc[idx]
    stratum = np.array([strata[k] for k in idx])
    out = {}
    for sname, mask in [("overall", np.ones(len(idx), bool))] + [(s, stratum == s) for s in STRATA]:
        if not mask.any():
            continue
        pages = np.array([k[0] for k in idx])[mask]
        order = [p for p in PAGES if p in set(pages)]
        res_s = {}
        for pname, col in PREDS.items():
            x, y = a[col].to_numpy(bool)[mask], b[col].to_numpy(bool)[mask]
            res = mcnemar(x, y)
            arrays = {"bf": np.array([x[pages == p].sum() for p in order], float),
                      "nv": np.array([y[pages == p].sum() for p in order], float),
                      "n":  np.array([(pages == p).sum() for p in order], float)}
            res["ci_lo_pp"], res["ci_hi_pp"] = pct_ci(page_bootstrap(order, arrays, delta_stat))
            res["n_pages"] = len(order)
            res_s[pname] = res
        out[sname] = res_s
    return out


def rate_ci(cell: pd.DataFrame, col: str):
    pages = np.array([k[0] for k in cell.index])
    v = cell[col].to_numpy(bool)
    arrays = {"s": np.array([v[pages == p].sum() for p in PAGES], float),
              "n": np.array([(pages == p).sum() for p in PAGES], float)}
    lo, hi = pct_ci(page_bootstrap(PAGES, arrays, rate_stat))
    return {"n": len(v), "k": int(v.sum()), "rate_pct": v.mean() * 100, "ci_lo_pct": lo, "ci_hi_pct": hi}


def fleiss_binary(totals) -> float:
    """Fleiss' κ for 3 raters, 2 categories, from sums: n events, s = Σ successes, a = Σ P_i."""
    n, s, a = totals["n"], totals["s"], totals["a"]
    p = s / (3 * n)
    pe = p * p + (1 - p) * (1 - p)
    return float("nan") if pe >= 1 else (a / n - pe) / (1 - pe)


def agreement(cells: list[pd.DataFrame], col: str) -> dict:
    k = sum(c[col].astype(int).to_numpy() for c in cells)          # successes over 3 reps, per event
    pages = np.array([i[0] for i in cells[0].index])
    p_i = (k * (k - 1) + (3 - k) * (2 - k)) / 6
    same = (k == 0) | (k == 3)
    arrays = {"n": np.array([(pages == p).sum() for p in PAGES], float),
              "s": np.array([k[pages == p].sum() for p in PAGES], float),
              "a": np.array([p_i[pages == p].sum() for p in PAGES], float),
              "same": np.array([same[pages == p].sum() for p in PAGES], float)}
    totals = {key: v.sum() for key, v in arrays.items()}
    kappa = fleiss_binary(totals)
    kd = page_bootstrap(PAGES, arrays, fleiss_binary)
    kd = kd[~np.isnan(kd)]
    sd = page_bootstrap(PAGES, arrays, lambda t: t["same"] / t["n"] * 100)
    return {"n": int(totals["n"]), "identical_n": int(totals["same"]),
            "identical_pct": totals["same"] / totals["n"] * 100,
            "identical_ci": pct_ci(sd), "kappa": kappa,
            "kappa_ci": pct_ci(kd) if len(kd) else (float("nan"), float("nan")),
            "kappa_boot_valid": int(len(kd))}


# Rows, Holm, formatting

def make_row(family, label, comp, in_holm, note=""):
    return {"family": family, "label": label, "in_holm": in_holm, "note": note, "result": comp}


def apply_holm(rows):
    """Holm per (family, predicate, stratum); rows not in_holm and undefined p are left out."""
    sets = collections.defaultdict(list)
    for r in rows:
        for s, res_s in r["result"].items():
            for pname, res in res_s.items():
                res["p_holm"] = res["p_holm_exact"] = None
                if r["in_holm"] and not math.isnan(res["p"]):
                    sets[(r["family"], pname, s)].append(res)
    for res_list in sets.values():
        for res, h1, h2 in zip(res_list, holm([x["p"] for x in res_list]), holm([x["p_exact"] for x in res_list])):
            res["p_holm"], res["p_holm_exact"] = h1, h2
    return {f"{k[0]}|{k[1]}|{k[2]}": len(v) for k, v in sorted(sets.items())}


def ph(p):
    return "raw only" if p is None else fmt_p(p)


def comp_table(rows, strata=("overall",) + tuple(STRATA)):
    out = []
    for r in rows:
        for s in strata:
            if s not in r["result"]:
                continue
            for pname, res in r["result"][s].items():
                undefined = math.isnan(res["p"])
                out.append([r["label"], s, pname, res["n"], f"{res['rate_first_pct']:.1f}",
                            f"{res['rate_second_pct']:.1f}", f"{res['delta_pp']:+.2f}",
                            f"[{res['ci_lo_pp']:+.2f}, {res['ci_hi_pp']:+.2f}]",
                            f"{res['b_second_only']}/{res['c_first_only']}",
                            "n/a" if undefined else f"{fmt_or(res['odds_ratio'])} [{fmt_or(res['or_ci_lo'])}, {fmt_or(res['or_ci_hi'])}]",
                            fmt_p(res["p"]), fmt_p(res["p_exact"]),
                            "n/a" if undefined else ph(res["p_holm"]),
                            "n/a" if undefined else ph(res["p_holm_exact"])])
    return md_table(["comparison (second − first)", "stratum", "pred", "n", "first %", "second %", "Δ pp",
                     "95% CI (pp)", "b/c", "OR [95% CI]", "p χ²", "p exact", "p χ² Holm", "p exact Holm"], out)


def p5(r, s="overall"):
    return r["result"][s]["P5"]


# Main

def main():
    print("[guard] protected files before")
    protected_before = protected_state()

    plan, plan_sha, events = load_plan()
    journal = load_journal(plan_sha, events)
    batch = load_batch(plan_sha, events)
    corpus = load_corpus()
    reused = rebuild_reused(plan, corpus)
    strata, attr_signals = load_truth()
    D = Data(pd.concat([corpus, batch, reused], ignore_index=True), strata)
    print(f"[load] batch {len(batch)} | corpus {len(corpus)} | reused {len(reused)} | "
          f"journal {journal['lines']} lines, {len(journal['released'])} released")

    # Controls
    ctl = Controls()
    bf1 = {r: D.cell(GPT, "B_full", "F1", r) for r in REPS}
    cop = compare(bf1[1], D.cell(GPT, "B_noVolatile", "F3", 1), strata)
    ctl.check("corpus: gpt-4.1 COP − B_full×F1 Δ P5 (pp)", round(p5({"result": cop})["delta_pp"], 2),
              CTRL["gpt_cop_delta_pp"])
    ctl.check("corpus: nano B_noVolatile×F1 successes", int(D.cell(NANO, "B_noVolatile", "F1", 1)["P5"].sum()),
              CTRL["nano_nvF1_ok"])
    ctl.check("corpus: nano B_noVolatile×F2 successes", int(D.cell(NANO, "B_noVolatile", "F2", 1)["P5"].sum()),
              CTRL["nano_nvF2_ok"])
    ctl.check("corpus: o4-mini COP successes", int(D.cell(O4, "B_noVolatile", "F3", 1)["P5"].sum()),
              CTRL["o4_cop_ok"])
    ctl.check("journal: released keys == released_keys.md", journal["released_md_equal"], True)
    for b, k in CTRL["cond5_true"].items():
        ctl.check(f"batch: condition 5 true, {b}×F1 (240 targets)", int(D.cell(GPT, b, "F1", 1)["cond5"].sum()), k)
    aria = D.cell(GPT, "B_full_minus_aria", "F1", 1)
    flip = {k for k in aria.index if bf1[1].loc[k, "cond5"] and not aria.loc[k, "cond5"]}
    by_truth = {k for k, v in attr_signals.items() if v == {"aria-label"}}
    ctl.check("batch: minus_aria condition-5 flips == targets whose only attribute signal is aria-label",
              flip == by_truth, True)
    ctl.check("batch: minus_aria condition-5 flips (count)", len(flip), CTRL["aria_flip"])
    # Deterministic per-event invariants (cond 5 and observation tokens depend on the observation only).
    det = [((GPT, b, e), (GPT, b, e), r) for b, e in [("B_full", "F1"), ("B_noVolatile", "F1"),
                                                     ("B_noVolatile", "F2"), ("B_noVolatile", "F3")] for r in (2, 3)]
    det += [((NANO, "B_noVolatile", e), (NANO, "B_noVolatile", e), r) for e in ("F1", "F2") for r in (2, 3)]
    det_ok = all((D.cell(*a, 1)[["cond5", "obs_tokens"]] == D.cell(*b, r)[["cond5", "obs_tokens"]]).all().all()
                 for a, b, r in det)
    ctl.check("batch: reps 2/3 have rep-1 condition 5 and observation tokens on every event", det_ok, True)
    o4bf = D.cell(O4, "B_full", "F1", 1)
    ctl.check("batch: o4-mini B_full×F1 condition 5 / tokens == gpt-4.1 B_full×F1",
              bool((o4bf[["cond5", "obs_tokens"]] == bf1[1][["cond5", "obs_tokens"]]).all().all()), True)
    f2l_ok = True
    for m, b in ((GPT, "B_full"), (GPT, "B_noVolatile"), (NANO, "B_noVolatile")):
        f2, f2l = D.cell(m, b, "F2", 1), D.cell(m, b, "F2L", 1)
        f2l_ok &= bool((f2l["cond5"] == f2["cond5"]).all()
                       and ((f2l["obs_tokens"] - f2["obs_tokens"]) == CTRL["f2l_minus_f2_tokens"]).all())
    ctl.check("batch: F2L condition 5 == F2 and F2L − F2 tokens == 151 on every event", f2l_ok, True)
    ctl.enforce()

    R = {"plan_sha256": plan_sha, "journal": journal, "controls": ctl.rows,
         "n_boot": N_BOOT, "seed": SEED}
    rows = []

    # F1 Repetitions
    print("\n[F1] repetitions")
    f1_cells = [(GPT, "B_full", "F1"), (GPT, "B_noVolatile", "F1"), (GPT, "B_noVolatile", "F2"),
                (GPT, "B_noVolatile", "F3"), (NANO, "B_noVolatile", "F1"), (NANO, "B_noVolatile", "F2")]
    f1a = []
    for m, b, e in f1_cells:
        cells = [D.cell(m, b, e, r) for r in REPS]
        for pname, col in PREDS.items():
            rates = [rate_ci(c, col) for c in cells]
            vals = [x["rate_pct"] for x in rates]
            f1a.append({"model": m, "bundle": b, "encoding": e, "pred": pname, "rates": rates,
                        "range_pp": max(vals) - min(vals), "agreement": agreement(cells, col)})
    R["F1a"] = f1a

    for r in REPS:
        rows.append(make_row("F1", f"(b) {GPT} B_noVolatile×F1 vs B_full×F1, rep {r}",
                             compare(bf1[r], D.cell(GPT, "B_noVolatile", "F1", r), strata), r != 1,
                             "both arms original corpus run" if r == 1 else ""))
    rows.append(make_row("F1", f"(b) {GPT} B_noVolatile×F1 vs B_full×F1, majority ≥2/3",
                         compare(D.majority(GPT, "B_full", "F1"), D.majority(GPT, "B_noVolatile", "F1"), strata),
                         True))
    for r in REPS:
        rows.append(make_row("F1", f"(c) {GPT} B_noVolatile×F3 (COP) vs B_full×F1, rep {r}",
                             compare(bf1[r], D.cell(GPT, "B_noVolatile", "F3", r), strata), r != 1,
                             "both arms original corpus run" if r == 1 else ""))
    for m in (GPT, NANO):
        for r in REPS:
            rows.append(make_row("F1", f"(d) {m} B_noVolatile F2 vs F1, rep {r}",
                                 compare(D.cell(m, "B_noVolatile", "F1", r), D.cell(m, "B_noVolatile", "F2", r),
                                         strata), r != 1, "both arms original corpus run" if r == 1 else ""))
    tok = []
    for r in REPS:
        a, b = bf1[r]["obs_tokens"], D.cell(GPT, "B_noVolatile", "F3", r)["obs_tokens"]
        tok.append({"rep": r, "n": len(a), "B_full_F1_mean": a.mean(), "COP_mean": b.mean(),
                    "B_full_F1_total": int(a.sum()), "COP_total": int(b.sum()),
                    "diff_mean": b.mean() - a.mean(), "reduction_pct": (1 - b.sum() / a.sum()) * 100})
    R["F1c_tokens"] = tok

    rb = {r: next(x for x in rows if x["label"].startswith("(b)") and x["label"].endswith(f"rep {r}")) for r in REPS}
    replicates = all(p5(rb[r])["delta_pp"] > 0 and p5(rb[r])["ci_lo_pp"] > 0 for r in (2, 3))
    R["F1b_verdict"] = {"replicates": replicates,
                        "criterion": "Δ > 0 and bootstrap CI lower bound > 0 in rep 2 AND rep 3 (P5, overall)"}

    # F2 Single-attribute ablations
    print("[F2] ablations")
    reused_pages = collections.defaultdict(list)
    for x in plan["reused_block1"]:
        reused_pages[x["bundle"]].append(x["page"])
    for b in ABLATIONS:
        cell = D.cell(GPT, b, "F1", 1)
        n_called = int((cell["origin"] == "batch").sum())
        both_corpus = n_called == 0
        rows.append(make_row("F2", f"{GPT} {b}×F1 vs B_full×F1", compare(bf1[1], cell, strata), not both_corpus,
                             f"n_called {n_called}; reused pages (identical observation, concordant by construction): "
                             f"{', '.join(reused_pages[b]) or 'none'}"
                             + ("; both arms original corpus records → raw p only" if both_corpus else "")))
    keep_rest = set(aria.index) - flip
    rows.append(make_row("F2-sub", f"{GPT} B_full_minus_aria×F1 vs B_full×F1, remaining {len(keep_rest)} targets",
                         compare(bf1[1], aria, strata, keep=keep_rest), True,
                         "subset row; own Holm set of size 1"))
    rows.append(make_row("F2-sub45", f"{GPT} B_full_minus_aria×F1 vs B_full×F1, the {len(flip)} flipped targets",
                         compare(bf1[1], aria, strata, keep=flip), True,
                         "subset row; condition 5 false by construction under minus_aria; own Holm set of size 1"))
    R["F2_aria_flipped_targets"] = sorted(f"{p} {t}" for p, t in flip)

    # F3 Key-name legend
    print("[F3] F2L legend")
    f3_verdicts = []
    for m, b in ((GPT, "B_full"), (GPT, "B_noVolatile"), (NANO, "B_noVolatile")):
        f2l = D.cell(m, b, "F2L", 1)
        r_f2 = make_row("F3", f"{m} {b}: F2L vs F2", compare(D.cell(m, b, "F2", 1), f2l, strata), True)
        r_f1 = make_row("F3", f"{m} {b}: F2L vs F1", compare(D.cell(m, b, "F1", 1), f2l, strata), True)
        rows += [r_f2, r_f1]
        first = p5(r_f2)["delta_pp"] > 0 and p5(r_f2)["ci_lo_pp"] > 0
        second = p5(r_f1)["ci_lo_pp"] <= 0 <= p5(r_f1)["ci_hi_pp"]
        verdict = "legend restores" if first and second else "partial" if first else "no effect"
        f3_verdicts.append({"model": m, "bundle": b, "F2L_minus_F2_ok": first, "F2L_minus_F1_CI_includes_0": second,
                            "verdict": verdict})
    R["F3_verdicts"] = f3_verdicts

    # F4 o4-mini
    print("[F4] o4-mini")
    o4cop = D.cell(O4, "B_noVolatile", "F3", 1)
    reissued_b4 = {(events[k]["page"], events[k]["task_id"]) for k in journal["released"] if events[k]["block"] == "4"}
    rows.append(make_row("F4", f"{O4} B_noVolatile×F3 (COP) vs B_full×F1, all events", compare(o4bf, o4cop, strata),
                         True))
    rows.append(make_row("F4", f"{O4} B_noVolatile×F3 (COP) vs B_full×F1, without re-issued events",
                         compare(o4bf, o4cop, strata, keep=set(o4bf.index) - reissued_b4), True,
                         f"excluded: {', '.join(f'{p} {t}' for p, t in sorted(reissued_b4))}"))
    gpt_ref = make_row("F4-ref", f"{GPT} B_noVolatile×F3 (COP) vs B_full×F1, rep 1 (reference)", cop, False,
                       "both arms original corpus run; direction reference")
    rows.append(gpt_ref)
    f4_all = next(r for r in rows if r["family"] == "F4" and r["label"].endswith("all events"))
    R["F4_direction"] = {"o4_delta_pp": p5(f4_all)["delta_pp"], "gpt_delta_pp": p5(gpt_ref)["delta_pp"],
                         "same_sign": bool(np.sign(p5(f4_all)["delta_pp"]) == np.sign(p5(gpt_ref)["delta_pp"]))}
    rel_by_block = collections.Counter(events[k]["block"] for k in journal["released"])
    R["reissued"] = {"keys": journal["released"], "by_block": {b: rel_by_block.get(b, 0) for b in BLOCK_COUNTS}}

    R["holm_sets"] = apply_holm(rows)
    R["rows"] = rows

    # Exploratory
    fm = (batch.assign(failure_mode=batch["failure_mode"].fillna("success"))
          .groupby(["block", "model", "bundle", "encoding", "rep", "failure_mode"]).size()
          .unstack(fill_value=0).reset_index())
    for c in ("success", LACKED, GRABBED, UNREACHABLE):
        if c not in fm:
            fm[c] = 0
    R["exploratory_failure_modes"] = fm.to_dict(orient="records")
    R["exploratory_finish_attempts"] = {
        "finish_reason_by_block": {f"{b}|{k}": int(v) for (b, k), v in
                                   batch.groupby(["block", "finish_reason"]).size().items()},
        "llm_attempts_by_block": {f"{b}|{k}": int(v) for (b, k), v in
                                  batch.groupby(["block", "llm_attempts"]).size().items()}}

    print("\n[guard] protected files after")
    protected_after = protected_state()
    unchanged = protected_after == protected_before
    R["protected_unchanged"] = unchanged
    R["protected_files"] = len(protected_after)

    write_md(R, rows, f1a, tok, journal)
    OUT_JSON.write_text(json.dumps(jsonable(R), indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {OUT_MD.relative_to(REPO)} and {OUT_JSON.relative_to(REPO)}")
    if not unchanged:
        raise SystemExit("[guard] protected files changed during the run")


def write_md(R, rows, f1a, tok, journal):
    fam = lambda *f: [r for r in rows if r["family"] in f]   # noqa: E731
    L = ["# Revision 1 — batch analysis", "",
         f"Zero LLM, zero network. Follows `batch_analysis_plan.md` (committed before any outcome was read); "
         f"anything else is under **Exploratory**. Plan `batch_plan.json` sha256 `{R['plan_sha256']}`; "
         f"`journal.jsonl` sha256 `{JOURNAL_SHA}`.", "",
         "Conventions: Δ = second − first, in percentage points; 95% CI = page-clustered percentile bootstrap "
         f"({N_BOOT:,} draws, seed {SEED}); b = second-only successes, c = first-only; OR = b/c with exact "
         "conditional 95% CI; p χ² = McNemar uncorrected, p exact = binomial on b/(b+c). P5 = five-condition "
         "predicate (primary); P_now = unique match ∧ matches oracle (secondary). Strata from "
         "`shared/testbed/pages/*.truth.json` (no_attribute_signal = NONE + text-only targets; P5 is 0 there by "
         "construction). gpt-4.1 / gpt-4.1-nano at temperature 0; o4-mini at the service default.", "",
         "Holm (plan § Multiplicity): one set per (family, predicate, stratum), on p χ² and on p exact. Rows whose "
         "two arms are both original corpus records show raw p only (`raw only`). Undefined p (no discordant "
         "pairs) → n/a, not in the set. Subset rows of F2 (minus_aria remaining / flipped targets) are their own "
         "sets of size 1. Both F4 o4-mini rows (all events, without re-issued) are in the F4 set. Set sizes: "
         + ", ".join(f"{k} = {v}" for k, v in R["holm_sets"].items()) + ".", ""]

    L += ["## Data", "",
          f"4,500 batch records (blocks {', '.join(f'{b}: {n:,}' for b, n in BLOCK_COUNTS.items())}); every plan key "
          f"ends in a journaled response; journal {journal['lines']:,} lines "
          f"({', '.join(f'{k} {v}' for k, v in sorted(journal['types'].items()))}). Observation sha256 of every "
          "record equals the audited manifest. Block-1 reused cells are rebuilt from the corpus records they reuse "
          "(B_full_minus_state = B_noState×F1 on 24 pages; minus_volClass pages 02/04/12/19 and minus_volId pages "
          "03/07 = B_full×F1).", "",
          f"Re-issued after client timeout / provider error (journal `released`, equal to `released_keys.md`: "
          f"{journal['released_md_equal']}): {len(journal['released'])} — by block "
          + ", ".join(f"{b}: {n}" for b, n in R["reissued"]["by_block"].items()) + ". Keys: "
          + "; ".join(f"`{k}`" for k in journal["released"]) + ".", ""]

    L += ["## Controls", ""]
    L += md_table(["control", "recomputed", "expected", "ok"],
                  [[c["control"], c["recomputed"], c["published"], "OK" if c["ok"] else "FAIL"] for c in R["controls"]])

    # F1
    L += ["", "## F1 — Repetitions (block 3; rep 1 = original corpus run)", "", "### (a) Stability", ""]
    t = []
    for x in f1a:
        rs = x["rates"]
        ag = x["agreement"]
        t.append([x["model"], f"{x['bundle']}×{x['encoding']}", x["pred"], rs[0]["n"]]
                 + [f"{q['rate_pct']:.1f} [{q['ci_lo_pct']:.1f}, {q['ci_hi_pct']:.1f}]" for q in rs]
                 + [f"{x['range_pp']:.2f}",
                    f"{ag['identical_n']}/{ag['n']} = {ag['identical_pct']:.1f} [{ag['identical_ci'][0]:.1f}, {ag['identical_ci'][1]:.1f}]",
                    f"{ag['kappa']:.3f} [{ag['kappa_ci'][0]:.3f}, {ag['kappa_ci'][1]:.3f}]"])
    L += md_table(["model", "cell", "pred", "n / rep", "rep 1 % [95% CI]", "rep 2 %", "rep 3 %", "range pp",
                   "identical across 3 reps, % [95% CI]", "Fleiss κ [95% CI]"], t)
    dropped = [f"{x['model']} {x['bundle']}×{x['encoding']} {x['pred']}: {N_BOOT - x['agreement']['kappa_boot_valid']}"
               for x in f1a if x["agreement"]["kappa_boot_valid"] < N_BOOT]
    L += ["", "Rate and agreement CIs: page-cluster bootstrap. κ CI: page-cluster bootstrap on per-page sums; "
          "replicates with undefined κ dropped: " + (", ".join(dropped) if dropped else "none") + ".", ""]
    for sub, title in (("(b)", "(b) Headline replication — B_noVolatile×F1 vs B_full×F1, gpt-4.1"),
                       ("(c)", "(c) COP — B_noVolatile×F3 vs B_full×F1, gpt-4.1"),
                       ("(d)", "(d) F2 drop — B_noVolatile F2 vs F1")):
        L += [f"### {title}", ""]
        L += comp_table([r for r in fam("F1") if r["label"].startswith(sub)])
        L += [""]
        if sub == "(b)":
            v = R["F1b_verdict"]
            L += [f"**Criterion** ({v['criterion']}): **{'replicates' if v['replicates'] else 'does not replicate'}**.", ""]
        if sub == "(c)":
            L += ["Observation tokens (o200k_base, deterministic):", ""]
            L += md_table(["rep", "n", "B_full×F1 mean", "COP mean", "Δ mean", "B_full×F1 total", "COP total",
                           "reduction %"],
                          [[x["rep"], x["n"], f"{x['B_full_F1_mean']:.1f}", f"{x['COP_mean']:.1f}",
                            f"{x['diff_mean']:+.1f}", f"{x['B_full_F1_total']:,}", f"{x['COP_total']:,}",
                            f"{x['reduction_pct']:.2f}"] for x in tok])
            L += [""]

    # F2
    L += ["## F2 — Single-attribute ablations (block 1, gpt-4.1, F1, rep 1)", ""]
    L += comp_table(fam("F2"))
    L += [""] + [f"- {r['label']}: {r['note']}" for r in fam("F2")] + [""]
    L += [f"minus_aria — {len(R['F2_aria_flipped_targets'])} targets whose condition 5 becomes false by construction "
          "(only attribute signal = aria-label): " + ", ".join(R["F2_aria_flipped_targets"]) + ".", ""]
    L += comp_table(fam("F2-sub", "F2-sub45"))
    L += [""]

    # F3
    L += ["## F3 — Key-name legend (block 2, rep 1)", ""]
    L += comp_table(fam("F3"))
    L += ["", "Fixed interpretation (P5, overall, unadjusted bootstrap CIs): *legend restores* if F2L−F2 > 0 with "
          "CI lower bound > 0 AND the CI of F2L−F1 includes 0; *partial* if only the first holds; *no effect* "
          "otherwise.", ""]
    L += md_table(["model", "bundle", "F2L−F2 > 0, CI lo > 0", "CI(F2L−F1) ∋ 0", "verdict"],
                  [[v["model"], v["bundle"], v["F2L_minus_F2_ok"], v["F2L_minus_F1_CI_includes_0"],
                    f"**{v['verdict']}**"] for v in R["F3_verdicts"]])

    # F4
    d = R["F4_direction"]
    L += ["", "## F4 — o4-mini (block 4; decoding at the service default, no temperature)", ""]
    L += comp_table(fam("F4", "F4-ref"))
    L += ["", f"Direction: o4-mini Δ(COP − B_full×F1) = {d['o4_delta_pp']:+.2f} pp; gpt-4.1 (rep 1) = "
          f"{d['gpt_delta_pp']:+.2f} pp → same sign: **{d['same_sign']}**.",
          f"Re-issued events in block 4: {R['reissued']['by_block']['4']} "
          f"({'; '.join(r['note'] for r in fam('F4') if r['note'])}).", ""]

    # Exploratory
    L += ["## Exploratory (not in the plan)", "", "Failure modes per batch cell (records called in the batch):", ""]
    L += md_table(["block", "model", "bundle", "enc", "rep", "success", "lacked", "grabbed", "unreachable"],
                  [[x["block"], x["model"], x["bundle"], x["encoding"], x["rep"], x["success"], x[LACKED],
                    x[GRABBED], x[UNREACHABLE]] for x in R["exploratory_failure_modes"]])
    fa = R["exploratory_finish_attempts"]
    L += ["", "finish_reason by block: " + ", ".join(f"{k} {v}" for k, v in fa["finish_reason_by_block"].items()) + ".",
          "llm_attempts by block: " + ", ".join(f"{k} {v}" for k, v in fa["llm_attempts_by_block"].items()) + ".", ""]

    L += [f"Protected files (FINDINGS.md, 24 matrix, 71 axisc, 24 truth) unchanged: {R['protected_files']} SHA-256 "
          f"{'equal' if R['protected_unchanged'] else 'CHANGED'}.", ""]
    OUT_MD.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
