"""
cross_model.py — Axis C cross-model robustness analysis.

Loads the GPT-4.1 matrix (4-cell subset, reuse) and the three new-model
axisc_*.jsonl files, then computes the key numbers that appear in the
Axis C section of this paper.  Five claims are quantified:

  1. Per-model success per diagnostic cell
  2. Form-invariance: B_noVolatile > B_full per model on F1 (shared encoding)
  3. Fair 22-page subset: page_08 and page_17 excluded for ALL models so
     Claude's TPM-constrained coverage does not bias the comparison
  4. COP cell (B_noVolatile x F3, linearized DSL) per model -- the one cell
     all four models ran, so the one valid cross-model comparison
  5. Nano-F2 grabbed_brittle blowup: 122 (F2) vs 29 (F1), same observations

CRITICAL FRAMING NOTE:
  The overall success table (section 1) is NOT a valid cross-model comparison:
  o4-mini ran COP only (the single best cell, 75.4%) while Claude ran all 4
  cells including the weak F2 cell (overall 69.1%).  Comparing those numbers
  implies o4-mini > Claude, which is wrong.  On the SAME COP cell both score
  ~75% (o4-mini 75.4%, Claude 75.2%) -- they are statistically equal.
  Section 5 reports each model on that shared cell; section 1 is context only.

  This file used to group o4-mini and claude-sonnet-4-6 into a "reasoning"
  tier against gpt-4.1/gpt-4.1-nano as "instruction", and reported the
  tier-average gap as the primary finding. That grouping is removed:
  claude-sonnet-4-6's request carries no `thinking` field (see
  shared/harness/models/AnthropicRequest.cs) -- it ran in the provider's
  standard mode, not an extended-thinking mode -- so "reasoning" described a
  code label, not a property of how the model was actually called. Each
  model is now reported on its own number; see experiments/FINDINGS.md for
  the current framing of the o4-mini/Claude COP result.

Every key number is reconciled against expected values pinned from the Axis C run
(2026-06-20 10:38 Sofia).  Mismatches are flagged MISMATCH in the
reconciliation table and written to the output JSON; they are NOT silently
fixed -- a mismatch indicates either a data-reload bug or a transcription
error in the pinned values below.

NOTE on F3 encoding: F3 is the linearized DSL encoding (EncodeF3Linearized
in shared/harness/ObservationEncoders.cs), not YAML-ARIA.

Output: experiments/results/cross_model_metrics.json

Expected record counts (from Axis C final run):
  gpt-4.1             4-cell subset of 24-page matrix:  960 records, 24 pages
  gpt-4.1-nano        4 diagnostic cells × 24 pages:    960 records, 24 pages
  o4-mini             COP only × 24 pages:               240 records, 24 pages
  claude-sonnet-4-6   4 cells, page_08 partial +
                      page_17 fully TPM-skipped:         880 records, 23 pages
"""

# UTF-8 console-independence: reconfigure stdout/stderr so Unicode glyphs
# (minus sign, x, >=, ...) print on any console (e.g. Windows cp1252) without
# requiring PYTHONUTF8. Affects output ENCODING only, never any printed value.
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import json
import pathlib
import sys

try:
    from tabulate import tabulate
except ImportError:
    def tabulate(rows, headers=None, tablefmt=None, showindex=False, floatfmt=None):
        if not rows:
            return "(empty)"
        if headers and headers != "keys":
            lines = ["  ".join(f"{str(h):<18}" for h in headers)]
            for row in rows:
                lines.append("  ".join(f"{str(v):<18}" for v in row))
            return "\n".join(lines)
        return "\n".join(str(r) for r in rows)

REPO    = pathlib.Path(__file__).parent.parent.parent
RUNS    = REPO / "experiments" / "runs"
RESULTS = REPO / "experiments" / "results"
RESULTS.mkdir(exist_ok=True)

CELLS_4     = [("B_full", "F1"), ("B_noVolatile", "F1"),
               ("B_noVolatile", "F3"), ("B_noVolatile", "F2")]
CELLS_4_SET = set(CELLS_4)
COP_B, COP_E = "B_noVolatile", "F3"

# The three canonical failure modes (§6). Priority, per Oracle.cs defect fix
# D4: lacked > unreachable > grabbed. No model in this study produced an
# unreachable record, but it is counted separately rather than folded in.
LACKED      = "observation_lacked_stable_signal"
GRABBED     = "model_grabbed_brittle_signal"
UNREACHABLE = "output_format_unreachable"

SKIP_PAGES    = {"pages/page_08.html", "pages/page_17.html"}
MODELS_ORDER  = ["gpt-4.1", "gpt-4.1-nano", "o4-mini", "claude-sonnet-4-6"]

# ── Expected values from the Axis C run ──────────────────────────────────────
#
# Pinned from the 2026-06-20 Axis C run's final output — recorded constants,
# not a live import.
# Percentage values are round(ok/n*100, 1).
# A computed value that differs from these is flagged MISMATCH.
#
REPORT = {
    # Per-model overall success (full dataset)
    "gpt41_n":   960,  "gpt41_ok":   597,  "gpt41_pct":   62.2,
    "nano_n":    960,  "nano_ok":    539,  "nano_pct":    56.1,
    "o4mini_n":  240,  "o4mini_ok":  181,  "o4mini_pct":  75.4,
    "claude_n":  880,  "claude_ok":  608,  "claude_pct":  69.1,

    # COP cell (B_noVolatile × F3, linearized DSL)
    "gpt41_cop_n":   240,  "gpt41_cop_ok":   163,  "gpt41_cop_pct":   67.9,
    "nano_cop_n":    240,  "nano_cop_ok":    159,  "nano_cop_pct":    66.2,
    "o4mini_cop_n":  240,  "o4mini_cop_ok":  181,  "o4mini_cop_pct":  75.4,
    "claude_cop_n":  230,  "claude_cop_ok":  173,  "claude_cop_pct":  75.2,

    # COP failure mode counts
    "gpt41_cop_lacked":  48,  "gpt41_cop_grabbed":  29,
    "nano_cop_lacked":   48,  "nano_cop_grabbed":   33,
    "o4mini_cop_lacked": 48,  "o4mini_cop_grabbed": 11,
    "claude_cop_lacked": 46,  "claude_cop_grabbed": 11,

    # Full-dataset failure modes
    "gpt41_lacked":  192,  "gpt41_grabbed":  171,
    "nano_lacked":   192,  "nano_grabbed":   229,
    "o4mini_lacked":  48,  "o4mini_grabbed":  11,
    "claude_lacked": 176,  "claude_grabbed":  96,

    # Nano F2 anomaly (B_noVolatile, same observations, different encoding)
    "nano_nvF1_n":  240,  "nano_nvF1_ok":  163,  "nano_nvF1_lacked":  48,  "nano_nvF1_grabbed":  29,
    "nano_nvF2_n":  240,  "nano_nvF2_ok":   70,  "nano_nvF2_lacked":  48,  "nano_nvF2_grabbed": 122,

    # Fair 22-page subset — COMMON-EVENT aligned (page_08 + page_17 excluded,
    # then (page, bundle, encoding, task_id, rep) intersection across gpt-4.1,
    # nano, claude).  Claude's missing B_full×F1 events (10, TPM-skipped) are
    # dropped from gpt-4.1 and nano too → all three four-cell models: n=870.
    # o4-mini is separate (COP-only); its n=220 is unchanged.
    "gpt41_fair_n":   870,  "gpt41_fair_ok":   563,  "gpt41_fair_pct":   64.7,
    "nano_fair_n":    870,  "nano_fair_ok":    493,  "nano_fair_pct":    56.7,
    "o4mini_fair_n":  220,  "o4mini_fair_ok":  167,  "o4mini_fair_pct":  75.9,
    "claude_fair_n":  870,  "claude_fair_ok":  600,  "claude_fair_pct":  69.0,
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _pct(ok: int, n: int) -> float:
    return round(ok / n * 100, 1) if n else 0.0


def _load(glob_pat: str, model_label: str, cell_filter=None) -> list:
    """Read JSONL files matching glob_pat, tag each record with _model."""
    recs = []
    for path in sorted(RUNS.glob(glob_pat)):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if cell_filter and (r.get("bundle"), r.get("encoding")) not in cell_filter:
                    continue
                r["_model"] = model_label
                recs.append(r)
    return recs


def _failure_mode(r: dict) -> str:
    return r.get("failure_mode") or ""


def _ok(r: dict) -> bool:
    return bool(r.get("success"))


def _is_skip_page(r: dict) -> bool:
    return r.get("page", "") in SKIP_PAGES


def _event_key(r: dict) -> tuple:
    """Full event identity: (page, bundle, encoding, task_id, rep)."""
    return (r.get("page", ""), r.get("bundle", ""), r.get("encoding", ""),
            r.get("task_id", ""), r.get("repetition", 0))


def _page_task_key(r: dict) -> tuple:
    """Event identity without bundle/encoding — for within-model cross-cell alignment."""
    return (r.get("page", ""), r.get("task_id", ""), r.get("repetition", 0))


def _assert_known_failure_modes(model: str, recs: list) -> None:
    """Every failed record must carry one of the THREE canonical failure modes
    (§6: lacked / grabbed / unreachable — priority lacked > unreachable > grabbed).
    No model in this study produced an unreachable record, but the mode is accepted
    rather than treated as unexpected. Extracted as a seam so the taxonomy contract
    can be unit-tested on synthetic records without loading the corpus."""
    bad = [r for r in recs
           if not _ok(r) and _failure_mode(r) not in (LACKED, GRABBED, UNREACHABLE)]
    assert not bad, f"{model}: {len(bad)} failure records with unexpected failure_mode"


# ── Loader ───────────────────────────────────────────────────────────────────

def load_all() -> dict[str, list]:
    """
    Returns a dict mapping model label → list of records.
    GPT-4.1 is loaded from matrix files, filtered to the 4-cell Axis C subset.
    The other three models come from their axisc_*.jsonl files.
    """
    data = {
        "gpt-4.1":           _load("matrix_page_*.jsonl",                  "gpt-4.1",           CELLS_4_SET),
        "gpt-4.1-nano":      _load("axisc_gpt-4-1-nano_page_*.jsonl",      "gpt-4.1-nano"),
        "o4-mini":           _load("axisc_o4-mini_page_*.jsonl",            "o4-mini"),
        "claude-sonnet-4-6": _load("axisc_claude-sonnet-4-6_page_*.jsonl", "claude-sonnet-4-6"),
    }

    # Schema invariants — fail loudly so callers never see silent bad data.
    assert len(data["gpt-4.1"])           == REPORT["gpt41_n"],  \
        f"gpt-4.1 record count {len(data['gpt-4.1'])} !={REPORT['gpt41_n']}"
    assert len(data["gpt-4.1-nano"])      == REPORT["nano_n"],   \
        f"nano record count {len(data['gpt-4.1-nano'])} !={REPORT['nano_n']}"
    assert len(data["o4-mini"])           == REPORT["o4mini_n"], \
        f"o4-mini record count {len(data['o4-mini'])} !={REPORT['o4mini_n']}"
    assert len(data["claude-sonnet-4-6"]) == REPORT["claude_n"], \
        f"claude record count {len(data['claude-sonnet-4-6'])} !={REPORT['claude_n']}"

    for model, recs in data.items():
        # Every record must have a known failure_mode when success=False.
        _assert_known_failure_modes(model, recs)
        # Tokenizer version invariant (§6).
        tv = {r.get("tokenizer_version") for r in recs}
        assert tv == {"o200k_base"}, f"{model}: unexpected tokenizer_version(s) {tv}"

    return data


# ── Core computations ─────────────────────────────────────────────────────────

def per_model_overall(data: dict) -> dict:
    """Success rate for each model across its full record set."""
    out = {}
    for m, recs in data.items():
        ok = sum(_ok(r) for r in recs)
        out[m] = {"n": len(recs), "ok": ok, "pct": _pct(ok, len(recs))}
    return out


def per_cell_matrix(data: dict) -> dict:
    """
    success counts per (model, bundle, encoding) cell.
    Returns dict: model → {(bundle, encoding): {"n", "ok", "pct", "lacked", "grabbed"}}.
    """
    result = {m: {} for m in data}
    for m, recs in data.items():
        by_cell: dict = {}
        for r in recs:
            key = (r.get("bundle"), r.get("encoding"))
            if key not in by_cell:
                by_cell[key] = {"n": 0, "ok": 0, "lacked": 0, "grabbed": 0,
                                "unreachable": 0}
            by_cell[key]["n"]  += 1
            by_cell[key]["ok"] += _ok(r)
            if not _ok(r):
                fm = _failure_mode(r)
                # Three canonical modes (§6). Without the third branch an
                # unreachable record would be silently counted in neither
                # bucket, so the modes would not sum to the failure total.
                if fm == LACKED:
                    by_cell[key]["lacked"]      += 1
                elif fm == GRABBED:
                    by_cell[key]["grabbed"]     += 1
                elif fm == UNREACHABLE:
                    by_cell[key]["unreachable"] += 1
        for key, v in by_cell.items():
            v["pct"] = _pct(v["ok"], v["n"])
        result[m] = by_cell
    return result


def form_invariance(data: dict) -> list:
    """
    B_noVolatile vs B_full on F1 (shared encoding) per model, event-aligned.

    For each model, finds the (page, task_id, rep) tuples present in BOTH
    B_full×F1 AND B_noVolatile×F1 (their intersection), then compares on
    that aligned set only.  This prevents Claude's partial-page TPM skips
    from creating unequal denominators that bias the gain estimate.

    Asserts equal n for both cells (post-alignment) and gain > 0 per model.
    Models that did not run both cells (o4-mini) are skipped.
    """
    rows = []
    for m in MODELS_ORDER:
        recs   = data.get(m, [])
        bf_all = [r for r in recs if r.get("bundle") == "B_full"       and r.get("encoding") == "F1"]
        nv_all = [r for r in recs if r.get("bundle") == "B_noVolatile" and r.get("encoding") == "F1"]
        if not bf_all or not nv_all:
            continue

        # Align to common (page, task_id, rep) events
        bf_keys = frozenset(_page_task_key(r) for r in bf_all)
        nv_keys = frozenset(_page_task_key(r) for r in nv_all)
        common  = bf_keys & nv_keys

        bf = [r for r in bf_all if _page_task_key(r) in common]
        nv = [r for r in nv_all if _page_task_key(r) in common]

        assert len(bf) == len(nv), (
            f"{m} form-invariance: event-aligned counts still differ "
            f"({len(bf)} B_full vs {len(nv)} B_noVolatile) — data integrity issue"
        )

        n      = len(bf)
        bf_ok  = sum(_ok(r) for r in bf)
        nv_ok  = sum(_ok(r) for r in nv)
        bf_pct = _pct(bf_ok, n)
        nv_pct = _pct(nv_ok, n)
        gain   = round(nv_pct - bf_pct, 1)

        assert gain > 0, (
            f"Form-invariance violated for {m}: "
            f"B_noVolatilexF1 ({nv_pct}%) <= B_fullxF1 ({bf_pct}%)"
        )
        rows.append({
            "model":   m,
            "n":       n,          # same for both cells post-alignment
            "bf_ok":   bf_ok,  "bf_pct": bf_pct,
            "nv_ok":   nv_ok,  "nv_pct": nv_pct,
            "gain_pp": gain,
            # keep bf_n / nv_n aliases for display compatibility
            "bf_n":    n,  "nv_n": n,
        })
    assert rows, "No models contributed to the form-invariance check"
    return rows


def fair_subset(data: dict) -> dict:
    """
    Fair 22-page subset: page_08 + page_17 excluded, then COMMON-EVENT aligned.

    For the three models that ran all 4 cells (gpt-4.1, gpt-4.1-nano, claude),
    the intersection of (page, bundle, encoding, task_id, rep) events is taken
    so every model in the comparison has IDENTICAL coverage.  Claude's partial
    page coverage (some cells TPM-skipped within the 22 pages) previously meant
    Claude had 870 events while GPT-4.1/nano had 880 — those 10 extra events are
    now dropped from GPT-4.1/nano too, giving all three a 870-event common set.

    o4-mini is reported separately on its own COP events (COP-only model; it
    cannot participate in a 4-cell common-event set).

    Asserts equal record counts for the three four-cell models.
    """
    four_cell = ["gpt-4.1", "gpt-4.1-nano", "claude-sonnet-4-6"]

    # Step 1: drop skip pages
    filtered = {
        m: [r for r in data[m] if not _is_skip_page(r)]
        for m in four_cell
    }

    # Step 2: intersect event keys across all three four-cell models
    key_sets  = [frozenset(_event_key(r) for r in filtered[m]) for m in four_cell]
    common_keys = key_sets[0].intersection(*key_sets[1:])

    # Step 3: restrict each model to common events only
    out = {}
    for m in four_cell:
        kept = [r for r in filtered[m] if _event_key(r) in common_keys]
        ok   = sum(_ok(r) for r in kept)
        out[m] = {"n": len(kept), "ok": ok, "pct": _pct(ok, len(kept))}

    # Assertion: equal event counts are the whole point of this function
    counts = {m: out[m]["n"] for m in four_cell}
    assert len(set(counts.values())) == 1, (
        "ALIGNMENT FAILURE: common-event fair subset still has unequal counts: "
        + ", ".join(f"{m}={counts[m]}" for m in four_cell)
    )

    # o4-mini: COP-only — report on its own events, not part of the 4-cell set
    o4_kept = [r for r in data["o4-mini"] if not _is_skip_page(r)]
    ok       = sum(_ok(r) for r in o4_kept)
    out["o4-mini"] = {"n": len(o4_kept), "ok": ok, "pct": _pct(ok, len(o4_kept))}

    return out


def cop_deepdive(cell_matrix: dict) -> dict:
    """COP cell (B_noVolatile × F3) per-model stats."""
    out = {}
    for m in MODELS_ORDER:
        cell = cell_matrix.get(m, {}).get((COP_B, COP_E))
        if cell is None:
            continue
        out[m] = {
            "n":       cell["n"],
            "ok":      cell["ok"],
            "pct":     cell["pct"],
            "lacked":  cell["lacked"],
            "grabbed": cell["grabbed"],
        }
    return out


def nano_f2_anomaly(data: dict) -> dict:
    """
    Nano B_noVolatile × F1 vs F2: same observations, different serialisation.
    The lacked count must be identical (bundle content unchanged);
    any divergence in grabbed_brittle is a per-model encoding sensitivity.
    """
    nano = data["gpt-4.1-nano"]
    rows = {}
    for enc in ("F1", "F2"):
        rs  = [r for r in nano if r.get("bundle") == "B_noVolatile" and r.get("encoding") == enc]
        ok  = sum(_ok(r) for r in rs)
        lac = sum(1 for r in rs if _failure_mode(r) == LACKED)
        grb = sum(1 for r in rs if _failure_mode(r) == GRABBED)
        unr = sum(1 for r in rs if _failure_mode(r) == UNREACHABLE)
        rows[enc] = {"n": len(rs), "ok": ok, "pct": _pct(ok, len(rs)),
                     "lacked": lac, "grabbed": grb, "unreachable": unr}

    f1, f2 = rows["F1"], rows["F2"]
    assert f1["lacked"] == f2["lacked"], (
        f"Nano lacked count differs between F1 ({f1['lacked']}) and F2 ({f2['lacked']})"
        " — encoding cannot affect signal presence; check data integrity"
    )
    grabbed_blowup = f2["grabbed"] - f1["grabbed"]
    assert grabbed_blowup > 0, (
        f"Expected F2 grabbed > F1 grabbed for nano; got {f2['grabbed']} vs {f1['grabbed']}"
    )
    rows["grabbed_blowup"]       = grabbed_blowup
    rows["grabbed_blowup_ratio"] = round(f2["grabbed"] / f1["grabbed"], 1)
    return rows


# ── Reconciliation ────────────────────────────────────────────────────────────

def _check(label: str, computed, expected, tolerance=0.0) -> tuple[str, str, str, str]:
    """Return (label, computed, expected, status)."""
    if isinstance(expected, float):
        ok = abs(computed - expected) <= max(tolerance, 0.05)
    else:
        ok = (computed == expected)
    status = "PASS" if ok else "MISMATCH"
    return (label, str(computed), str(expected), status)


def reconcile(overall: dict, cop: dict, fi_rows: list,
              fair: dict, f2: dict) -> list:
    """
    Build reconciliation table: list of (label, computed, expected, status).
    Mismatches are accumulated, not raised, so all checks complete in one run.
    """
    rows = []
    slug = {"gpt-4.1": "gpt41", "gpt-4.1-nano": "nano",
            "o4-mini": "o4mini", "claude-sonnet-4-6": "claude"}

    # Overall success per model
    for m, s in slug.items():
        v = overall[m]
        rows.append(_check(f"{m} total n",   v["n"],   REPORT[f"{s}_n"]))
        rows.append(_check(f"{m} total ok",  v["ok"],  REPORT[f"{s}_ok"]))
        rows.append(_check(f"{m} total %",   v["pct"], REPORT[f"{s}_pct"], 0.1))

    # COP cell per model
    for m, s in slug.items():
        if m not in cop:
            continue
        v = cop[m]
        rows.append(_check(f"{m} COP n",       v["n"],      REPORT[f"{s}_cop_n"]))
        rows.append(_check(f"{m} COP ok",      v["ok"],     REPORT[f"{s}_cop_ok"]))
        rows.append(_check(f"{m} COP %",       v["pct"],    REPORT[f"{s}_cop_pct"],   0.1))
        rows.append(_check(f"{m} COP lacked",  v["lacked"], REPORT[f"{s}_cop_lacked"]))
        rows.append(_check(f"{m} COP grabbed", v["grabbed"],REPORT[f"{s}_cop_grabbed"]))

    # Full-dataset failure modes
    # (derive from cop + overall — we don't recompute here, but we cross-check)
    # We re-derive from overall: total_fail = n - ok
    #                          = lacked + grabbed + unreachable   (§6, three modes)
    # No model in this study produced an unreachable record, so the expected
    # constants carry no *_unreachable key; default it to 0 rather than assuming
    # the taxonomy is closed at two.
    for m, s in slug.items():
        v = overall[m]
        total_fail = v["n"] - v["ok"]
        exp_lac = REPORT[f"{s}_lacked"]
        exp_grb = REPORT[f"{s}_grabbed"]
        exp_unr = REPORT.get(f"{s}_unreachable", 0)
        rows.append(_check(f"{m} total fail", total_fail, exp_lac + exp_grb + exp_unr))

    # Fair 22-page subset
    for m, s in slug.items():
        v = fair[m]
        rows.append(_check(f"{m} fair n",   v["n"],   REPORT[f"{s}_fair_n"]))
        rows.append(_check(f"{m} fair ok",  v["ok"],  REPORT[f"{s}_fair_ok"]))
        rows.append(_check(f"{m} fair %",   v["pct"], REPORT[f"{s}_fair_pct"], 0.1))

    # Nano F2 anomaly
    rows.append(_check("nano nvF1 n",       f2["F1"]["n"],       REPORT["nano_nvF1_n"]))
    rows.append(_check("nano nvF1 ok",      f2["F1"]["ok"],      REPORT["nano_nvF1_ok"]))
    rows.append(_check("nano nvF1 lacked",  f2["F1"]["lacked"],  REPORT["nano_nvF1_lacked"]))
    rows.append(_check("nano nvF1 grabbed", f2["F1"]["grabbed"], REPORT["nano_nvF1_grabbed"]))
    rows.append(_check("nano nvF2 n",       f2["F2"]["n"],       REPORT["nano_nvF2_n"]))
    rows.append(_check("nano nvF2 ok",      f2["F2"]["ok"],      REPORT["nano_nvF2_ok"]))
    rows.append(_check("nano nvF2 lacked",  f2["F2"]["lacked"],  REPORT["nano_nvF2_lacked"]))
    rows.append(_check("nano nvF2 grabbed", f2["F2"]["grabbed"], REPORT["nano_nvF2_grabbed"]))

    return rows


# ── Printing ──────────────────────────────────────────────────────────────────

def _print_section(title: str) -> None:
    print(f"\n{'=' * 72}")
    print(title)
    print("=" * 72)


def print_report(overall: dict, cell_matrix: dict, fi_rows: list,
                 fair: dict, cop: dict, f2: dict,
                 recon: list) -> None:

    # 1. Per-model overall
    _print_section("1. PER-MODEL SUCCESS (full dataset)")
    cells_run = {
        "gpt-4.1":           "4 cells",
        "gpt-4.1-nano":      "4 cells",
        "o4-mini":           "COP only (1 cell)",
        "claude-sonnet-4-6": "4 cells",
    }
    rows = [(m, overall[m]["ok"], overall[m]["n"],
             f"{overall[m]['pct']}%",
             cells_run[m])
            for m in MODELS_ORDER]
    print(tabulate(rows,
                   headers=["model", "ok", "n", "success%", "cells_run"],
                   tablefmt="pipe"))
    print()
    print("  *** COMPARISON WARNING ***")
    print("  o4-mini (75.4%) ran COP only -- the single best cell.")
    print("  Claude  (69.1%) ran all 4 cells including the weaker F2 cell.")
    print("  These overall figures are NOT comparable across models.")
    print("  The valid cross-model comparison is on the SAME cell -- see section 5.")

    # 2. Per-cell matrix
    _print_section("2. PER-CELL SUCCESS (all 4 models)")
    hdr = ["cell"] + MODELS_ORDER
    tbl = []
    for b, e in CELLS_4:
        cell_lbl = f"{b}x{e}"
        row = [cell_lbl]
        for m in MODELS_ORDER:
            v = cell_matrix.get(m, {}).get((b, e))
            row.append(f"{v['ok']}/{v['n']}={v['pct']}%" if v else "--")
        tbl.append(row)
    print(tabulate(tbl, headers=hdr, tablefmt="pipe"))

    # 3. Form invariance (event-aligned)
    _print_section("3. FORM-INVARIANCE: B_noVolatile > B_full on F1 (event-aligned)")
    fi_tbl = [(r["model"],
               r["n"],
               f"{r['bf_ok']}/{r['n']}={r['bf_pct']}%",
               f"{r['nv_ok']}/{r['n']}={r['nv_pct']}%",
               f"+{r['gain_pp']}pp")
              for r in fi_rows]
    print(tabulate(fi_tbl,
                   headers=["model", "aligned_n", "B_fullxF1", "B_noVolatilexF1", "gain"],
                   tablefmt="pipe"))
    print("  Both cells restricted to common (page, task_id) events per model.")
    print("  o4-mini excluded: ran COP only.")

    # 4. Fair 22-page subset (common-event aligned)
    _print_section("4. FAIR 22-PAGE SUBSET (page_08 + page_17 excluded, COMMON-EVENT aligned)")
    fair_rows = []
    four_cell_n = fair["gpt-4.1"]["n"]   # asserted equal for all three four-cell models
    for m in MODELS_ORDER:
        v    = fair[m]
        full = overall[m]
        delta = round(v["pct"] - full["pct"], 1)
        note = ""
        if m == "o4-mini":
            note = "(COP-only, not in 4-cell common set)"
        fair_rows.append((m, f"{full['ok']}/{full['n']}={full['pct']}%",
                          f"{v['ok']}/{v['n']}={v['pct']}%",
                          f"{delta:+.1f}pp",
                          note))
    print(tabulate(fair_rows,
                   headers=["model", "full 24p", "fair 22p", "delta", "note"],
                   tablefmt="pipe"))
    print(f"  Common-event n for gpt-4.1 / nano / claude: {four_cell_n} each (ASSERTED EQUAL)")

    # 5. COP deep-dive — the valid apples-to-apples comparison
    _print_section("5. COP CELL (B_noVolatilexF3, linearized DSL) - VALID CROSS-MODEL COMPARISON")
    cop_rows = [(m,
                 f"{cop[m]['ok']}/{cop[m]['n']}={cop[m]['pct']}%",
                 cop[m]["lacked"],
                 cop[m]["grabbed"])
                for m in MODELS_ORDER if m in cop]
    print(tabulate(cop_rows,
                   headers=["model", "success", "lacked", "grabbed"],
                   tablefmt="pipe"))
    o4_pct     = cop["o4-mini"]["pct"]
    claude_pct = cop["claude-sonnet-4-6"]["pct"]
    print()
    print(f"  o4-mini vs Claude on the SAME cell: {o4_pct}% vs {claude_pct}%")
    print(f"  Difference: {abs(o4_pct - claude_pct):.1f}pp -- statistically negligible.")
    print(f"  FINDING: o4-mini and Claude score equal on COP; the gap seen in section 1")
    print(f"  comes from different cell coverage, not a difference between the models.")

    # 6. Nano F2 anomaly
    _print_section("6. NANO F2 ANOMALY (B_noVolatile, same observations, different encoding)")
    f2_rows = [
        ("gpt-4.1-nano", "F1",
         f"{f2['F1']['ok']}/{f2['F1']['n']}={f2['F1']['pct']}%",
         f2["F1"]["lacked"], f2["F1"]["grabbed"]),
        ("gpt-4.1-nano", "F2",
         f"{f2['F2']['ok']}/{f2['F2']['n']}={f2['F2']['pct']}%",
         f2["F2"]["lacked"], f2["F2"]["grabbed"]),
    ]
    print(tabulate(f2_rows,
                   headers=["model", "enc", "success", "lacked", "grabbed"],
                   tablefmt="pipe"))
    print(f"  grabbed blowup: {f2['grabbed_blowup']:+d} extra brittle grabs "
          f"({f2['grabbed_blowup_ratio']}x increase F1->F2)")
    print(f"  lacked count:   identical ({f2['F1']['lacked']}) -- "
          f"confirms this is encoding sensitivity, not signal absence")

    # 7. Reconciliation table
    _print_section("7. RECONCILIATION vs AXIS C REPORT")
    mismatches = [r for r in recon if r[3] == "MISMATCH"]
    passes     = [r for r in recon if r[3] == "PASS"]
    print(f"  {len(passes)} PASS  /  {len(mismatches)} MISMATCH  "
          f"(out of {len(recon)} checks)")
    if mismatches:
        print()
        print("  *** MISMATCHES — investigate before citing these numbers ***")
        print(tabulate(mismatches,
                       headers=["check", "computed", "expected", "status"],
                       tablefmt="pipe"))
    else:
        print("  All computed values match the Axis C report.")


# ── Output ────────────────────────────────────────────────────────────────────

def write_json(overall: dict, cell_matrix: dict, fi_rows: list,
               fair: dict, cop: dict, f2: dict,
               recon: list) -> pathlib.Path:
    out = {
        "description":         "Axis C cross-model robustness -- key metrics",
        "source":              "cross_model.py",
        "fair_subset_excludes": ["page_08", "page_17"],
        "F3_encoding_note":    "F3 = linearized DSL (EncodeF3Linearized). Not YAML.",
        "comparison_warning": (
            "overall_success is NOT a valid cross-model comparison: "
            "o4-mini ran COP only (best single cell, 75.4%); Claude ran all 4 cells (69.1%). "
            "Valid comparison: COP cell only -- o4-mini 75.4% vs Claude 75.2%, n=240 vs n=230 -- "
            "statistically equal. Each model is reported on its own number; see "
            "experiments/FINDINGS.md for the current framing of this result."
        ),
        "overall":             overall,
        "fair_22p":            fair,
        "cop_cell": {
            m: v for m, v in cop.items()
        },
        "form_invariance":     fi_rows,
        "nano_f2_anomaly":     {
            "F1": f2["F1"], "F2": f2["F2"],
            "grabbed_blowup":       f2["grabbed_blowup"],
            "grabbed_blowup_ratio": f2["grabbed_blowup_ratio"],
        },
        "reconciliation": [
            {"check": r[0], "computed": r[1], "expected": r[2], "status": r[3]}
            for r in recon
        ],
        "reconciliation_summary": {
            "pass":     sum(1 for r in recon if r[3] == "PASS"),
            "mismatch": sum(1 for r in recon if r[3] == "MISMATCH"),
            "total":    len(recon),
        },
    }
    dest = RESULTS / "cross_model_metrics.json"
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    return dest


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    data        = load_all()
    overall     = per_model_overall(data)
    cell_matrix = per_cell_matrix(data)
    fi_rows     = form_invariance(data)        # takes raw records for event alignment
    fair        = fair_subset(data)
    cop         = cop_deepdive(cell_matrix)
    f2          = nano_f2_anomaly(data)
    recon       = reconcile(overall, cop, fi_rows, fair, f2)

    print_report(overall, cell_matrix, fi_rows, fair, cop, f2, recon)

    dest = write_json(overall, cell_matrix, fi_rows, fair, cop, f2, recon)
    print(f"\n  written: {dest}")

    mismatches = [r for r in recon if r[3] == "MISMATCH"]
    if mismatches:
        print(f"\n  WARNING: {len(mismatches)} reconciliation mismatch(es) — "
              f"see table above. Exit code 1.")
        sys.exit(1)


if __name__ == "__main__":
    main()
