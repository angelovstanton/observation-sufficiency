"""
cc_volatility_analysis.py — the analysis pre-registered in analysis_plan.md (commit checked at start).

Run from the repository root (plain python: numpy/pandas are needed by revision1_diagnostics):

    python experiments/results/revision1/cc_volatility/cc_volatility_analysis.py

Preconditions (else exit 1, nothing computed): analysis_plan.md committed and unchanged;
fetch_integrity.json 200/200 required checks; classifier_validation.json passed.
Reads raw WARC records only from ../_external/cc_cache/warc/.  No network, no LLM.
Writes volatility_analysis.md / .json next to this file (derived statistics only, no HTML).
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import gzip
import json
import math
import pathlib
import re
from collections import Counter, defaultdict

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cc_common import (REPO, CACHE, build_cli, classify, port_flag, extract_values, committed,  # noqa: E402
                       md_table)
sys.path.insert(0, str(REPO / "experiments" / "analysis"))
from revision1_diagnostics import (N_BOOT, SEED, page_bootstrap, pct_ci, jsonable,  # noqa: E402
                                   protected_state)
from cc_fetch_warc import parse_record                                              # noqa: E402

PLAN_PATH = "experiments/results/revision1/cc_volatility/analysis_plan.md"
TYPES = ("class", "id")
META_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([A-Za-z0-9_\-:.]+)""", re.I)
HTTP_CHARSET = re.compile(r"charset\s*=\s*[\"']?([A-Za-z0-9_\-:.]+)", re.I)


def decode(payload, http_h, stats):
    if (http_h.get("content-encoding") or "").lower() == "gzip" and payload[:2] == b"\x1f\x8b":
        payload = gzip.decompress(payload)
        stats["gzip_decompressed"] += 1
    for source, cs in (("http", (HTTP_CHARSET.search(http_h.get("content-type") or "") or [None, None])[1]),
                       ("meta", (META_CHARSET.search(payload[:4096]) or [None, None])[1])):
        if cs:
            cs = cs.decode("ascii", "replace") if isinstance(cs, bytes) else cs
            try:
                text = payload.decode(cs, errors="replace")
                stats[f"charset_{source}"] += 1
                return text
            except LookupError:
                stats[f"charset_{source}_unknown"] += 1
    stats["charset_default_utf8"] += 1
    return payload.decode("utf-8", errors="replace")


def snapshot(path, stats):
    _, warc, _, http_h, payload = parse_record(path.read_bytes())
    if warc.get("warc-truncated"):
        stats["truncated"] += 1
    return extract_values(decode(payload, http_h, stats))


def delta_block(units, domains, label):
    """units: list of dicts (domain, flagged, vanished). Primary metric + domain-clustered CI."""
    order = sorted({u["domain"] for u in units if u["domain"] in domains})
    idx = {d: i for i, d in enumerate(order)}
    arr = {k: np.zeros(len(order)) for k in ("fn", "fv", "un", "uv")}
    for u in units:
        if u["domain"] not in idx:
            continue
        i = idx[u["domain"]]
        if u["flagged"]:
            arr["fn"][i] += 1
            arr["fv"][i] += u["vanished"]
        else:
            arr["un"][i] += 1
            arr["uv"][i] += u["vanished"]

    def stat(t):
        if t["fn"] == 0 or t["un"] == 0:
            return float("nan")
        return t["fv"] / t["fn"] - t["uv"] / t["un"]

    tot = {k: float(v.sum()) for k, v in arr.items()}
    point = stat(tot)
    if order and not math.isnan(point):
        draws = page_bootstrap(order, arr, stat, n_boot=N_BOOT, seed=SEED)
        fin = draws[np.isfinite(draws)]
        lo, hi = pct_ci(fin) if fin.size else (float("nan"), float("nan"))
        undefined = int(draws.size - fin.size)
    else:
        lo, hi, undefined = float("nan"), float("nan"), N_BOOT
    return {"label": label, "domains": len(order), "flagged": int(tot["fn"]), "flagged_vanished": int(tot["fv"]),
            "unflagged": int(tot["un"]), "unflagged_vanished": int(tot["uv"]),
            "p_vanish_flagged": tot["fv"] / tot["fn"] if tot["fn"] else float("nan"),
            "p_vanish_unflagged": tot["uv"] / tot["un"] if tot["un"] else float("nan"),
            "delta": point, "ci_lo": lo, "ci_hi": hi, "boot_undefined": undefined}


def main():
    plan = committed(PLAN_PATH)
    integ = json.loads((HERE / "fetch_integrity.json").read_text(encoding="utf-8"))
    valid = json.loads((HERE / "classifier_validation.json").read_text(encoding="utf-8"))
    pre = {"plan_committed_and_clean": bool(plan["sha"]) and plan["clean"],
           "integrity_200": integ.get("required_ok") == 200 and integ.get("digest_header_ok") == 200,
           "classifier_validation_passed": bool(valid.get("passed"))}
    if not all(pre.values()):
        raise SystemExit(f"[preconditions] not met: {pre}")
    guard = protected_state()
    cli_describe = build_cli()

    dry = json.loads((HERE / "dry_run.json").read_text(encoding="utf-8"))
    c_may, c_sep = dry["crawls"]
    stats = Counter()
    snaps = {}
    for q in dry["qualified_domains"]:
        d = q["domain"]
        snaps[d] = {"rank": q["rank"], "same_digest": q["same_digest"]}
        for c, key in ((c_may, "may"), (c_sep, "sep")):
            path = CACHE / "warc" / c / f"{q['rank']:04d}_{d}.warc.gz"
            snaps[d][key] = snapshot(path, stats)

    # Units (May), outcome (absent from Sept, same type)
    units = {t: [] for t in TYPES}
    for d, s in snaps.items():
        for ti, t in enumerate(TYPES):
            may, sep = s["may"][ti], s["sep"][ti]
            for v, cnt in may.items():
                units[t].append({"domain": d, "value": v, "may_count": cnt, "vanished": v not in sep})

    # Classifier of record (C# CLI) on all CC values; port cross-check on the same values
    all_pairs = {(t, v) for d, s in snaps.items() for ti, t in enumerate(TYPES)
                 for part in ("may", "sep") for v in s[part][ti]}
    flags = classify(all_pairs)
    port_dis = [{"t": t, "v": v, "cli": f, "port": port_flag(t, v)} for (t, v), f in flags.items()
                if port_flag(t, v) != f]
    if port_dis:
        out = {"stopped": "port vs CLI disagreement on Common Crawl values", "disagreements": port_dis[:200]}
        (HERE / "volatility_analysis.json").write_text(json.dumps(jsonable(out), indent=1) + "\n", encoding="utf-8")
        raise SystemExit(f"[STOP] port disagrees with CLI on {len(port_dis)} CC values")
    for t in TYPES:
        for u in units[t]:
            u["flagged"] = flags[(t, u["value"])]

    # Exclusion count (no manual removal)
    has = {t: {u["domain"] for u in units[t]} for t in TYPES}
    excl = {"no_class_units": sorted(set(snaps) - has["class"]), "no_id_units": sorted(set(snaps) - has["id"]),
            "no_class_and_no_id_units": sorted(set(snaps) - has["class"] - has["id"])}

    # Sensitivities
    same_digest = {d for d, s in snaps.items() if s["same_digest"]}
    jacc = {}
    for d, s in snaps.items():
        a, b = set(s["may"][0]), set(s["sep"][0])
        if not a and not b:
            jacc[d] = None
        elif not a or not b:
            jacc[d] = 0.0
        else:
            jacc[d] = len(a & b) / len(a | b)
    low_j = {d for d, j in jacc.items() if j is not None and j < 0.2}
    all_d = set(snaps)

    res = {}
    for t in TYPES:
        u = units[t]
        fl = [x for x in u if x["flagged"]]
        van = [x for x in u if x["vanished"]]
        fv = [x for x in fl if x["vanished"]]
        fnv = defaultdict(lambda: {"domains": set(), "may_count": 0})
        for x in fl:
            if not x["vanished"]:
                fnv[x["value"]]["domains"].add(x["domain"])
                fnv[x["value"]]["may_count"] += x["may_count"]
        fp_list = sorted(({"value": v, "domains": len(r["domains"]), "may_count": r["may_count"],
                           "domain_list": sorted(r["domains"])} for v, r in fnv.items()),
                         key=lambda r: (-r["domains"], -r["may_count"], r["value"]))
        res[t] = {
            "units": len(u), "domains_with_units": len(has[t]),
            "primary": delta_block(u, all_d, "all domains"),
            "precision": len(fv) / len(fl) if fl else float("nan"),
            "recall": len(fv) / len(van) if van else float("nan"),
            "flagged": len(fl), "vanished": len(van), "flagged_and_vanished": len(fv),
            "prevalence_domains_with_flagged": len({x["domain"] for x in fl}),
            "flagged_not_vanishing": fp_list,
            "sensitivity_a_without_identical_digest": delta_block(u, all_d - same_digest,
                                                                  f"without {len(same_digest)} identical-digest domains"),
            "sensitivity_b_without_class_jaccard_lt_0_2": delta_block(u, all_d - low_j,
                                                                     f"without {len(low_j)} domains with class "
                                                                     "Jaccard < 0.2"),
        }
        lo = res[t]["primary"]["ci_lo"]
        res[t]["interpretation"] = ("support (95% CI lower bound > 0)" if (not math.isnan(lo) and lo > 0)
                                    else "no support by the pre-registered criterion (95% CI lower bound ≤ 0 or "
                                         "undefined); reported as is")

    if protected_state() != guard:
        raise SystemExit("[guard] protected evidence files changed during the run")

    out = {"analysis_plan_commit": plan, "preconditions": pre, "cli": cli_describe,
           "crawls": {"may": c_may, "sep": c_sep}, "domains": len(snaps),
           "extraction_stats": dict(stats), "integrity_summary": {k: integ[k] for k in
                                                                  ("required_ok", "digest_header_ok",
                                                                   "digest_recomputed_ok", "target_uri_ok",
                                                                   "truncated", "content_encoding_gzip")},
           "classifier": {"validation_corpus": valid["agreement"], "cc_values_classified": len(flags),
                          "cc_port_disagreements": 0},
           "exclusion": excl, "identical_digest_domains": sorted(same_digest),
           "class_jaccard": jacc, "low_jaccard_domains": sorted(low_j), "results": res,
           "n_boot": N_BOOT, "seed": SEED}
    (HERE / "volatility_analysis.json").write_text(json.dumps(jsonable(out), indent=1, ensure_ascii=False) + "\n",
                                                   encoding="utf-8", newline="\n")
    write_md(out)
    for t in TYPES:
        p = res[t]["primary"]
        print(f"[{t}] Δ={p['delta']:.4f} CI=[{p['ci_lo']:.4f},{p['ci_hi']:.4f}] flagged={p['flagged']} "
              f"units={res[t]['units']} -> {res[t]['interpretation']}")


def f(x, d=3):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}f}"


def pct(x):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.1f}%"


def write_md(o):
    plan = o["analysis_plan_commit"]
    L = ["# Common Crawl Part A — volatility analysis (per analysis_plan.md)", "",
         f"- **analysis_plan.md commit `{plan['sha']}`** ({plan['committed']}; working copy clean: {plan['clean']}). "
         "Sampling rule: `sampling_rule.md` (commit `4cb40ce`).",
         f"- Crawls: May `{o['crawls']['may']}` → September `{o['crawls']['sep']}`; {o['domains']} domains "
         "(dry_run.json → qualified_domains).",
         f"- Integrity: required checks {o['integrity_summary']['required_ok']}/200; WARC-Payload-Digest == index "
         f"digest {o['integrity_summary']['digest_header_ok']}/200; recomputed SHA-1 "
         f"{o['integrity_summary']['digest_recomputed_ok']}/200; target URI {o['integrity_summary']['target_uri_ok']}"
         f"/200; WARC-Truncated {o['integrity_summary']['truncated']}; gzip Content-Encoding "
         f"{o['integrity_summary']['content_encoding_gzip']}.",
         f"- Classifier of record: C# CLI (reflection on `Oracle.IsVolatileClass` / `Oracle.IsVolatileId`, Oracle "
         f"source unchanged). Python port agreement: corpus {json.dumps(o['classifier']['validation_corpus'])}; "
         f"Common Crawl values {o['classifier']['cc_values_classified']}/{o['classifier']['cc_values_classified']}.",
         f"- Extraction: html.parser; decoding {json.dumps(o['extraction_stats'])} (HTTP charset → meta charset → "
         "UTF-8, errors replaced).",
         f"- Bootstrap: domain-clustered percentile, {o['n_boot']:,} replicates, seed {o['seed']}; clusters = domains "
         "with ≥1 unit of the type; replicates with undefined Δ are excluded and counted.",
         "- Limitation (pre-registered): Common Crawl stores server HTML, not the rendered DOM. Classes generated "
         "in the browser are missing, so prevalence is underestimated.", "",
         "## Primary metric: Δ = P(vanish | flagged) − P(vanish | unflagged)", ""]
    rows = []
    for t in TYPES:
        p = o["results"][t]["primary"]
        rows.append([t, p["domains"], f"{p['flagged_vanished']}/{p['flagged']} ({pct(p['p_vanish_flagged'])})",
                     f"{p['unflagged_vanished']}/{p['unflagged']} ({pct(p['p_vanish_unflagged'])})",
                     f"**{f(p['delta'])}**", f"[{f(p['ci_lo'])}, {f(p['ci_hi'])}]", p["boot_undefined"],
                     o["results"][t]["interpretation"]])
    L += md_table(["type", "domains", "flagged vanished", "unflagged vanished", "Δ", "95% CI",
                   "undefined replicates", "pre-registered interpretation"], rows)
    L += ["", "## Pre-specified sensitivity analyses", ""]
    rows = []
    for t in TYPES:
        for key in ("sensitivity_a_without_identical_digest", "sensitivity_b_without_class_jaccard_lt_0_2"):
            p = o["results"][t][key]
            rows.append([t, p["label"], p["domains"], f"{p['flagged_vanished']}/{p['flagged']}",
                         f"{p['unflagged_vanished']}/{p['unflagged']}", f(p["delta"]),
                         f"[{f(p['ci_lo'])}, {f(p['ci_hi'])}]", p["boot_undefined"]])
    L += md_table(["type", "sensitivity", "domains", "flagged vanished", "unflagged vanished", "Δ", "95% CI",
                   "undefined replicates"], rows)
    L += ["", f"- (a) identical-digest domains: {', '.join(o['identical_digest_domains']) or '(none)'}",
          f"- (b) class-token Jaccard < 0.2: {', '.join(o['low_jaccard_domains']) or '(none)'}", "",
          "## Secondary metrics", ""]
    L += md_table(["type", "units", "flagged", "vanished", "flagged ∩ vanished", "precision", "recall",
                   "prevalence (domains with ≥1 flagged)"],
                  [[t, r["units"], r["flagged"], r["vanished"], r["flagged_and_vanished"], pct(r["precision"]),
                    pct(r["recall"]), f"{r['prevalence_domains_with_flagged']} of {r['domains_with_units']}"]
                   for t, r in o["results"].items()])
    L += ["", "## Exclusion (count only; no manual removal)", "",
          f"- Domains with no class units: {len(o['exclusion']['no_class_units'])}; with no id units: "
          f"{len(o['exclusion']['no_id_units'])}; with neither: {len(o['exclusion']['no_class_and_no_id_units'])}."]
    for t in TYPES:
        lst = o["results"][t]["flagged_not_vanishing"]
        L += ["", f"## Flagged values that do not vanish — {t} (top 50 of {len(lst)}; full list in the json)", "",
              "Ordered by number of domains holding the value, then by May occurrences.", ""]
        L += md_table(["#", "value", "domains", "May occurrences", "domains (first 5)"],
                      [[i + 1, f"`{r['value']}`", r["domains"], r["may_count"], ", ".join(r["domain_list"][:5])]
                       for i, r in enumerate(lst[:50])]) if lst else ["(none)"]
    (HERE / "volatility_analysis.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
