"""
rp_cost.py — Step 4 of the real-site pilot preparation: cost estimate (no model calls).

Scope (pilot_analysis_plan.md addendum): all eligible sites, no rank cut.
- 4 primary cells (B_full, B_noVolatile × F1, F3) for every target;
- class_only × F1/F3 only where the site's class_only observation is not byte-identical (sha256) to its
  B_noVolatile observation; identical ones reuse the B_noVolatile result (no call).
Input tokens per call = CountTokens(SystemPrompt) + CountTokens(BuildUserPrompt(observation, task)), o200k_base
(shared/tokenizer), from the step-3 dump (observations/prompt_tokens.tsv). Upper bound per call at the gpt-4.1
list price: (input + CHAT_OVERHEAD) × $2.00/M + 256 output tokens × $8.00/M (max output tokens, LlmClient.cs).
Hard cap = upper bound × 1.10.

Run from the repository root:  python experiments/results/revision1/real_pilot/rp_cost.py
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import json
import math
import statistics
from collections import Counter, defaultdict

from rp_common import HERE, read_tsv

PRICE_IN, PRICE_OUT = 2.00, 8.00          # USD per 1M tokens, gpt-4.1 list price
MAX_OUT = 256                              # shared/harness/LlmClient.cs MaxTokens
CHAT_OVERHEAD = 16                         # assumed chat-format tokens per call (2 messages); stated, not measured
CAP_MARGIN = 1.10                          # hard cap = upper bound + 10%
LABEL = {"B_full": "B_full", "B_noVolatileConsistent": "B_noVolatile", "B_full_minus_volClass": "class_only"}
CELL_ORDER = [(b, e) for e in ("F1", "F3") for b in LABEL]
PRIMARY = {("B_full", "F1"), ("B_noVolatileConsistent", "F1"), ("B_full", "F3"), ("B_noVolatileConsistent", "F3")}


def call_cost(tokens):
    return (tokens + CHAT_OVERHEAD) * PRICE_IN / 1e6 + MAX_OUT * PRICE_OUT / 1e6


def plan():
    """The pilot's call plan: per (site, cell) whether it is called, reused or excluded."""
    el = json.loads((HERE / "eligibility.json").read_text(encoding="utf-8"))
    tg = json.loads((HERE / "targets.json").read_text(encoding="utf-8"))
    eligible = {s["domain"] for s in el["sites"] if s["eligible"]}
    man = {(r["site"], r["bundle"], r["encoding"]): r for r in read_tsv(HERE / "observations" / "manifest.tsv")}
    keys = {f"{t['rank']:04d}_{t['domain']}": (t["rank"], t["domain"]) for t in tg["items"]}
    status = {}
    for k, (_, d) in keys.items():
        for b, e in CELL_ORDER:
            if d not in eligible:
                status[(k, b, e)] = "excluded_site"
            elif (b, e) in PRIMARY:
                status[(k, b, e)] = "call"
            else:
                same = man[(k, b, e)]["sha256"] == man[(k, "B_noVolatileConsistent", e)]["sha256"]
                status[(k, b, e)] = "reuse_B_noVolatile" if same else "call"
    return el, tg, keys, status


def main():
    el, tg, keys, status = plan()
    rows = read_tsv(HERE / "observations" / "prompt_tokens.tsv")

    per_cell = defaultdict(list)
    per_site = defaultdict(lambda: {"calls": 0, "tokens": 0, "cost": 0.0})
    reused = Counter()
    for r in rows:
        st = status[(r["site"], r["bundle"], r["encoding"])]
        if st != "call":
            reused[st] += 1
            continue
        n = int(r["prompt_tokens"])
        per_cell[(r["bundle"], r["encoding"])].append(n)
        s = per_site[r["site"]]
        s["calls"] += 1; s["tokens"] += n; s["cost"] += call_cost(n)
    calls = sum(s["calls"] for s in per_site.values())
    tokens = sum(s["tokens"] for s in per_site.values())
    upper = sum(s["cost"] for s in per_site.values())
    cap = math.ceil(upper * CAP_MARGIN * 100) / 100
    eligible_items = [t for t in tg["items"] if status[(f"{t['rank']:04d}_{t['domain']}", "B_full", "F1")] == "call"]
    co_sites = {e: sorted(keys[k][1] for (k, b, enc), st in status.items()
                          if b == "B_full_minus_volClass" and enc == e and st == "call") for e in ("F1", "F3")}

    cost = {"price_in": PRICE_IN, "price_out": PRICE_OUT, "max_out": MAX_OUT, "chat_overhead": CHAT_OVERHEAD,
            "scope": "all eligible sites; 4 primary cells; class_only only where its observation != B_noVolatile",
            "eligible_sites": len({t["domain"] for t in eligible_items}), "targets": len(eligible_items),
            "class_only_called_sites": co_sites,
            "per_cell": {f"{LABEL[b]}|{e}": ({"calls": len(per_cell[(b, e)]), "min": min(per_cell[(b, e)]),
                                              "median": statistics.median(per_cell[(b, e)]),
                                              "max": max(per_cell[(b, e)]), "sum": sum(per_cell[(b, e)])}
                                             if per_cell[(b, e)] else {"calls": 0})
                         for b, e in CELL_ORDER},
            "not_called": dict(reused),
            "total": {"calls": calls, "input_tokens": tokens, "upper_bound_usd": round(upper, 2)},
            "hard_cap_usd": cap, "cap_margin": CAP_MARGIN}
    (HERE / "cost_estimate.json").write_text(json.dumps(cost, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(json.dumps(cost, indent=2))


if __name__ == "__main__":
    main()
