"""
revision1_diagnostics.py — diagnostics D1, D2, D3 on the existing corpus (exploratory, not pre-registered).

Reads the corpus (experiments/runs/*.jsonl) and the testbed truth files; writes only under
experiments/results/revision1/.  D2 re-scores rewritten locators through the C# Oracle via
the zero-LLM `--replay` mode (dotnet + Playwright).

  0. Guards: SHA-256 of FINDINGS.md (pinned to run_all.py), the corpus and truth files, before and after.
  1. Controls: reproduce the published numbers (transitions 515/11/102/140/192, OR 9.27 = 102/11,
     90 of 102 recoveries are volatile catches, bootstrap CI, page-level tests, 601/311 grabbed split,
     token reductions, Pareto 4/17 + COP).  Any mismatch exits with code 1.
  2. D1: relaxed predicates (P5, P_now = cond 1+2, P_now_np = cond 1+2+4).
  3. D2: F2 abbreviated-key mechanism + Oracle replay of key-expanded locators.
  4. D3: page-level effect sizes, GEE, clustered McNemar, Holm family, token bootstrap CIs,
     grabbed subtypes, Pareto under API-reported prompt tokens.
  5. diagnostics.md + diagnostics.json and a summary of every number that differs from the published one.

Seed 42 for every bootstrap (fresh generator per statistic, as in stats.py); no timestamps in the output.

Run: python experiments/analysis/revision1_diagnostics.py
"""

# UTF-8 console-independence (same convention as the other analysis modules).
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import hashlib
import json
import math
import pathlib
import re
import shutil
import subprocess
import warnings
from math import comb

import numpy as np
import pandas as pd
from scipy.stats import beta, binomtest, chi2, norm, wilcoxon

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))

from load import load_dataframe, DOM_ENCODINGS          # noqa: E402
import stats as published_stats                          # noqa: E402
from bundle_ladder import BUNDLE_LADDER_ORDER            # noqa: E402
import cross_model                                       # noqa: E402

OUT_DIR    = REPO / "experiments" / "results" / "revision1"
REPLAY_DIR = OUT_DIR / "replay"
FINDINGS   = REPO / "experiments" / "FINDINGS.md"
RUNS       = REPO / "experiments" / "runs"
TRUTH_DIR  = REPO / "shared" / "testbed" / "pages"
RUN_ALL    = HERE / "run_all.py"
ENCODERS_CS = REPO / "shared" / "harness" / "ObservationEncoders.cs"
RUNNER_CS   = REPO / "shared" / "harness" / "GroundingRunner.cs"

N_BOOT = published_stats.N_BOOTSTRAP     # 10,000
REPLAY_ATTEMPTS = 3
SEED   = published_stats.RNG_SEED        # 42

LACKED      = "observation_lacked_stable_signal"
GRABBED     = "model_grabbed_brittle_signal"
UNREACHABLE = "output_format_unreachable"

KEY = ["page", "task_id", "encoding", "repetition"]
PRED_COLS = [
    "success", "failure_mode", "predicate_unique_match", "predicate_matches_oracle",
    "predicate_non_volatile", "predicate_non_positional",
    "stable_signal_present_in_bundle", "locator_value",
]

# Published values used as controls (source in the comment of each entry).
PUBLISHED = {
    "transitions": {  # FINDINGS.md transition matrix (BF state -> NV state)
        ("success", "success"): 515, ("success", "grabbed"): 11,
        ("grabbed", "success"): 102, ("grabbed", "grabbed"): 140,
        ("lacked", "lacked"): 192,
    },
    "b": 102, "c": 11, "odds_ratio": 9.27, "mcnemar_chi2": 73.28,
    "volatile_catches": 90, "recoveries": 102,
    "boot_ci": (4.90, 15.52),                       # page-clustered percentile bootstrap, stats.py
    "sign_p": 4.0e-4, "wilcoxon_p": 3.5e-4,         # page-level sign / Wilcoxon tests, stats.py
    "grabbed_total": 912, "grabbed_volatile": 601, "grabbed_other": 311,
    "cop_reduction_pct": 34.0, "f3_reduction_pct": 29.1,
    "frontier": {("B_identityCore", "F3"), ("B_identityCore", "F0"),
                 ("B_playwrightMCP", "F4"), ("B_noVolatile", "F3")},
    "cop": ("B_noVolatile", "F3"),
}


# Generic helpers

def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_state() -> dict:
    """
    SHA-256 snapshot of the evidence files — experiments/FINDINGS.md, the JSONL corpus
    (matrix + axisc) and the testbed truth files — compared before and after the run.
    This guard independently hashes the evidence files. FINDINGS.md is additionally pinned to
    run_all.py's EXPECTED_FINDINGS_SHA256 (read as text, not imported).
    """
    matrix = sorted(RUNS.glob("matrix_page_*.jsonl"))
    axisc  = sorted(RUNS.glob("axisc_*.jsonl"))
    truth  = sorted(TRUTH_DIR.glob("*.truth.json"))
    if (len(matrix), len(axisc), len(truth)) != (24, 71, 24):
        raise SystemExit(f"[guard] unexpected evidence file counts: matrix={len(matrix)}, "
                         f"axisc={len(axisc)}, truth={len(truth)} (expected 24/71/24)")
    state = {p.relative_to(REPO).as_posix(): sha256(p) for p in [FINDINGS] + matrix + axisc + truth}
    pinned = re.search(r'EXPECTED_FINDINGS_SHA256\s*=\s*"([0-9a-f]{64})"',
                       RUN_ALL.read_text(encoding="utf-8"))
    if not pinned or state["experiments/FINDINGS.md"] != pinned.group(1):
        raise SystemExit("[guard] experiments/FINDINGS.md does not match run_all.py EXPECTED_FINDINGS_SHA256")
    return state


def jsonable(x):
    """Recursively convert numpy / non-finite values into JSON-safe values."""
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, (np.floating, float)):
        x = float(x)
        if math.isnan(x):
            return "nan"
        if math.isinf(x):
            return "inf" if x > 0 else "-inf"
        return x
    return x


def fmt_p(p) -> str:
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "n/a"
    return f"{p:.2e}" if p < 1e-3 else f"{p:.4f}"


def fmt_or(v) -> str:
    return "inf" if math.isinf(v) else f"{v:.2f}"


def md_table(headers, rows) -> list[str]:
    out = ["| " + " | ".join(str(h) for h in headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def state_of(success: bool, failure_mode) -> str:
    if success:
        return "success"
    return {LACKED: "lacked", GRABBED: "grabbed", UNREACHABLE: "unreach"}[failure_mode]


def mcnemar(first: np.ndarray, second: np.ndarray) -> dict:
    """
    Paired comparison of two boolean outcome vectors.
    b = second-only successes, c = first-only successes (stats.py convention:
    b = NV-only, c = BF-only).  Uncorrected chi-square (stats._mcnemar_chi2),
    exact binomial p, OR = b/c with the exact conditional 95% CI
    (Clopper-Pearson on b/(b+c), transformed to pi/(1-pi)).
    """
    first = np.asarray(first, dtype=bool)
    second = np.asarray(second, dtype=bool)
    n11 = int((first & second).sum())
    b   = int((~first & second).sum())
    c   = int((first & ~second).sum())
    n00 = int((~first & ~second).sum())
    if b + c > 0:
        chi2_stat, p = published_stats._mcnemar_chi2(b, c)
        p_exact = float(binomtest(b, b + c, 0.5).pvalue)
    else:
        chi2_stat, p, p_exact = float("nan"), float("nan"), float("nan")
    if b + c == 0:   # no discordant pairs: OR and its CI are undefined
        odds, or_lo, or_hi = float("nan"), float("nan"), float("nan")
    else:
        odds = b / c if c > 0 else float("inf")
        pi_lo = float(beta.ppf(0.025, b, c + 1)) if b > 0 else 0.0
        pi_hi = float(beta.ppf(0.975, b + 1, c)) if c > 0 else 1.0
        or_lo = pi_lo / (1 - pi_lo)
        or_hi = pi_hi / (1 - pi_hi) if pi_hi < 1 else float("inf")
    n = len(first)
    return {
        "n": n, "n11_both": n11, "b_second_only": b, "c_first_only": c, "n00_neither": n00,
        "success_first": n11 + c, "success_second": n11 + b,
        "rate_first_pct": (n11 + c) / n * 100, "rate_second_pct": (n11 + b) / n * 100,
        "delta_pp": (b - c) / n * 100,
        "chi2": chi2_stat, "p": p, "p_exact": p_exact,
        "odds_ratio": odds, "or_ci_lo": or_lo, "or_ci_hi": or_hi,
    }


def page_bootstrap(page_order, arrays: dict, stat_fn, n_boot=N_BOOT, seed=SEED) -> np.ndarray:
    """
    Page-cluster percentile bootstrap with the exact draw sequence of
    stats._cluster_bootstrap_ci: fresh default_rng(seed), and per replicate
    rng.choice(pages, size=len(pages), replace=True) over the same page order.
    `arrays` holds per-page sums aligned to page_order; stat_fn receives the
    resampled totals.  Equivalent to concatenating the sampled pages' records.
    """
    pages = np.asarray(page_order, dtype=object)
    index_of = {p: i for i, p in enumerate(page_order)}
    rng = np.random.default_rng(seed)
    out = np.empty(n_boot)
    for i in range(n_boot):
        sampled = rng.choice(pages, size=len(pages), replace=True)
        sel = np.fromiter((index_of[p] for p in sampled), dtype=int, count=len(pages))
        out[i] = stat_fn({k: v[sel].sum() for k, v in arrays.items()})
    return out


def pct_ci(draws: np.ndarray) -> tuple[float, float]:
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def holm(pvals: list[float]) -> list[float]:
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pvals[i])
        adj[i] = min(1.0, running)
    return adj


# Controls

class Controls:
    def __init__(self):
        self.rows = []

    def check(self, label, got, expected, tol=0.0):
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            ok = abs(float(got) - float(expected)) <= tol
        else:
            ok = got == expected
        self.rows.append({"control": label, "recomputed": got, "published": expected,
                          "tolerance": tol, "ok": bool(ok)})
        return ok

    def enforce(self):
        failed = [r for r in self.rows if not r["ok"]]
        for r in self.rows:
            flag = "OK  " if r["ok"] else "FAIL"
            print(f"  [{flag}] {r['control']}: recomputed={r['recomputed']!r} "
                  f"published={r['published']!r}")
        if failed:
            print(f"\n[controls] {len(failed)} control(s) do not reproduce — stopping.")
            raise SystemExit(1)


def build_pairs(df, first_bundle, second_bundle, encodings=DOM_ENCODINGS):
    """
    One row per event shared by two bundles, suffixes _bf (first) / _nv (second).
    Same filter and merge as stats._build_pairs, so the row and page order are
    identical (required for the bootstrap to reproduce the published CI).
    """
    a = df[(df["bundle"] == first_bundle) & df["encoding"].isin(encodings)][
        KEY + PRED_COLS + ["semantic_density"]]
    b = df[(df["bundle"] == second_bundle) & df["encoding"].isin(encodings)][KEY + PRED_COLS]
    return a.merge(b, on=KEY, suffixes=("_bf", "_nv"))


def build_encoding_pairs(df, bundle, first_enc, second_enc):
    k = ["page", "task_id", "repetition"]
    a = df[(df["bundle"] == bundle) & (df["encoding"] == first_enc)][k + ["success"]]
    b = df[(df["bundle"] == bundle) & (df["encoding"] == second_enc)][k + ["success"]]
    return a.merge(b, on=k, suffixes=("_bf", "_nv"))


def pareto_walk(cells: pd.DataFrame, cost_col: str) -> pd.DataFrame:
    """Frontier walk exactly as pareto.py: sort by cost, keep strictly-improving success."""
    s = cells.sort_values(cost_col).copy()
    s["pareto_status"] = "dominated"
    best = -1.0
    for idx in s.index:
        if s.loc[idx, "success_rate"] > best:
            s.loc[idx, "pareto_status"] = "FRONTIER"
            best = s.loc[idx, "success_rate"]
    return s


def pareto_cells(df) -> pd.DataFrame:
    bundles = ["B_full", "B_noVolatile", "B_noState", "B_noSemantic", "B_identityCore"]
    recs = df[(df["bundle"].isin(bundles) & df["encoding"].isin(DOM_ENCODINGS))
              | (df["bundle"] == "B_playwrightMCP")]
    assert len(recs) == 5040
    cells = recs.groupby(["bundle", "encoding"]).agg(
        n_success=("success", "sum"), n_records=("success", "count"),
        mean_obs_tokens=("observation_tokens", "mean"),
        mean_api_prompt_tokens=("prompt_tokens_total", "mean"),
    )
    cells["success_rate"] = cells["n_success"] / cells["n_records"]
    return cells


def cop_of(walked: pd.DataFrame):
    frontier = walked[walked["pareto_status"] == "FRONTIER"]
    return frontier[frontier["success_rate"] > 0.50].iloc[0].name


# D2 helpers

HTML_TAGS = {
    "a", "abbr", "address", "area", "article", "aside", "audio", "b", "bdi", "bdo", "body",
    "br", "button", "canvas", "caption", "code", "col", "dd", "del", "details", "dfn",
    "dialog", "div", "dl", "dt", "em", "embed", "fieldset", "footer", "form", "h1", "h2",
    "h3", "h4", "h5", "h6", "head", "header", "hr", "html", "i", "img", "input", "ins",
    "kbd", "label", "legend", "li", "main", "mark", "menu", "meter", "nav", "ol", "option",
    "output", "p", "pre", "q", "s", "section", "select", "small", "span", "strong", "sub",
    "summary", "sup", "table", "tbody", "td", "th", "thead", "tr", "u", "ul", "var",
    "video", "tt",
}

QUOTED_RE   = re.compile(r'"[^"]*"|\'[^\']*\'')
ATTR_NAME_RE = re.compile(r'\[\s*([A-Za-z_][\w-]*)\s*(?:[~|^$*]?=|\])')
BRACKET_RE  = re.compile(r'\[[^\]]*\]')
IDENT_RE    = re.compile(r'[A-Za-z_][\w-]*')


def parse_f2_keymap() -> dict:
    src = ENCODERS_CS.read_text(encoding="utf-8")
    block = src[src.index("F2KeyMap ="):]
    block = block[:block.index("};")]
    pairs = re.findall(r'\["([^"]+)"\]\s*=\s*"([^"]+)"', block)
    keymap = dict(pairs)
    assert len(pairs) == 33 and len(keymap) == 33, f"F2KeyMap: expected 33 entries, got {len(pairs)}"
    assert len(set(keymap.values())) == 33, "F2KeyMap is not bijective"
    return keymap


def classify_abbrev(locator: str, abbrevs: set, elsewhere_keys: set) -> tuple[str, list, list]:
    """
    A = an abbreviated key used as a CSS attribute NAME ([dt=, [cl=, [ro], ...).
    B = an abbreviated key elsewhere: a whole identifier token outside brackets
        (e.g. .cl, #al) or a hyphen segment of a bracketed attribute name
        (e.g. [data-dt=]).  Only keys of length >= 2 that are not HTML tag names.
    C = neither.  Quoted values are blanked first so attribute values never match.
    """
    bare = QUOTED_RE.sub('""', locator)
    names = ATTR_NAME_RE.findall(bare)
    attr_hits = [n for n in names if n.lower() in abbrevs]
    else_hits = []
    for n in names:
        if n.lower() in abbrevs:
            continue
        for seg in n.lower().split("-"):
            if seg in elsewhere_keys:
                else_hits.append(f"[{n}]~{seg}")
    outside = BRACKET_RE.sub(" ", bare)
    for tok in IDENT_RE.findall(outside):
        if tok.lower() in elsewhere_keys:
            else_hits.append(tok)
    cls = "A_attr_name" if attr_hits else ("B_elsewhere" if else_hits else "C_none")
    return cls, attr_hits, else_hits


def expand_attr_names(locator_raw: str, reverse: dict) -> str:
    """Replace abbreviated attribute NAMES by their full names; quoted values untouched."""
    pattern = re.compile(r'"[^"]*"|\'[^\']*\'|(\[\s*)([A-Za-z_][\w-]*)(?=\s*(?:[~|^$*]?=|\]))')

    def repl(m):
        if m.group(1) is None:
            return m.group(0)
        name = m.group(2)
        full = reverse.get(name.lower())
        return m.group(1) + (full if full else name)

    return pattern.sub(repl, locator_raw)


def run_replay(records: pd.DataFrame, locator_col: str, tag: str) -> pd.DataFrame:
    """Re-score locators through the real C# Oracle (--replay, zero LLM)."""
    in_dir = REPLAY_DIR / f"in_{tag}"
    out_file = REPLAY_DIR / f"out_{tag}.jsonl"
    if in_dir.exists():
        shutil.rmtree(in_dir)
    in_dir.mkdir(parents=True)
    if out_file.exists():
        out_file.unlink()   # ReplayMode appends; start from an empty file
    with open(in_dir / "records.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for _, r in records.iterrows():
            fh.write(json.dumps({
                "page": r["testbed_page"], "bundle": r["bundle"], "encoding": r["encoding"],
                "task_id": r["task_id"], "locator_raw": r[locator_col],
            }, ensure_ascii=False) + "\n")
    cmd = ["dotnet", "run", "--project", "experiments", "-c", "Release", "--",
           "--replay", str(in_dir), "--replay-out", str(out_file)]
    print(f"  [replay:{tag}] {len(records)} locators -> {out_file.relative_to(REPO)}")
    # The replay serves the testbed with `python -m http.server`, which occasionally
    # stalls a navigation past the 90 s budget.  Retry the whole replay (fresh output
    # file) up to REPLAY_ATTEMPTS times; every attempt is kept in the log.
    log = []
    for attempt in range(1, REPLAY_ATTEMPTS + 1):
        if out_file.exists():
            out_file.unlink()
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8")
        log.append(f"===== attempt {attempt} (exit {proc.returncode}) =====\n{proc.stdout}{proc.stderr}")
        if proc.returncode == 0 and out_file.exists():
            break
        print(f"  [replay:{tag}] attempt {attempt} failed (exit {proc.returncode})")
    (REPLAY_DIR / f"log_{tag}.txt").write_text("\n".join(log), encoding="utf-8")
    if proc.returncode != 0 or not out_file.exists():
        raise SystemExit(f"[replay:{tag}] dotnet replay failed {REPLAY_ATTEMPTS} times; "
                         f"see {REPLAY_DIR / f'log_{tag}.txt'}")
    out = pd.read_json(out_file, lines=True)
    assert len(out) == len(records), f"[replay:{tag}] {len(out)} records back, expected {len(records)}"
    return out


# Main

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[guard] verifying protected files ...")
    before = protected_state()

    df = load_dataframe(REPO)
    R = {"meta": {
        "script": "experiments/analysis/revision1_diagnostics.py",
        "corpus": "experiments/runs/matrix_page_*.jsonl (6,000 records, gpt-4.1)",
        "n_boot": N_BOOT, "seed": SEED,
        "versions": {"numpy": np.__version__, "pandas": pd.__version__,
                     "scipy": __import__("scipy").__version__,
                     "statsmodels": __import__("statsmodels").__version__},
    }}
    md = []
    ctl = Controls()

    # 1. Controls
    print("\n[1] Controls")
    pairs = build_pairs(df, "B_full", "B_noVolatile")
    ref_pairs = published_stats._build_pairs(df)
    assert len(pairs) == 960
    assert (pairs[KEY].values == ref_pairs[KEY].values).all(), "pair order differs from stats.py"
    assert (pairs["success_bf"].values == ref_pairs["success_bf"].values).all()
    page_order = list(pairs["page"].unique())

    pairs["state_bf"] = [state_of(s, f) for s, f in zip(pairs["success_bf"], pairs["failure_mode_bf"])]
    pairs["state_nv"] = [state_of(s, f) for s, f in zip(pairs["success_nv"], pairs["failure_mode_nv"])]
    states = ["success", "grabbed", "lacked", "unreach"]
    trans = pd.crosstab(pairs["state_bf"], pairs["state_nv"]).reindex(
        index=states, columns=states, fill_value=0)
    for s1 in states:
        for s2 in states:
            ctl.check(f"transition {s1}->{s2}", int(trans.loc[s1, s2]),
                      PUBLISHED["transitions"].get((s1, s2), 0))

    p5 = mcnemar(pairs["success_bf"], pairs["success_nv"])
    ctl.check("McNemar b (NV-only)", p5["b_second_only"], PUBLISHED["b"])
    ctl.check("McNemar c (BF-only)", p5["c_first_only"], PUBLISHED["c"])
    ctl.check("OR = b/c", round(p5["odds_ratio"], 2), PUBLISHED["odds_ratio"])
    ctl.check("McNemar chi2", round(p5["chi2"], 2), PUBLISHED["mcnemar_chi2"])

    recov = pairs[(pairs["state_bf"] == "grabbed") & (pairs["state_nv"] == "success")]
    vol_catch = recov[~recov["predicate_non_volatile_bf"].astype(bool)]
    ctl.check("grabbed->success recoveries", len(recov), PUBLISHED["recoveries"])
    ctl.check("volatile catches among recoveries", len(vol_catch), PUBLISHED["volatile_catches"])

    print(f"  running published stats._cluster_bootstrap_ci (n={N_BOOT:,}) ...")
    ci_lo, ci_hi, _ = published_stats._cluster_bootstrap_ci(ref_pairs, N_BOOT, SEED)
    ctl.check("bootstrap CI lo (pp)", round(ci_lo, 2), PUBLISHED["boot_ci"][0])
    ctl.check("bootstrap CI hi (pp)", round(ci_hi, 2), PUBLISHED["boot_ci"][1])

    def per_page_success(p, bf_col, nv_col):
        g = p.groupby("page", sort=False)
        return {"bf": g[bf_col].sum().reindex(page_order).to_numpy(dtype=float),
                "nv": g[nv_col].sum().reindex(page_order).to_numpy(dtype=float),
                "n":  g[bf_col].count().reindex(page_order).to_numpy(dtype=float)}

    delta_stat = lambda t: (t["nv"] / t["n"] - t["bf"] / t["n"]) * 100
    fast = pct_ci(page_bootstrap(page_order, per_page_success(pairs, "success_bf", "success_nv"), delta_stat))
    ctl.check("fast bootstrap == published bootstrap (lo)", round(fast[0], 9), round(ci_lo, 9))
    ctl.check("fast bootstrap == published bootstrap (hi)", round(fast[1], 9), round(ci_hi, 9))

    page_sens = published_stats._page_level_sensitivity(ref_pairs)
    ctl.check("sign test p", float(f"{page_sens['sign_test_p']:.1e}"), PUBLISHED["sign_p"])
    ctl.check("Wilcoxon p", float(f"{page_sens['wilcoxon_p']:.1e}"), PUBLISHED["wilcoxon_p"])

    grabbed = df[df["failure_mode"] == GRABBED].copy()
    ctl.check("grabbed total", len(grabbed), PUBLISHED["grabbed_total"])
    ctl.check("grabbed volatile (cond3 false)",
              int((~grabbed["predicate_non_volatile"].astype(bool)).sum()), PUBLISHED["grabbed_volatile"])
    ctl.check("grabbed non-volatile",
              int(grabbed["predicate_non_volatile"].astype(bool).sum()), PUBLISHED["grabbed_other"])

    cells = pareto_cells(df)
    tok = cells["mean_obs_tokens"]
    cop_red = (tok[("B_full", "F1")] - tok[("B_noVolatile", "F3")]) / tok[("B_full", "F1")] * 100
    f3_red  = (tok[("B_noVolatile", "F1")] - tok[("B_noVolatile", "F3")]) / tok[("B_noVolatile", "F1")] * 100
    ctl.check("COP vs B_full x F1 token reduction %", round(cop_red, 1), PUBLISHED["cop_reduction_pct"])
    ctl.check("F3 vs F1 (B_noVolatile) token reduction %", round(f3_red, 1), PUBLISHED["f3_reduction_pct"])
    walk_obs = pareto_walk(cells, "mean_obs_tokens")
    frontier_obs = set(walk_obs[walk_obs["pareto_status"] == "FRONTIER"].index)
    ctl.check("Pareto frontier membership (o200k_base)", frontier_obs == PUBLISHED["frontier"], True)
    ctl.check("Pareto dominated count", int((walk_obs["pareto_status"] == "dominated").sum()), 17)
    ctl.check("COP (o200k_base)", cop_of(walk_obs), PUBLISHED["cop"])
    ctl.enforce()
    R["controls"] = ctl.rows

    md += ["# Revision 1 — diagnostics", "",
           "Generated by `python experiments/analysis/revision1_diagnostics.py` from the "
           "corpus (`experiments/runs/matrix_page_*.jsonl`, 6,000 records, GPT-4.1, temperature 0). "
           "Facts only; no interpretation. All bootstraps: page-clustered percentile, "
           f"{N_BOOT:,} replicates, seed {SEED}, fresh generator per statistic, same page order "
           "and draw sequence as `stats.py`.", "",
           "## 0. Controls (published values reproduced before any diagnostic)", ""]
    md += md_table(["control", "recomputed", "published", "ok"],
                   [[r["control"], r["recomputed"], r["published"], "yes" if r["ok"] else "NO"]
                    for r in ctl.rows])
    md += ["", "Transition matrix (B_full state → B_noVolatile state), 960 paired events:", ""]
    md += md_table(["B_full ↓ / B_noVolatile →"] + states,
                   [[s1] + [int(trans.loc[s1, s2]) for s2 in states] for s1 in states])

    # 2. D1 — relaxed predicates
    print("\n[2] D1 — relaxed predicates")
    for side in ("bf", "nv"):
        u = pairs[f"predicate_unique_match_{side}"].astype(bool)
        o = pairs[f"predicate_matches_oracle_{side}"].astype(bool)
        np_ = pairs[f"predicate_non_positional_{side}"].astype(bool)
        pairs[f"P5_{side}"] = pairs[f"success_{side}"].astype(bool)
        pairs[f"Pnow_{side}"] = u & o
        pairs[f"Pnownp_{side}"] = u & o & np_
    predicate_defs = {
        "P5": "original five-condition predicate (success field)",
        "P_now": "conditions 1+2 (unique match AND matches oracle)",
        "P_now_np": "conditions 1+2+4 (unique, oracle, non-positional)",
    }
    cols = {"P5": "P5", "P_now": "Pnow", "P_now_np": "Pnownp"}
    d1 = {}
    for name, col in cols.items():
        res = mcnemar(pairs[f"{col}_bf"], pairs[f"{col}_nv"])
        draws = page_bootstrap(page_order, per_page_success(pairs, f"{col}_bf", f"{col}_nv"), delta_stat)
        res["boot_ci_lo_pp"], res["boot_ci_hi_pp"] = pct_ci(draws)
        res["definition"] = predicate_defs[name]
        d1[name] = res
    assert abs(d1["P5"]["boot_ci_lo_pp"] - ci_lo) < 1e-9 and abs(d1["P5"]["boot_ci_hi_pp"] - ci_hi) < 1e-9

    vc = vol_catch
    vc_u = vc["predicate_unique_match_bf"].astype(bool)
    vc_o = vc["predicate_matches_oracle_bf"].astype(bool)
    vc_np = vc["predicate_non_positional_bf"].astype(bool)
    vc_ssp = vc["stable_signal_present_in_bundle_bf"].astype(bool)
    d1_vc = {
        "n_volatile_catches": len(vc),
        "bf_unique_and_oracle (pass P_now under B_full)": int((vc_u & vc_o).sum()),
        "bf_unique_oracle_nonpositional (pass P_now_np under B_full)": int((vc_u & vc_o & vc_np).sum()),
        "bf_unique_but_wrong_element": int((vc_u & ~vc_o).sum()),
        "bf_not_unique": int((~vc_u).sum()),
        "bf_stable_signal_present": int(vc_ssp.sum()),
    }
    ssp_false_pass = {}
    for side, bname in (("bf", "B_full"), ("nv", "B_noVolatile")):
        ssp = pairs[f"stable_signal_present_in_bundle_{side}"].astype(bool)
        ssp_false_pass[bname] = {
            "records_ssp_false": int((~ssp).sum()),
            "ssp_false_pass_P_now": int((~ssp & pairs[f"Pnow_{side}"]).sum()),
            "ssp_false_pass_P_now_np": int((~ssp & pairs[f"Pnownp_{side}"]).sum()),
        }
    # The 11 regressions (success -> grabbed): how many are volatile under B_noVolatile.
    regress = pairs[(pairs["state_bf"] == "success") & (pairs["state_nv"] == "grabbed")]
    regress_info = {
        "n": len(regress),
        "nv_volatile (cond3 false)": int((~regress["predicate_non_volatile_nv"].astype(bool)).sum()),
        "nv_not_unique": int((~regress["predicate_unique_match_nv"].astype(bool)).sum()),
        "nv_unique_wrong": int((regress["predicate_unique_match_nv"].astype(bool)
                                & ~regress["predicate_matches_oracle_nv"].astype(bool)).sum()),
        "events": [f"{r.page} {r.task_id} {r.encoding}" for r in regress.itertuples()],
    }
    R["D1"] = {"predicates": d1, "volatile_catches": d1_vc,
               "ssp_false_passing_relaxed": ssp_false_pass, "regressions_11": regress_info}

    md += ["", "## D1 — relaxed predicate (same 960 B_full / B_noVolatile pairs)", "",
           "Computed from the per-condition fields in the records (`predicate_unique_match`, "
           "`predicate_matches_oracle`, `predicate_non_positional`, `success`); no re-evaluation "
           "was needed. `predicate_matches_oracle` is only evaluated when the match is unique "
           "(Oracle.cs), so P_now = unique ∧ oracle.", ""]
    md += md_table(
        ["predicate", "definition", "B_full", "B_noVolatile", "Δ pp", "both", "NV-only (b)",
         "BF-only (c)", "neither", "χ² (uncorr.)", "p", "p exact", "OR = b/c", "OR 95% CI (exact cond.)",
         "bootstrap 95% CI Δ pp"],
        [[n, r["definition"], f"{r['success_first']}/960 ({r['rate_first_pct']:.2f}%)",
          f"{r['success_second']}/960 ({r['rate_second_pct']:.2f}%)", f"{r['delta_pp']:+.2f}",
          r["n11_both"], r["b_second_only"], r["c_first_only"], r["n00_neither"],
          f"{r['chi2']:.2f}", fmt_p(r["p"]), fmt_p(r["p_exact"]), fmt_or(r["odds_ratio"]),
          f"[{r['or_ci_lo']:.2f}, {fmt_or(r['or_ci_hi'])}]",
          f"[{r['boot_ci_lo_pp']:+.2f}, {r['boot_ci_hi_pp']:+.2f}]"] for n, r in d1.items()])
    md += ["", "2×2 tables (rows B_full, columns B_noVolatile):", ""]
    for n, r in d1.items():
        md += [f"*{n}*", ""]
        md += md_table(["", "NV success", "NV fail"],
                       [["BF success", r["n11_both"], r["c_first_only"]],
                        ["BF fail", r["b_second_only"], r["n00_neither"]]])
        md += [""]
    md += ["The 90 volatile catches (grabbed under B_full with `predicate_non_volatile = false`, "
           "success under B_noVolatile), evaluated under B_full:", ""]
    md += md_table(["quantity", "count"], [[k, v] for k, v in d1_vc.items()])
    md += ["", "Records whose bundle carried no stable signal (condition 5 false) but that pass the "
           "relaxed predicates (P_now / P_now_np drop condition 5):", ""]
    md += md_table(["bundle", "records with cond 5 false", "of which pass P_now", "of which pass P_now_np"],
                   [[b, v["records_ssp_false"], v["ssp_false_pass_P_now"], v["ssp_false_pass_P_now_np"]]
                    for b, v in ssp_false_pass.items()])
    md += ["", f"The 11 success→grabbed regressions under B_noVolatile: "
           f"{regress_info['nv_volatile (cond3 false)']} volatile (cond 3 false), "
           f"{regress_info['nv_not_unique']} not unique, {regress_info['nv_unique_wrong']} unique-wrong "
           f"(categories can overlap). Events: {', '.join(regress_info['events'])}."]

    # 2b. D1b — D1 by target design stratum
    print("\n[2b] D1b — D1 by target design stratum")
    # Condition 5 (Oracle.ComputeStableSignalPresence) looks each signal_attrs NAME up in
    # the oracle element's DOM attributes (rawOracleEl.Attrs).  "text" is a virtual key
    # (AttributeBundles: not in element.Attrs), so a signal listed only as "text" can
    # never satisfy condition 5.  The DOM walk captures every HTML attribute
    # (el.attributes), so every other signal_attrs value is an attribute name.
    NON_ATTRIBUTE_SIGNALS = {"text"}
    none_targets, text_only_targets, non_attr_listing, signal_vocab = set(), set(), [], {}
    for tf in sorted(TRUTH_DIR.glob("*.truth.json")):
        tj = json.loads(tf.read_text(encoding="utf-8"))
        for t in tj["targets"]:
            sa = t["signal_attrs"]
            for a in sa:
                signal_vocab[a] = signal_vocab.get(a, 0) + 1
            if not sa:
                none_targets.add((tj["page_id"], t["id"]))
            elif all(a in NON_ATTRIBUTE_SIGNALS for a in sa):
                text_only_targets.add((tj["page_id"], t["id"]))
            if any(a in NON_ATTRIBUTE_SIGNALS for a in sa):
                non_attr_listing.append({"page": tj["page_id"], "task_id": t["id"], "signal_attrs": sa})
    no_attr_targets = none_targets | text_only_targets

    def stratum_of(frame):
        return ["NONE" if (p, k) in none_targets
                else "text_only_signal" if (p, k) in text_only_targets
                else "has_attribute_signal"
                for p, k in zip(frame["page"], frame["task_id"])]

    def add_relaxed(frame):
        for side in ("bf", "nv"):
            u = frame[f"predicate_unique_match_{side}"].astype(bool)
            o = frame[f"predicate_matches_oracle_{side}"].astype(bool)
            frame[f"P5_{side}"] = frame[f"success_{side}"].astype(bool)
            frame[f"Pnow_{side}"] = u & o
            frame[f"Pnownp_{side}"] = u & o & frame[f"predicate_non_positional_{side}"].astype(bool)
        frame["stratum"] = stratum_of(frame)
        return frame

    def predicate_block(frame):
        """P5 / P_now / P_now_np on one paired frame; bootstrap over the pages present in it."""
        order_sub = list(frame["page"].unique())
        out = {}
        for name, col in cols.items():
            res = mcnemar(frame[f"{col}_bf"], frame[f"{col}_nv"])
            g = frame.groupby("page", sort=False)
            arrays = {"bf": g[f"{col}_bf"].sum().reindex(order_sub).to_numpy(dtype=float),
                      "nv": g[f"{col}_nv"].sum().reindex(order_sub).to_numpy(dtype=float),
                      "n":  g[f"{col}_bf"].count().reindex(order_sub).to_numpy(dtype=float)}
            res["boot_ci_lo_pp"], res["boot_ci_hi_pp"] = pct_ci(page_bootstrap(order_sub, arrays, delta_stat))
            res["n_pages"] = len(order_sub)
            out[name] = res
        return out

    pairs = add_relaxed(pairs)
    pairs["no_attr"] = [(p, k) in no_attr_targets for p, k in zip(pairs["page"], pairs["task_id"])]
    for side, bname in (("bf", "B_full"), ("nv", "B_noVolatile")):
        ssp_false = ~pairs[f"stable_signal_present_in_bundle_{side}"].astype(bool)
        ctl.check(f"NONE + text-only events == condition-5-false events ({bname}, same 960 pairs)",
                  bool((pairs["no_attr"] == ssp_false).all()) and int(pairs["no_attr"].sum()) == 192, True)
    # Target level: under the most permissive DOM bundle (B_full, F0–F3) condition 5 is
    # false on every encoding exactly for the no-attribute-signal targets.
    bf_dom = df[(df["bundle"] == "B_full") & df["encoding"].isin(DOM_ENCODINGS)]
    never_cond5 = {k for k, g in bf_dom.groupby(["page", "task_id"])
                   if not g["stable_signal_present_in_bundle"].astype(bool).any()}
    ctl.check("targets with condition 5 false on every B_full encoding == NONE + text-only targets",
              never_cond5 == no_attr_targets, True)
    if not all(r["ok"] for r in ctl.rows[-3:]):
        ctl.enforce()

    cop_pairs = (df[(df["bundle"] == "B_full") & (df["encoding"] == "F1")][
                     ["page", "task_id", "repetition"] + PRED_COLS]
                 .merge(df[(df["bundle"] == "B_noVolatile") & (df["encoding"] == "F3")][
                            ["page", "task_id", "repetition"] + PRED_COLS],
                        on=["page", "task_id", "repetition"], suffixes=("_bf", "_nv")))
    assert len(cop_pairs) == 240
    cop_pairs = add_relaxed(cop_pairs)
    cop_pairs["no_attr"] = [(p, k) in no_attr_targets for p, k in zip(cop_pairs["page"], cop_pairs["task_id"])]
    cop_overall = mcnemar(cop_pairs["P5_bf"], cop_pairs["P5_nv"])
    ctl.check("COP vs B_full×F1 success delta (P5) pp", round(cop_overall["delta_pp"], 2), 10.00)
    if not ctl.rows[-1]["ok"]:
        ctl.enforce()

    groups = {
        "has_attribute_signal": lambda f: f["stratum"] == "has_attribute_signal",
        "NONE": lambda f: f["stratum"] == "NONE",
        "text_only_signal": lambda f: f["stratum"] == "text_only_signal",
        "no_attribute_signal (NONE + text-only)": lambda f: f["no_attr"],
    }
    d1b = {"main_960": {}, "cop_vs_bff1_240": {}}
    for gname, sel in groups.items():
        d1b["main_960"][gname] = predicate_block(pairs[sel(pairs)])
        d1b["cop_vs_bff1_240"][gname] = predicate_block(cop_pairs[sel(cop_pairs)])
    d1b["stratum_definition"] = {
        "has_attribute_signal": "signal_attrs contains at least one HTML attribute name",
        "NONE": "signal_attrs empty",
        "text_only_signal": "signal_attrs non-empty but only non-attribute signals ('text')",
        "no_attribute_signal (NONE + text-only)": "union of NONE and text_only_signal — row used in the paper",
    }
    d1b["targets"] = {"NONE": len(none_targets), "text_only_signal": sorted(text_only_targets),
                      "no_attribute_signal": len(no_attr_targets)}
    d1b["targets_listing_non_attribute_signals"] = non_attr_listing
    d1b["signal_attrs_vocabulary"] = signal_vocab
    d1b["checks"] = {"no_attr_events_equal_cond5_false": {"B_full": True, "B_noVolatile": True},
                     "never_cond5_on_B_full_equals_no_attr_targets": True}
    R["D1b"] = d1b

    n_events = {g: d1b["main_960"][g]["P5"]["n"] for g in groups}
    md += ["", "## D1b — D1 by target design stratum", "",
           "Strata from the target's design class in `shared/testbed/pages/*.truth.json`:", "",
           f"- **has_attribute_signal** — `signal_attrs` contains at least one HTML attribute name "
           f"({n_events['has_attribute_signal']} pairs);",
           f"- **NONE** — `signal_attrs` empty ({len(none_targets)} targets, {n_events['NONE']} pairs);",
           f"- **text_only_signal** — `signal_attrs` non-empty but only `text` "
           f"({', '.join(f'{p} {k}' for p, k in sorted(text_only_targets))}; {n_events['text_only_signal']} pairs);",
           f"- **no_attribute_signal** = NONE + text_only_signal ({len(no_attr_targets)} targets, "
           f"{n_events['no_attribute_signal (NONE + text-only)']} pairs) — the row used in the paper.", "",
           "Why condition 5 is false on every bundle and encoding for the text-only target: condition 5 "
           "(`Oracle.ComputeStableSignalPresence`) looks each `signal_attrs` entry up as an attribute NAME on "
           "the oracle element (`rawOracleEl.Attrs`) after checking bundle membership. `text` is not an HTML "
           "attribute — the DOM walk stores visible text separately (`ElementData.Text`), and `text` is a "
           "virtual key in `AttributeBundles` — so the lookup never succeeds and the target cannot pass P5 in "
           "any cell, by construction.", "",
           "`signal_attrs` vocabulary across the 240 targets (entry: number of targets listing it): "
           + ", ".join(f"`{k}`: {v}" for k, v in sorted(signal_vocab.items(), key=lambda kv: -kv[1]))
           + ". The DOM walk records every HTML attribute of an element (`el.attributes`), so every entry "
           "except `text` is an attribute name. Targets whose `signal_attrs` contain a non-attribute signal: "
           + "; ".join(f"{x['page']} {x['task_id']} {x['signal_attrs']}" for x in non_attr_listing) + ".", "",
           "Checks: in the 960 B_full / B_noVolatile pairs the no_attribute_signal events are exactly the events "
           "with condition 5 = false, in both bundles (192 each, identical event sets); and the targets whose "
           "condition 5 is false on every B_full DOM encoding are exactly the no_attribute_signal targets. "
           "Bootstrap: same procedure, resampling the pages present in the stratum. With no discordant pairs "
           "the McNemar statistic and the OR are undefined (n/a / nan).", ""]
    for block_key, title in (("main_960", "B_full vs B_noVolatile, F0–F3 (960 pairs)"),
                             ("cop_vs_bff1_240", "COP B_noVolatile×F3 vs B_full×F1 (240 pairs)")):
        md += [f"### {title}", ""]
        md += md_table(
            ["stratum", "predicate", "n pairs", "pages", "B_full", "B_noVolatile", "Δ pp", "both",
             "NV-only (b)", "BF-only (c)", "neither", "χ² (uncorr.)", "p", "p exact", "OR = b/c",
             "OR 95% CI (exact cond.)", "bootstrap 95% CI Δ pp"],
            [[g, n, r["n"], r["n_pages"],
              f"{r['success_first']} ({r['rate_first_pct']:.2f}%)",
              f"{r['success_second']} ({r['rate_second_pct']:.2f}%)", f"{r['delta_pp']:+.2f}",
              r["n11_both"], r["b_second_only"], r["c_first_only"], r["n00_neither"],
              "n/a" if math.isnan(r["chi2"]) else f"{r['chi2']:.2f}", fmt_p(r["p"]), fmt_p(r["p_exact"]),
              "nan" if math.isnan(r["odds_ratio"]) else fmt_or(r["odds_ratio"]),
              "nan" if math.isnan(r["or_ci_lo"]) else f"[{r['or_ci_lo']:.2f}, {fmt_or(r['or_ci_hi'])}]",
              f"[{r['boot_ci_lo_pp']:+.2f}, {r['boot_ci_hi_pp']:+.2f}]"]
             for g in groups for n, r in d1b[block_key][g].items()])
        md += ["", "2×2 tables (rows B_full, columns B_noVolatile):", ""]
        md += md_table(["stratum", "predicate", "BF✓ NV✓", "BF✓ NV✗", "BF✗ NV✓", "BF✗ NV✗"],
                       [[g, n, r["n11_both"], r["c_first_only"], r["b_second_only"], r["n00_neither"]]
                        for g in groups for n, r in d1b[block_key][g].items()])
        md += [""]

    # 3. D2 — F2 mechanism
    print("\n[3] D2 — F2 mechanism")
    keymap = parse_f2_keymap()
    reverse = {v.lower(): k for k, v in keymap.items()}
    abbrevs = set(reverse)
    elsewhere_keys = {a for a in abbrevs if len(a) >= 2 and a not in HTML_TAGS}

    def classify_frame(frame):
        out = frame.copy()
        res = [classify_abbrev(v, abbrevs, elsewhere_keys) for v in out["locator_value"]]
        out["abbr_class"] = [r[0] for r in res]
        out["abbr_attr_hits"] = [r[1] for r in res]
        out["abbr_else_hits"] = [r[2] for r in res]
        return out

    f2_all = classify_frame(df[df["encoding"] == "F2"])
    f1_all = classify_frame(df[df["encoding"] == "F1"])
    f2_fail = f2_all[~f2_all["success"]]
    f1_fail = f1_all[~f1_all["success"]]
    f2_fail_keys = set(zip(f2_fail["page"], f2_fail["task_id"], f2_fail["bundle"]))
    f1_same = f1_all[[k in f2_fail_keys for k in zip(f1_all["page"], f1_all["task_id"], f1_all["bundle"])]]
    f1_same_fail = f1_same[~f1_same["success"]]

    classes = ["A_attr_name", "B_elsewhere", "C_none"]

    def class_counts(frame):
        vc_ = frame["abbr_class"].value_counts()
        return {c: int(vc_.get(c, 0)) for c in classes} | {"total": len(frame)}

    by_bundle = {}
    for b in sorted(f2_fail["bundle"].unique()):
        by_bundle[b] = {"F2_failures": class_counts(f2_fail[f2_fail["bundle"] == b]),
                        "F1_failures": class_counts(f1_fail[f1_fail["bundle"] == b])}
    key_usage = {}
    for hits in f2_fail["abbr_attr_hits"]:
        for h in hits:
            key_usage[h.lower()] = key_usage.get(h.lower(), 0) + 1
    success_with_abbr = {
        "F2_successes_with_A": int((f2_all[f2_all["success"]]["abbr_class"] == "A_attr_name").sum()),
        "F2_successes_with_B": int((f2_all[f2_all["success"]]["abbr_class"] == "B_elsewhere").sum()),
        "F1_successes_with_A": int((f1_all[f1_all["success"]]["abbr_class"] == "A_attr_name").sum()),
    }
    f2_fail_modes = pd.crosstab(f2_fail["abbr_class"], f2_fail["failure_mode"]).to_dict()

    # F1 vs F2 success per bundle (context for the published "consistent across all bundles").
    f1f2 = {}
    for b in ["B_full", "B_noVolatile", "B_noState", "B_noSemantic", "B_identityCore", "B_minimalCore"]:
        s1 = int(df[(df["bundle"] == b) & (df["encoding"] == "F1")]["success"].sum())
        s2 = int(df[(df["bundle"] == b) & (df["encoding"] == "F2")]["success"].sum())
        f1f2[b] = {"F1_success": s1, "F2_success": s2, "delta_pp": (s2 - s1) / 240 * 100}

    # Before scoring rewritten locators, replay all original F2 locators and require an
    # exact match with the stored predicate fields; any mismatch stops the script.
    jk = ["page_path", "bundle", "encoding", "task_id"]
    fields = ["success", "failure_mode", "predicate_unique_match", "predicate_matches_oracle",
              "predicate_non_volatile", "predicate_non_positional", "stable_signal_present_in_bundle"]

    def _nn(v):
        return None if v is None or (isinstance(v, float) and math.isnan(v)) else v

    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    f2_corpus = f2_all.sort_values(["page", "bundle", "task_id"]).reset_index(drop=True)
    rep_f2 = run_replay(f2_corpus, "locator_raw", "fidelity_all_f2")
    chk = f2_corpus.rename(columns={"testbed_page": "page_path"}).merge(
        rep_f2.rename(columns={"page": "page_path"})[jk + fields + ["observation_tokens"]],
        on=jk, suffixes=("", "_replay"))
    assert len(chk) == len(f2_corpus) == 1440, f"fidelity join: {len(chk)} of {len(f2_corpus)}"
    mism = [{"page": r["page"], "bundle": r["bundle"], "task_id": r["task_id"], "field": f,
             "stored": _nn(r[f]), "replayed": _nn(r[f + "_replay"])}
            for _, r in chk.iterrows() for f in fields if _nn(r[f]) != _nn(r[f + "_replay"])]
    obs_tok_diff = int((chk["observation_tokens"] != chk["observation_tokens_replay"]).sum())
    (REPLAY_DIR / "fidelity_mismatches.json").write_text(
        json.dumps(jsonable(mism), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"  [fidelity] {len(chk)} original F2 locators, {len(fields)} predicate fields: "
          f"{len(mism)} mismatches; observation_tokens differ on {obs_tok_diff} (informational)")
    if not ctl.check("replay fidelity: all 1,440 original F2 locators re-scored identically",
                     len(mism), 0):
        events = sorted({(m["page"], m["bundle"], m["task_id"]) for m in mism})
        print(f"\n[fidelity] STOP — {len(mism)} field mismatches on {len(events)} events:")
        for m in mism:
            print(f"  {m['page']} {m['bundle']}×F2 {m['task_id']}  {m['field']}: "
                  f"stored={m['stored']!r} replayed={m['replayed']!r}")
        print(f"(also written to {(REPLAY_DIR / 'fidelity_mismatches.json').relative_to(REPO)})")
        raise SystemExit(1)

    # Oracle replay of the key-expanded locators (class-A F2 failures only).
    target = f2_fail[f2_fail["abbr_class"] == "A_attr_name"].copy()
    target = target.sort_values(["page", "bundle", "task_id"]).reset_index(drop=True)
    target["locator_expanded"] = [expand_attr_names(v, reverse) for v in target["locator_raw"]]
    assert (target["locator_expanded"] != target["locator_raw"]).all()
    rep_exp = run_replay(target, "locator_expanded", "expanded")
    t = target.rename(columns={"testbed_page": "page_path"})

    e = rep_exp.rename(columns={"page": "page_path"})
    ex = t.merge(e[["page_path", "bundle", "encoding", "task_id"] + fields],
                 on=["page_path", "bundle", "encoding", "task_id"], suffixes=("", "_exp"))
    assert len(ex) == len(target)
    ex["keys_used"] = [",".join(sorted({h.lower() for h in hits})) for hits in ex["abbr_attr_hits"]]
    n_new_success = int(ex["success_exp"].astype(bool).sum())
    still = ex[~ex["success_exp"].astype(bool)]
    still_reason = {
        "not_unique": int((~still["predicate_unique_match_exp"].astype(bool)).sum()),
        "unique_wrong_element": int((still["predicate_unique_match_exp"].astype(bool)
                                     & ~still["predicate_matches_oracle_exp"].astype(bool)).sum()),
        "volatile": int((~still["predicate_non_volatile_exp"].astype(bool)).sum()),
        "positional": int((~still["predicate_non_positional_exp"].astype(bool)).sum()),
        "cond5_false": int((~still["stable_signal_present_in_bundle_exp"].astype(bool)).sum()),
    }
    by_key = {}
    for kset, g in ex.groupby("keys_used"):
        by_key[kset] = {"n": len(g), "success_after_expansion": int(g["success_exp"].astype(bool).sum())}
    by_bundle_exp = {b: {"n": len(g), "success_after_expansion": int(g["success_exp"].astype(bool).sum())}
                     for b, g in ex.groupby("bundle")}
    replay_rows = [{"page": r.page, "bundle": r.bundle, "task_id": r.task_id,
                    "locator_original": r.locator_value, "locator_expanded": r.locator_expanded,
                    "success_after": bool(r.success_exp),
                    "unique_after": bool(r.predicate_unique_match_exp),
                    "oracle_after": bool(r.predicate_matches_oracle_exp),
                    "non_volatile_after": bool(r.predicate_non_volatile_exp)}
                   for r in ex.itertuples()]

    # Prompt check: does the prompt carry the abbreviation dictionary?
    runner = RUNNER_CS.read_text(encoding="utf-8")
    sp_block = runner[runner.index("public const string SystemPrompt ="):]
    sp_block = sp_block[:sp_block.index(";")]
    system_prompt = "".join(json.loads(f'"{s}"') for s in re.findall(r'"((?:[^"\\]|\\.)*)"', sp_block))
    up_line = re.search(r'UserPrompt\(string observation, string taskDescription\)\s*=>\s*\$"(.*)";', runner)
    user_template = up_line.group(1) if up_line else ""
    prompt_text = system_prompt + "\n" + user_template
    words = set(re.findall(r"[A-Za-z][\w-]*", prompt_text.lower()))
    full_in_prompt = sorted(k for k in keymap if k.lower() in words)
    abbr_in_prompt = sorted(a for a in abbrevs if a in words)
    pairs_in_prompt = sorted(f"{k}->{keymap[k]}" for k in keymap
                             if k.lower() in words and keymap[k].lower() in words)
    enc_src = ENCODERS_CS.read_text(encoding="utf-8")
    f2_body = enc_src[enc_src.index("public static string EncodeF2CompactJson"):]
    f2_body = f2_body[:f2_body.index("public static string ExpandF2Keys")]
    f2_returns_array_only = f2_body.count("return JsonSerializer.Serialize(arr") == 1 \
        and f2_body.count("return ") == 1
    prompt_check = {
        "system_prompt": system_prompt,
        "user_prompt_template": user_template,
        "full_key_names_present_as_words": full_in_prompt,
        "abbreviations_present_as_words": abbr_in_prompt,
        "full_and_abbreviation_both_present": pairs_in_prompt,
        "mentions_abbreviation_or_legend": bool(re.search(r"abbrev|legend|key map|keymap", prompt_text, re.I)),
        "F2_encoder_returns_only_the_json_array": f2_returns_array_only,
        "contains_abbreviation_dictionary": bool(pairs_in_prompt) or bool(
            re.search(r"abbrev|legend|key map|keymap", prompt_text, re.I)) or not f2_returns_array_only,
    }

    audit = [{"page": r.page, "bundle": r.bundle, "task_id": r.task_id, "encoding": "F2",
              "class": r.abbr_class, "attr_hits": r.abbr_attr_hits, "elsewhere_hits": r.abbr_else_hits,
              "locator": r.locator_value} for r in f2_fail.itertuples() if r.abbr_class != "C_none"]
    audit += [{"page": r.page, "bundle": r.bundle, "task_id": r.task_id, "encoding": "F1",
               "class": r.abbr_class, "attr_hits": r.abbr_attr_hits, "elsewhere_hits": r.abbr_else_hits,
               "locator": r.locator_value} for r in f1_fail.itertuples() if r.abbr_class != "C_none"]

    R["D2"] = {
        "f2_keymap": keymap,
        "elsewhere_keys_considered": sorted(elsewhere_keys),
        "classification_rule": {
            "A_attr_name": "abbreviated key as CSS attribute name: \\[\\s*KEY\\s*([~|^$*]?=|\\])",
            "B_elsewhere": "key (len>=2, not an HTML tag) as a whole identifier outside brackets, "
                           "or as a hyphen segment of a bracketed attribute name; quoted values blanked",
            "C_none": "neither",
        },
        "F2_failures": class_counts(f2_fail), "F1_failures": class_counts(f1_fail),
        "F1_failures_same_page_task_bundle_as_F2_failures": class_counts(f1_same_fail),
        "by_bundle": by_bundle, "abbreviated_attr_name_usage_in_F2_failures": key_usage,
        "successes_containing_abbreviations": success_with_abbr,
        "F2_failure_class_by_failure_mode": f2_fail_modes,
        "F1_vs_F2_success_by_bundle": f1f2,
        "replay": {
            "method": "dotnet run --project experiments -c Release -- --replay <dir> --replay-out <file> "
                      "(GroundingRunner.ReplayOneAsync -> Oracle.EvaluateLocatorAsync, zero LLM)",
            "n_locators": len(target),
            "fidelity_check": {"n_original_f2_locators": len(chk), "fields": fields,
                               "predicate_mismatches": len(mism),
                               "observation_tokens_differ_informational": obs_tok_diff},
            "success_after_expansion": n_new_success,
            "still_failing": len(still), "still_failing_conditions": still_reason,
            "by_keys_used": by_key, "by_bundle": by_bundle_exp, "records": replay_rows,
        },
        "prompt_check": prompt_check,
        "audit_matches": audit,
    }

    md += ["", "## D2 — F2 mechanism", "",
           f"F2 dictionary parsed from `shared/harness/ObservationEncoders.cs` (`F2KeyMap`, "
           f"{len(keymap)} pairs, bijective). Classification of failing locators:", "",
           "- **A** — an abbreviated key used as a CSS attribute name (`[dt=`, `[cl=`, `[ro]` …);",
           "- **B** — an abbreviated key elsewhere: a whole identifier outside brackets (`.cl`, `#al`) or a "
           "hyphen segment of a bracketed attribute name (`[data-dt=`); only keys of length ≥ 2 that are not "
           f"HTML tag names ({len(elsewhere_keys)} keys); quoted values are blanked first;",
           "- **C** — neither.", ""]
    md += md_table(["set", "A attr-name", "B elsewhere", "C none", "total"],
                   [[lbl, c["A_attr_name"], c["B_elsewhere"], c["C_none"], c["total"]] for lbl, c in [
                       ("F2 failures, all bundles", class_counts(f2_fail)),
                       ("F1 failures, all bundles (control)", class_counts(f1_fail)),
                       ("F1 failures on the (page, task, bundle) of the F2 failures", class_counts(f1_same_fail)),
                   ]])
    md += ["", "By bundle (F2 failures / F1 failures):", ""]
    md += md_table(["bundle", "F2 A", "F2 B", "F2 C", "F2 total", "F1 A", "F1 B", "F1 C", "F1 total"],
                   [[b, v["F2_failures"]["A_attr_name"], v["F2_failures"]["B_elsewhere"],
                     v["F2_failures"]["C_none"], v["F2_failures"]["total"],
                     v["F1_failures"]["A_attr_name"], v["F1_failures"]["B_elsewhere"],
                     v["F1_failures"]["C_none"], v["F1_failures"]["total"]] for b, v in by_bundle.items()])
    md += ["", "Abbreviated attribute names used in F2 failures (occurrences): "
           + ", ".join(f"`{k}`={v}" for k, v in sorted(key_usage.items(), key=lambda kv: -kv[1])) + ".",
           f"Successful F2 locators containing an A-class key: {success_with_abbr['F2_successes_with_A']}; "
           f"B-class: {success_with_abbr['F2_successes_with_B']}. "
           f"Successful F1 locators containing an A-class key: {success_with_abbr['F1_successes_with_A']}.", "",
           "F1 vs F2 success by bundle (240 events each):", ""]
    md += md_table(["bundle", "F1", "F2", "Δ pp"],
                   [[b, v["F1_success"], v["F2_success"], f"{v['delta_pp']:+.2f}"] for b, v in f1f2.items()])
    md += ["", "### Key expansion + Oracle replay", "",
           f"The {len(target)} class-A F2 failures had their abbreviated attribute names replaced by the full "
           "names from the dictionary (attribute values untouched) and were re-scored through the C# Oracle "
           "with the zero-LLM `--replay` mode (`--replay-out` into `results/revision1/replay/`). "
           f"Sanity check first: all {len(chk):,} original (unmodified) F2 locators of the corpus were "
           f"replayed the same way; {len(mism)} mismatches against the stored records on the "
           f"{len(fields)} predicate fields ({', '.join(f'`{x}`' for x in fields)}); "
           f"`observation_tokens` (re-encoded during replay) differed on {obs_tok_diff}.", "",
           f"- Successes after expansion: **{n_new_success} / {len(target)}**",
           f"- Still failing: {len(still)} — not unique {still_reason['not_unique']}, unique-wrong "
           f"{still_reason['unique_wrong_element']}, volatile {still_reason['volatile']}, positional "
           f"{still_reason['positional']}, condition 5 false {still_reason['cond5_false']} (can overlap)", ""]
    md += md_table(["abbreviated keys in locator", "n", "success after expansion"],
                   [[k, v["n"], v["success_after_expansion"]] for k, v in by_key.items()])
    md += [""] + md_table(["bundle", "n", "success after expansion"],
                          [[b, v["n"], v["success_after_expansion"]] for b, v in by_bundle_exp.items()])
    md += ["", "### Prompt check", "",
           f"`GroundingRunner.SystemPrompt`: “{system_prompt.replace(chr(10), ' ')}”", "",
           f"`UserPrompt` template: `{user_template}`", "",
           f"- Full key names present as words: {full_in_prompt or 'none'}",
           f"- Abbreviations present as words: {abbr_in_prompt or 'none'}",
           f"- Full name and its abbreviation both present: {pairs_in_prompt or 'none'}",
           f"- Mentions of abbreviation / legend / key map: {prompt_check['mentions_abbreviation_or_legend']}",
           f"- `EncodeF2CompactJson` returns only the serialized element array: {f2_returns_array_only}",
           f"- **Prompt contains the abbreviation dictionary: {prompt_check['contains_abbreviation_dictionary']}**"]

    # 4. D3
    print("\n[4] D3 — statistics")
    # 4a. Page-level effect sizes
    by_page = pairs.groupby("page", sort=False)[["success_bf", "success_nv"]].sum().reindex(page_order)
    d = (by_page["success_nv"] - by_page["success_bf"]).to_numpy(dtype=float)
    nz = d[d != 0]
    n_nz = len(nz)
    ranks = pd.Series(np.abs(nz)).rank(method="average").to_numpy()
    w_plus, w_minus = float(ranks[nz > 0].sum()), float(ranks[nz < 0].sum())
    _, tie_counts = np.unique(np.abs(nz), return_counts=True)
    var_w = n_nz * (n_nz + 1) * (2 * n_nz + 1) / 24 - (tie_counts ** 3 - tie_counts).sum() / 48
    z = (w_plus - n_nz * (n_nz + 1) / 4) / math.sqrt(var_w)
    wz = wilcoxon(by_page["success_nv"], by_page["success_bf"], method="approx")
    page_level = {
        "n_pages": 24, "n_nonzero": n_nz, "ties": int((d == 0).sum()),
        "nv_favoring": int((d > 0).sum()), "bf_favoring": int((d < 0).sum()),
        "wilcoxon_W_published_form": page_sens["wilcoxon_stat"], "wilcoxon_p": page_sens["wilcoxon_p"],
        "W_plus": w_plus, "W_minus": w_minus,
        "z_normal_approx_tie_corrected": z, "scipy_approx_z": float(abs(wz.zstatistic)),
        "scipy_approx_p": float(wz.pvalue),
        "r = Z/sqrt(N_nonzero)": z / math.sqrt(n_nz), "r = Z/sqrt(24)": z / math.sqrt(24),
        "matched_pairs_rank_biserial": (w_plus - w_minus) / (w_plus + w_minus),
        "sign_test_share_nonzero": int((d > 0).sum()) / n_nz,
        "share_pages_nv_ge_bf": int((d >= 0).sum()) / 24,
        "sign_test_p": page_sens["sign_test_p"],
    }
    assert abs(abs(z) - abs(float(wz.zstatistic))) < 1e-9, "manual Z differs from scipy approx Z"

    # 4b. GEE (cluster = page, exchangeable) + clustered McNemar
    import statsmodels.api as sm
    long = pd.concat([
        pd.DataFrame({"page": pairs["page"], "is_nv": 0, "success": pairs["success_bf"].astype(int),
                      "is_low": (pairs["semantic_density"] == "LOW").astype(int)}),
        pd.DataFrame({"page": pairs["page"], "is_nv": 1, "success": pairs["success_nv"].astype(int),
                      "is_low": (pairs["semantic_density"] == "LOW").astype(int)}),
    ], ignore_index=True)
    long["page_idx"] = long["page"].map({p: i for i, p in enumerate(page_order)})
    long = long.sort_values(["page_idx", "is_nv"], kind="mergesort").reset_index(drop=True)

    def gee_fit(formula, term):
        out = {}
        for cov in ("robust", "bias_reduced"):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                model = sm.GEE.from_formula(formula, groups="page_idx", data=long,
                                            family=sm.families.Binomial(),
                                            cov_struct=sm.cov_struct.Exchangeable())
                res = model.fit(cov_type=cov)
            coef, se = float(res.params[term]), float(res.bse[term])
            lo, hi = (float(v) for v in res.conf_int().loc[term])
            out[cov] = {"coef_log_or": coef, "se": se, "odds_ratio": math.exp(coef),
                        "or_ci_lo": math.exp(lo), "or_ci_hi": math.exp(hi),
                        "z": float(res.tvalues[term]), "p": float(res.pvalues[term]),
                        "exchangeable_corr": float(model.cov_struct.dep_params),
                        "warnings": sorted({str(w.message) for w in caught})}
        return out

    gee_main = gee_fit("success ~ is_nv", "is_nv")
    gee_inter = gee_fit("success ~ is_nv * is_low", "is_nv:is_low")

    g = pairs.groupby("page", sort=False)
    x1 = g["success_bf"].sum().reindex(page_order).to_numpy(dtype=float)
    x2 = g["success_nv"].sum().reindex(page_order).to_numpy(dtype=float)
    nk = g["success_bf"].count().reindex(page_order).to_numpy(dtype=float)
    K, N = len(nk), nk.sum()
    dk = x1 - x2
    dbar = dk.sum() / N
    var_diff = K / (K - 1) * ((dk - nk * dbar) ** 2).sum() / N ** 2
    obu_x2 = (dk.sum() / N) ** 2 / var_diff
    obuchowski = {"K": K, "N": int(N), "p_bf": x1.sum() / N, "p_nv": x2.sum() / N,
                  "diff_nv_minus_bf_pp": (x2.sum() - x1.sum()) / N * 100,
                  "se_diff_pp": math.sqrt(var_diff) * 100, "chi2": obu_x2,
                  "p": float(chi2.sf(obu_x2, 1))}

    # 4c. Holm family
    family = []

    def add(group, label, res, n_desc):
        family.append({"group": group, "comparison": label, "n_pairs": res["n"], "basis": n_desc,
                       "delta_pp": res["delta_pp"], "b": res["b_second_only"], "c": res["c_first_only"],
                       "chi2": res["chi2"], "p_raw": res["p"], "p_exact": res["p_exact"]})

    ladder_res = {}
    for upper, lower in zip(BUNDLE_LADDER_ORDER[:-1], BUNDLE_LADDER_ORDER[1:]):
        lp = build_pairs(df, upper, lower)
        assert len(lp) == 960
        r = mcnemar(lp["success_bf"], lp["success_nv"])
        ladder_res[f"{upper}->{lower}"] = r
        add("bundle ladder", f"{upper} → {lower}", r, "960 pairs, F0–F3")
    enc_res = {}
    for enc in ("F0", "F2", "F3"):
        ep = build_encoding_pairs(df, "B_noVolatile", "F1", enc)
        assert len(ep) == 240
        r = mcnemar(ep["success_bf"], ep["success_nv"])
        enc_res[f"F1->{enc}"] = r
        add("encoding vs F1", f"B_noVolatile: F1 → {enc}", r, "240 pairs")
    strat_res = {}
    for s in ("LOW", "HIGH"):
        sp = pairs[pairs["semantic_density"] == s]
        r = mcnemar(sp["success_bf"], sp["success_nv"])
        strat_res[s] = r
        add("moderator", f"B_full → B_noVolatile, {s} pages", r, "480 pairs")

    # Exact permutation test on page-level deltas (LOW minus HIGH mean), all C(24,12) splits.
    dpage = (by_page["success_nv"] - by_page["success_bf"]).astype(int)
    low_pages = [p for p in page_order if p in set(pairs.loc[pairs["semantic_density"] == "LOW", "page"])]
    assert len(low_pages) == 12
    vals = [int(dpage[p]) for p in page_order]
    T = sum(vals)
    s_obs = sum(int(dpage[p]) for p in low_pages)
    offset = sum(abs(v) for v in vals)
    width = 2 * offset + 1
    dp = [[0] * width for _ in range(13)]
    dp[0][offset] = 1
    for v in vals:
        for k in range(12, 0, -1):
            prev, cur = dp[k - 1], dp[k]
            for s in range(width):
                if prev[s]:
                    cur[s + v] += prev[s]
    total_splits = sum(dp[12])
    assert total_splits == comb(24, 12)
    obs_abs = abs(2 * s_obs - T)
    n_extreme = sum(cnt for s, cnt in enumerate(dp[12]) if cnt and abs(2 * (s - offset) - T) >= obs_abs)
    stat_obs = (s_obs / 12 - (T - s_obs) / 12) / 40 * 100
    perm = {"statistic": "mean page Δ(LOW) − mean page Δ(HIGH), pp", "observed_pp": stat_obs,
            "n_splits": total_splits, "n_as_or_more_extreme": n_extreme,
            "p_two_sided_exact": n_extreme / total_splits}
    family.append({"group": "moderator", "comparison": "LOW vs HIGH page-level Δ (exact permutation)",
                   "n_pairs": 24, "basis": "24 page deltas, C(24,12) splits", "delta_pp": stat_obs,
                   "b": None, "c": None, "chi2": None, "p_raw": perm["p_two_sided_exact"],
                   "p_exact": perm["p_two_sided_exact"]})

    # Cross-model
    cm = cross_model.load_all()
    ptk = cross_model._page_task_key
    cross_res = {}
    for m in ["gpt-4.1", "gpt-4.1-nano", "claude-sonnet-4-6"]:
        recs = cm[m]
        bf = {ptk(r): bool(r["success"]) for r in recs if r["bundle"] == "B_full" and r["encoding"] == "F1"}
        nv = {ptk(r): bool(r["success"]) for r in recs if r["bundle"] == "B_noVolatile" and r["encoding"] == "F1"}
        common = sorted(set(bf) & set(nv))
        r = mcnemar([bf[k] for k in common], [nv[k] for k in common])
        cross_res[f"form_invariance_{m}"] = r
        add("cross-model", f"{m}: B_full×F1 → B_noVolatile×F1", r, f"{len(common)} aligned events")
    four = ["gpt-4.1", "gpt-4.1-nano", "claude-sonnet-4-6"]
    ek = cross_model._event_key
    filt = {m: {ek(r): bool(r["success"]) for r in cm[m] if not cross_model._is_skip_page(r)} for m in four}
    common_ev = sorted(set(filt[four[0]]).intersection(*[set(filt[m]) for m in four[1:]]))
    for m in ["claude-sonnet-4-6", "gpt-4.1-nano"]:
        r = mcnemar([filt["gpt-4.1"][k] for k in common_ev], [filt[m][k] for k in common_ev])
        cross_res[f"fair_subset_{m}_vs_gpt-4.1"] = r
        add("cross-model", f"fair subset: gpt-4.1 → {m}", r, f"{len(common_ev)} common events")
    gcop = {ptk(r): bool(r["success"]) for r in cm["gpt-4.1"]
            if r["bundle"] == cross_model.COP_B and r["encoding"] == cross_model.COP_E}
    ocop = {ptk(r): bool(r["success"]) for r in cm["o4-mini"]
            if r["bundle"] == cross_model.COP_B and r["encoding"] == cross_model.COP_E}
    common_cop = sorted(set(gcop) & set(ocop))
    r = mcnemar([gcop[k] for k in common_cop], [ocop[k] for k in common_cop])
    cross_res["cop_o4-mini_vs_gpt-4.1"] = r
    add("cross-model", "COP cell: gpt-4.1 → o4-mini", r, f"{len(common_cop)} common events")

    fi_claude = cross_res["form_invariance_claude-sonnet-4-6"]
    ctl.check("Claude form-invariance 150/210 -> 163/210",
              (fi_claude["success_first"], fi_claude["success_second"], fi_claude["n"]), (150, 163, 210))
    fs = cross_res["fair_subset_claude-sonnet-4-6_vs_gpt-4.1"]
    ctl.check("fair subset gpt-4.1 563 / claude 600 / n 870",
              (fs["success_first"], fs["success_second"], fs["n"]), (563, 600, 870))
    ctl.check("ladder B_noState -> B_noSemantic cliff pp",
              round(ladder_res["B_noState->B_noSemantic"]["delta_pp"], 2), -19.79)
    ctl.check("F2 - F1 (B_noVolatile) pp", round(enc_res["F1->F2"]["delta_pp"], 2), -12.08)
    ctl.check("F3 - F1 (B_noVolatile) pp", round(enc_res["F1->F3"]["delta_pp"], 2), 0.42)
    ctl.check("LOW delta pp", round(strat_res["LOW"]["delta_pp"], 2), 15.00)
    ctl.check("HIGH delta pp", round(strat_res["HIGH"]["delta_pp"], 2), 3.96, tol=0.01)
    late_fail = [c for c in ctl.rows[-7:] if not c["ok"]]
    if late_fail:
        ctl.enforce()

    assert len(family) == 17, f"Holm family has {len(family)} tests, expected 17"
    holm_raw = holm([f["p_raw"] for f in family])
    holm_exact = holm([f["p_exact"] for f in family])
    for f_, h1, h2 in zip(family, holm_raw, holm_exact):
        f_["p_holm"] = h1
        f_["p_holm_exact"] = h2

    # 4d. Token-savings bootstrap CIs
    def cell(b, e):
        return df[(df["bundle"] == b) & (df["encoding"] == e)]

    def tok_arrays(col):
        arr = {}
        for name, (b, e) in {"nvf3": ("B_noVolatile", "F3"), "bff1": ("B_full", "F1"),
                             "nvf1": ("B_noVolatile", "F1")}.items():
            gg = cell(b, e).groupby("page")
            arr[f"{name}_tok"] = gg[col].sum().reindex(page_order).to_numpy(dtype=float)
            arr[f"{name}_n"] = gg[col].count().reindex(page_order).to_numpy(dtype=float)
        return arr

    def reduction(t, num, den):
        return (1 - (t[f"{num}_tok"] / t[f"{num}_n"]) / (t[f"{den}_tok"] / t[f"{den}_n"])) * 100

    token_ci = {}
    for col, label in (("observation_tokens", "o200k_base observation tokens"),
                       ("prompt_tokens_total", "API-reported prompt tokens (system + observation + task)")):
        arr = tok_arrays(col)
        full = {k: v.sum() for k, v in arr.items()}
        for name, num, den in (("COP (B_noVolatile×F3) vs B_full×F1", "nvf3", "bff1"),
                               ("F3 vs F1 within B_noVolatile", "nvf3", "nvf1")):
            draws = page_bootstrap(page_order, arr, lambda t, a=num, b=den: reduction(t, a, b))
            lo, hi = pct_ci(draws)
            token_ci[f"{name} [{col}]"] = {"metric": label, "reduction_pct": reduction(full, num, den),
                                           "boot_ci_lo_pct": lo, "boot_ci_hi_pct": hi,
                                           "records_per_page_per_cell": 10}

    # 4e. Grabbed subtypes
    shadow_re = re.compile(r'\[\s*(?:data-shadow|is_shadow|sh)\s*(?:[~|^$*]?=|\])|\[S\]|>>>|/deep/|::shadow',
                           re.I)
    gb = grabbed.copy()
    gb["f_volatile"] = ~gb["predicate_non_volatile"].astype(bool)
    gb["f_positional"] = ~gb["predicate_non_positional"].astype(bool)
    gb["f_shadow_syntax"] = gb["locator_value"].str.contains(shadow_re)
    gb["f_non_unique"] = ~gb["predicate_unique_match"].astype(bool)
    gb["f_wrong_element"] = gb["predicate_unique_match"].astype(bool) & ~gb["predicate_matches_oracle"].astype(bool)
    order = [("volatile", "f_volatile"), ("positional", "f_positional"),
             ("invalid cross-shadow syntax", "f_shadow_syntax"), ("non-unique", "f_non_unique"),
             ("wrong element", "f_wrong_element")]

    def primary(row):
        for name, col in order:
            if row[col]:
                return name
        return "residual"

    gb["subtype"] = gb.apply(primary, axis=1)
    assert (gb["subtype"] == "residual").sum() == 0, "grabbed record with no failing predicate"
    assert (gb["subtype"] == "volatile").sum() == 601
    sub_counts = {name: int((gb["subtype"] == name).sum()) for name, _ in order}
    flag_counts = {name: int(gb[col].sum()) for name, col in order}
    combo = gb[[c for _, c in order]].apply(
        lambda r: "+".join(n for n, c in order if r[c]), axis=1).value_counts()
    sub_by_bundle = pd.crosstab(gb["bundle"], gb["subtype"]).reindex(columns=[n for n, _ in order],
                                                                   fill_value=0)
    sub_by_enc = pd.crosstab(gb["encoding"], gb["subtype"]).reindex(columns=[n for n, _ in order],
                                                                   fill_value=0)
    shadow_examples = sorted(gb.loc[gb["f_shadow_syntax"], "locator_value"].unique())[:15]

    # 4f. Pareto under API-reported prompt tokens
    walk_api = pareto_walk(cells, "mean_api_prompt_tokens")
    frontier_api = list(walk_api[walk_api["pareto_status"] == "FRONTIER"].index)
    cop_api = cop_of(walk_api)
    cop_row = cells.loc[PUBLISHED["cop"]]
    dominators = [c for c in cells.index if c != PUBLISHED["cop"]
                  and cells.loc[c, "mean_api_prompt_tokens"] <= cop_row["mean_api_prompt_tokens"]
                  and cells.loc[c, "success_rate"] >= cop_row["success_rate"]]
    api_tok = cells["mean_api_prompt_tokens"]
    pareto_api = {
        "cost_field": "prompt_tokens_total (API usage: system prompt + observation + task)",
        "note_missing_field": "No API-reported observation-only token count exists in the records.",
        "prompt_minus_observation_tokens": {
            "min": int((df["prompt_tokens_total"] - df["observation_tokens"]).min()),
            "max": int((df["prompt_tokens_total"] - df["observation_tokens"]).max()),
            "mean": float((df["prompt_tokens_total"] - df["observation_tokens"]).mean())},
        "frontier": [list(c) for c in frontier_api],
        "frontier_o200k": [list(c) for c in walk_obs[walk_obs["pareto_status"] == "FRONTIER"].index],
        "dominated_count": int((walk_api["pareto_status"] == "dominated").sum()),
        "cop_rule": "cheapest frontier cell with success > 50% (pareto.py)",
        "cop": list(cop_api), "published_cop_on_frontier": PUBLISHED["cop"] in frontier_api,
        "published_cop_weakly_dominated_by": [list(c) for c in dominators],
        "cop_vs_bff1_reduction_pct": (api_tok[("B_full", "F1")] - api_tok[("B_noVolatile", "F3")])
                                     / api_tok[("B_full", "F1")] * 100,
        "f3_vs_f1_reduction_pct": (api_tok[("B_noVolatile", "F1")] - api_tok[("B_noVolatile", "F3")])
                                  / api_tok[("B_noVolatile", "F1")] * 100,
        "cells": [{"bundle": b, "encoding": e, "success_pct": float(r.success_rate * 100),
                   "mean_obs_tokens": float(r.mean_obs_tokens),
                   "mean_api_prompt_tokens": float(r.mean_api_prompt_tokens),
                   "status_o200k": walk_obs.loc[(b, e), "pareto_status"],
                   "status_api": walk_api.loc[(b, e), "pareto_status"]}
                  for (b, e), r in walk_api.iterrows()],
    }

    R["D3"] = {
        "page_level": page_level,
        "gee_main": gee_main, "gee_interaction_bundle_x_stratum": gee_inter,
        "clustered_mcnemar_obuchowski": obuchowski,
        "holm_family": family, "permutation_moderator": perm,
        "cross_model_tests": cross_res, "ladder_tests": ladder_res, "encoding_tests": enc_res,
        "stratum_tests": strat_res,
        "token_savings_ci": token_ci,
        "grabbed_subtypes": {"priority": [n for n, _ in order], "primary": sub_counts,
                             "flags_multilabel": flag_counts, "combinations": combo.to_dict(),
                             "by_bundle": sub_by_bundle.to_dict(orient="index"),
                             "by_encoding": sub_by_enc.to_dict(orient="index"),
                             "shadow_syntax_rule": shadow_re.pattern,
                             "shadow_syntax_examples": shadow_examples},
        "pareto_api_tokens": pareto_api,
    }

    md += ["", "## D3 — statistics", "", "### Page-level analysis (n = 24)", ""]
    md += md_table(["quantity", "value"], [
        ["pages B_noVolatile > / < / = B_full",
         f"{page_level['nv_favoring']} / {page_level['bf_favoring']} / {page_level['ties']}"],
        ["Wilcoxon W (scipy, published form), p", f"{page_level['wilcoxon_W_published_form']:.1f}, "
                                                    f"{fmt_p(page_level['wilcoxon_p'])}"],
        ["W+ / W− (non-zero pages)", f"{w_plus:.1f} / {w_minus:.1f}"],
        ["Z (normal approx., tie-corrected, no continuity corr.)", f"{z:.3f}"],
        ["r = Z/√N, N = non-zero pages", f"{page_level['r = Z/sqrt(N_nonzero)']:.3f} (N = {n_nz})"],
        ["r = Z/√24", f"{page_level['r = Z/sqrt(24)']:.3f}"],
        ["matched-pairs rank-biserial", f"{page_level['matched_pairs_rank_biserial']:.3f}"],
        ["sign test share (NV-favouring / non-tied)",
         f"{page_level['nv_favoring']}/{n_nz} = {page_level['sign_test_share_nonzero']:.3f}"],
        ["share of pages NV ≥ BF", f"{int((d >= 0).sum())}/24 = {page_level['share_pages_nv_ge_bf']:.3f}"],
        ["sign test p (published form)", fmt_p(page_level["sign_test_p"])],
    ])
    md += ["", "### Cluster-robust versions of the main comparison", "",
           "GEE logistic, `success ~ is_nv`, 1,920 rows (960 events × 2 bundles), cluster = page (24 "
           "clusters of 80), exchangeable working correlation. The GEE odds ratio is a marginal "
           "(population-averaged) estimand; the McNemar OR (b/c) is conditional on the event.", ""]
    md += md_table(["model", "cov_type", "OR", "95% CI", "SE(log OR)", "z", "p", "exch. corr."],
                   [[lbl, cov, f"{v['odds_ratio']:.3f}", f"[{v['or_ci_lo']:.3f}, {v['or_ci_hi']:.3f}]",
                     f"{v['se']:.4f}", f"{v['z']:.3f}", fmt_p(v["p"]), f"{v['exchangeable_corr']:.4f}"]
                    for lbl, fit in (("success ~ is_nv", gee_main),
                                     ("is_nv × is_low (interaction term; consistency check only)", gee_inter))
                    for cov, v in fit.items()])
    warn_all = sorted({w for fit in (gee_main, gee_inter) for v in fit.values() for w in v["warnings"]})
    md += ["", f"statsmodels warnings during GEE fitting: {warn_all or 'none'}.", "",
           "Clustered McNemar (Obuchowski 1998): with x₁ₖ, x₂ₖ the B_full and B_noVolatile successes "
           "on page k, nₖ events on page k, N = Σnₖ, K = 24, dₖ = x₁ₖ − x₂ₖ, d̄ = Σdₖ/N:",
           "X² = (Σdₖ/N)² / [K/(K−1) · Σ(dₖ − nₖ·d̄)² / N²], df = 1.", ""]
    md += md_table(["K", "N", "p̂ B_full", "p̂ B_noVolatile", "Δ pp", "SE(Δ) pp", "X²", "p"],
                   [[K, int(N), f"{obuchowski['p_bf']:.4f}", f"{obuchowski['p_nv']:.4f}",
                     f"{obuchowski['diff_nv_minus_bf_pp']:+.2f}", f"{obuchowski['se_diff_pp']:.2f}",
                     f"{obu_x2:.2f}", fmt_p(obuchowski["p"])]])
    md += ["", "### Holm correction (family of 17 tests)", "",
           "McNemar tests use the uncorrected χ² (as in `stats.py`); the exact binomial p is shown "
           "alongside, with its own Holm column as a sensitivity check. Each row compares the first "
           "condition (→ left) to the second (→ right); b = second-only successes, c = first-only. "
           f"The moderator permutation statistic is {perm['statistic']}; observed "
           f"{stat_obs:+.2f} pp, {n_extreme:,} of {total_splits:,} label splits as or more extreme "
           f"(two-sided), exact p = {fmt_p(perm['p_two_sided_exact'])}. The GEE bundle × stratum "
           "Wald test is outside the family (table above).", ""]
    md += md_table(["group", "comparison", "basis", "Δ pp", "b", "c", "χ²", "p raw", "p Holm",
                    "p exact", "p Holm (exact)"],
                   [[f_["group"], f_["comparison"], f_["basis"], f"{f_['delta_pp']:+.2f}",
                     "" if f_["b"] is None else f_["b"], "" if f_["c"] is None else f_["c"],
                     "" if f_["chi2"] is None else f"{f_['chi2']:.2f}", fmt_p(f_["p_raw"]),
                     fmt_p(f_["p_holm"]), fmt_p(f_["p_exact"]), fmt_p(f_["p_holm_exact"])]
                    for f_ in family])
    md += ["", "### Token savings — bootstrap CIs", "",
           "Same page-cluster percentile procedure; each cell has 10 targets per page, so a resampled "
           "page contributes its 10 records to each cell. Reduction = 1 − mean(cell)/mean(reference).", ""]
    md += md_table(["comparison", "token measure", "reduction %", "95% CI %"],
                   [[k.split(" [")[0], v["metric"], f"{v['reduction_pct']:.2f}",
                     f"[{v['boot_ci_lo_pct']:.2f}, {v['boot_ci_hi_pct']:.2f}]"] for k, v in token_ci.items()])
    md += ["", "### The 912 grabbed failures by subtype", "",
           "Mutually exclusive assignment in priority order: volatile (cond 3 false) → positional "
           "(cond 4 false) → invalid cross-shadow syntax → non-unique (cond 1 false) → wrong element "
           "(cond 1 true, cond 2 false). Invalid cross-shadow syntax = the locator text contains an "
           "invented shadow marker attribute or a non-standard piercing combinator "
           f"(`{shadow_re.pattern}`). The records carry no match count, so non-unique covers both "
           "zero matches and ≥ 2 matches. A descendant selector that crosses a shadow boundary is not "
           "identifiable from the records and is counted under non-unique / wrong element.", ""]
    md += md_table(["subtype", "primary (exclusive)", "flag (multi-label)"],
                   [[n, sub_counts[n], flag_counts[n]] for n, _ in order] + [["total", len(gb), ""]])
    md += ["", "Flag combinations:", ""]
    md += md_table(["combination", "n"], [[k or "(none)", int(v)] for k, v in combo.items()])
    md += ["", "Primary subtype by bundle:", ""]
    md += md_table(["bundle"] + [n for n, _ in order],
                   [[b] + [int(v) for v in row] for b, row in sub_by_bundle.iterrows()])
    md += ["", "Primary subtype by encoding:", ""]
    md += md_table(["encoding"] + [n for n, _ in order],
                   [[e] + [int(v) for v in row] for e, row in sub_by_enc.iterrows()])
    md += ["", "### Pareto frontier and COP under API-reported tokens", "",
           "**Missing field:** the records carry no API-reported token count for the observation alone. "
           "`prompt_tokens_total` is the API usage for the whole prompt (system prompt + observation + "
           "task). For these GPT-4.1 records, `prompt_tokens_total − observation_tokens` ranges "
           f"{pareto_api['prompt_minus_observation_tokens']['min']}–"
           f"{pareto_api['prompt_minus_observation_tokens']['max']} tokens "
           f"(mean {pareto_api['prompt_minus_observation_tokens']['mean']:.1f}). The frontier below uses "
           "mean `prompt_tokens_total` per cell; success values are unchanged.", ""]
    md += md_table(["bundle", "encoding", "success %", "mean o200k obs tok", "mean API prompt tok",
                    "status (o200k)", "status (API)"],
                   [[c["bundle"], c["encoding"], f"{c['success_pct']:.2f}", f"{c['mean_obs_tokens']:.0f}",
                     f"{c['mean_api_prompt_tokens']:.0f}", c["status_o200k"], c["status_api"]]
                    for c in pareto_api["cells"]])
    md += ["", f"- Frontier (API): {', '.join('×'.join(c) for c in frontier_api)}",
           f"- Dominated (API): {pareto_api['dominated_count']} of 21",
           f"- COP under API tokens: {'×'.join(cop_api)}; B_noVolatile×F3 on the frontier: "
           f"{pareto_api['published_cop_on_frontier']}; weakly dominated by: "
           f"{pareto_api['published_cop_weakly_dominated_by'] or 'none'}",
           f"- COP vs B_full×F1 reduction (API): {pareto_api['cop_vs_bff1_reduction_pct']:.2f}%; "
           f"F3 vs F1 within B_noVolatile (API): {pareto_api['f3_vs_f1_reduction_pct']:.2f}%"]

    # 5. Differences vs published
    diffs = []
    exact_tokens = {
        "B_noVolatile×F3 mean observation tokens": (17887, tok[("B_noVolatile", "F3")],
                                                    "FINDINGS.md / amendments cite 17,887; encoding.py asserts 17,888 ±1"),
        "B_noVolatile×F1 mean observation tokens": (25238, tok[("B_noVolatile", "F1")],
                                                    "FINDINGS.md cites 25,238; pareto.py/encoding.py assert 25,239 ±1"),
        "B_full×F1 mean observation tokens": (27097, tok[("B_full", "F1")], "FINDINGS.md cites 27,097"),
    }
    for label, (pub, got, src) in exact_tokens.items():
        if round(got) != pub:
            diffs.append({"item": label, "published": pub, "recomputed": got,
                          "reason": f"rounding of a non-integer mean ({got:.3f}); {src}"})
    if f"{p5['p']:.2e}" != "1.12e-17":
        diffs.append({"item": "McNemar p", "published": "1.12e-17", "recomputed": f"{p5['p']:.3e}",
                      "reason": "formatting"})
    if regress_info["nv_volatile (cond3 false)"] != 4:
        diffs.append({"item": "11 regressions: genuine volatile grabs", "published": "~4",
                      "recomputed": regress_info["nv_volatile (cond3 false)"],
                      "reason": "FINDINGS.md gives an approximate count ('~4'); recomputed from "
                                "predicate_non_volatile under B_noVolatile"})
    rn_line = next((i for i, line in enumerate(FINDINGS.read_text(encoding="utf-8").splitlines(), 1)
                    if "r/n for role/name" in line), None)
    if rn_line and (keymap.get("role") != "r" or keymap.get("name") != "n"):
        diffs.append({"item": f"F2 abbreviations named in experiments/FINDINGS.md line {rn_line} (prose)",
                      "published": "r/n for role/name",
                      "recomputed": f"role→{keymap.get('role')}, name→{keymap.get('name')}",
                      "reason": "FINDINGS.md prose does not match ObservationEncoders.F2KeyMap"})
    R["differences_vs_published"] = diffs
    R["controls"] = ctl.rows

    md += ["", "## Differences from published values", ""]
    if diffs:
        md += md_table(["item", "published", "recomputed", "reason"],
                       [[x["item"], x["published"],
                         f"{x['recomputed']:.3f}" if isinstance(x["recomputed"], float) else x["recomputed"],
                         x["reason"]] for x in diffs])
    else:
        md += ["None."]
    md += ["", "All other published values listed in section 0 reproduce exactly."]

    # Write outputs, re-verify guards
    (OUT_DIR / "diagnostics.json").write_text(
        json.dumps(jsonable(R), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    (OUT_DIR / "diagnostics.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")

    after = protected_state()
    if after != before:
        changed = [k for k in before if before[k] != after.get(k)]
        raise SystemExit(f"[guard] protected files changed during the run: {changed}")
    print(f"\n[guard] experiments/FINDINGS.md, corpus and truth files unchanged ({len(after)} files).")
    print(f"[out] {(OUT_DIR / 'diagnostics.md').relative_to(REPO)}")
    print(f"[out] {(OUT_DIR / 'diagnostics.json').relative_to(REPO)}")

    print("\n" + "=" * 72)
    print("DIFFERENCES FROM PUBLISHED VALUES")
    print("=" * 72)
    if not diffs:
        print("  none")
    for x in diffs:
        print(f"  - {x['item']}: published {x['published']} | recomputed {x['recomputed']}\n"
              f"      reason: {x['reason']}")


if __name__ == "__main__":
    main()
