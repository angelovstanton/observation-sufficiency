"""
cc_classifier_validation.py — analysis_plan.md, "Predictor": the Python port must agree 100%
with the C# Oracle CLI on every class/id value of the 24 corpus pages (static testbed HTML and
the runtime B_full F1 observation dumps). Any disagreement exits 1.

Run from the repository root:  python experiments/results/revision1/cc_volatility/cc_classifier_validation.py
No network, no LLM. Writes classifier_validation.md / .json next to this file.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import json
import pathlib
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cc_common import (REPO, build_cli, classify, port_flag, extract_values, class_tokens,  # noqa: E402
                       committed, md_table)

PAGES = REPO / "shared" / "testbed" / "pages"
OBS = REPO / "experiments" / "results" / "revision1" / "observations"


def main():
    plan = committed("experiments/results/revision1/cc_volatility/analysis_plan.md")
    describe = build_cli()
    src = Counter()
    pairs = set()
    for p in sorted(PAGES.glob("page_*.html")):
        cls, ids = extract_values(p.read_text(encoding="utf-8"))
        pairs |= {("class", v) for v in cls} | {("id", v) for v in ids}
        src["static_html_pages"] += 1
    for p in sorted(OBS.glob("page_*__B_full__F1.txt")):
        for e in json.loads(p.read_text(encoding="utf-8")):
            if e.get("class"):
                pairs |= {("class", t) for t in class_tokens(e["class"])}
            if e.get("id"):
                pairs.add(("id", e["id"]))
        src["f1_dumps"] += 1
    if (src["static_html_pages"], src["f1_dumps"]) != (24, 24):
        raise SystemExit(f"[validation] expected 24 pages and 24 F1 dumps, got {dict(src)}")
    cli = classify(pairs)
    rows, disagree = Counter(), []
    for (t, v), f in sorted(cli.items()):
        pf = port_flag(t, v)
        rows[(t, f, pf)] += 1
        if pf != f:
            disagree.append({"t": t, "v": v, "cli": f, "port": pf})
    n = {t: sum(1 for (tt, _) in cli if tt == t) for t in ("class", "id")}
    flagged = {t: sum(1 for (tt, _), f in cli.items() if tt == t and f) for t in ("class", "id")}
    ok = not disagree
    out = {"analysis_plan_commit": plan, "cli": describe, "sources": dict(src), "values": n,
           "cli_flagged": flagged, "agreement": {t: n[t] - sum(d["t"] == t for d in disagree) for t in n},
           "disagreements": disagree, "passed": ok}
    (HERE / "classifier_validation.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                                                     encoding="utf-8", newline="\n")
    L = ["# Classifier validation — Python port vs C# Oracle CLI (corpus values)", "",
         f"- analysis_plan.md commit: `{plan['sha']}` ({plan['committed']}; working copy clean: {plan['clean']})",
         "- Classifier of record: `oracle_cli/` (reflection on `Oracle.IsVolatileClass` / `Oracle.IsVolatileId`, "
         "Oracle source unchanged).",
         "- CLI `--describe`:", "", "```", describe, "```", "",
         "- Values: unique class tokens (ASCII-whitespace split) and id values from the 24 static testbed pages "
         "(`shared/testbed/pages/page_*.html`, html.parser) together with the 24 runtime "
         "`observations/page_XX__B_full__F1.txt` dumps.", ""]
    L += md_table(["type", "unique values", "CLI flagged", "port == CLI", "result"],
                  [[t, n[t], flagged[t], f"{out['agreement'][t]}/{n[t]}",
                    "100%" if out["agreement"][t] == n[t] else "MISMATCH"] for t in ("class", "id")])
    L += ["", f"**{'PASSED' if ok else 'FAILED — STOP'}**: "
          f"{sum(out['agreement'].values())}/{sum(n.values())} values agree."]
    if disagree:
        L += ["", "Disagreements:", ""] + md_table(["type", "value", "CLI", "port"],
                                                   [[d["t"], f"`{d['v']}`", d["cli"], d["port"]] for d in disagree])
    (HERE / "classifier_validation.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print(f"[validation] {'PASSED' if ok else 'FAILED'} class {out['agreement']['class']}/{n['class']} "
          f"id {out['agreement']['id']}/{n['id']}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
