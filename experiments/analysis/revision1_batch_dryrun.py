"""
Dry-run for the revision batch (Blocks 1–4), zero LLM. Writes the event plan that
REVISION_BATCH=1 executes (batch_plan.json) and the per-block call / token / price estimate.

No plan is written unless:
  - sha256 of B_full×F1, B_noVolatile×F1/F2 and B_noVolatileConsistent×F1 in
    batch_observations/ equal observations/manifest.tsv;
  - dumped tokens equal the stored observation_tokens for every corpus cell that is re-run or
    used as an overhead source (gpt-4.1: B_full F1/F2, B_noVolatile F1/F2/F3, F3 checked
    against observations/; Axis C nano: B_noVolatile F1/F2);
  - B_full_minus_state ≡ B_noState byte-for-byte on 24/24 pages;
  - the ladder_composition.json fidelity flag is true;
  - `git diff --numstat shared/` has 0 deleted lines.

Blocks:
  1  gpt-4.1 × F1 × {B_full_minus_volClass, _volId, _aria}, only on pages whose observation
     differs from B_full×F1; other pages reuse the stored B_full×F1 record. B_full_minus_state
     is not run (≡ B_noState×F1, stored record reused).
  2  F2L: gpt-4.1 × {B_full, B_noVolatile}; gpt-4.1-nano × B_noVolatile.
  3  reps 2 and 3 (repetition 1, 2; the corpus is repetition 0): gpt-4.1 B_full×F1,
     B_noVolatile×F1/F2/F3; gpt-4.1-nano B_noVolatile×F1/F2 (Axis C supplies rep 1).
  4  o4-mini B_full×F1 (no temperature, as in the original o4-mini run).

Input tokens = observation tokens (dump, or the stored record for a repeated cell) + prompt
overhead (prompt_tokens_total − observation_tokens) of a stored event with the same page, task
and model. Output tokens = completion_tokens of a stored analogous event (estimate).

Output: experiments/results/revision1/batch_plan.json; the estimate is printed.
"""
from __future__ import annotations

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import json
import pathlib
import subprocess

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from load import load_dataframe                                                    # noqa: E402
from revision1_diagnostics import REPO, OUT_DIR, protected_state, jsonable, md_table   # noqa: E402

DUMP = OUT_DIR / "batch_observations"
OBS = OUT_DIR / "observations"
TRUTH = REPO / "shared" / "testbed" / "pages"
PAGES = [f"page_{n:02d}" for n in range(1, 25)]
MODELS = {"gpt-4.1": "BAR_MODEL_DEPLOYMENT_1", "gpt-4.1-nano": "BAR_MODEL_DEPLOYMENT_2",
          "o4-mini": "BAR_MODEL_DEPLOYMENT_4"}
# Public list prices, USD per 1M tokens, no caching (indicative only; Azure tariff differs).
PRICE = {"gpt-4.1": (2.00, 8.00), "gpt-4.1-nano": (0.10, 0.40), "o4-mini": (1.10, 4.40)}


def load_axisc():
    rows = []
    for f in sorted((REPO / "experiments" / "runs").glob("axisc_*.jsonl")):
        rows += [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    ax = pd.DataFrame(rows)
    ax["page"] = ax["page"].str.extract(r"(page_\d{2})", expand=False)
    return ax


def main():
    before = protected_state()
    man = pd.read_csv(DUMP / "manifest.tsv", sep="\t", dtype={"sha256": str}).set_index(["page", "bundle", "encoding"])
    old = pd.read_csv(OBS / "manifest.tsv", sep="\t", dtype={"sha256": str}).set_index(["page", "bundle", "encoding"])
    df = load_dataframe(REPO)
    ax = load_axisc()
    truth = {p: json.loads((TRUTH / f"{p}.truth.json").read_text(encoding="utf-8")) for p in PAGES}
    tasks = {p: [t["id"] for t in truth[p]["targets"]] for p in PAGES}

    # Gate
    gate = {}
    sha_cells = [("B_full", "F1"), ("B_noVolatile", "F1"), ("B_noVolatile", "F2"), ("B_noVolatileConsistent", "F1")]
    sha_bad = [f"{p} {b} {e}" for p in PAGES for b, e in sha_cells
               if man.loc[(p, b, e), "sha256"] != old.loc[(p, b, e), "sha256"]]
    gate["existing_bundles_byte_identical_96"] = not sha_bad

    def stored_tok(frame, b, e):
        g = frame[(frame.bundle == b) & (frame.encoding == e)].groupby("page").observation_tokens.agg(["min", "max"])
        return g
    tok_bad = []
    for frame, label, cells in ((df, "gpt-4.1", [("B_full", "F1"), ("B_full", "F2"),
                                                 ("B_noVolatile", "F1"), ("B_noVolatile", "F2")]),
                                (ax[ax.model == "gpt-4.1-nano"], "nano", [("B_noVolatile", "F1"), ("B_noVolatile", "F2")])):
        for b, e in cells:
            g = stored_tok(frame, b, e)
            for p in PAGES:
                if not (g.loc[p, "min"] == g.loc[p, "max"] == int(man.loc[(p, b, e), "tokens"])):
                    tok_bad.append(f"{label} {p} {b} {e}")
    g = stored_tok(df, "B_noVolatile", "F3")
    tok_bad += [f"gpt-4.1 {p} B_noVolatile F3" for p in PAGES
                if not (g.loc[p, "min"] == g.loc[p, "max"] == int(old.loc[(p, "B_noVolatile", "F3"), "tokens"]))]
    gate["dump_tokens_equal_stored"] = not tok_bad
    state_bad = [p for p in PAGES if man.loc[(p, "B_full_minus_state", "F1"), "sha256"]
                 != man.loc[(p, "B_noState", "F1"), "sha256"]]
    gate["minus_state_identical_to_B_noState_24"] = not state_bad
    gate["ladder_fidelity"] = bool(json.loads((OUT_DIR / "ladder_composition.json").read_text(
        encoding="utf-8"))["fidelity_F1_tokens_equal_corpus"])
    numstat = subprocess.run(["git", "diff", "--numstat", "HEAD", "--", "shared/"], cwd=REPO,
                             capture_output=True, text=True).stdout.split("\n")
    shared_numstat = [l.split("\t") for l in numstat if l.strip()]
    gate["shared_zero_deleted_lines"] = all(r[1] == "0" for r in shared_numstat)
    gate["pass"] = all(gate.values())
    if not gate["pass"]:
        sys.exit(f"gate FAIL — {gate}; sha {sha_bad[:5]} tok {tok_bad[:5]} state {state_bad}")

    # Plan
    events, reuse = [], []

    def add(block, model, bundle, enc, page, repetition):
        for t in tasks[page]:
            events.append({"block": block, "model": model, "model_env": MODELS[model], "bundle": bundle,
                           "encoding": enc, "page": page, "task_id": t, "repetition": repetition,
                           "rep": repetition + 1})

    for b in ("B_full_minus_volClass", "B_full_minus_volId", "B_full_minus_aria"):
        for p in PAGES:
            if man.loc[(p, b, "F1"), "sha256"] == man.loc[(p, "B_full", "F1"), "sha256"]:
                reuse.append({"bundle": b, "page": p, "source": "original_B_full×F1 (identical observation)"})
            else:
                add("1", "gpt-4.1", b, "F1", p, 0)
    reuse += [{"bundle": "B_full_minus_state", "page": p, "source": "original_B_noState×F1 (identical observation)"}
              for p in PAGES]
    for p in PAGES:
        add("2", "gpt-4.1", "B_full", "F2L", p, 0)
        add("2", "gpt-4.1", "B_noVolatile", "F2L", p, 0)
        add("2", "gpt-4.1-nano", "B_noVolatile", "F2L", p, 0)
    nano_rep1 = {e: int(((ax.model == "gpt-4.1-nano") & (ax.bundle == "B_noVolatile") & (ax.encoding == e)
                         & (ax.repetition == 0)).sum()) for e in ("F1", "F2")}
    nano_reps = [1, 2] if all(v == 240 for v in nano_rep1.values()) else [0, 1, 2]
    for rep in (1, 2):
        for b, e in (("B_full", "F1"), ("B_noVolatile", "F1"), ("B_noVolatile", "F2"), ("B_noVolatile", "F3")):
            for p in PAGES:
                add("3", "gpt-4.1", b, e, p, rep)
    for rep in nano_reps:
        for e in ("F1", "F2"):
            for p in PAGES:
                add("3", "gpt-4.1-nano", "B_noVolatile", e, p, rep)
    for p in PAGES:
        add("4", "o4-mini", "B_full", "F1", p, 0)
    ev = pd.DataFrame(events)
    assert not ev.duplicated(["block", "model", "bundle", "encoding", "page", "task_id", "repetition"]).any()

    # Token estimate
    stored = pd.concat([df.assign(src="matrix"), ax.assign(src="axisc")], ignore_index=True)
    stored = stored[stored.repetition == 0]
    idx = stored.set_index(["model", "bundle", "encoding", "page", "task_id"])
    assert not idx.index.duplicated().any()

    def rec(model, bundle, enc, page, task):
        return idx.loc[(model, bundle, enc, page, task)]

    obs_new, overhead, out_est = [], [], []
    for r in ev.itertuples():
        if r.block == "1":
            o = int(man.loc[(r.page, r.bundle, "F1"), "tokens"]); s = rec("gpt-4.1", "B_full", "F1", r.page, r.task_id)
        elif r.block == "2":
            o = int(man.loc[(r.page, r.bundle, "F2L"), "tokens"]); s = rec(r.model, r.bundle, "F2", r.page, r.task_id)
        elif r.block == "3":
            s = rec(r.model, r.bundle, r.encoding, r.page, r.task_id); o = int(s.observation_tokens)
        else:
            o = int(man.loc[(r.page, "B_full", "F1"), "tokens"]); s = rec("o4-mini", "B_noVolatile", "F3", r.page, r.task_id)
        obs_new.append(o)
        overhead.append(int(s.prompt_tokens_total) - int(s.observation_tokens))
        out_est.append(int(s.completion_tokens))
    ev["obs_tokens"] = obs_new
    ev["prompt_overhead"] = overhead
    ev["input_tokens"] = ev.obs_tokens + ev.prompt_overhead
    ev["output_tokens_est"] = out_est
    ev["usd_in"] = [i / 1e6 * PRICE[m][0] for i, m in zip(ev.input_tokens, ev.model)]
    ev["usd_out"] = [o / 1e6 * PRICE[m][1] for o, m in zip(ev.output_tokens_est, ev.model)]

    by_cell = (ev.groupby(["block", "model", "bundle", "encoding", "repetition"])
               .agg(calls=("task_id", "size"), pages=("page", "nunique"), input_tokens=("input_tokens", "sum"),
                    mean_obs=("obs_tokens", "mean"), output_est=("output_tokens_est", "sum"),
                    usd=("usd_in", "sum"), usd_out=("usd_out", "sum")).reset_index())
    by_cell["usd"] += by_cell.pop("usd_out")
    by_block = (ev.groupby("block").agg(calls=("task_id", "size"), input_tokens=("input_tokens", "sum"),
                                        output_est=("output_tokens_est", "sum"), max_input=("input_tokens", "max"),
                                        usd_in=("usd_in", "sum"), usd_out=("usd_out", "sum")).reset_index())
    by_model = (ev.groupby("model").agg(calls=("task_id", "size"), input_tokens=("input_tokens", "sum"),
                                        output_est=("output_tokens_est", "sum"), max_input=("input_tokens", "max"),
                                        usd_in=("usd_in", "sum"), usd_out=("usd_out", "sum")).reset_index())
    by_page = ev.pivot_table(index="page", columns="block", values="input_tokens", aggfunc="sum", fill_value=0)
    tot = {"calls": int(len(ev)), "input_tokens": int(ev.input_tokens.sum()),
           "output_tokens_est": int(ev.output_tokens_est.sum()), "max_input_single_call": int(ev.input_tokens.max()),
           "usd_list_price": round(float(ev.usd_in.sum() + ev.usd_out.sum()), 2)}

    # Condition 5 under the ablations (facts for Block 1)
    c5 = json.loads((DUMP / "cond5_batch.json").read_text(encoding="utf-8"))
    c5_counts = {b: sum(r["condition5"][b] for r in c5) for b in
                 ("B_full", "B_full_minus_volClass", "B_full_minus_volId", "B_full_minus_state", "B_full_minus_aria",
                  "B_noState")}
    aria_drop = [f"{r['page']} {r['task_id']}" for r in c5
                 if r["condition5"]["B_full"] and not r["condition5"]["B_full_minus_aria"]]
    legend_tokens = sorted({int(man.loc[(p, b, "F2L"), "tokens"]) - int(man.loc[(p, b, "F2"), "tokens"])
                            for p in PAGES for b in ("B_full", "B_noVolatile")})

    # Report
    fmt = lambda v: f"{int(v):,}"
    L = ["# Revision 1 — batch dry-run (Blocks 1–4)", "",
         "Zero model calls. The run (`REVISION_BATCH=1`) executes exactly the events in `batch_plan.json`; "
         "output `experiments/results/revision1/batch_runs/`; `experiments/runs/` is not written. Regime full_page, canonical prompt "
         "(unchanged). Temperature: 0 for gpt-4.1 / gpt-4.1-nano, omitted for o4-mini (LlmClient, as in the "
         "original runs).", "",
         "Gate: " + ", ".join(f"{k} {'yes' if v else 'NO'}" for k, v in gate.items() if k != "pass")
         + f" → **{'PASS' if gate['pass'] else 'FAIL'}**. `shared/` numstat: "
         + ", ".join(f"{r[2]} +{r[0]}/−{r[1]}" for r in shared_numstat) + ".", "",
         "## Totals", ""]
    L += md_table(["calls", "input tokens", "output tokens (est.)", "max input / call", "USD (list price)"],
                  [[fmt(tot["calls"]), fmt(tot["input_tokens"]), fmt(tot["output_tokens_est"]),
                    fmt(tot["max_input_single_call"]), f"${tot['usd_list_price']:.2f}"]])
    L += ["", "## By block", ""]
    L += md_table(["block", "calls", "input tokens", "output (est.)", "max input / call", "USD"],
                  [[r.block, fmt(r.calls), fmt(r.input_tokens), fmt(r.output_est), fmt(r.max_input),
                    f"${r.usd_in + r.usd_out:.2f}"] for r in by_block.itertuples()])
    L += ["", "## By model", ""]
    L += md_table(["model", "env", "calls", "input tokens", "output (est.)", "max input / call", "USD"],
                  [[r.model, MODELS[r.model], fmt(r.calls), fmt(r.input_tokens), fmt(r.output_est), fmt(r.max_input),
                    f"${r.usd_in + r.usd_out:.2f}"] for r in by_model.itertuples()])
    L += ["", "## By cell", ""]
    L += md_table(["block", "model", "bundle", "enc", "rep", "pages", "calls", "mean obs tokens", "input tokens",
                   "output (est.)", "USD"],
                  [[r.block, r.model, r.bundle, r.encoding, r.repetition + 1, r.pages, r.calls, f"{r.mean_obs:,.0f}",
                    fmt(r.input_tokens), fmt(r.output_est), f"${r.usd:.2f}"] for r in by_cell.itertuples()])
    L += ["", "## Block 1 — reused cells (no call)", ""]
    rs = pd.DataFrame(reuse).groupby(["bundle", "source"]).page.apply(lambda s: f"{len(s)}: " + ", ".join(s))
    L += md_table(["bundle", "source", "pages"], [[b, s, v] for (b, s), v in rs.items()])
    L += ["", "Condition 5 true (of 240 targets): " + ", ".join(f"{b} {n}" for b, n in c5_counts.items())
          + f". B_full_minus_aria: condition 5 true → false on {len(aria_drop)} targets (signal_attrs = [aria-label] "
          "only; has_attribute_signal → no_attribute_signal under this ablation): " + ", ".join(aria_drop) + ".", "",
          "## Block 2 — F2L", "",
          f"Legend line = `{json.loads((DUMP / 'bundle_composition.json').read_text(encoding='utf-8'))['f2_legend']}`; "
          f"F2L − F2 observation tokens = {legend_tokens} (o200k_base).", "",
          "## Block 3 — repetitions", "",
          f"gpt-4.1-nano rep 1 in axisc (repetition 0): B_noVolatile×F1 {nano_rep1['F1']}, ×F2 {nano_rep1['F2']} "
          f"→ {'2 repetitions (rep 2, rep 3)' if nano_reps == [1, 2] else '3 repetitions'} planned.", "",
          "## Estimation method", "",
          "Input = observation tokens (dumped observation; stored record for a repeated cell) + "
          "`prompt_tokens_total − observation_tokens` of a stored event of the same page, task and model "
          "(Block 1: gpt-4.1 B_full×F1; Block 2: F2 of the same model and bundle; Block 3: the cell itself; "
          "Block 4: o4-mini B_noVolatile×F3). Output = `completion_tokens` of that stored event (o4-mini includes "
          "reasoning tokens). USD at public list price, no caching: "
          + ", ".join(f"{m} ${a:.2f}/${b:.2f} per M" for m, (a, b) in PRICE.items())
          + "; the Azure tariff must be checked separately. The paper reports tokens only.", ""]
    L += ["## Input tokens by page and block", ""]
    L += md_table(["page"] + [f"block {b}" for b in by_page.columns],
                  [[p] + [fmt(v) for v in row] for p, row in by_page.iterrows()])

    after = protected_state()
    assert before == after, "protected files changed during the run"
    L += ["", f"Protected files (FINDINGS.md, 24 matrix, 71 axisc, 24 truth) unchanged: {len(before)} SHA-256 equal.", ""]

    plan_cols = ["block", "model", "model_env", "bundle", "encoding", "page", "task_id", "repetition", "rep"]
    (OUT_DIR / "batch_plan.json").write_text(json.dumps({
        "description": "Revision 1 batch plan (Blocks 1–4); executed by REVISION_BATCH=1",
        "counts": ev.groupby("block").size().to_dict(), "reused_block1": reuse,
        "events": ev[plan_cols].to_dict("records")}, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
