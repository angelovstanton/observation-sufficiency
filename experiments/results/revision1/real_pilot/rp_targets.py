"""
rp_targets.py — Step 2 of the real-site pilot preparation: targets.json (pilot_rule.md §3–§5, §7).

Reads the per-site state written by rp_eligibility.py (../_external/cc_cache/real_pilot/state.json)
and writes targets.json for the eligible sites. Marker ids t_01… follow the selection order (ascending
sha256 key). No network, no LLM, no browser.

Run from the repository root:  python experiments/results/revision1/real_pilot/rp_targets.py
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import json
from collections import Counter

from rp_common import HERE, RP_CACHE, committed

RULE = "experiments/results/revision1/real_pilot/pilot_rule.md"


def main():
    state = json.loads((RP_CACHE / "state.json").read_text(encoding="utf-8"))
    rule = committed(RULE)
    if rule["sha"] != state["rule_commit"]["sha"] or not rule["clean"]:
        raise SystemExit(f"[targets] pilot_rule.md changed since step 1: {rule} vs {state['rule_commit']}")
    sites = sorted((s for s in state["sites"] if s["eligible"]), key=lambda s: s["rank"])
    targets = []
    for s in sites:
        for i, t in enumerate(s["selected"], 1):
            targets.append({"domain": s["domain"], "rank": s["rank"], "marker": f"t_{i:02d}", "xpath": t["xpath"],
                            "role": t["role"], "name": t["name"], "task": t["task"], "stratum": t["stratum"],
                            "signal_attrs": t["signal_attrs"], "sha256_key": t["key"]})
    out = {"rule_commit": rule["sha"], "crawl": "CC-MAIN-2026-21", "sites": len(sites), "targets": len(targets),
           "by_stratum": dict(Counter(t["stratum"] for t in targets)), "items": targets}
    (HERE / "targets.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                                       newline="\n")
    print(f"[targets] {len(sites)} sites, {len(targets)} targets, {out['by_stratum']}")


if __name__ == "__main__":
    main()
