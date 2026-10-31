"""
rp_eligibility.py — Step 1 of the real-site pilot preparation: site eligibility (pilot_rule.md §2).

0. Preconditions: pilot_rule.md / pilot_analysis_plan.md committed and clean; the verbatim JS blocks
   in the committed pilot_rule.md equal rp_candidates.js / rp_shim_random.js.
1. Shim check on the 24 corpus pages (six cells, with vs without shims). Any difference -> STOP.
2. (а) static volatile class (CLI) -> (б) offline load + walker + two identical dumps
   -> (в) >= 5 eligible targets -> (г) largest-cell prompt <= 128,000 tokens.

Run from the repository root:  python experiments/results/revision1/real_pilot/rp_eligibility.py
Writes eligibility.md / eligibility.json next to this file (domains, counts, sizes: no page text) and
the per-site state to ../_external/cc_cache/real_pilot/state.json.  No network, no LLM.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import json
import re
import subprocess
from collections import Counter

from rp_common import (HERE, REPO, RP_CACHE, PROMPT_CAP, MIN_TARGETS, build_cli, classify, committed, decoded_html,
                       dry_run, eligible_targets, extract_values, md_table, oracle_lists, read_tsv, role_of,
                       run_mode, select_targets, signal_attrs, site_key, task_of, ts_iso)

RULE = "experiments/results/revision1/real_pilot/pilot_rule.md"
PLAN = "experiments/results/revision1/real_pilot/pilot_analysis_plan.md"
CELLS = [(b, e) for e in ("F1", "F3") for b in ("B_full", "B_noVolatileConsistent", "B_full_minus_volClass")]


def preconditions():
    rule, plan = committed(RULE), committed(PLAN)
    if not (rule["sha"] and rule["clean"] and plan["sha"] and plan["clean"]):
        raise SystemExit(f"[pre] rule/plan not committed and clean: {rule} {plan}")
    text = subprocess.run(["git", "-C", str(REPO), "show", f"{rule['sha']}:{RULE}"], capture_output=True,
                          encoding="utf-8").stdout
    blocks = re.findall(r"```js\n(.*?)\n```", text, re.S)
    files = [(HERE / f).read_text(encoding="utf-8").rstrip("\n") for f in ("rp_candidates.js", "rp_shim_random.js")]
    if blocks != files:
        raise SystemExit("[pre] JS in the committed pilot_rule.md differs from rp_candidates.js / rp_shim_random.js")
    return rule, plan


def shimcheck():
    out = RP_CACHE / "shimcheck"
    if run_mode("shimcheck", None, out, "shimcheck.log") != 0:
        raise SystemExit("[shimcheck] adapter failed (see log)")
    rows = read_tsv(out / "shimcheck.tsv")
    by = {}
    for r in rows:
        by.setdefault((r["page"], r["bundle"], r["encoding"]), {})[r["shims"]] = r["sha256"]
    diff = [k for k, v in by.items() if v.get("True") != v.get("False")]
    batch = {(r["page"], r["bundle"], r["encoding"]): r["sha256"]
             for r in read_tsv(REPO / "experiments/results/revision1/batch_observations/manifest.tsv")}
    parity = [(k, by[k]["False"] == batch[k]) for k in sorted(by) if k in batch]
    res = {"pages": len({k[0] for k in by}), "cells": len(by), "differ_with_vs_without": len(diff),
           "differing": [list(k) for k in diff],
           "corpus_dump_parity": {"compared": len(parity), "equal": sum(ok for _, ok in parity),
                                  "unequal": [list(k) for k, ok in parity if not ok]}}
    return res


def write_md(out):
    """eligibility.md from the eligibility.json content."""
    rule, plan, sc, sites = out["rule_commit"], out["plan_commit"], out["shimcheck"], out["sites"]

    def yn(v):
        return "–" if v is None else ("yes" if v else "no")
    L = ["# Real-site pilot: step 1, site eligibility", "",
         f"- pilot_rule.md commit: `{rule['sha']}` ({rule['committed']}); pilot_analysis_plan.md: `{plan['sha']}`",
         f"- Shim check (24 corpus pages × 6 cells, with vs without shims): {sc['cells']} cells, "
         f"**{sc['differ_with_vs_without']} differ**. Adapter vs stored corpus dump "
         f"(`batch_observations/manifest.tsv`, F1 cells): {sc['corpus_dump_parity']['equal']}/"
         f"{sc['corpus_dump_parity']['compared']} identical.",
         f"- Decoding (May payloads): {out['decode_stats']}"]
    L += [f"- {n}" for n in out.get("notes", [])]
    L += ["", f"**Eligible sites: {out['eligible']} of {len(sites)}.**", "", "## Counts by first failing criterion", ""]
    L += md_table(["criterion", "sites"], sorted(out["counts"].items()))
    dexcl = [s for s in sites if s["reason"].startswith("(г)")]
    if dexcl:
        L += ["", "(г) exclusions, largest-cell prompt size:", ""]
        L += md_table(["rank", "domain", "max prompt tokens"], [[s["rank"], s["domain"], f"{s['max_prompt_tokens']:,}"]
                                                                  for s in dexcl])
    L += ["", "## All sites", ""]
    L += md_table(["domain", "rank", "(а)", "(б)", "(в)", "(г)", "eligible", "reason"],
                  [[s["domain"], s["rank"], yn(s["a"]), yn(s["b"]),
                    "–" if s["c"] is None else f"{yn(s['c'])} ({s['eligible_targets']})",
                    "–" if s["d"] is None else f"{yn(s['d'])} ({s['max_prompt_tokens']:,})",
                    yn(s["eligible"]), s["reason"]] for s in sites])
    (HERE / "eligibility.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


def main():
    rule, plan = preconditions()
    describe = build_cli()
    sc = shimcheck()
    print(f"[shimcheck] {sc['cells']} cells, differ={sc['differ_with_vs_without']}, "
          f"corpus parity {sc['corpus_dump_parity']['equal']}/{sc['corpus_dump_parity']['compared']}")
    if sc["differ_with_vs_without"]:
        (HERE / "eligibility.json").write_text(json.dumps({"shimcheck": sc, "stopped": True}, indent=2) + "\n",
                                               encoding="utf-8", newline="\n")
        raise SystemExit("[shimcheck] corpus observations differ with vs without shims -> STOP")

    dr = dry_run()
    may = dr["crawls"][0]
    stats = Counter()
    sites = []
    for q in dr["qualified_domains"]:
        html, path, uri = decoded_html(may, q, stats)
        cls, _ = extract_values(html)
        sites.append({"key": site_key(q), "rank": q["rank"], "domain": q["domain"], "url": uri, "html_path": str(path),
                      "timestamp": ts_iso(q[may]["timestamp"]), "static_classes": sorted(cls)})
    flags = classify({("class", t) for s in sites for t in s["static_classes"]})
    for s in sites:
        s["a_flagged_classes"] = sum(flags[("class", t)] for t in s.pop("static_classes"))
        s["a"] = s["a_flagged_classes"] > 0

    # (б) part 1: probe (load + candidates + walked values)
    pa = [s for s in sites if s["a"]]
    probe_dir = RP_CACHE / "probe"
    rc = run_mode("probe", {"sites": [{"key": s["key"], "url": s["url"], "htmlPath": s["html_path"],
                                  "timestamp": s["timestamp"], "volIds": [], "volClasses": [],
                                  "markers": [], "tasks": []} for s in pa],
                       "shims": True, "writeObs": False}, probe_dir, "probe.log")
    if rc != 0:
        raise SystemExit(f"[probe] adapter process exited with {rc} (adapter failure, not a site property) -> STOP")
    for s in pa:
        pf = probe_dir / f"{s['key']}.probe.json"
        pr = json.loads(pf.read_text(encoding="utf-8")) if pf.exists() else {"ok": False, "error": "no probe output"}
        s["probe_ok"], s["probe_error"] = pr["ok"], pr.get("error")
        if not pr["ok"]:
            continue
        s["load"] = pr["load"]
        s["walked_elements"] = pr["walked_elements"]
        vol_ids, vol_cls, _ = oracle_lists(pr["class_attrs"], pr["ids"])
        s["vol_ids"], s["vol_classes"] = vol_ids, vol_cls
        cands = pr["candidates"]["candidates"]
        s["candidates"] = len(cands)
        s["candidate_exclusions"] = pr["candidates"]["excluded"]
        s["xpath_roundtrip_failures"] = sum(not c["xpathRoundTrip"] for c in cands)
        elig = eligible_targets(cands)
        s["eligible_targets"] = len(elig)
        sel = []
        for key, c in select_targets(s["domain"], elig):
            role = role_of(c)
            sa = signal_attrs(c["attrs"], set(vol_ids))
            sel.append({"key": key, "xpath": c["xpath"], "xpath_roundtrip": c["xpathRoundTrip"], "tag": c["tag"],
                        "role": role, "name": c["name"], "name_source": c["nameSource"],
                        "task": task_of(role, c["name"]), "signal_attrs": sa,
                        "stratum": "has stable signal" if sa else "no stable signal"})
        s["selected"] = sel

    # (б) part 2: two dumps without markers, separate processes
    pb = [s for s in pa if s.get("probe_ok")]
    payload = {"sites": [{"key": s["key"], "url": s["url"], "htmlPath": s["html_path"], "timestamp": s["timestamp"],
                          "volIds": s["vol_ids"], "volClasses": s["vol_classes"], "markers": [],
                          "tasks": [t["task"] for t in s["selected"]]} for s in pb],
               "shims": True, "writeObs": False}
    runs = []
    for i in (1, 2):
        d = RP_CACHE / f"step1_dump{i}"
        rc = run_mode("dump", payload, d, f"dump{i}.log")
        if rc != 0:
            raise SystemExit(f"[dump{i}] adapter process exited with {rc} (adapter failure, not a site property) -> STOP")
        runs.append({"sites": {r["site"]: r for r in read_tsv(d / "sites.tsv")},
                     "manifest": {(r["site"], r["bundle"], r["encoding"]): r for r in read_tsv(d / "manifest.tsv")},
                     "prompts": read_tsv(d / "prompt_tokens.tsv")})
    for s in pb:
        k = s["key"]
        oks = [r["sites"].get(k, {}).get("ok") == "True" for r in runs]
        s["dump_ok"] = all(oks)
        s["dump_error"] = next((r["sites"].get(k, {}).get("error") for r in runs
                                if r["sites"].get(k, {}).get("ok") != "True"), None)
        if s["dump_ok"]:
            h = [[r["manifest"].get((k, b, e), {}).get("sha256") for b, e in CELLS] for r in runs]
            s["deterministic"] = h[0] == h[1] and None not in h[0]
            s["cells_differing_between_dumps"] = sum(x != y for x, y in zip(*h))
            s["cell_tokens"] = {f"{b}|{e}": int(runs[0]["manifest"][(k, b, e)]["tokens"]) for b, e in CELLS}
            pt = [int(r["prompt_tokens"]) for r in runs[0]["prompts"] if r["site"] == k]
            s["max_prompt_tokens"] = max(pt) if pt else None
            s["b_full_ne_nvc"] = all(runs[0]["manifest"][(k, "B_full", e)]["sha256"]
                                     != runs[0]["manifest"][(k, "B_noVolatileConsistent", e)]["sha256"]
                                     for e in ("F1", "F3"))

    # criteria in order, first failing reason
    for s in sites:
        if not s["a"]:
            s.update(b=None, c=None, d=None, eligible=False, reason="(а) no flagged class token: B_full ≡ B_noVolatile by construction")
            continue
        if not s.get("probe_ok"):
            s.update(b=False, c=None, d=None, eligible=False, reason=f"(б) load/probe failed: {s.get('probe_error')}")
            continue
        if not s.get("dump_ok"):
            s.update(b=False, c=None, d=None, eligible=False, reason=f"(б) walker/dump failed: {s.get('dump_error')}")
            continue
        if not s["deterministic"]:
            s.update(b=False, c=None, d=None, eligible=False,
                     reason=f"(б) not deterministic: {s['cells_differing_between_dumps']}/6 cells differ between two dumps")
            continue
        s["b"] = True
        s["c"] = s["eligible_targets"] >= MIN_TARGETS
        if not s["c"]:
            s.update(d=None, eligible=False, reason=f"(в) {s['eligible_targets']} eligible targets < {MIN_TARGETS}")
            continue
        s["d"] = s["max_prompt_tokens"] <= PROMPT_CAP
        if not s["d"]:
            s.update(eligible=False, reason=f"(г) largest-cell prompt {s['max_prompt_tokens']:,} > {PROMPT_CAP:,} tokens")
            continue
        s.update(eligible=True, reason="")

    eligible = [s for s in sites if s["eligible"]]
    reasons = Counter(s["reason"].split(" ")[0] if s["reason"] else "eligible" for s in sites)
    state = {"rule_commit": rule, "plan_commit": plan, "cli": describe, "decode_stats": dict(stats), "sites": sites}
    (RP_CACHE / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")

    public = [{k: s.get(k) for k in ("rank", "domain", "a", "a_flagged_classes", "b", "c", "d", "eligible", "reason",
                                      "eligible_targets", "max_prompt_tokens", "walked_elements", "load",
                                      "xpath_roundtrip_failures", "b_full_ne_nvc", "cells_differing_between_dumps")}
              for s in sites]
    out = {"rule_commit": rule, "plan_commit": plan, "cli": describe, "shimcheck": sc,
           "decode_stats": dict(stats), "counts": dict(reasons), "eligible": len(eligible), "sites": public}
    (HERE / "eligibility.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8", newline="\n")

    write_md(out)
    print(f"[eligibility] eligible {len(eligible)}/{len(sites)}; {dict(reasons)}")
    if len(eligible) < MIN_TARGETS:
        raise SystemExit(f"[eligibility] fewer than 5 eligible sites ({len(eligible)}) -> STOP and ask")


if __name__ == "__main__":
    main()
