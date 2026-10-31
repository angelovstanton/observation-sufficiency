"""
rp_common.py — shared helpers for the real-site pilot preparation (pilot_rule.md, pilot_analysis_plan.md).

- run_mode(mode, input, out_dir): runs the C# adapter (experiments/modes/RealPilotMode.cs, REAL_PILOT=<mode>)
- decoded May/Sept HTML from the cached WARC records (cc_volatility decoding, unchanged)
- the selection functions of pilot_rule.md §3–§5 and §7 (on the rp_candidates.js output)

Raw and decoded HTML, probe output and step-1 dumps live only under ../_external/cc_cache/real_pilot/.
No network, no LLM.
"""

import hashlib
import json
import os
import re
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
CCV = HERE.parent / "cc_volatility"
sys.path.insert(0, str(CCV))
from cc_common import (REPO, CACHE, ASCII_WS, build_cli, classify, extract_values,  # noqa: E402,F401
                       committed, md_table)
from cc_fetch_warc import parse_record                                                    # noqa: E402
import cc_volatility_analysis as CVA                                                      # noqa: E402

RP_CACHE = CACHE / "real_pilot"
HTML_DIR = RP_CACHE / "html"
STABLE_ATTRS = ("id", "data-testid", "aria-label", "name", "placeholder", "href")   # pilot_rule.md §7
FILL_ROLES = {"textbox", "searchbox", "spinbutton", "combobox", "listbox"}          # pilot_rule.md §5
INPUT_ROLE = {**{t: "button" for t in ("button", "submit", "reset", "image", "file", "color")},
              "checkbox": "checkbox", "radio": "radio", "range": "slider", "number": "spinbutton",
              "search": "searchbox"}
PROMPT_CAP = 128_000                                                                 # pilot_rule.md §2 (г)
MAX_TARGETS, MIN_TARGETS = 10, 5


def dry_run():
    return json.loads((CCV / "dry_run.json").read_text(encoding="utf-8"))


def site_key(q):
    return f"{q['rank']:04d}_{q['domain']}"


def decoded_html(crawl, q, stats):
    """Decode the cached WARC payload exactly as cc_volatility; cache the UTF-8 text under RP_CACHE."""
    out = HTML_DIR / crawl / f"{site_key(q)}.html"
    raw = (CACHE / "warc" / crawl / f"{site_key(q)}.warc.gz").read_bytes()
    _, warc, _, http_h, payload = parse_record(raw)
    if warc.get("warc-truncated"):
        stats["warc-truncated"] += 1
    html = CVA.decode(payload, http_h, stats)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8", newline="")
    return html, out, warc["warc-target-uri"]


def ts_iso(ts14):
    return f"{ts14[0:4]}-{ts14[4:6]}-{ts14[6:8]}T{ts14[8:10]}:{ts14[10:12]}:{ts14[12:14]}Z"


def run_mode(mode, payload, out_dir, log_name):
    """Run the C# adapter once (own process; PID logged). Returns the exit code."""
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, REAL_PILOT=mode, BAR_RP_OUT=str(out_dir))
    if payload is not None:
        inp = out_dir / "input.json"
        inp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        env["BAR_RP_INPUT"] = str(inp)
    with open(out_dir / log_name, "w", encoding="utf-8") as log:
        p = subprocess.Popen(["dotnet", "run", "--project", str(REPO / "experiments"), "--no-build"],
                             cwd=str(REPO), env=env, stdout=log, stderr=subprocess.STDOUT)
        print(f"[adapter] {mode} pid={p.pid} -> {out_dir}", flush=True)
        return p.wait()


def read_tsv(path):
    lines = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    return [dict(zip(head, ln.split("\t"))) for ln in lines[1:] if ln]


# pilot_rule.md §5: role table and task template
def role_of(c):
    tok = (c.get("roleAttr") or "").strip().split()
    if tok:
        return tok[0].lower()
    t = c["tag"]
    if t == "a":
        return "link"
    if t == "button":
        return "button"
    if t == "select":
        return "listbox" if c.get("multiple") or (c.get("size") or 0) > 1 else "combobox"
    if t == "textarea":
        return "textbox"
    if t == "input":
        return INPUT_ROLE.get(c.get("type") or "", "textbox")
    raise ValueError(f"no role for {t}")


def task_of(role, name):
    return f"{'Fill' if role in FILL_ROLES else 'Click'} the {role} labelled '{name}'"


# pilot_rule.md §3–§4: eligible targets and selection
def eligible_targets(candidates):
    """Candidates (rp_candidates.js output, already kind- and visibility-filtered) -> eligible list."""
    named = [c for c in candidates if 1 <= c["nameLength"] <= 80]
    counts = {}
    for c in named:
        k = c["name"].casefold()
        counts[k] = counts.get(k, 0) + 1
    return [c for c in named if counts[c["name"].casefold()] == 1]


def target_key(domain, xpath):
    return hashlib.sha256(f"{domain}|{xpath}".encode("utf-8")).hexdigest()


def select_targets(domain, eligible):
    keyed = sorted(((target_key(domain, c["xpath"]), c) for c in eligible), key=lambda kc: kc[0])
    return keyed[:MAX_TARGETS]


# pilot_rule.md §6–§7: Oracle lists, signal_attrs, stratum
def class_tokens_both(value):
    """ASCII-whitespace tokens and single-space tokens (the bundle code splits on ' ')."""
    toks = {t for t in ASCII_WS.split(value) if t}
    toks |= {t for t in value.split(" ") if t}
    return toks


def oracle_lists(class_attrs, ids):
    pairs = {("class", t) for v in class_attrs for t in class_tokens_both(v)} | {("id", v) for v in ids}
    flags = classify(pairs)
    vol_cls = sorted(v for (t, v), f in flags.items() if t == "class" and f)
    vol_ids = sorted(v for (t, v), f in flags.items() if t == "id" and f)
    return vol_ids, vol_cls, flags


def signal_attrs(attrs, vol_ids):
    out = []
    for a in STABLE_ATTRS:
        v = attrs.get(a)
        if v is None or v == "":
            continue
        if a == "id" and v in vol_ids:
            continue
        out.append(a)
    return out
