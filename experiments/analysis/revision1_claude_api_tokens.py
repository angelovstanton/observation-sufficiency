"""Exploratory check of the COP token saving under Claude's API-reported prompt tokens.

Reads existing claude-sonnet-4-6 records and reuses revision1_diagnostics.page_bootstrap.
Writes only claude_api_tokens.{md,json}; an identical rerun leaves them untouched.
Run from the repo root.
"""

import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
import sys

import numpy as np

sys.dont_write_bytecode = True
from revision1_diagnostics import page_bootstrap, pct_ci

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "experiments/results/revision1"
CELLS = [("B_full", "F1"), ("B_noVolatile", "F1"),
         ("B_noVolatile", "F2"), ("B_noVolatile", "F3")]
REFERENCE, COP = CELLS[0], CELLS[-1]
MEASURES = ("observation_tokens", "prompt_tokens_total")
N_BOOT, SEED = 10_000, 42
TITLE = "# EXPLORATORY — not part of any registered plan"
LIMITATIONS = [
    "The Pareto frontier cannot be recomputed under Claude tokens because Claude covers only 4 cells.",
    "gpt-4.1 uses o200k_base, so the existing gpt-4.1 API-token check "
    "(diagnostics.md D3) tests the prompt overhead, not a different tokenizer.",
    "Claude prompt_tokens_total is Anthropic API-reported for the whole prompt "
    "(system + observation + task); no Claude observation-only token count is available. "
    "This comparison combines tokenizer dependence and prompt overhead; it does not isolate them.",
    "Coverage exclusions constrain generalization to the omitted large/extreme pages. "
    "No LLM calls, network access, or retokenization are used by this script.",
]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_state():
    paths = {REPO / "experiments/FINDINGS.md"}
    paths.update(p for p in (REPO / "experiments/runs").rglob("*") if p.is_file())
    paths.update(p for p in OUT.rglob("*") if p.is_file())
    # Git enumerates source truth files without traversing build/dependency trees.
    truth_names = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "*truth.json"],
        cwd=REPO, check=True, capture_output=True).stdout.decode("utf-8").split("\0")
    paths.update(REPO / name for name in truth_names if name)
    return {str(p.relative_to(REPO)): sha256(p) for p in sorted(paths)}


def independent_check(files):
    """Separate raw-record aggregation and Python random page bootstrap (no stats.py)."""
    records = [json.loads(line) for path in files
               for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ref = {(r["page"], r["task_id"]): r for r in records
           if (r["bundle"], r["encoding"]) == REFERENCE}
    cop = {(r["page"], r["task_id"]): r for r in records
           if (r["bundle"], r["encoding"]) == COP}
    keys = sorted(ref.keys() & cop.keys())
    pages = sorted({k[0] for k in keys})
    result = {}
    for metric in MEASURES:
        ref_mean = sum(ref[k][metric] for k in keys) / len(keys)
        cop_mean = sum(cop[k][metric] for k in keys) / len(keys)
        totals = {p: (sum(ref[k][metric] for k in keys if k[0] == p),
                      sum(cop[k][metric] for k in keys if k[0] == p)) for p in pages}
        rng = random.Random(SEED)
        draws = []
        for _ in range(N_BOOT):
            sampled = rng.choices(pages, k=len(pages))
            draws.append(100 * (1 - sum(totals[p][1] for p in sampled)
                                / sum(totals[p][0] for p in sampled)))
        # Independent linear percentile interpolation, matching NumPy's default definition.
        draws.sort()
        def percentile(q):
            position = (len(draws) - 1) * q
            lower = math.floor(position)
            return draws[lower] + (position - lower) * (draws[lower + 1] - draws[lower])
        result[metric] = {"reference_mean": ref_mean, "cop_mean": cop_mean,
                          "reduction_pct": 100 * (1 - cop_mean / ref_mean),
                          "ci95_pct": [percentile(.025), percentile(.975)]}
    return result


def main():
    before = protected_state()
    files = sorted((REPO / "experiments/runs").glob("axisc_claude-sonnet-4-6_page_*.jsonl"))
    if len(files) != 23:
        raise ValueError(f"Expected 23 input files, found {len(files)}")
    cells = {c: {} for c in CELLS}
    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            cell = (row["bundle"], row["encoding"])
            key = (row["page"], row["task_id"])
            if (row["model"], row["regime"], row["repetition"], row["tokenizer_version"]) != (
                    "claude-sonnet-4-6", "full_page", 0, "o200k_base"):
                raise ValueError(f"Unexpected condition in {path.name}: {key}")
            if cell not in cells or key in cells[cell]:
                raise ValueError(f"Unexpected cell or duplicate event: {cell}, {key}")
            if any(type(row[m]) is not int or row[m] <= 0 for m in MEASURES):
                raise ValueError(f"Invalid token count: {cell}, {key}")
            cells[cell][key] = row
    common = sorted(cells[REFERENCE].keys() & cells[COP].keys())
    pages = sorted({key[0] for key in common})
    if len(common) != 210 or len(pages) != 21 or any(
            sum(k[0] == p for k in common) != 10 for p in pages):
        raise ValueError("Expected 210 common events, 21 pages, 10 events/page")
    excluded = []
    for number in range(1, 25):
        page = f"pages/page_{number:02d}.html"
        if page not in pages:
            counts = {f"{b}×{e}": sum(k[0] == page for k in cells[b, e]) for b, e in CELLS}
            reason = ("No Claude input file; no events in either cell (TPM skip)." if number == 17
                      else "No B_full×F1 reference events; 10 COP events cannot be paired (partial TPM skip).")
            excluded.append({"page": page, "reason": reason, "available_events_by_cell": counts})
    results = {}
    for metric in MEASURES:
        arrays = {name: np.array([sum(cells[cell][k][metric] for k in common if k[0] == p)
                                  for p in pages], dtype=float)
                  for name, cell in (("ref", REFERENCE), ("cop", COP))}
        # Both cells have the same event counts, so ratio of sums = ratio of means.
        draws = page_bootstrap(pages, arrays, lambda t: 1 - t["cop"] / t["ref"],
                               n_boot=N_BOOT, seed=SEED)
        reduction = 1 - arrays["cop"].sum() / arrays["ref"].sum()
        results[metric] = {"reference_mean": float(arrays["ref"].sum() / len(common)),
                           "cop_mean": float(arrays["cop"].sum() / len(common)),
                           "reduction": float(reduction), "reduction_pct": float(100 * reduction),
                           "ci95_pct": [100 * x for x in pct_ci(draws)]}
    ratios = []
    for cell, records in cells.items():
        sums = {m: sum(r[m] for r in records.values()) for m in MEASURES}
        ratios.append({"cell": "×".join(cell), "events": len(records),
                       "pages": len({k[0] for k in records}), **sums,
                       "api_to_observation_ratio": sums["prompt_tokens_total"] / sums["observation_tokens"]})
    check = independent_check(files)
    mismatches = []
    for metric, expected in zip(MEASURES, ((17391, 10856, 37.57), (20443, 13335, 34.77))):
        actual = results[metric]
        for field in ("reference_mean", "cop_mean", "reduction_pct"):
            if not math.isclose(actual[field], check[metric][field], abs_tol=1e-10):
                raise ValueError(f"Independent point estimate mismatch: {metric} {field}")
        rounded = (round(actual["reference_mean"]), round(actual["cop_mean"]), round(actual["reduction_pct"], 2))
        if rounded != expected:
            mismatches.append({"metric": metric, "expected": expected, "actual": rounded})
    report = {"status": "EXPLORATORY — not part of any registered plan", "model": "claude-sonnet-4-6",
              "key": ["page", "task_id"], "reference": list(REFERENCE), "cop": list(COP),
              "common_events": len(common), "common_pages": pages, "excluded_pages": excluded,
              "bootstrap": {"function": "revision1_diagnostics.page_bootstrap", "replicates": N_BOOT,
                            "seed": SEED, "ci": "page-clustered percentile, 2.5/97.5 percentiles",
                            "page_order": "sorted", "fresh_generator_per_measure": True},
              "measures": results, "cell_ratios_scope": "all available events per cell (unpaired)",
              "cell_ratios": ratios, "independent_python_random_check": check,
              "supplied_point_estimate_mismatches": mismatches, "limitations": LIMITATIONS,
              "input_sha256": {p.relative_to(REPO).as_posix(): sha256(p) for p in files}}
    md = [TITLE, "", "Tokenizer dependence of the COP saving (claude-sonnet-4-6).", "",
          "Run: `python experiments/analysis/revision1_claude_api_tokens.py` (local dependencies only).", "",
          "Reference: B_full×F1; COP: B_noVolatile×F3. Key = (page, task_id). "
          "Only the intersection is used: **210 events, 21 pages**, 10 events per page per cell. "
          "Records are included regardless of grounding success.", "",
          "Reduction = 1 − mean(COP)/mean(reference). 95% page-clustered percentile bootstrap: "
          "10,000 replicates, seed 42, sorted page order, fresh generator per measure. "
          "Uses `revision1_diagnostics.page_bootstrap` and `pct_ci` directly; each sampled page "
          "contributes all 10 paired events to both cells.", "",
          "| Measure | Mean reference | Mean COP | Reduction % | 95% CI % |",
          "|---|---:|---:|---:|---:|"]
    for metric, r in results.items():
        label = "observation_tokens (o200k_base)" if metric == MEASURES[0] else "prompt_tokens_total (Anthropic API; whole prompt)"
        md.append(f"| {label} | {r['reference_mean']:.6f} | {r['cop_mean']:.6f} | {r['reduction_pct']:.4f} | "
                  f"[{r['ci95_pct'][0]:.4f}, {r['ci95_pct'][1]:.4f}] |")
    md += ["", "## Coverage exclusions", ""]
    for e in excluded:
        md.append(f"- {e['page']}: {e['reason']} Available events: {e['available_events_by_cell']}.")
    md += ["", "The absent/partial-cell pattern is visible in the input records; TPM attribution "
           "is documented in existing experiments/FINDINGS.md (Axis C coverage). No missing events are imputed.", "",
           "## API / observation ratios", "",
           "sum(prompt_tokens_total) / sum(observation_tokens), using **all available events per cell**. "
           "These denominators differ from the paired reduction sample.", "",
           "| Cell | Events | Pages | API token sum | Observation token sum | Ratio |",
           "|---|---:|---:|---:|---:|---:|"]
    for r in ratios:
        md.append(f"| {r['cell']} | {r['events']} | {r['pages']} | {r['prompt_tokens_total']} | "
                  f"{r['observation_tokens']} | {r['api_to_observation_ratio']:.6f} |")
    md += ["", "## Independent cross-check", "",
           "Separate raw-record aggregation and Python random.Random(42).choices page bootstrap, "
           "10,000 replicates, independent percentile interpolation; no stats.py computation. "
           "Point estimates agree with the primary computation. Small CI differences reflect different draws.", ""]
    for metric, r in check.items():
        md.append(f"- {metric}: {r['reference_mean']:.6f} → {r['cop_mean']:.6f}; reduction "
                  f"{r['reduction_pct']:.4f}%; Python random 95% CI "
                  f"[{r['ci95_pct'][0]:.4f}, {r['ci95_pct'][1]:.4f}]%.")
    md += ["", f"Supplied rounded point-estimate mismatches: {mismatches or 'none'}. "
           "The supplied API CI ≈ [30.7, 37.5]% is approximate; use the diagnostics-resampler CI above.",
           "", "## Interpretation limits", ""] + [f"- {s}" for s in LIMITATIONS]
    md += ["", "## Input SHA-256", "", "| Input | SHA-256 |", "|---|---|"]
    md += [f"| {p} | {digest} |" for p, digest in report["input_sha256"].items()]
    payloads = {OUT / "claude_api_tokens.json": json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                OUT / "claude_api_tokens.md": "\n".join(md) + "\n"}
    # Preflight both paths before creating either; never overwrite existing results.
    for path, content in payloads.items():
        if path.exists() and path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"Refusing to modify existing output: {path}")
    if protected_state() != before:
        raise RuntimeError("Protected evidence changed during computation")
    for path, content in payloads.items():
        if not path.exists():
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
    after = protected_state()
    if any(after.get(p) != digest for p, digest in before.items()):
        raise RuntimeError("Existing protected file changed")
    print(json.dumps({"common_events": len(common), "pages": len(pages), "measures": results,
                      "cell_ratios": ratios, "mismatches": mismatches}, indent=2))
    print(f"Protected existing files unchanged: {len(before)}")


if __name__ == "__main__":
    main()
