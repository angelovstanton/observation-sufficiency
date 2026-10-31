"""
Analysis of the real-site pilot (`experiments/batch --plan pilot`); zero LLM, zero network.

Implements experiments/results/revision1/real_pilot/pilot_analysis_plan.md with its addenda (9f0bb2b scope /
class_only reuse / hard cap; 9ead395 "no stable signal" descriptive only; 4bcc9e8 final figures) and nothing else.
Committed before any pilot record was read.

Inputs
  - <records>/batch_pilot_*.jsonl (default experiments/results/revision1/batch_runs_pilot/): one record per called
    event and per reused class_only event; <records>/journal.jsonl if present (run summary only).
  - Pinned by sha256: real_pilot/pilot_plan.json, pilot_reuse_map.json, targets.json (stratum and signal_attrs per
    target; the records do not carry them), pilot_sites.json (Tranco order = bootstrap cluster order),
    survival_targets.json (September target per May target).
  - Survival TSV from rp_survival.py, optional; without it survival is reported as not computed.

Outcomes: P5 = success (five-condition predicate); P_now = condition 1 ∧ 2.

Primary: B_full vs B_noVolatile (B_noVolatileConsistent) on the same target, per encoding (F1, F3), metric and
stratum; Δ = P(B_noVolatile) − P(B_full) in pp. "has stable signal": McNemar (uncorrected χ², exact p, OR = b/c
with exact conditional CI) and a site-clustered percentile bootstrap CI for Δ (10,000, seed 42, 33 sites in
Tranco order; replicates with an empty stratum are excluded and counted). "no stable signal": counts and shares
only (addendum 9ead395). No multiplicity correction. Sensitivity: class_only (B_full_minus_volClass) in place of
B_noVolatile; a reused class_only record carries its source's result (addendum 9f0bb2b).

Interpretation, fixed before any outcome: P5 matches the corpus pattern if Δ > 0; P_now matches "≈ 0" if the
95% bootstrap CI of Δ contains 0. No claim that the effect size transfers.

Secondary, survival: per cell, the share of locators that resolve to exactly the September target, among targets
with a unique September target (others excluded and counted). Addendum (д): locators left undetermined (unstable
DOM after 5 loads) are counted separately and left out of the share.

Also reported, descriptive only: per-site results and a run summary. Calls not made (e.g. cap stop) are reported as
missing, not replaced; a pair needs both arms.

Output: experiments/results/revision1/pilot_analysis.md / pilot_analysis.json (or --out-prefix).
Run:    python experiments/analysis/revision1_pilot_analysis.py [--records DIR] [--survival TSV] [--out-prefix PATH]
"""
from __future__ import annotations

import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import argparse      # noqa: E402
import collections   # noqa: E402
import hashlib       # noqa: E402
import json          # noqa: E402
import math          # noqa: E402

import numpy as np    # noqa: E402

from revision1_diagnostics import (                                         # noqa: E402
    OUT_DIR, N_BOOT, SEED, jsonable, md_table, fmt_p, fmt_or, mcnemar, page_bootstrap, pct_ci,
)

RP_DIR = OUT_DIR / "real_pilot"
RECORDS_DIR = OUT_DIR / "batch_runs_pilot"
SURVIVAL_TSV = OUT_DIR / "pilot_survival.tsv"
SURVIVAL_REFERENCE = "survival_reference.json"                  # in real_pilot/; addenda (е), (е′)
SURVIVAL_HEADER = "event_key\tlocator_sha256\tunique_match\tmatches_target\tstatus\tattempts\tpre_hashes\twindows"
SURVIVAL_STATUSES = ("survived", "broken", "undetermined", "undetermined_no_reference")
SURVIVAL_REFERENCE_SHA = "d115fe48f201bea1e2291563d511efc0ca8ef6c16e0ae37c1965c364af79b1b3"  # real_pilot/survival_reference.json
NO_REFERENCE = "undetermined (no stable reference)"            # (е′) point 3, (е‴) point 3
OUT_PREFIX = OUT_DIR / "pilot_analysis"

PINS = {
    "pilot_plan.json": "b79364225b5e3a025067c87c89218beb60c3790c7ced58f247d098961f209a90",
    "pilot_reuse_map.json": "41fddd0efcbe0e92acdff9343396e8e326735b384673c30a8b8d30c14f9c0364",
    "targets.json": "e890544fcfd19789f0587e564b17e9ebb62d7877f3ad99b4d8a3070e7b243fec",
    "pilot_sites.json": "15ab318758d54d820bd611628dc4c6efaf5378e5286624a5d388176444b4d0ba",
    "survival_targets.json": "6bdd67be22b43caa126305ab50784ff2136c46bce05e507bae8bd5dac70874db",
}
N_CALLED, N_REUSED, N_SITES, N_TARGETS = 1476, 480, 33, 326
PRICE_IN, PRICE_OUT, CAP_USD = 2.00, 8.00, 114.34          # USD per 1M tokens; hard cap (addendum 4bcc9e8)
MAX_OUTPUT_TOKENS = 256                                      # the runner's output bound per call (BudgetModel.Bound)

CELL_OF = {"B_full": "B_full", "B_noVolatileConsistent": "B_noVolatile", "B_full_minus_volClass": "class_only"}
CELLS = ["B_full", "B_noVolatile", "class_only"]
ENCODINGS = ["F1", "F3"]
METRICS = ["P5", "P_now"]
HAS, NONE = "has stable signal", "no stable signal"
COMPARISONS = [("primary", "B_full", "B_noVolatile"), ("sensitivity", "B_full", "class_only")]
CORPUS_PATTERN = {"P5": "↑ (Δ > 0)", "P_now": "≈ 0 (95% CI of Δ contains 0)"}


class PilotDataError(Exception):
    """The records disagree with the pinned plan; nothing is analysed."""


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: pathlib.Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


# Pinned inputs

def load_pinned(rp_dir: pathlib.Path = RP_DIR) -> dict:
    for name, pin in PINS.items():
        got = sha256(rp_dir / name)
        if got != pin:
            raise PilotDataError(f"{name} sha256 {got} != pinned {pin}")
    plan = json.loads((rp_dir / "pilot_plan.json").read_text(encoding="utf-8"))
    reuse = json.loads((rp_dir / "pilot_reuse_map.json").read_text(encoding="utf-8"))
    targets = json.loads((rp_dir / "targets.json").read_text(encoding="utf-8"))["items"]
    sites = json.loads((rp_dir / "pilot_sites.json").read_text(encoding="utf-8"))["sites"]
    survival = json.loads((rp_dir / "survival_targets.json").read_text(encoding="utf-8"))
    called = {e["event_key"]: e for e in plan["events"]}
    reused = {r["class_only_event_key"]: r for r in reuse["reuse"]}
    if len(called) != N_CALLED or len(reused) != N_REUSED or len(sites) != N_SITES or len(targets) != N_TARGETS:
        raise PilotDataError("pinned counts differ from 1,476 / 480 / 33 / 326")
    site_order = [s["key"] for s in sorted(sites, key=lambda s: s["rank"])]
    target = {(f"{t['rank']:04d}_{t['domain']}", t["marker"]): t for t in targets}
    sept = {(f"{t['rank']:04d}_{t['domain']}", t["marker"]): t for t in survival["items"]}
    check_join(called, reused, target, reuse.get("plan_sha256"))
    return {"plan": plan, "called": called, "reused": reused, "site_order": site_order, "target": target,
            "sept": sept, "sites": {s["key"]: s for s in sites}}


def check_join(called: dict, reused: dict, target: dict, reuse_plan_sha: str | None) -> None:
    """Strict 1:1 join of plan, reuse map and targets: every (target × cell × encoding) is exactly one event,
    called or reused, never both; every reuse source is a called B_noVolatile event of the same target and
    encoding; the plan's stratum is the target's."""
    if reuse_plan_sha != PINS["pilot_plan.json"]:
        raise PilotDataError(f"pilot_reuse_map.json names plan {reuse_plan_sha}, not {PINS['pilot_plan.json']}")
    both = set(called) & set(reused)
    if both:
        raise PilotDataError(f"{len(both)} event key(s) both called and reused, e.g. {sorted(both)[0]}")
    cells: dict[tuple, str] = {}
    for k, e in called.items():
        if e["cell"] not in CELLS:
            raise PilotDataError(f"{k}: unknown cell {e['cell']!r}")
        t = target.get((e["page"], e["task_id"]))
        if t is None:
            raise PilotDataError(f"{k}: target {e['page']} {e['task_id']} not in targets.json")
        if e["stratum"] != t["stratum"]:
            raise PilotDataError(f"{k}: plan stratum {e['stratum']!r} != targets.json {t['stratum']!r}")
        cells.setdefault((e["page"], e["task_id"], e["cell"], e["encoding"]), k)
    for k, r in reused.items():
        src = called.get(r["reused_event_key"])
        if src is None or src["cell"] != "B_noVolatile" or (src["page"], src["task_id"], src["encoding"]) != \
                (r["page"], r["task_id"], r["encoding"]):
            raise PilotDataError(f"{k}: reuse source {r['reused_event_key']} is not the called B_noVolatile event of "
                                 f"the same target and encoding")
        if r["class_only_observation_sha256"] != r["b_novolatile_observation_sha256"] or \
                r["b_novolatile_observation_sha256"] != src["observation_sha256"]:
            raise PilotDataError(f"{k}: reuse map observation sha256 differs from its source's")
        if (r["page"], r["task_id"]) not in target:
            raise PilotDataError(f"{k}: target {r['page']} {r['task_id']} not in targets.json")
        cells.setdefault((r["page"], r["task_id"], "class_only", r["encoding"]), k)
    n_events = len(called) + len(reused)
    want = {(p, task, c, enc) for (p, task) in target for c in CELLS for enc in ENCODINGS}
    if len(cells) != n_events or set(cells) != want:
        raise PilotDataError(f"plan + reuse map: {n_events} events cover {len(cells)} distinct (target, cell, "
                             f"encoding); expected exactly {len(want)} = {len(target)} × {len(CELLS)} × {len(ENCODINGS)}, 1:1")


def expected_events(pin: dict) -> dict:
    """event_key → (page, task_id, cell, encoding, reused_from or None)."""
    out = {}
    for k, e in pin["called"].items():
        out[k] = (e["page"], e["task_id"], e["cell"], e["encoding"], None)
    for k, r in pin["reused"].items():
        out[k] = (r["page"], r["task_id"], "class_only", r["encoding"], r["reused_event_key"])
    return out


# Records

def load_records(records_dir: pathlib.Path, pin: dict) -> tuple[dict, dict]:
    if not records_dir.is_dir():
        raise PilotDataError(f"records directory not found: {records_dir}")
    exp = expected_events(pin)
    plan_sha = PINS["pilot_plan.json"]
    recs: dict[str, dict] = {}
    for f in sorted(records_dir.glob("batch_pilot_*.jsonl")):
        for n, r in enumerate(read_jsonl(f), 1):
            where = f"{f.name}:{n}"
            key = r.get("event_key")
            if key not in exp:
                raise PilotDataError(f"{where}: event_key {key!r} is not a pilot event")
            if key in recs:
                raise PilotDataError(f"{where}: duplicate record for {key}")
            page, task, cell, enc, src = exp[key]
            if (r["page"], r["task_id"], CELL_OF.get(r["bundle"]), r["encoding"]) != (page, task, cell, enc):
                raise PilotDataError(f"{where}: page/task/bundle/encoding differ from the plan for {key}")
            if r["plan_sha256"] != plan_sha:
                raise PilotDataError(f"{where}: plan_sha256 {r['plan_sha256']} != {plan_sha}")
            if bool(r.get("reused")) != (src is not None) or r.get("reused_from_event_key") != src:
                raise PilotDataError(f"{where}: reuse marker disagrees with pilot_reuse_map.json")
            want_sha = (pin["called"][key]["observation_sha256"] if src is None
                        else pin["reused"][key]["class_only_observation_sha256"])
            if r["observation_sha256"] != want_sha:
                raise PilotDataError(f"{where}: observation_sha256 != pilot_plan.json / pilot_reuse_map.json")
            t = pin["target"][(page, task)]
            if bool(r["stable_signal_present_in_bundle"]) != (t["stratum"] == HAS):
                raise PilotDataError(f"{where}: condition 5 {r['stable_signal_present_in_bundle']} != stratum '{t['stratum']}'")
            recs[key] = r
    # A reused record is its source's result (same locator, same score), re-keyed.
    for key, r in recs.items():
        src = exp[key][4]
        if src is None:
            continue
        s = recs.get(src)
        if s is None:
            raise PilotDataError(f"reused record {key} without its source record {src}")
        for f in ("locator_raw", "success", "predicate_unique_match", "predicate_matches_oracle", "failure_mode"):
            if r[f] != s[f]:
                raise PilotDataError(f"reused record {key}: {f} differs from source {src}")
    return recs, exp


def outcome_rows(recs: dict, exp: dict, pin: dict) -> dict:
    """(page, task_id, encoding, cell) → outcome row."""
    rows = {}
    for key, r in recs.items():
        page, task, cell, enc, src = exp[key]
        t = pin["target"][(page, task)]
        rows[(page, task, enc, cell)] = {
            "event_key": key, "page": page, "task_id": task, "encoding": enc, "cell": cell,
            "stratum": t["stratum"], "P5": bool(r["success"]),
            "P_now": bool(r["predicate_unique_match"]) and bool(r["predicate_matches_oracle"]),
            "failure_mode": r["failure_mode"], "reused": src is not None, "locator_raw": r["locator_raw"],
            "prompt_tokens": int(r["prompt_tokens_total"]), "completion_tokens": int(r["completion_tokens"]),
            "observation_tokens": int(r["observation_tokens"]),
        }
    return rows


# Statistics

def site_bootstrap(site_order: list[str], pairs: list[tuple[str, bool, bool]],
                   n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """Site-clustered percentile bootstrap of Δ = P(second) − P(first), pp. Empty replicates → undefined, counted."""
    idx = {s: i for i, s in enumerate(site_order)}
    n = np.zeros(len(site_order)); f = np.zeros(len(site_order)); s = np.zeros(len(site_order))
    for site, a, b in pairs:
        n[idx[site]] += 1; f[idx[site]] += a; s[idx[site]] += b
    stat = lambda t: float("nan") if t["n"] == 0 else (t["s"] / t["n"] - t["f"] / t["n"]) * 100  # noqa: E731
    draws = page_bootstrap(site_order, {"n": n, "f": f, "s": s}, stat, n_boot=n_boot, seed=seed)
    ok = draws[~np.isnan(draws)]
    lo, hi = pct_ci(ok) if len(ok) else (float("nan"), float("nan"))
    return {"ci_lo": lo, "ci_hi": hi, "replicates": int(n_boot), "empty_replicates": int(len(draws) - len(ok))}


def pairs_of(rows: dict, first: str, second: str, enc: str, stratum: str) -> list[tuple[str, str, bool, bool, str]]:
    out = []
    for (page, task, e, cell), r in rows.items():
        if e != enc or cell != first or r["stratum"] != stratum:
            continue
        o = rows.get((page, task, enc, second))
        if o is not None:
            out.append((page, task, r, o))
    return sorted(out, key=lambda x: (x[0], x[1]))


def compare(rows: dict, site_order: list[str], kind: str, first: str, second: str, enc: str, metric: str) -> dict:
    p = pairs_of(rows, first, second, enc, HAS)
    a = np.array([x[2][metric] for x in p], dtype=bool)
    b = np.array([x[3][metric] for x in p], dtype=bool)
    res = {"comparison": kind, "first": first, "second": second, "encoding": enc, "metric": metric, "stratum": HAS}
    if len(p) == 0:
        return {**res, "n": 0, "undefined": "no pairs"}
    res.update(mcnemar(a, b))
    res.update(site_bootstrap(site_order, [(x[0], bool(x[2][metric]), bool(x[3][metric])) for x in p]))
    d = res["delta_pp"]
    res["direction"] = "+" if d > 0 else ("−" if d < 0 else "0")
    if metric == "P5":
        res["matches_corpus"] = bool(d > 0)
    else:
        res["matches_corpus"] = bool(res["ci_lo"] <= 0 <= res["ci_hi"])
    return res


def describe(rows: dict, stratum: str, metric_cells=CELLS) -> list[dict]:
    out = []
    for enc in ENCODINGS:
        for cell in metric_cells:
            sel = [r for (pg, t, e, c), r in rows.items() if e == enc and c == cell and r["stratum"] == stratum]
            n = len(sel)
            row = {"stratum": stratum, "encoding": enc, "cell": cell, "n": n}
            for m in METRICS:
                k = sum(r[m] for r in sel)
                row[f"{m}_count"] = k
                row[f"{m}_pct"] = (k / n * 100) if n else float("nan")
            out.append(row)
    return out


def per_site(rows: dict, site_order: list[str]) -> list[dict]:
    out = []
    for site in site_order:
        for enc in ENCODINGS:
            row = {"site": site, "encoding": enc}
            for cell in CELLS:
                sel = [r for (pg, t, e, c), r in rows.items() if pg == site and e == enc and c == cell]
                row[f"{cell}_n"] = len(sel)
                for m in METRICS:
                    row[f"{cell}_{m}"] = sum(r[m] for r in sel)
            out.append(row)
    return out


def load_reference(path: pathlib.Path | None) -> dict | None:
    """Addenda (е)/(е′): the September reference per site; None if the file does not exist."""
    if path is None or not path.exists():
        return None
    ref = json.loads(path.read_text(encoding="utf-8"))
    sites = {s["key"]: s for s in ref["sites"]}
    if len(sites) != N_SITES:
        raise PilotDataError(f"{path.name}: {len(sites)} sites, expected {N_SITES}")
    pending = sorted(k for k, s in sites.items() if not s["stable"] and s.get("status") != NO_REFERENCE)
    if pending:
        raise PilotDataError(f"{path.name}: {pending} neither stable nor marked {NO_REFERENCE!r}")
    return {"sha256": sha256(path), "stable": sorted(k for k, s in sites.items() if s["stable"]),
            "no_reference": sorted(k for k, s in sites.items() if not s["stable"])}


def survival(rows: dict, pin: dict, tsv: pathlib.Path | None, reference: dict | None = None) -> dict:
    sept = pin["sept"]
    undefined_targets = collections.Counter(t["status"] for t in sept.values() if t["status"] != "unique")
    if tsv is None or not tsv.exists():
        return {"computed": False, "undefined_targets": dict(undefined_targets)}
    if reference is None:
        raise PilotDataError("survival TSV without real_pilot/survival_reference.json (addendum (е))")
    no_ref = set(reference["no_reference"])
    lines = tsv.read_text(encoding="utf-8").splitlines()
    if lines[0] != SURVIVAL_HEADER:
        raise PilotDataError(f"unexpected survival header in {tsv}")
    res = {}
    for ln in lines[1:]:
        k, lsha, um, mt, status, *_ = ln.split("\t")
        if k in res:
            raise PilotDataError(f"survival: duplicate {k}")
        # Addendum (д): survived / broken (determined on an unchanged DOM) or undetermined (unstable DOM, 5 attempts);
        # addendum (е′): undetermined_no_reference (the site has no stable September reference; not evaluated).
        if status not in SURVIVAL_STATUSES or \
                (status == "survived") != (um == "True" and mt == "True" and not status.startswith("undetermined")) or \
                (status == "undetermined_no_reference" and (um, mt) != ("", "")):
            raise PilotDataError(f"survival: {k} status {status!r} disagrees with unique_match {um} / matches_target {mt}")
        site = k.split("|")[3]
        if (status == "undetermined_no_reference") != (site in no_ref):
            raise PilotDataError(f"survival: {k} status {status!r} disagrees with the reference of {site} "
                                 f"({'no stable reference' if site in no_ref else 'stable'})")
        res[k] = (lsha, status)
    by_key = {r["event_key"]: r for r in rows.values()}
    cells = []
    for enc in ENCODINGS:
        for cell in CELLS:
            sel = [r for (pg, t, e, c), r in rows.items() if e == enc and c == cell]
            defined = [r for r in sel if sept[(r["page"], r["task_id"])]["status"] == "unique"]
            survived = undetermined = no_reference = 0
            for r in defined:
                if r["event_key"] not in res:
                    raise PilotDataError(f"survival: no result for {r['event_key']}")
                lsha, status = res[r["event_key"]]
                if lsha != hashlib.sha256(r["locator_raw"].encode("utf-8")).hexdigest():
                    raise PilotDataError(f"survival: locator of {r['event_key']} differs from the record")
                survived += status == "survived"
                undetermined += status == "undetermined"
                no_reference += status == "undetermined_no_reference"
            determined = len(defined) - undetermined - no_reference
            cells.append({"encoding": enc, "cell": cell, "records": len(sel), "defined": len(defined),
                          "undefined": len(sel) - len(defined), "undetermined": undetermined,
                          "undetermined_no_reference": no_reference,
                          "determined": determined, "survived": survived, "broken": determined - survived,
                          "share_pct": (survived / determined * 100) if determined else float("nan")})
    extra = set(res) - set(by_key)
    if extra:
        raise PilotDataError(f"survival: {len(extra)} results without a record")
    return {"computed": True, "undefined_targets": dict(undefined_targets), "cells": cells,
            "reference_sha256": reference["sha256"], "no_reference_sites": reference["no_reference"]}


def released_liability(journal: list[dict]) -> tuple[int, int]:
    """Addendum (е) point 4: Σ over `released` lines of Bound(reservation) = reservation × 2 + 256 × 8 µUSD, as the
    runner's BudgetModel.Liability. The reservation is the line's own, else that of the key's last `pending`;
    `overrun_released` adds nothing (its usage is counted with the response). Returns (µUSD, released lines)."""
    resv, micro, n = {}, 0, 0
    for e in journal:
        if e["type"] == "pending":
            resv[e["key"]] = int(e["reservation"])
        elif e["type"] == "released":
            r = int(e["reservation"]) if e.get("reservation") is not None else resv[e["key"]]
            micro += r * int(PRICE_IN) + MAX_OUTPUT_TOKENS * int(PRICE_OUT)
            n += 1
    return micro, n


def run_summary(recs: dict, exp: dict, records_dir: pathlib.Path) -> dict:
    present = collections.Counter((exp[k][2], exp[k][3]) for k in recs)
    expected = collections.Counter((v[2], v[3]) for v in exp.values())
    missing = sorted(k for k in exp if k not in recs)
    called = [r for k, r in recs.items() if exp[k][4] is None]
    p = sum(int(r["prompt_tokens_total"]) for r in called)
    c = sum(int(r["completion_tokens"]) for r in called)
    out = {
        "records": len(recs), "expected": len(exp), "missing": len(missing), "missing_keys": missing,
        "per_cell": [{"cell": cell, "encoding": enc, "present": present[(cell, enc)], "expected": expected[(cell, enc)]}
                     for enc in ENCODINGS for cell in CELLS],
        "called_records": len(called), "reused_records": len(recs) - len(called),
        "prompt_tokens": p, "completion_tokens": c,
        "list_price_usd": p * PRICE_IN / 1e6 + c * PRICE_OUT / 1e6, "cap_usd": CAP_USD,
    }
    jp = records_dir / "journal.jsonl"
    if jp.exists():
        j = read_jsonl(jp)
        out["journal"] = {"sha256": sha256(jp), "lines": len(j),
                          "types": dict(sorted(collections.Counter(e["type"] for e in j).items())),
                          "released_keys": sorted({e["key"] for e in j if e["type"] == "released"})}
        micro, n = released_liability(j)
        out["released_lines"] = n
        out["released_liability_usd"] = micro / 1e6
        out["total_usd"] = out["list_price_usd"] + micro / 1e6
    return out


# Report

def pct(x) -> str:
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.1f}"


def ci(lo, hi) -> str:
    return "n/a" if math.isnan(lo) else f"[{lo:+.2f}, {hi:+.2f}]"


def render(result: dict) -> str:
    L = ["# Revision 1 — real-site pilot analysis", "",
         "Zero LLM, zero network. Follows `real_pilot/pilot_analysis_plan.md` and its addenda (committed before any "
         "model call); this script was committed before any pilot record was read. Nothing outside the plan is "
         "computed for the pilot claim.", "",
         "**Direction, not size.** What is reported is the direction of Δ and whether it matches the corpus pattern; "
         "no claim is made that the effect size transfers from the corpus to real sites. Conclusions about B_full vs "
         "B_noVolatile (and the class-only sensitivity) are drawn only for the stratum \"has stable signal\"; the "
         "stratum \"no stable signal\" is descriptive only.", "",
         f"Conventions: Δ = second − first (pp); 95% CI = site-clustered percentile bootstrap ({N_BOOT:,} replicates, "
         f"seed {SEED}, clusters = {N_SITES} sites in Tranco order; empty-stratum replicates excluded and counted); "
         "b = second-only, c = first-only; OR = b/c with exact conditional CI; p χ² = McNemar uncorrected; "
         "p exact = binomial. P5 = five-condition predicate; P_now = unique match ∧ matches oracle. Corpus pattern "
         "(has stable signal): P5 ↑ — read as Δ > 0; P_now ≈ 0 — read as 95% CI of Δ contains 0.", ""]
    s = result["run_summary"]
    L += ["## Run", "",
          f"Records {s['records']:,} / {s['expected']:,} expected ({s['called_records']:,} called, "
          f"{s['reused_records']:,} reused class_only); missing {s['missing']:,} (not replaced; a pair needs both arms). "
          f"Called records: prompt tokens {s['prompt_tokens']:,}, completion tokens {s['completion_tokens']:,}, "
          f"list price USD {s['list_price_usd']:.6f} (cap {s['cap_usd']:.2f}).", ""]
    if "released_liability_usd" in s:
        L += [f"Cost with release liability (addendum (е) point 4): called records USD {s['list_price_usd']:.6f} + "
              f"liability of {s['released_lines']} released key line(s) USD {s['released_liability_usd']:.6f} "
              f"(Bound = reservation × 2 + 256 × 8 µUSD) = **USD {s['total_usd']:.6f}**.", ""]
    else:
        L += ["Cost with release liability: not computed (no journal.jsonl).", ""]
    L += md_table(["encoding", "cell", "present", "expected"],
                  [[r["encoding"], r["cell"], r["present"], r["expected"]] for r in s["per_cell"]])
    if "journal" in s:
        j = s["journal"]
        L += ["", f"Journal: {j['lines']:,} lines, sha256 `{j['sha256']}`; types {j['types']}; "
                  f"released keys {len(j['released_keys'])}."]
    hdr = ["comparison (second − first)", "enc", "pred", "n", "first %", "second %", "Δ pp", "95% CI (pp)",
           "empty repl.", "b/c", "OR [95% CI]", "p χ²", "p exact", "direction", "matches corpus"]
    for kind, title in (("primary", "Primary — B_full vs B_noVolatile, stratum \"has stable signal\""),
                        ("sensitivity", "Sensitivity — B_full vs class_only, stratum \"has stable signal\"")):
        L += ["", f"## {title}", ""]
        rows = []
        for r in result["comparisons"]:
            if r["comparison"] != kind:
                continue
            if r.get("n", 0) == 0:
                rows.append([f"{r['second']} vs {r['first']}", r["encoding"], r["metric"], 0] + ["n/a"] * 11)
                continue
            rows.append([f"{r['second']} vs {r['first']}", r["encoding"], r["metric"], r["n"],
                         pct(r["rate_first_pct"]), pct(r["rate_second_pct"]), f"{r['delta_pp']:+.2f}",
                         ci(r["ci_lo"], r["ci_hi"]), r["empty_replicates"],
                         f"{r['b_second_only']}/{r['c_first_only']}",
                         "n/a" if math.isnan(r["odds_ratio"]) else
                         f"{fmt_or(r['odds_ratio'])} [{fmt_or(r['or_ci_lo'])}, {fmt_or(r['or_ci_hi'])}]",
                         fmt_p(r["p"]), fmt_p(r["p_exact"]), r["direction"],
                         f"{r['matches_corpus']} ({CORPUS_PATTERN[r['metric']]})"])
        L += md_table(hdr, rows)
    L += ["", "## Stratum \"no stable signal\" — descriptive only (no McNemar, no CI, no direction test)", ""]
    L += md_table(["enc", "cell", "n", "P5", "P5 %", "P_now", "P_now %"],
                  [[r["encoding"], r["cell"], r["n"], r["P5_count"], pct(r["P5_pct"]), r["P_now_count"],
                    pct(r["P_now_pct"])] for r in result["descriptive_no_signal"]])
    L += ["", "Stratum \"has stable signal\", per cell (shares, for reference):", ""]
    L += md_table(["enc", "cell", "n", "P5", "P5 %", "P_now", "P_now %"],
                  [[r["encoding"], r["cell"], r["n"], r["P5_count"], pct(r["P5_pct"]), r["P_now_count"],
                    pct(r["P_now_pct"])] for r in result["descriptive_has_signal"]])
    sv = result["survival"]
    L += ["", "## Secondary — survival (September, CC-MAIN-2026-39)", "",
          f"Targets without a unique September element (same role and name), survival undefined and excluded: "
          f"{sv['undefined_targets']} (`real_pilot/survival_targets.json`)."]
    if not sv["computed"]:
        L += ["", "Not computed: no survival TSV (`real_pilot/rp_survival.py run`)."]
    else:
        L += ["", "Share = survived / determined. Each attempt first checks the B_full × F1 pre-hash against the "
                  f"site's September reference (addenda (е), (е′); `real_pilot/{SURVIVAL_REFERENCE}`, sha256 "
                  f"`{sv['reference_sha256']}`). Undetermined = unstable September DOM after 5 fresh loads "
                  "(addendum (д)); no reference = the site has no stable reference (addendum (е′)); both reported "
                  f"separately. Sites without a stable reference: {sv['no_reference_sites'] or 'none'}."]
        L += [""] + md_table(["enc", "cell", "records", "defined", "undefined", "undetermined", "no reference",
                              "determined", "survived", "broken", "share %"],
                             [[r["encoding"], r["cell"], r["records"], r["defined"], r["undefined"], r["undetermined"],
                               r["undetermined_no_reference"], r["determined"], r["survived"], r["broken"],
                               pct(r["share_pct"])] for r in sv["cells"]])
    L += ["", "## Per site (descriptive): successes per cell", ""]
    L += md_table(["site", "enc"] + [f"{c} n / P5 / P_now" for c in CELLS],
                  [[r["site"], r["encoding"]] + [f"{r[f'{c}_n']} / {r[f'{c}_P5']} / {r[f'{c}_P_now']}" for c in CELLS]
                   for r in result["per_site"]])
    return "\n".join(L) + "\n"


def analyse(records_dir: pathlib.Path = RECORDS_DIR, survival_tsv: pathlib.Path | None = SURVIVAL_TSV,
            rp_dir: pathlib.Path = RP_DIR, reference: pathlib.Path | None = None) -> dict:
    pin = load_pinned(rp_dir)
    ref = load_reference(reference if reference is not None else rp_dir / SURVIVAL_REFERENCE)
    if reference is None and ref is not None and ref["sha256"] != SURVIVAL_REFERENCE_SHA:
        raise PilotDataError(f"{SURVIVAL_REFERENCE} sha256 {ref['sha256']} != pinned {SURVIVAL_REFERENCE_SHA}")
    recs, exp = load_records(records_dir, pin)
    rows = outcome_rows(recs, exp, pin)
    comps = [compare(rows, pin["site_order"], kind, first, second, enc, m)
             for kind, first, second in COMPARISONS for enc in ENCODINGS for m in METRICS]
    return {
        "plan_sha256": PINS["pilot_plan.json"], "pins": PINS,
        "run_summary": run_summary(recs, exp, records_dir),
        "comparisons": comps,
        "descriptive_no_signal": describe(rows, NONE),
        "descriptive_has_signal": describe(rows, HAS),
        "survival": survival(rows, pin, survival_tsv, ref),
        "per_site": per_site(rows, pin["site_order"]),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--records", type=pathlib.Path, default=RECORDS_DIR)
    ap.add_argument("--survival", type=pathlib.Path, default=SURVIVAL_TSV)
    ap.add_argument("--out-prefix", type=pathlib.Path, default=OUT_PREFIX)
    a = ap.parse_args(argv)
    result = analyse(a.records, a.survival)
    a.out_prefix.with_suffix(".json").write_text(json.dumps(jsonable(result), ensure_ascii=False, indent=1) + "\n",
                                                 encoding="utf-8")
    a.out_prefix.with_suffix(".md").write_text(render(result), encoding="utf-8")
    print(f"wrote {a.out_prefix.with_suffix('.md')} and .json")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
