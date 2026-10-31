"""
COP (B_noVolatile × F3) vs the Playwright-MCP-shaped ARIA snapshot (B_playwrightMCP × F4), gpt-4.1.
Existing records only, zero LLM, zero network; not in the registered batch plan.

One attempt per task; the two arms are paired on the same 240 targets.
  - rep 1: COP rep 1 (corpus) vs B_playwrightMCP × F4 rep 1 (corpus).
  - reps 2-3: COP reps 2-3 (revision batch, block 3) vs the same F4 rep 1, reused unchanged
    because no other F4 run exists.
Loading, record checks, strata and statistics come from revision1_batch_analysis.py (imported
read-only): Δ = COP − F4 (pp); b = COP-only, c = F4-only; OR = b/c with exact conditional CI;
McNemar uncorrected χ² and exact binomial p; 95% CI = page-clustered percentile bootstrap
(10,000 draws, seed 42). Breakdowns: stratum (truth.json signal attributes), page shadow level
(S0 / S1 / S2) and the crossover pages page_17 + page_18. Tokens: observation_tokens (o200k_base).

Writes experiments/results/revision1/cop_vs_aria.{md,json}.
"""
import json
import pathlib
import sys

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import revision1_batch_analysis as BA  # noqa: E402
from revision1_diagnostics import OUT_DIR, TRUTH_DIR, fmt_or, fmt_p, jsonable, md_table  # noqa: E402

OUT_PREFIX = OUT_DIR / "cop_vs_aria"
COP = ("B_noVolatile", "F3")
ARIA = ("B_playwrightMCP", "F4")
CROSSOVER = ("page_17", "page_18")
LEVELS = ["S0", "S1", "S2"]
LABEL = ("Not in the registered batch plan; existing records only, computed after the registered batch analysis "
         "and the real-site pilot results (f6a00d3)")


def load():
    corpus = BA.load_corpus()
    plan, plan_sha, events = BA.load_plan()
    batch = BA.load_batch(plan_sha, events)
    frame = pd.concat([corpus, batch], ignore_index=True)
    frame = frame[frame["model"] == BA.GPT]
    strata, _ = BA.load_truth()
    shadow = {}
    for tf in sorted(TRUTH_DIR.glob("*.truth.json")):
        tj = json.loads(tf.read_text(encoding="utf-8"))
        shadow[tj["page_id"]] = tj["shadow"]
    assert len(shadow) == 24 and set(shadow.values()) <= set(LEVELS)
    return BA.Data(frame, strata), strata, shadow


def subsets(index, shadow):
    out = [("all pages", None)]
    for lv in LEVELS:
        out.append((f"{lv} pages ({sum(1 for p in BA.PAGES if shadow[p] == lv)})",
                    {k for k in index if shadow[k[0]] == lv}))
    out.append(("page_17 + page_18 (crossover)", {k for k in index if k[0] in CROSSOVER}))
    return out


def tokens(cell, keys=None):
    v = cell["obs_tokens"] if keys is None else cell.loc[sorted(keys)]["obs_tokens"]
    return {"n": int(len(v)), "mean": float(v.mean()), "median": float(np.median(v))}


def main() -> int:
    data, strata, shadow = load()
    aria = data.cell(BA.GPT, *ARIA, 1)
    res = {"label": LABEL, "shadow": shadow, "comparisons": [], "tokens": {}}
    for rep in BA.REPS:
        cop = data.cell(BA.GPT, *COP, rep)
        for name, keep in subsets(aria.index, shadow):
            comp = BA.compare(aria, cop, strata, keep=keep)
            res["comparisons"].append({"rep": rep, "subset": name, "result": comp,
                                       "pages": sorted({k[0] for k in (keep or aria.index)})})
    r2, r3 = data.cell(BA.GPT, *COP, 2), data.cell(BA.GPT, *COP, 3)
    res["cop_rep2_equals_rep3"] = {"P5_equal": int((r2["P5"] == r3["P5"]).sum()),
                                   "Pnow_equal": int((r2["Pnow"] == r3["Pnow"]).sum())}
    cop1 = data.cell(BA.GPT, *COP, 1)
    for name, keep in subsets(aria.index, shadow):
        a, c = tokens(aria, keep), tokens(cop1, keep)
        res["tokens"][name] = {"F4": a, "COP": c, "ratio_mean_F4_over_COP": a["mean"] / c["mean"],
                               "ratio_median_F4_over_COP": a["median"] / c["median"]}
    for rep in (2, 3):
        res["tokens"][f"COP rep {rep} mean (all pages)"] = tokens(data.cell(BA.GPT, *COP, rep))
    OUT_PREFIX.with_suffix(".json").write_text(json.dumps(jsonable(res), ensure_ascii=False, indent=1) + "\n",
                                               encoding="utf-8", newline="\n")
    OUT_PREFIX.with_suffix(".md").write_text(render(res), encoding="utf-8", newline="\n")
    print(f"wrote {OUT_PREFIX}.md and .json")
    return 0


def render(res) -> str:
    L = ["# COP (B_noVolatile × F3) vs B_playwrightMCP × F4 — gpt-4.1, paired", "", f"**{LABEL}.**", "",
         "One attempt per task: each arm is one cell of one repetition, paired on the same 240 targets. COP rep 1 = "
         "original corpus run; COP reps 2-3 = revision-1 batch (block 3); B_playwrightMCP × F4 exists for rep 1 only "
         "and is the F4 arm of every row. Δ = COP − F4 (pp); b = COP-only, c = F4-only; OR = b/c with the exact "
         "conditional 95% CI; p exact = McNemar exact binomial; 95% CI = page-clustered percentile bootstrap (10,000 "
         "draws, seed 42; with 2 pages in the crossover row it is descriptive only). Strata from "
         "`shared/testbed/pages/*.truth.json` (`no_attribute_signal`: P5 is 0 by construction, shown for P_now "
         "only). Shadow level = truth.json `shadow` of the page. No multiplicity correction.", ""]
    hdr = ["COP rep", "pages", "stratum", "pred", "n", "F4 %", "COP %", "Δ pp", "95% CI (pp)", "b/c", "OR [95% CI]",
           "p exact", "p χ²"]
    for rep in BA.REPS:
        rows = []
        for x in (c for c in res["comparisons"] if c["rep"] == rep):
            for s in ("overall", "has_attribute_signal", "no_attribute_signal"):
                if s not in x["result"]:
                    continue
                for pname in ("P5", "P_now"):
                    if s == "no_attribute_signal" and pname == "P5":
                        continue
                    r = x["result"][s][pname]
                    disc = r["b_second_only"] + r["c_first_only"]
                    rows.append([rep, x["subset"], s, pname, r["n"], f"{r['rate_first_pct']:.1f}",
                                 f"{r['rate_second_pct']:.1f}", f"{r['delta_pp']:+.2f}",
                                 f"[{r['ci_lo_pp']:+.2f}, {r['ci_hi_pp']:+.2f}]",
                                 f"{r['b_second_only']}/{r['c_first_only']}",
                                 f"{fmt_or(r['odds_ratio'])} [{fmt_or(r['or_ci_lo'])}, {fmt_or(r['or_ci_hi'])}]"
                                 if disc else "n/a", fmt_p(r["p_exact"]), fmt_p(r["p"])])
        L += [f"## COP rep {rep} vs B_playwrightMCP × F4 rep 1", ""] + md_table(hdr, rows) + [""]
    same = res["cop_rep2_equals_rep3"]
    L += [f"COP reps 2 and 3 (separate calls, different event keys): P5 and P_now identical on "
          f"{same['P5_equal']}/240 and {same['Pnow_equal']}/240 events, so their two tables coincide.", ""]
    L += ["Pages per shadow level: " + "; ".join(
        f"{lv}: " + ", ".join(p for p in BA.PAGES if res["shadow"][p] == lv) for lv in LEVELS) + ".", ""]
    L += ["## Observation tokens (o200k_base), COP rep 1 vs B_playwrightMCP × F4 rep 1", ""]
    L += md_table(["pages", "n", "F4 mean", "COP mean", "F4 / COP (means)", "F4 median", "COP median",
                   "F4 / COP (medians)"],
                  [[k, v["F4"]["n"], f"{v['F4']['mean']:,.0f}", f"{v['COP']['mean']:,.0f}",
                    f"{v['ratio_mean_F4_over_COP']:.2f}", f"{v['F4']['median']:,.0f}", f"{v['COP']['median']:,.0f}",
                    f"{v['ratio_median_F4_over_COP']:.2f}"]
                   for k, v in res["tokens"].items() if "F4" in v])
    L += ["", "COP observations are identical across reps (same pages, bundle, encoding): " + ", ".join(
        f"rep {k.split()[2]} mean {v['mean']:,.0f}" for k, v in res["tokens"].items() if "F4" not in v) + "."]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
