"""
rp_plan.py — the real-site pilot's call plan for the experiments/batch runner (pilot profile). No model, no network.

Writes pilot_plan.json (events to call) and pilot_reuse_map.json (class_only cells not called, each mapped to the
B_noVolatile event whose result it reuses), by pilot_rule.md (addendum 2026-10-13: fresh load per cell,
2(б) = 5 identical dumps) and pilot_analysis_plan.md with its addenda (9f0bb2b: scope, class_only reuse, hard cap;
9ead395: "no stable signal" descriptive only). The per-(site, cell) status is rp_cost.plan(), the same rule
cost_estimate.json used. Every check must pass before anything is written.

Run from the repository root:  python experiments/results/revision1/real_pilot/rp_plan.py
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import hashlib
import json
import math
import subprocess
from collections import Counter, defaultdict

from rp_common import HERE, REPO, committed, read_tsv
from rp_cost import CELL_ORDER, CHAT_OVERHEAD, LABEL, MAX_OUT, PRICE_IN, PRICE_OUT, call_cost, plan

MODEL, MODEL_ENV, BLOCK, REPETITION = "gpt-4.1", "BAR_MODEL_DEPLOYMENT_1", "pilot", 0
CLASS_ONLY, NVC = "B_full_minus_volClass", "B_noVolatileConsistent"


def event_key(model, bundle, encoding, page, task_id, repetition):
    """experiments/batch/BatchModel.cs PlanEvent.Key."""
    return f"{model}|{bundle}|{encoding}|{page}|{task_id}|{repetition}"


def sha_file(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def source(rel):
    c = committed(rel)
    return {"path": rel, "commit": c["sha"], "clean": c["clean"], "sha256": sha_file(REPO / rel)}


def main():
    el, tg, keys, status = plan()
    cost = json.loads((HERE / "cost_estimate.json").read_text(encoding="utf-8"))
    man = {(r["domain"], r["code_bundle"], r["encoding"]): r for r in read_tsv(HERE / "observations_manifest.tsv")}
    ptok = {(r["site"], r["bundle"], r["encoding"], int(r["task_index"])): int(r["prompt_tokens"])
            for r in read_tsv(HERE / "observations" / "prompt_tokens.tsv")}
    reasons = {s["domain"]: s["reason"] for s in el["sites"]}
    eligible = {s["domain"] for s in el["sites"] if s["eligible"]}

    by_site = defaultdict(list)
    for t in tg["items"]:
        by_site[f"{t['rank']:04d}_{t['domain']}"].append(t)

    events, reuse = [], []
    excluded = set(el.get("redump", {}).get("excluded", {}))   # candidates of the 2(б) re-dump that failed
    for page in sorted(by_site, key=lambda k: keys[k][0]):
        for i, t in enumerate(by_site[page]):
            for enc in ("F1", "F3"):
                for b, e in CELL_ORDER:
                    if e != enc:
                        continue
                    st = status[(page, b, e)]
                    key = event_key(MODEL, b, e, page, t["marker"], REPETITION)
                    sha = man[(t["domain"], b, e)]["sha256"]
                    if st == "excluded_site":
                        excluded.add(t["domain"])   # in targets.json but not eligible
                    elif st == "call":
                        events.append({
                            "block": BLOCK, "model": MODEL, "model_env": MODEL_ENV, "bundle": b, "encoding": e,
                            "page": page, "task_id": t["marker"], "repetition": REPETITION, "rep": REPETITION + 1,
                            "event_key": key, "cell": LABEL[b], "domain": t["domain"], "rank": t["rank"],
                            "target_sha256_key": t["sha256_key"], "xpath": t["xpath"], "task": t["task"],
                            "stratum": t["stratum"], "observation_sha256": sha, "input_tokens": ptok[(page, b, e, i)]})
                    else:
                        assert st == "reuse_B_noVolatile" and b == CLASS_ONLY, (page, b, e, st)
                        reuse.append({
                            "class_only_event_key": key,
                            "reused_event_key": event_key(MODEL, NVC, e, page, t["marker"], REPETITION),
                            "domain": t["domain"], "page": page, "task_id": t["marker"], "encoding": e,
                            "class_only_observation_sha256": sha,
                            "b_novolatile_observation_sha256": man[(t["domain"], NVC, e)]["sha256"]})

    # checks
    res, fail = [], []

    def check(name, ok, detail):
        res.append(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        if not ok:
            fail.append(name)

    n_calls, n_tok = len(events), sum(ev["input_tokens"] for ev in events)
    upper = sum(call_cost(ev["input_tokens"]) for ev in events)
    cap = math.ceil(upper * 1.10 * 100) / 100
    check("1 calls", n_calls == cost["total"]["calls"], f"{n_calls:,} (cost_estimate {cost['total']['calls']:,})")
    check("1 input tokens", n_tok == cost["total"]["input_tokens"],
          f"{n_tok:,} (cost_estimate {cost['total']['input_tokens']:,})")
    check("1 upper bound / cap", round(upper, 2) == cost["total"]["upper_bound_usd"]
          and cap == cost["hard_cap_usd"], f"${upper:.2f} / ${cap:.2f} (cost_estimate "
          f"${cost['total']['upper_bound_usd']:.2f} / ${cost['hard_cap_usd']:.2f})")
    per_cell = {}
    for b, e in CELL_ORDER:
        sel = [ev["input_tokens"] for ev in events if ev["bundle"] == b and ev["encoding"] == e]
        per_cell[f"{LABEL[b]}|{e}"] = {"calls": len(sel), "input_tokens": sum(sel)}
    pc_ok = all(per_cell[k]["calls"] == v["calls"] and per_cell[k]["input_tokens"] == v.get("sum", 0)
                for k, v in cost["per_cell"].items())
    check("1 per-cell calls and tokens = cost_estimate", pc_ok,
          ", ".join(f"{k} {v['calls']}/{v['input_tokens']:,}" for k, v in per_cell.items()))

    man_shas = {r["sha256"] for r in man.values()}
    bad_sha = [ev["event_key"] for ev in events if ev["observation_sha256"] not in man_shas
               or man[(ev["domain"], ev["bundle"], ev["encoding"])]["sha256"] != ev["observation_sha256"]]
    check("2 observation_sha256 in observations_manifest.tsv", not bad_sha, f"{n_calls - len(bad_sha)}/{n_calls}")
    cells = {(ev["page"], ev["bundle"], ev["encoding"]) for ev in events}
    bad_txt = [c for c in cells
               if sha_file(HERE / "observations" / f"{c[0]}__{c[1]}__{c[2]}.txt")
               != man[(c[0].split("_", 1)[1], c[1], c[2])]["sha256"]]
    check("2 sha256(local observation text) = manifest", not bad_txt, f"{len(cells) - len(bad_txt)}/{len(cells)} cells")

    tkeys = {(t["domain"], t["marker"], t["xpath"], t["sha256_key"]) for t in tg["items"]}
    bad_t = [ev["event_key"] for ev in events
             if (ev["domain"], ev["task_id"], ev["xpath"], ev["target_sha256_key"]) not in tkeys]
    check("3 target in targets.json", not bad_t, f"{n_calls - len(bad_t)}/{n_calls}")
    off = [x for x in events + reuse if x["domain"] not in eligible or x["domain"] in excluded]
    check("3 only eligible sites", not off, f"{len(off)} events/reuse entries on other sites; excluded sites "
          f"{sorted(excluded)}")
    n_targets = len({(ev["domain"], ev["task_id"]) for ev in events})
    n_sites = len({ev["domain"] for ev in events})
    want = [t for t in tg["items"] if t["domain"] in eligible]
    check("3 targets / sites", n_targets == len(want) == cost["targets"] and n_sites == len(eligible)
          == cost["eligible_sites"], f"{n_targets} targets on {n_sites} sites")

    ev_keys = {ev["event_key"] for ev in events}
    bad_r = [r["class_only_event_key"] for r in reuse
             if r["class_only_observation_sha256"] != r["b_novolatile_observation_sha256"]
             or r["reused_event_key"] not in ev_keys or r["class_only_event_key"] in ev_keys]
    check("4 reuse pairs: equal hashes, reused key planned, not also called", not bad_r,
          f"{len(reuse) - len(bad_r)}/{len(reuse)}")
    for e in ("F1", "F3"):
        called = sum(1 for ev in events if ev["bundle"] == CLASS_ONLY and ev["encoding"] == e)
        reused = sum(1 for r in reuse if r["encoding"] == e)
        check(f"4 class_only × {e}: called + reused = targets", called + reused == n_targets,
              f"{called} + {reused} = {called + reused}")

    all_keys = [ev["event_key"] for ev in events] + [r["class_only_event_key"] for r in reuse]
    dup = [k for k, n in Counter(all_keys).items() if n > 1]
    check("5 unique event keys (plan ∪ reuse map)", not dup, f"{len(set(all_keys))} unique of {len(all_keys)}")
    recomputed = [ev for ev in events if ev["event_key"] != event_key(
        ev["model"], ev["bundle"], ev["encoding"], ev["page"], ev["task_id"], ev["repetition"])]
    check("5 event_key = runner formula", not recomputed, f"{n_calls - len(recomputed)}/{n_calls}")

    untouched = subprocess.run(["git", "status", "--porcelain", "--", "experiments/batch", "shared",
                                "experiments/results/revision1/batch_plan.json"],
                               cwd=REPO, capture_output=True, text=True).stdout.strip()
    check("6 experiments/batch, shared/, batch_plan.json unchanged", untouched == "", untouched or "git status clean")

    print("\n".join(res))
    if fail:
        print(f"STOP: {len(fail)} check(s) failed; nothing written")
        sys.exit(1)

    # write
    rp = "experiments/results/revision1/real_pilot/"
    plan_doc = {
        "description": "Real-site pilot call plan (pilot_rule.md + addendum 1a16fa1, pilot_analysis_plan.md + addenda 9f0bb2b, "
                       "9ead395); "
                       "for the experiments/batch runner, pilot profile. One generation per (target x cell); events listed in "
                       "Tranco-rank, target, encoding, cell order. class_only cells whose observation is byte-identical "
                       "to B_noVolatile are not called (pilot_reuse_map.json).",
        "fields": {
            "block": "as batch_plan.json; \"pilot\"",
            "model": "as batch_plan.json; \"gpt-4.1\"",
            "model_env": "as batch_plan.json; deployment env var (BAR_MODEL_DEPLOYMENT_1, the corpus gpt-4.1)",
            "bundle": "as batch_plan.json; code bundle: B_full, B_noVolatileConsistent (pilot B_noVolatile), "
                      "B_full_minus_volClass (pilot class_only)",
            "encoding": "as batch_plan.json; F1 (EncodeF1Json) or F3 (EncodeF3Linearized)",
            "page": "as batch_plan.json, here the site key <rank:04d>_<domain> (observation dump / manifest key)",
            "task_id": "as batch_plan.json, here the target marker t_NN (targets.json 'marker'; unique within a site)",
            "repetition": "as batch_plan.json; 0",
            "rep": "as batch_plan.json; repetition + 1",
            "event_key": "experiments/batch PlanEvent.Key: model|bundle|encoding|page|task_id|repetition",
            "cell": "pilot cell label: B_full, B_noVolatile, class_only",
            "domain": "site domain (targets.json)",
            "rank": "Tranco rank (targets.json)",
            "target_sha256_key": "targets.json sha256_key = SHA-256(domain|xpath)",
            "xpath": "target XPath on the May page (targets.json; sets the data-oracle-id marker)",
            "task": "template task (targets.json; pilot_rule.md §5)",
            "stratum": "has stable signal / no stable signal (targets.json; condition 5 on B_full)",
            "observation_sha256": "sha256 of the observation text for (page, bundle, encoding), "
                                  "= observations_manifest.tsv",
            "input_tokens": "CountTokens(SystemPrompt) + CountTokens(BuildUserPrompt(obs, task)), o200k_base "
                            "(observations/prompt_tokens.tsv, as summed in cost_estimate.json)",
        },
        "sources": [source(rp + f) for f in ("pilot_rule.md", "pilot_analysis_plan.md", "targets.json",
                                              "eligibility.json", "observations_manifest.tsv", "cost_estimate.json")],
        "settings": {"model": MODEL, "model_env": MODEL_ENV, "temperature": 0, "max_output_tokens": MAX_OUT,
                     "prompt": "corpus prompt, unchanged: GroundingRunner.SystemPrompt + "
                               "GroundingRunner.BuildUserPrompt(observation, task)",
                     "tokenizer": "o200k_base (shared/tokenizer TokenCounter.CountTokens)", "repetitions": 1},
        "excluded_sites": [{"domain": d, "reason": reasons[d]} for d in sorted(excluded)],
        "counts": {BLOCK: n_calls},
        "per_cell": per_cell,
        "class_only_not_called": len(reuse),
        "budget": {"source_commit": "9f0bb2b", "planned_calls": n_calls, "planned_input_tokens": n_tok,
                   "chat_overhead_tokens": CHAT_OVERHEAD, "max_output_tokens": MAX_OUT,
                   "price_usd_per_1M": {"input": PRICE_IN, "output": PRICE_OUT},
                   "upper_bound_usd": round(upper, 2), "hard_cap_usd": cap,
                   "stop_rule": "Track the cumulative list-price cost from the API-reported prompt and completion "
                                "tokens. Stop before any call whose upper bound ((input_tokens + 16) x $2.00/M + "
                                "256 x $8.00/M) would take the total above hard_cap_usd. Calls not made because of "
                                "the cap are reported as such and not replaced."},
        "events": events,
    }
    reuse_doc = {
        "description": "class_only (B_full_minus_volClass) cells of the real-site pilot that are NOT called: their "
                       "observation is byte-identical (sha256) to the B_noVolatile (B_noVolatileConsistent) "
                       "observation of the same site and encoding, so the prompt is identical and the B_noVolatile "
                       "result is reused as the class_only result (pilot_analysis_plan.md addendum 9f0bb2b).",
        "plan_sha256": hashlib.sha256((json.dumps(plan_doc, indent=1) + "\n").encode("utf-8")).hexdigest(),
        "count": len(reuse),
        "reuse": reuse,
    }
    for name, doc in (("pilot_plan.json", plan_doc), ("pilot_reuse_map.json", reuse_doc)):
        (HERE / name).write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"wrote {name}  sha256 {sha_file(HERE / name)}")


if __name__ == "__main__":
    main()
