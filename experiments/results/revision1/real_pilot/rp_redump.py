"""
rp_redump.py — observation dump under the pilot_rule.md addendum (2026-10-13): every cell on a fresh load
(RealPilotOffline.ObserveCellAsync, as in the paid run), criterion 2(б) = five independent full dumps with
identical observation sha256 for all cells. No model, no network.

Steps: preconditions and the 24-page shim check (from rp_eligibility); candidates = every site that passed (а),
(в) and (г) so far, including those excluded under (б) (wikipedia.org, kaspersky.com), with probe, Oracle lists
and selection unchanged and markers t_01… in selection order; five dumps in separate processes (dump 1 texts to
real_pilot/observations/, not committed, dumps 2–5 hashes only to the external cache); criteria in the rule's
order, updating state.json and eligibility.json / .md.

Checks on the eligible sites (any failure stops; nothing written past state): all markers set in every load,
B_full != B_noVolatile (F1, F3), no 'data-oracle' in any observation, oracle element found and condition 5
(B_full × F1 load) == stratum, git diff -- shared/ empty. Writes observations_manifest.tsv and dump_checks.json.

Run from the repository root:  python experiments/results/revision1/real_pilot/rp_redump.py
Then: rp_targets.py, rp_cost.py, rp_plan.py, rp_sites.py.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import json
import shutil
import subprocess
from collections import Counter

from rp_common import HERE, REPO, RP_CACHE, PROMPT_CAP, MIN_TARGETS, read_tsv, run_mode
from rp_eligibility import CELLS, preconditions, shimcheck, write_md

N_DUMPS = 5
LABEL = {"B_full": "B_full", "B_noVolatileConsistent": "B_noVolatile", "B_full_minus_volClass": "class_only"}
DUMP_DIRS = [HERE / "observations"] + [RP_CACHE / f"redump_{i}" for i in range(2, N_DUMPS + 1)]


def is_candidate(s):
    """Passed (а), (в) and (г) so far; (б) is applied anew (rule addendum 2026-10-13)."""
    if not s.get("a") or not s.get("probe_ok") or s.get("eligible_targets", 0) < MIN_TARGETS:
        return False
    return s["eligible"] or s["reason"].startswith("(б)")


def main():
    rule, plan = preconditions()
    sc = shimcheck()
    print(f"[shimcheck] {sc['cells']} cells, differ={sc['differ_with_vs_without']}, "
          f"corpus parity {sc['corpus_dump_parity']['equal']}/{sc['corpus_dump_parity']['compared']}")
    if sc["differ_with_vs_without"]:
        raise SystemExit("[shimcheck] corpus observations differ with vs without shims -> STOP")

    state_p = RP_CACHE / "state.json"
    state = json.loads(state_p.read_text(encoding="utf-8"))
    cands = sorted((s for s in state["sites"] if is_candidate(s)), key=lambda s: s["rank"])
    print(f"[redump] {len(cands)} candidates: {', '.join(s['domain'] for s in cands)}")
    payload = {"sites": [{"key": s["key"], "url": s["url"], "htmlPath": s["html_path"], "timestamp": s["timestamp"],
                          "volIds": s["vol_ids"], "volClasses": s["vol_classes"],
                          "markers": [{"id": f"t_{i:02d}", "xpath": t["xpath"], "signalAttrs": t["signal_attrs"]}
                                      for i, t in enumerate(s["selected"], 1)],
                          "tasks": [t["task"] for t in s["selected"]]} for s in cands],
               "shims": True}

    old = HERE / "observations"
    if old.exists():
        dest = RP_CACHE / "observations_before_2026-10-13"
        if dest.exists():
            raise SystemExit(f"[redump] {dest} exists -> STOP (not overwriting the previous protocol's dump)")
        shutil.move(str(old), str(dest))
    old.mkdir()
    (old / ".gitignore").write_text("*\n", encoding="utf-8")
    for i, d in enumerate(DUMP_DIRS, 1):
        if d != old and d.exists():
            shutil.rmtree(d)
        if run_mode("dump", {**payload, "writeObs": i == 1}, d, f"dump{i}.log") != 0:
            raise SystemExit(f"[redump] dump {i}: adapter process failed (not a site property) -> STOP")

    runs = [{"sites": {r["site"]: r for r in read_tsv(d / "sites.tsv")},
             "manifest": {(r["site"], r["bundle"], r["encoding"]): r for r in read_tsv(d / "manifest.tsv")},
             "prompts": read_tsv(d / "prompt_tokens.tsv"),
             "cond5": {(r["site"], r["marker"]): r for r in read_tsv(d / "cond5.tsv")}} for d in DUMP_DIRS]

    # criteria for the candidates (а → б → в → г), first failing reason
    for s in cands:
        k = s["key"]
        oks = [r["sites"].get(k, {}).get("ok") == "True" for r in runs]
        s["dump_ok"] = all(oks)
        s["dump_error"] = next((r["sites"].get(k, {}).get("error") for r in runs
                                if r["sites"].get(k, {}).get("ok") != "True"), None)
        s["dumps"] = N_DUMPS
        if s["dump_ok"]:
            h = [[r["manifest"].get((k, b, e), {}).get("sha256") for b, e in CELLS] for r in runs]
            s["cells_differing_between_dumps"] = sum(len(set(col)) > 1 for col in zip(*h))
            s["deterministic"] = s["cells_differing_between_dumps"] == 0 and None not in h[0]
            s["cell_tokens"] = {f"{b}|{e}": int(runs[0]["manifest"][(k, b, e)]["tokens"]) for b, e in CELLS}
            pt = [int(r["prompt_tokens"]) for r in runs[0]["prompts"] if r["site"] == k]
            s["max_prompt_tokens"] = max(pt) if pt else None
            s["b_full_ne_nvc"] = all(runs[0]["manifest"][(k, "B_full", e)]["sha256"]
                                     != runs[0]["manifest"][(k, "B_noVolatileConsistent", e)]["sha256"]
                                     for e in ("F1", "F3"))
        if not s["dump_ok"]:
            s.update(b=False, c=None, d=None, eligible=False, reason=f"(б) walker/dump failed: {s['dump_error']}")
        elif not s["deterministic"]:
            s.update(b=False, c=None, d=None, eligible=False,
                     reason=f"(б) not deterministic: {s['cells_differing_between_dumps']}/6 cells differ across "
                            f"{N_DUMPS} dumps (fresh load per cell)")
        else:
            s["b"] = True
            s["c"] = s["eligible_targets"] >= MIN_TARGETS
            if not s["c"]:
                s.update(d=None, eligible=False, reason=f"(в) {s['eligible_targets']} eligible targets < {MIN_TARGETS}")
            else:
                s["d"] = s["max_prompt_tokens"] <= PROMPT_CAP
                if not s["d"]:
                    s.update(eligible=False,
                             reason=f"(г) largest-cell prompt {s['max_prompt_tokens']:,} > {PROMPT_CAP:,} tokens")
                else:
                    s.update(eligible=True, reason="")

    state["rule_commit"], state["plan_commit"] = rule, plan
    state_p.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")

    sites = state["sites"]
    eligible = sorted((s for s in sites if s["eligible"]), key=lambda s: s["rank"])
    el_old = json.loads((HERE / "eligibility.json").read_text(encoding="utf-8"))
    public = [{k: s.get(k) for k in ("rank", "domain", "a", "a_flagged_classes", "b", "c", "d", "eligible", "reason",
                                      "eligible_targets", "max_prompt_tokens", "walked_elements", "load",
                                      "xpath_roundtrip_failures", "b_full_ne_nvc", "cells_differing_between_dumps")}
              for s in sites]
    out = {"rule_commit": rule, "plan_commit": plan, "cli": el_old["cli"], "shimcheck": sc,
           "decode_stats": el_old["decode_stats"],
           "counts": dict(Counter(s["reason"].split(" ")[0] if s["reason"] else "eligible" for s in sites)),
           "eligible": len(eligible), "sites": public,
           "redump": {"protocol": "pilot_rule.md addendum 2026-10-13: fresh load per cell "
                                  "(RealPilotOffline.ObserveCellAsync), 2(б) = 5 identical dumps",
                      "dumps": N_DUMPS, "candidates": [s["domain"] for s in cands],
                      "eligible": [s["domain"] for s in cands if s["eligible"]],
                      "excluded": {s["domain"]: s["reason"] for s in cands if not s["eligible"]}},
           "notes": [f"Criterion (б) re-applied under the observation protocol of the pilot_rule.md addendum "
                     f"(2026-10-13, commit {rule['sha'][:7]}): every cell on a fresh load, {N_DUMPS} independent "
                     f"dumps, to the {len(cands)} sites that passed (а), (в) and (г) "
                     f"(`rp_redump.py`). Probe, Oracle lists and target selection unchanged. The other sites keep "
                     f"their recorded reason; the shim check above is under the same protocol."]}
    (HERE / "eligibility.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8", newline="\n")
    write_md(out)
    print(f"[eligibility] eligible {len(eligible)}/{len(sites)}; {out['counts']}; excluded now: "
          f"{out['redump']['excluded']}")

    # checks on the eligible sites
    chk, fails = Counter(), []
    obs = DUMP_DIRS[0]
    for s in eligible:
        k, sel = s["key"], s["selected"]
        chk["sites_dumped"] += 1
        if all(int(r["sites"][k]["markers_set"]) == len(sel) for r in runs):
            chk["sites_all_markers_set"] += 1
        else:
            fails.append(f"{k}: markers set {[r['sites'][k]['markers_set'] for r in runs]} of {len(sel)}")
        if not all(int(r["sites"][k]["loads"]) == len(CELLS) and int(r["sites"][k]["fulfilled"]) == len(CELLS)
                   for r in runs):
            fails.append(f"{k}: loads/fulfilled != {len(CELLS)}")
        chk["websockets"] += sum(int(r["sites"][k]["websockets"]) for r in runs)
        chk["nvc_extra_class"] += int(runs[0]["sites"][k]["nvc_extra_class"])
        chk["nvc_extra_id"] += int(runs[0]["sites"][k]["nvc_extra_id"])
        chk["sites_with_nvc_extra"] += any(int(runs[0]["sites"][k][f]) for f in ("nvc_extra_class", "nvc_extra_id"))
        chk["sites_b_full_ne_b_novolatile"] += s["b_full_ne_nvc"]
        if not s["b_full_ne_nvc"]:
            fails.append(f"{k}: B_full == B_noVolatile")
        for b, e in CELLS:
            chk["cells"] += 1
            chk["cells_det_equal"] += len({r["manifest"][(k, b, e)]["sha256"] for r in runs}) == 1
            chk["cells_data_oracle_hits"] += int(runs[0]["manifest"][(k, b, e)]["data_oracle_hits"])
            chk["cells_grep_data_oracle"] += "data-oracle" in (obs / f"{k}__{b}__{e}.txt").read_text(
                encoding="utf-8").lower()
        for i, t in enumerate(sel, 1):
            chk["targets"] += 1
            agree = found = True
            for r in runs:
                c = r["cond5"].get((k, f"t_{i:02d}"))
                found &= c is not None and c["found"] == "True"
                agree &= c is not None and (c["condition5_B_full"] == "True") == (t["stratum"] == "has stable signal")
            chk["targets_oracle_found"] += found
            chk["targets_cond5_eq_stratum"] += agree
            if not (found and agree):
                fails.append(f"{k} t_{i:02d}: oracle found {found}, condition 5 == stratum {agree}")
    if chk["cells_data_oracle_hits"] or chk["cells_grep_data_oracle"]:
        fails.append("'data-oracle' in an observation")
    shared_diff = subprocess.run(["git", "-C", str(REPO), "diff", "--stat", "--", "shared/"], capture_output=True,
                                 encoding="utf-8").stdout.strip()
    shared_cached = subprocess.run(["git", "-C", str(REPO), "diff", "--cached", "--stat", "--", "shared/"],
                                   capture_output=True, encoding="utf-8").stdout.strip()
    if shared_diff or shared_cached:
        fails.append(f"shared/ changed: {shared_diff} {shared_cached}")

    res = {"protocol": out["redump"]["protocol"], "rule_commit": rule, "dumps": N_DUMPS,
           "dump_dirs": [str(d) for d in DUMP_DIRS], "candidates": out["redump"]["candidates"],
           "checks": dict(chk), "failures": fails,
           "git_diff_stat_shared": shared_diff, "git_diff_cached_stat_shared": shared_cached}
    (HERE / "dump_checks.json").write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                                           newline="\n")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if fails:
        raise SystemExit(f"[redump] {len(fails)} check(s) failed -> STOP (observations_manifest.tsv not written)")

    with open(HERE / "observations_manifest.tsv", "w", encoding="utf-8", newline="\n") as f:
        f.write("domain\trank\tcell_bundle\tcode_bundle\tencoding\ttokens\tsha256\n")
        for s in eligible:
            for b, e in CELLS:
                r = runs[0]["manifest"][(s["key"], b, e)]
                f.write(f"{s['domain']}\t{s['rank']}\t{LABEL[b]}\t{b}\t{e}\t{r['tokens']}\t{r['sha256']}\n")
    print(f"[redump] observations_manifest.tsv: {len(eligible)} sites × {len(CELLS)} cells")


if __name__ == "__main__":
    main()
