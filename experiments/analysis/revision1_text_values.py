"""
Values quoted in the revised manuscript text that no other script writes. Shipped records and
testbed files only; zero LLM, zero network, no browser.

  - Table 1 and ¶51–52: page counts per shadow level, semantic density, size tier and framework
    fingerprint, and fingerprint × density (shared/testbed/pages/*.truth.json).
  - ¶74: text fields truncated by the DOM walk in the B_full × F1 observation dumps
    (results/revision1/observations/, the 24 page_*__B_full__F1.txt files), and their element tags.
    Length is counted in UTF-16 code units, as the walk truncates in JavaScript
    (shared/harness/Observation.cs:34: rawText.length > 300 ? rawText.slice(0, 300) + '…'); a field is
    truncated when it ends in "…" after exactly 300 code units.
  - ¶141: Δ success B_noVolatile − B_full on LOW pages per fingerprint, paired F0–F3 events of the
    gpt-4.1 corpus; React also without page_21.
  - ¶149: Δ success F2 − F1 under B_noVolatile on LOW pages.
  - ¶160: the 240 B_playwrightMCP × F4 events: failures by mode, grabbed failures with the
    unique-match condition false, and grabbed subtypes in the priority order of
    revision1_diagnostics.py (volatile → positional → invalid cross-shadow syntax → non-unique →
    wrong element).
  - ¶168: token saving of F3 vs F1 under B_noVolatile. Per page: 1 − mean F3 / mean F1
    observation tokens. Tier saving: the mean of the per-page savings within each size tier.
    Spearman ρ between page size (mean F1 observation tokens per page under B_noVolatile) and the
    per-page saving.
  - ¶173: claude-sonnet-4-6 B_noVolatile × F2 successes, and all Claude records.
  - Shadow-root targets: targets whose truth.json entry has `in_shadow` (S1 or S2), of the 240.
  - Claude coverage: the (page, cell) pairs of the four Claude cells with no record, and the same set
    derived from the guard rule (experiments/modes/AxisCMode.cs:32: a Claude cell is skipped when the
    largest gpt-4.1 observation of that page and cell exceeds 75,000 tokens).

Every value is checked against the manuscript; a mismatch stops the script before an output is
written. Outputs: experiments/results/revision1/revision1_text_values.{md,json}
Run: python -B experiments/analysis/revision1_text_values.py
"""
import collections
import json
import pathlib
import re
import sys

from scipy.stats import spearmanr

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from revision1_diagnostics import (OUT_DIR, RUNS, TRUTH_DIR, GRABBED, LACKED, jsonable,  # noqa: E402
                                   md_table, protected_state)

OUT_PREFIX = OUT_DIR / "revision1_text_values"
OBS_DIR = OUT_DIR / "observations"
DOM_ENCODINGS = ("F0", "F1", "F2", "F3")
FINGERPRINTS = {"R": "React", "A": "Angular", "V": "Vue"}
TIERS = ("standard", "large", "extreme")
TRUNCATE_AT = 300
TPM_GUARD = 75_000
CLAUDE_CELLS = (("B_full", "F1"), ("B_noVolatile", "F1"), ("B_noVolatile", "F2"), ("B_noVolatile", "F3"))
# Same pattern as the grabbed-subtype breakdown in revision1_diagnostics.py.
SHADOW_RE = re.compile(r'\[\s*(?:data-shadow|is_shadow|sh)\s*(?:[~|^$*]?=|\])|\[S\]|>>>|/deep/|::shadow', re.I)


class Controls:
    def __init__(self):
        self.rows, self.failed = [], 0

    def check(self, item, got, expected):
        ok = got == expected
        self.failed += not ok
        self.rows.append((item, got, expected, "MATCH" if ok else "MISMATCH"))


def page_of(r):
    return pathlib.PurePosixPath(r["page"]).stem


def load_jsonl(pattern):
    return [json.loads(line) for f in sorted(RUNS.glob(pattern)) for line in f.open(encoding="utf-8")]


def load_truth():
    truth = {}
    for f in sorted(TRUTH_DIR.glob("page_*.truth.json")):
        t = json.loads(f.read_text(encoding="utf-8"))
        truth[t["page_id"]] = t
    assert len(truth) == 24
    return truth


def rate(rs):
    return 100.0 * sum(bool(r["success"]) for r in rs) / len(rs)


def utf16_len(s):
    return len(s.encode("utf-16-le")) // 2


def table1(truth):
    c = collections.Counter
    return {
        "shadow": dict(sorted(c(t["shadow"] for t in truth.values()).items())),
        "semantic_density": dict(sorted(c(t["semantic_density"] for t in truth.values()).items())),
        "size_tier": {k: c(t["size_tier"] for t in truth.values())[k] for k in TIERS},
        "fingerprint": {FINGERPRINTS[k]: v for k, v in sorted(c(t["fingerprint_variant"] for t in truth.values()).items())},
        "fingerprint_low": {FINGERPRINTS[k]: sum(1 for t in truth.values() if t["fingerprint_variant"] == k
                                                 and t["semantic_density"] == "low") for k in FINGERPRINTS},
    }


def truncated_fields(truth):
    per_page, tags = {}, collections.Counter()
    for page in sorted(truth):
        items = json.loads((OBS_DIR / f"{page}__B_full__F1.txt").read_text(encoding="utf-8"))
        hits = [el for el in items for v in el.values()
                if isinstance(v, str) and v.endswith("…") and utf16_len(v[:-1]) == TRUNCATE_AT]
        per_page[page] = len(hits)
        tags.update(el["tag"] for el in hits)
    return {"per_page": per_page, "tags": dict(tags.most_common())}


def fingerprint_gains(corpus, truth):
    dom = [r for r in corpus if r["encoding"] in DOM_ENCODINGS]
    out = {}
    for code, name in FINGERPRINTS.items():
        pages = {p for p, t in truth.items() if t["fingerprint_variant"] == code and t["semantic_density"] == "low"}
        for label, keep in (("all", pages), ("without page_21", pages - {"page_21"})):
            if label != "all" and keep == pages:
                continue
            arm = {b: [r for r in dom if page_of(r) in keep and r["bundle"] == b] for b in ("B_full", "B_noVolatile")}
            out[f"{name} ({label})"] = {"pages": len(keep), "events_per_bundle": len(arm["B_full"]),
                                        "delta_pp": rate(arm["B_noVolatile"]) - rate(arm["B_full"])}
    p21 = {b: [r for r in dom if page_of(r) == "page_21" and r["bundle"] == b] for b in ("B_full", "B_noVolatile")}
    out["page_21"] = {"pages": 1, "events_per_bundle": len(p21["B_full"]),
                      "delta_pp": rate(p21["B_noVolatile"]) - rate(p21["B_full"])}
    return out


def low_f2_drop(corpus, truth):
    low = {p for p, t in truth.items() if t["semantic_density"] == "low"}
    arm = {e: [r for r in corpus if r["bundle"] == "B_noVolatile" and r["encoding"] == e and page_of(r) in low]
           for e in ("F1", "F2")}
    return {"events_per_encoding": len(arm["F1"]), "F1_pct": rate(arm["F1"]), "F2_pct": rate(arm["F2"]),
            "delta_pp": rate(arm["F2"]) - rate(arm["F1"])}


def subtype(r):
    if not r["predicate_non_volatile"]:
        return "volatile"
    if not r["predicate_non_positional"]:
        return "positional"
    if SHADOW_RE.search(r["locator_value"] or ""):
        return "invalid cross-shadow syntax"
    if not r["predicate_unique_match"]:
        return "non-unique"
    if not r["predicate_matches_oracle"]:
        return "wrong element"
    return "residual"


def f4_failures(corpus):
    f4 = [r for r in corpus if r["bundle"] == "B_playwrightMCP" and r["encoding"] == "F4"]
    fails = [r for r in f4 if not r["success"]]
    grabbed = [r for r in fails if r["failure_mode"] == GRABBED]
    order = ["volatile", "positional", "invalid cross-shadow syntax", "non-unique", "wrong element"]
    sub = collections.Counter(subtype(r) for r in grabbed)
    assert sub["residual"] == 0
    return {"events": len(f4), "failures": len(fails),
            "lacked": sum(r["failure_mode"] == LACKED for r in fails), "grabbed": len(grabbed),
            "grabbed_not_unique": sum(not r["predicate_unique_match"] for r in grabbed),
            "grabbed_primary_subtype": {k: sub[k] for k in order}}


def f3_savings(corpus, truth):
    tok = collections.defaultdict(list)
    for r in corpus:
        if r["bundle"] == "B_noVolatile" and r["encoding"] in ("F1", "F3"):
            tok[(page_of(r), r["encoding"])].append(r["observation_tokens"])
    mean = lambda xs: sum(xs) / len(xs)
    pages = sorted(truth)
    f1 = {p: mean(tok[(p, "F1")]) for p in pages}
    per_page = {p: 100.0 * (1 - mean(tok[(p, "F3")]) / f1[p]) for p in pages}
    tiers = {t: {"pages": sum(truth[p]["size_tier"] == t for p in pages),
                 "mean_saving_pct": mean([per_page[p] for p in pages if truth[p]["size_tier"] == t])} for t in TIERS}
    rho, p_value = spearmanr([f1[p] for p in pages], [per_page[p] for p in pages])
    lo, hi = min(per_page, key=per_page.get), max(per_page, key=per_page.get)
    return {"per_page_pct": per_page, "f1_mean_tokens": f1, "tiers": tiers,
            "min": {"page": lo, "pct": per_page[lo]}, "max": {"page": hi, "pct": per_page[hi]},
            "spearman_rho": float(rho), "spearman_p": float(p_value)}


def claude(claude_recs):
    cell = [r for r in claude_recs if r["bundle"] == "B_noVolatile" and r["encoding"] == "F2"]
    return {"nv_f2_success": sum(bool(r["success"]) for r in cell), "nv_f2_events": len(cell),
            "nv_f2_pct": rate(cell), "all_success": sum(bool(r["success"]) for r in claude_recs),
            "all_events": len(claude_recs)}


def shadow_targets(truth):
    depth = collections.Counter(tg.get("in_shadow", "none") for t in truth.values() for tg in t["targets"])
    total = sum(depth.values())
    inside = total - depth["none"]
    return {"targets": total, "in_shadow": inside, "pct": 100.0 * inside / total,
            "by_depth": {k: depth[k] for k in ("none", "S1", "S2")}}


def claude_coverage(corpus, claude_recs, truth):
    planned = [(p, b, e) for p in sorted(truth) for b, e in CLAUDE_CELLS]
    present = {(page_of(r), r["bundle"], r["encoding"]) for r in claude_recs}
    max_obs = collections.defaultdict(int)
    for r in corpus:
        key = (page_of(r), r["bundle"], r["encoding"])
        max_obs[key] = max(max_obs[key], r["observation_tokens"])
    skipped = [c for c in planned if c not in present]
    over_guard = [c for c in planned if max_obs[c] > TPM_GUARD]
    return {"planned_cells": len(planned), "skipped": [f"{p} {b} × {e}" for p, b, e in skipped],
            "skipped_per_page": dict(sorted(collections.Counter(p for p, _, _ in skipped).items())),
            "over_guard": [f"{p} {b} × {e}" for p, b, e in over_guard],
            "max_obs_tokens": {f"{p} {b} × {e}": max_obs[(p, b, e)] for p, b, e in skipped}}


def run_controls(res):
    ctl = Controls()
    t1 = res["table1"]
    ctl.check("Table 1 shadow S0/S1/S2", [t1["shadow"][k] for k in ("S0", "S1", "S2")], [8, 8, 8])
    ctl.check("Table 1 density HIGH/LOW", [t1["semantic_density"][k] for k in ("high", "low")], [12, 12])
    ctl.check("Table 1 size standard/large/extreme", [t1["size_tier"][k] for k in TIERS], [16, 6, 2])
    ctl.check("Table 1 fingerprint React/Angular/Vue", [t1["fingerprint"][k] for k in ("React", "Angular", "Vue")],
              [8, 8, 8])
    ctl.check("¶51 LOW pages React/Angular/Vue", [t1["fingerprint_low"][k] for k in ("React", "Angular", "Vue")],
              [6, 3, 3])
    tr, tags = res["truncated_fields"]["per_page"], res["truncated_fields"]["tags"]
    ctl.check("¶74 truncated fields", sum(tr.values()), 302)
    ctl.check("¶74 pages with a truncated field", sum(v > 0 for v in tr.values()), 24)
    ctl.check("¶74 div + article are the majority", tags.get("div", 0) + tags.get("article", 0) > sum(tr.values()) / 2,
              True)
    g = res["fingerprint_gains"]
    ctl.check("¶141 React LOW Δ pp", f"{g['React (all)']['delta_pp']:+.2f}", "+20.42")
    ctl.check("¶141 React LOW without page_21 Δ pp", f"{g['React (without page_21)']['delta_pp']:+.2f}", "+11.50")
    ctl.check("¶141 Vue LOW Δ pp", f"{g['Vue (all)']['delta_pp']:+.2f}", "+10.83")
    ctl.check("¶141 Angular LOW Δ pp", f"{g['Angular (all)']['delta_pp']:+.2f}", "+8.33")
    ctl.check("¶141 page_21 Δ pp", f"{g['page_21']['delta_pp']:+.1f}", "+65.0")
    ctl.check("¶149 LOW B_noVolatile F2 − F1 pp", f"{res['low_f2']['delta_pp']:+.2f}", "-15.00")
    f4 = res["f4_failures"]
    ctl.check("¶160 F4 failures / lacked / grabbed", [f4["failures"], f4["lacked"], f4["grabbed"]], [127, 48, 79])
    ctl.check("¶160 grabbed with unique match false", f4["grabbed_not_unique"], 75)
    ctl.check("¶160 grabbed, non-unique by priority", f4["grabbed_primary_subtype"]["non-unique"], 65)
    s = res["f3_savings"]
    ctl.check("¶168 tier savings %", [f"{s['tiers'][t]['mean_saving_pct']:.1f}" for t in TIERS], ["31.5", "31.4", "27.5"])
    ctl.check("¶168 lowest per-page saving", (s["min"]["page"], f"{s['min']['pct']:.1f}"), ("page_23", "21.8"))
    ctl.check("¶168 highest per-page saving", (s["max"]["page"], f"{s['max']['pct']:.1f}"), ("page_15", "37.6"))
    ctl.check("¶168 Spearman ρ, p", (f"{s['spearman_rho']:.2f}", f"{s['spearman_p']:.2f}"), ("-0.30", "0.15"))
    c = res["claude"]
    ctl.check("¶173 Claude B_noVolatile × F2", (c["nv_f2_success"], c["nv_f2_events"], f"{c['nv_f2_pct']:.2f}"),
              (116, 220, "52.73"))
    ctl.check("¶173 Claude all cells", (c["all_success"], c["all_events"]), (608, 880))
    sh = res["shadow_targets"]
    ctl.check("Targets inside shadow roots", (sh["in_shadow"], sh["targets"], f"{sh['pct']:.1f}"), (76, 240, "31.7"))
    cc = res["claude_coverage"]
    ctl.check("Claude cells skipped", (len(cc["skipped"]), cc["planned_cells"]), (8, 96))
    ctl.check("Claude cells skipped per page", cc["skipped_per_page"], {"page_08": 3, "page_17": 4, "page_18": 1})
    ctl.check("Claude skipped cells = cells over the 75,000-token guard", cc["skipped"] == cc["over_guard"], True)
    return ctl


def render(res, ctl) -> str:
    L = ["# Text values of the revised manuscript", "",
         "Recomputed from shipped files only (gpt-4.1 corpus `experiments/runs/matrix_page_*.jsonl`, Claude records "
         "`experiments/runs/axisc_claude-sonnet-4-6_page_*.jsonl`, `shared/testbed/pages/*.truth.json`, and the "
         "B_full × F1 observation dumps in `experiments/results/revision1/observations/`). Zero LLM calls, zero network. "
         "Generated by `python -B experiments/analysis/revision1_text_values.py`.", "",
         "## Checks against the manuscript", ""]
    L += md_table(["item", "recomputed", "manuscript", "result"], ctl.rows)
    t1 = res["table1"]
    L += ["", "## Table 1 and ¶51–52 — testbed composition", ""]
    L += md_table(["dimension", "counts"], [(k, ", ".join(f"{a} {b}" for a, b in v.items())) for k, v in t1.items()])
    tr, tags = res["truncated_fields"]["per_page"], res["truncated_fields"]["tags"]
    total = sum(tr.values())
    L += ["", "## ¶74 — truncated text fields (B_full × F1)", "",
          f"The DOM walk cuts text longer than {TRUNCATE_AT} characters to {TRUNCATE_AT} and appends \"…\". It runs in "
          "JavaScript (`shared/harness/Observation.cs:34`), so length is counted in UTF-16 code units; the count here does the same. "
          f"Total {total} fields on {sum(v > 0 for v in tr.values())} of 24 pages.", ""]
    L += md_table(["element tag", "truncated fields", "share %"], [(k, v, f"{100 * v / total:.1f}") for k, v in tags.items()])
    L += [""]
    L += md_table(["page", "truncated fields"], sorted(tr.items()))
    L += ["", "## ¶141 — Δ success B_noVolatile − B_full on LOW pages, by fingerprint", "",
          "Paired F0–F3 events of the gpt-4.1 corpus (10 targets × 4 encodings per page and bundle).", ""]
    L += md_table(["subset", "pages", "events per bundle", "Δ pp"],
                  [(k, v["pages"], v["events_per_bundle"], f"{v['delta_pp']:+.2f}") for k, v in res["fingerprint_gains"].items()])
    lf = res["low_f2"]
    L += ["", "## ¶149 — F2 − F1 under B_noVolatile on LOW pages", "",
          f"{lf['events_per_encoding']} events per encoding: F1 {lf['F1_pct']:.2f}%, F2 {lf['F2_pct']:.2f}%, "
          f"Δ {lf['delta_pp']:+.2f} pp.", ""]
    f4 = res["f4_failures"]
    L += ["## ¶160 — B_playwrightMCP × F4 failures", "",
          f"{f4['events']} events, {f4['failures']} failures: {f4['lacked']} lacked, {f4['grabbed']} grabbed. "
          f"Grabbed with the unique-match condition false: {f4['grabbed_not_unique']}. "
          "Primary subtype of the grabbed failures, assigned in priority order (volatile → positional → invalid "
          "cross-shadow syntax → non-unique → wrong element):", ""]
    L += md_table(["subtype", "grabbed failures"], list(f4["grabbed_primary_subtype"].items()))
    s = res["f3_savings"]
    L += ["", "## ¶168 — F3 vs F1 token saving under B_noVolatile", "",
          "Per-page saving = 1 − (mean F3 observation tokens / mean F1 observation tokens) on that page. "
          "Tier saving = the mean of the per-page savings within the size tier. Spearman ρ between page size "
          "(mean F1 observation tokens per page) and the per-page saving, 24 pages.", ""]
    L += md_table(["size tier", "pages", "mean per-page saving %"],
                  [(t, v["pages"], f"{v['mean_saving_pct']:.2f}") for t, v in s["tiers"].items()])
    L += ["", f"Range: {s['min']['pct']:.2f}% ({s['min']['page']}) to {s['max']['pct']:.2f}% ({s['max']['page']}). "
              f"Spearman ρ = {s['spearman_rho']:.3f}, p = {s['spearman_p']:.3f}.", ""]
    L += md_table(["page", "F1 mean tokens", "F3 saving %"],
                  [(p, f"{s['f1_mean_tokens'][p]:.1f}", f"{v:.2f}") for p, v in s["per_page_pct"].items()])
    c = res["claude"]
    L += ["", "## ¶173 — claude-sonnet-4-6", "",
          f"B_noVolatile × F2: {c['nv_f2_success']}/{c['nv_f2_events']} ({c['nv_f2_pct']:.2f}%). "
          f"All four cells: {c['all_success']}/{c['all_events']}.", ""]
    sh = res["shadow_targets"]
    L += ["## Targets inside shadow roots", "",
          f"{sh['in_shadow']} of {sh['targets']} targets ({sh['pct']:.1f}%) have `in_shadow` in truth.json.", ""]
    L += md_table(["target depth", "targets"], list(sh["by_depth"].items()))
    cc = res["claude_coverage"]
    L += ["", "## claude-sonnet-4-6 coverage", "",
          f"{len(cc['skipped'])} of {cc['planned_cells']} (page, cell) pairs have no Claude record. They are exactly the "
          f"pairs whose largest gpt-4.1 observation exceeds {TPM_GUARD:,} tokens "
          "(`experiments/modes/AxisCMode.cs:32`).", ""]
    L += md_table(["page and cell", "largest gpt-4.1 observation tokens"], list(cc["max_obs_tokens"].items()))
    L += [""]
    return "\n".join(L)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    before = protected_state()
    truth = load_truth()
    corpus = load_jsonl("matrix_page_*.jsonl")
    assert len(corpus) == 6000
    claude_recs = load_jsonl("axisc_claude-sonnet-4-6_page_*.jsonl")
    res = {"table1": table1(truth), "truncated_fields": truncated_fields(truth),
           "fingerprint_gains": fingerprint_gains(corpus, truth), "low_f2": low_f2_drop(corpus, truth),
           "f4_failures": f4_failures(corpus), "f3_savings": f3_savings(corpus, truth), "claude": claude(claude_recs),
           "shadow_targets": shadow_targets(truth), "claude_coverage": claude_coverage(corpus, claude_recs, truth)}
    ctl = run_controls(res)
    for item, got, exp, verdict in ctl.rows:
        print(f"  {verdict:8} {item}: {got} (manuscript {exp})")
    if ctl.failed:
        print(f"{ctl.failed} value(s) do not reproduce; no output written.")
        return 1
    if protected_state() != before:
        raise SystemExit("[guard] evidence files changed during the run; no outputs written")
    res["checks"] = [{"item": i, "recomputed": g, "manuscript": e, "result": v} for i, g, e, v in ctl.rows]
    OUT_PREFIX.with_suffix(".json").write_text(json.dumps(jsonable(res), ensure_ascii=False, indent=1) + "\n",
                                               encoding="utf-8", newline="\n")
    OUT_PREFIX.with_suffix(".md").write_text(render(res, ctl) + "\n", encoding="utf-8", newline="\n")
    print(f"All {len(ctl.rows)} values match; wrote {OUT_PREFIX.name}.md / .json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
