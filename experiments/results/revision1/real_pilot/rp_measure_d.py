"""
rp_measure_d.py — criterion (г) re-measured under the new observation protocol (pilot_rule.md addendum 2026-10-13,
"(г) under the new observation protocol"): every candidate excluded so far under (г) is dumped once through the
adapter's dump mode (each cell on a fresh load, RealPilotOffline.ObserveCellAsync, all markers of the site set),
and its largest-cell prompt is compared with the unchanged threshold (128,000 tokens). No model, no network.

Writes d_remeasure.json next to this file (sizes only, no page text). The observation texts are not written.
A site that passes is reported; (б) and (в) for it follow under the unchanged rules (rp_redump.py flow).

Run from the repository root:  python experiments/results/revision1/real_pilot/rp_measure_d.py
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import json

from rp_common import HERE, RP_CACHE, PROMPT_CAP, read_tsv, run_mode
from rp_eligibility import CELLS, preconditions


def main():
    rule, plan = preconditions()
    state = json.loads((RP_CACHE / "state.json").read_text(encoding="utf-8"))
    cands = sorted((s for s in state["sites"] if s["reason"].startswith("(г)")), key=lambda s: s["rank"])
    print(f"[(г)] {len(cands)} sites excluded under (г): {', '.join(s['domain'] for s in cands)}")
    payload = {"sites": [{"key": s["key"], "url": s["url"], "htmlPath": s["html_path"], "timestamp": s["timestamp"],
                          "volIds": s["vol_ids"], "volClasses": s["vol_classes"],
                          "markers": [{"id": f"t_{i:02d}", "xpath": t["xpath"], "signalAttrs": t["signal_attrs"]}
                                      for i, t in enumerate(s["selected"], 1)],
                          "tasks": [t["task"] for t in s["selected"]]} for s in cands],
               "shims": True, "writeObs": False}
    out_dir = RP_CACHE / "d_remeasure"
    if run_mode("dump", payload, out_dir, "dump.log") != 0:
        raise SystemExit("[(г)] adapter process failed (not a site property) -> STOP")
    sites = {r["site"]: r for r in read_tsv(out_dir / "sites.tsv")}
    man = {(r["site"], r["bundle"], r["encoding"]): r for r in read_tsv(out_dir / "manifest.tsv")}
    prompts = read_tsv(out_dir / "prompt_tokens.tsv")

    rows = []
    for s in cands:
        k, r = s["key"], sites.get(s["key"], {})
        ok = r.get("ok") == "True"
        pt = [int(p["prompt_tokens"]) for p in prompts if p["site"] == k]
        new = max(pt) if ok and pt else None
        rows.append({"rank": s["rank"], "domain": s["domain"], "dump_ok": ok, "error": r.get("error") or None,
                     "loads": int(r["loads"]) if ok else None, "fulfilled": int(r["fulfilled"]) if ok else None,
                     "markers_set": int(r["markers_set"]) if ok else None, "markers": len(s["selected"]),
                     "old_max_prompt_tokens": s["max_prompt_tokens"], "new_max_prompt_tokens": new,
                     "old_cell_tokens": s["cell_tokens"],
                     "new_cell_tokens": {f"{b}|{e}": int(man[(k, b, e)]["tokens"]) for b, e in CELLS} if ok else None,
                     "passes_d": new is not None and new <= PROMPT_CAP})
    res = {"rule_commit": rule, "plan_commit": plan, "threshold": PROMPT_CAP,
           "protocol": "fresh load per cell (RealPilotOffline.ObserveCellAsync), all markers set, one dump",
           "sites": rows, "passing": [x["domain"] for x in rows if x["passes_d"]]}
    (HERE / "d_remeasure.json").write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                                           newline="\n")
    for x in rows:
        print(f"  {x['domain']:<18} old {x['old_max_prompt_tokens']:>9,}  new "
              f"{x['new_max_prompt_tokens'] if x['new_max_prompt_tokens'] is None else format(x['new_max_prompt_tokens'], ',')!s:>9}"
              f"  loads {x['loads']} markers {x['markers_set']}/{x['markers']}  passes (г): {x['passes_d']}")
    print(f"[(г)] passing: {res['passing'] or 'none'}")


if __name__ == "__main__":
    main()
