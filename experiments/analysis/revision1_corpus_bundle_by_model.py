"""
Exploratory: B_full vs B_noVolatile per model on the 24-page corpus, from existing records only.
Not pre-registered (computed after batch_analysis.md and the real-site pilot results, f6a00d3).
Zero LLM, zero network.

Records: the corpus (gpt-4.1 matrix runs; Axis C runs of gpt-4.1-nano, o4-mini,
claude-sonnet-4-6) and the revision batch (batch_runs/: reps 2-3, F2L, o4-mini B_full×F1).
Loading, record checks, strata and paired statistics come from revision1_batch_analysis.py
(imported read-only): McNemar (exact binomial p, uncorrected χ²), page-clustered percentile
bootstrap of Δ (10,000 draws, seed 42). Claude's Axis C records are loaded the same way
(BA.standardise) and paired on the events present in both arms (TPM-skipped events missing).

Per model: every (encoding, rep) with both B_full and B_noVolatile, and COP (B_noVolatile × F3)
vs B_full × F1 per rep. Writes experiments/results/revision1/corpus_bundle_by_model.{md,json}.
"""
import collections
import json
import pathlib
import sys

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import revision1_batch_analysis as BA  # noqa: E402
from revision1_diagnostics import OUT_DIR, RUNS, fmt_p, jsonable, md_table  # noqa: E402

CLAUDE = "claude-sonnet-4-6"
MODELS = [BA.GPT, BA.NANO, BA.O4, CLAUDE]
ENCODINGS = ["F0", "F1", "F2", "F2L", "F3"]
OUT_PREFIX = OUT_DIR / "corpus_bundle_by_model"
LABEL = ("EXPLORATORY — not pre-registered; existing corpus and batch records only, computed after the registered "
         "batch analysis and the real-site pilot results (f6a00d3)")


def load() -> tuple[pd.DataFrame, dict]:
    corpus = BA.load_corpus()
    plan, plan_sha, events = BA.load_plan()
    batch = BA.load_batch(plan_sha, events)
    recs = [r for f in sorted(RUNS.glob("axisc_claude-sonnet-4-6_page_*.jsonl")) for r in BA.read_jsonl(f)]
    assert len(recs) == 880, len(recs)
    claude = BA.standardise(pd.DataFrame(recs), CLAUDE, "corpus")
    frame = pd.concat([corpus, batch, claude], ignore_index=True)
    frame = frame[frame["bundle"].isin(["B_full", "B_noVolatile"])]
    dup = frame.duplicated(["model", "bundle", "encoding", "rep", "page", "task_id"])
    assert not dup.any(), frame[dup].head()
    strata, _ = BA.load_truth()
    return frame, strata


def cell(frame, model, bundle, enc, rep) -> pd.DataFrame:
    c = frame[(frame["model"] == model) & (frame["bundle"] == bundle) & (frame["encoding"] == enc)
              & (frame["rep"] == rep)]
    return c.set_index(["page", "task_id"]).sort_index()


def availability(frame) -> list[dict]:
    out = []
    for (m, b, e, r), g in frame.groupby(["model", "bundle", "encoding", "rep"]):
        pages = sorted(set(g["page"]))
        partial = sorted(p for p, n in g.groupby("page").size().items() if n < 10)
        out.append({"model": m, "bundle": b, "encoding": e, "rep": int(r), "n": len(g), "pages": len(pages),
                    "missing_pages": sorted(set(BA.PAGES) - set(pages)), "partial_pages": partial,
                    "origin": ",".join(sorted(set(g["origin"])))})
    return out


def pair(frame, strata, model, first, second, label, kind):
    a, b = cell(frame, model, *first), cell(frame, model, *second)
    if a.empty or b.empty:
        return None
    idx = a.index.intersection(b.index)
    res = BA.compare(a.loc[idx], b.loc[idx], strata)
    return {"model": model, "kind": kind, "label": label, "first": first, "second": second,
            "n_first_cell": len(a), "n_second_cell": len(b), "n_paired": len(idx), "result": res}


def analyse(frame, strata):
    rows, missing = [], []
    for m in MODELS:
        have = {(e, r) for (b, e, r) in frame[frame["model"] == m][["bundle", "encoding", "rep"]]
                .drop_duplicates().itertuples(index=False, name=None) if b == "B_full"}
        have_nv = {(e, r) for (b, e, r) in frame[frame["model"] == m][["bundle", "encoding", "rep"]]
                   .drop_duplicates().itertuples(index=False, name=None) if b == "B_noVolatile"}
        for e, r in sorted(have | have_nv, key=lambda x: (ENCODINGS.index(x[0]), x[1])):
            if (e, r) in have and (e, r) in have_nv:
                rows.append(pair(frame, strata, m, ("B_full", e, r), ("B_noVolatile", e, r),
                                 f"B_noVolatile vs B_full, {e}, rep {r}", "same encoding"))
            else:
                missing.append({"model": m, "comparison": f"B_noVolatile vs B_full, {e}, rep {r}",
                                "missing": "B_full" if (e, r) not in have else "B_noVolatile"})
        for r in (1, 2, 3):
            cop, naive = ("F3", r) in have_nv, ("F1", r) in have
            if cop and naive:
                rows.append(pair(frame, strata, m, ("B_full", "F1", r), ("B_noVolatile", "F3", r),
                                 f"COP (B_noVolatile×F3) vs B_full×F1, rep {r}", "COP"))
            elif cop or naive:
                missing.append({"model": m, "comparison": f"COP vs B_full×F1, rep {r}",
                                "missing": "B_noVolatile×F3" if not cop else "B_full×F1"})
    return [x for x in rows if x], missing


def render(res) -> str:
    L = ["# Corpus — B_full vs B_noVolatile per model", "", f"**{LABEL}.**", "",
         "Existing records only, no model calls. Loading, checks, strata (`has_attribute_signal` / "
         "`no_attribute_signal` from `shared/testbed/pages/*.truth.json`) and statistics are those of the registered "
         "`revision1_batch_analysis.py`: Δ = second − first (pp); McNemar exact binomial p (b = second-only, c = "
         "first-only); 95% CI = page-clustered percentile bootstrap (10,000 draws, seed 42). P5 is 0 in "
         "`no_attribute_signal` by construction, so that stratum is shown for P_now only. Claude's arms are paired on "
         "the events present in both cells (TPM-skipped events are missing). gpt-4.1 and gpt-4.1-nano at "
         "temperature 0; o4-mini at the service default; rep 1 = the original corpus run, reps 2-3 and F2L = the "
         "revision-1 batch. No multiplicity correction (exploratory).", ""]
    hdr = ["model", "comparison", "stratum", "n", "P5 first %", "P5 second %", "Δ P5 pp [95% CI]", "p exact",
           "P_now first %", "P_now second %", "Δ P_now pp [95% CI]", "p exact"]
    body = []
    for x in res["pairs"]:
        for s in ("overall", "has_attribute_signal", "no_attribute_signal"):
            if s not in x["result"]:
                continue
            p5, pn = x["result"][s]["P5"], x["result"][s]["P_now"]
            show_p5 = s != "no_attribute_signal"
            body.append([x["model"], x["label"], s, pn["n"],
                         f"{p5['rate_first_pct']:.1f}" if show_p5 else "—",
                         f"{p5['rate_second_pct']:.1f}" if show_p5 else "—",
                         f"{p5['delta_pp']:+.2f} [{p5['ci_lo_pp']:+.2f}, {p5['ci_hi_pp']:+.2f}]" if show_p5 else "—",
                         fmt_p(p5["p_exact"]) if show_p5 else "—",
                         f"{pn['rate_first_pct']:.1f}", f"{pn['rate_second_pct']:.1f}",
                         f"{pn['delta_pp']:+.2f} [{pn['ci_lo_pp']:+.2f}, {pn['ci_hi_pp']:+.2f}]", fmt_p(pn["p_exact"])])
    L += ["## Paired comparisons", ""] + md_table(hdr, body)
    L += ["", "Paired events where a cell is incomplete: " + "; ".join(
        f"{x['model']} {x['label']}: {x['n_paired']} paired ({x['n_first_cell']} / {x['n_second_cell']} in the cells)"
        for x in res["pairs"] if not (x["n_paired"] == x["n_first_cell"] == x["n_second_cell"] == 240)) + "."]
    L += ["", "## Comparisons not possible (cell missing)", ""]
    L += md_table(["model", "comparison", "missing arm"], [[m["model"], m["comparison"], m["missing"]]
                                                           for m in res["missing"]])
    L += ["", "Also not in these records: B_noVolatileConsistent exists for gpt-4.1 only, on 6 pages (`consistent_runs/`, "
              "see `sensitivity_consistent.md`); no model other than gpt-4.1 has F0 or B_noVolatile×F2L with B_full.", ""]
    L += ["## Cells present (B_full, B_noVolatile)", ""]
    L += md_table(["model", "bundle", "enc", "rep", "records", "pages", "missing pages", "partial pages", "origin"],
                  [[a["model"], a["bundle"], a["encoding"], a["rep"], a["n"], a["pages"],
                    ", ".join(a["missing_pages"]) or "—", ", ".join(a["partial_pages"]) or "—", a["origin"]]
                   for a in sorted(res["availability"], key=lambda a: (MODELS.index(a["model"]), a["bundle"],
                                                                         ENCODINGS.index(a["encoding"]), a["rep"]))])
    return "\n".join(L) + "\n"


def main() -> int:
    frame, strata = load()
    pairs, missing = analyse(frame, strata)
    res = {"label": LABEL, "pairs": pairs, "missing": missing, "availability": availability(frame)}
    OUT_PREFIX.with_suffix(".json").write_text(json.dumps(jsonable(res), ensure_ascii=False, indent=1) + "\n",
                                               encoding="utf-8", newline="\n")
    OUT_PREFIX.with_suffix(".md").write_text(render(res), encoding="utf-8", newline="\n")
    print(f"wrote {OUT_PREFIX}.md and .json; {len(pairs)} comparisons, {len(missing)} not possible")
    return 0


if __name__ == "__main__":
    sys.exit(main())
