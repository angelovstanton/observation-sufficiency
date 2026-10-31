"""
Exploratory analysis of the real-site pilot. Not pre-registered; computed after the registered results
(f6a00d3: pilot_analysis.{json,md}, pilot_survival.tsv). Zero LLM, zero network, no browser.
Pins and record checks are reused from revision1_pilot_analysis.py; nothing here feeds the registered claim.

  1. Survival by May outcome: per cell, share survived among determined locators with P5 = true vs false (and
     P_now); Wilson 95% CI per share, Newcombe hybrid-score 95% CI for the difference.
  2. Why the 353 broken locators broke: locator kind × what changed between the May and September target element.
     Element attributes come from the offline probes (RP_CACHE/probe, RP_CACHE/survival_probe_1); only interactive
     candidates are known, so the CSS is matched against the target and the candidates, not the whole DOM.
     The probes hold page text and are not redistributed; without them only this breakdown is skipped (the counts of
     broken locators and of those already wrong in May come from the records).
  3. Leave-one-site-out of the primary Δ P5 (B_noVolatile − B_full, "has stable signal"), F1 and F3; per-site signs.
  4. Paired survival: McNemar B_full vs B_noVolatile on the same target (both determined), F1 and F3.
  5. Mean tokens per cell (observation_tokens, o200k_base; API prompt tokens) and the % saving F3 vs F1 and
     B_noVolatile vs B_full.
  6. Survival among locators correct in May (P_now = true): P5 = true vs false; Newcombe CI, Fisher exact p.
  7. COP (B_noVolatile × F3) vs B_full × F1, paired, "has stable signal": P5, P_now (McNemar, site-clustered
     bootstrap 10,000 / seed 42) and input tokens.

Output: experiments/results/revision1/pilot_exploratory.{md,json}
"""
import collections
import hashlib
import json
import math
import pathlib
import re
import sys

import numpy as np
from scipy.stats import fisher_exact, norm

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import revision1_pilot_analysis as PA  # noqa: E402
from revision1_diagnostics import GRABBED, fmt_or, fmt_p, jsonable, mcnemar, md_table  # noqa: E402

RP_CACHE = HERE.parents[1].parent / "_external" / "cc_cache" / "real_pilot"
MAY_PROBE, SEPT_PROBE = RP_CACHE / "probe", RP_CACHE / "survival_probe_1"
OUT_PREFIX = PA.OUT_DIR / "pilot_exploratory"
REGISTERED_COMMIT = "f6a00d3"
PROBES_MISSING = ("Breakdown by locator kind and change skipped: it needs the probe files of the archived pages "
                  "(RP_CACHE probe/, survival_probe_1/), which are not redistributed")
SURVIVAL_TSV_SHA = None   # filled from the file; reported, not pinned (the registered output is the pin)
LABEL = f"EXPLORATORY — not pre-registered, computed after the registered results ({REGISTERED_COMMIT})"
Z = norm.ppf(0.975)


# 1. Wilson / Newcombe

def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def newcombe(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float, float]:
    """Δ = p1 − p2 and its Newcombe (1998, method 10) hybrid-score 95% CI from the two Wilson intervals."""
    if n1 == 0 or n2 == 0:
        return float("nan"), float("nan"), float("nan")
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    return d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


# 2. CSS (the subset the model emitted) against probe candidates

ATTR_RE = re.compile(r"""\[\s*([\w:-]+)\s*(?:([~|^$*]?=)\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|[^\]\s]+)\s*([iIsS])?)?\s*\]""")
TEXT_PSEUDO = ("contains", "has-text", "text", "text-is")
POSITIONAL = ("nth-child", "nth-of-type", "first-child", "last-child", "nth-last-child", "first-of-type",
              "last-of-type", "only-child", "eq", "nth", "first", "last")


def split_top(s: str, seps: str) -> list[tuple[str, str]]:
    """Split at top level (outside [], (), quotes) on any char in seps; returns [(sep_before, part)]."""
    out, cur, depth, q, sep = [], "", 0, None, ""
    i = 0
    while i < len(s):
        ch = s[i]
        if q:
            cur += ch
            if ch == "\\" and i + 1 < len(s):
                cur += s[i + 1]; i += 1
            elif ch == q:
                q = None
        elif ch in "\"'":
            q = ch; cur += ch
        elif ch in "[(":
            depth += 1; cur += ch
        elif ch in "])":
            depth -= 1; cur += ch
        elif depth == 0 and ch in seps:
            if cur.strip():
                out.append((sep, cur.strip()))
                sep = ""
            if ch.strip():
                sep = ch
            elif not sep:
                sep = " "
            cur = ""
        else:
            cur += ch
        i += 1
    if cur.strip():
        out.append((sep, cur.strip()))
    return out


def unquote(v: str) -> str:
    if v and v[0] in "\"'" and v[-1] == v[0]:
        v = v[1:-1]
    return re.sub(r"\\(.)", r"\1", v)


def parse_compound(c: str) -> dict:
    """tag, ids, classes, attrs [(name, op, value, ci)], text [values], pseudos [names], nots [compound dicts]."""
    out = {"tag": None, "ids": [], "classes": [], "attrs": [], "text": [], "pseudos": [], "nots": [], "has": False}
    rest = c
    for m in ATTR_RE.finditer(c):
        name, op, val, flag = m.group(1).lower(), m.group(2), m.group(3), m.group(4)
        out["attrs"].append((name, op, unquote(val) if val is not None else None, (flag or "").lower() == "i"))
    rest = ATTR_RE.sub(" ", rest)
    # pseudos with balanced arguments
    i = 0
    plain = ""
    while i < len(rest):
        if rest[i] == ":" and (i + 1 < len(rest)):
            j = i + 1
            if j < len(rest) and rest[j] == ":":
                j += 1
            m = re.match(r"[\w-]+", rest[j:])
            name = m.group(0).lower() if m else ""
            j += len(name)
            arg = None
            if j < len(rest) and rest[j] == "(":
                depth, k = 0, j
                while k < len(rest):
                    if rest[k] == "(":
                        depth += 1
                    elif rest[k] == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    k += 1
                arg = rest[j + 1:k]
                j = k + 1
            if name in TEXT_PSEUDO and arg is not None:
                out["text"].append(unquote(arg.strip()))
            elif name == "not" and arg is not None:
                out["nots"] += [parse_compound(a) for _, a in split_top(arg, ",")]
            elif name == "has":
                out["has"] = True
            out["pseudos"].append(name)
            i = j
        else:
            plain += rest[i]; i += 1
    m = re.match(r"\s*([a-zA-Z][\w-]*|\*)", plain)
    if m:
        out["tag"] = m.group(1).lower()
    out["ids"] = [unquote(x) for x in re.findall(r"#((?:\\.|[\w-])+)", plain)]
    out["classes"] = [unquote(x) for x in re.findall(r"\.((?:\\.|[\w-])+)", plain)]
    for name, op, val, ci in list(out["attrs"]):
        if name == "text" and op == "=":     # the model's pseudo-attribute [text="…"]
            out["text"].append(val)
    return out


def attr_ok(have: str | None, op: str | None, val: str | None, ci: bool) -> bool:
    if have is None:
        return False
    if op is None:
        return True
    h, v = (have.lower(), val.lower()) if ci else (have, val)
    return {"=": h == v, "~=": v in h.split(), "|=": h == v or h.startswith(v + "-"), "^=": bool(v) and h.startswith(v),
            "$=": bool(v) and h.endswith(v), "*=": bool(v) and v in h}[op]


def compound_ok(p: dict, el: dict) -> bool:
    """Does the parsed compound match the element (tag, attrs, name)? Structural pseudos are ignored here."""
    a = {k.lower(): v for k, v in el["attrs"].items() if not k.startswith("$")}
    if p["tag"] not in (None, "*") and p["tag"] != el["tag"]:
        return False
    if any(a.get("id") != i for i in p["ids"]):
        return False
    cls = (a.get("class") or "").split()
    if any(c not in cls for c in p["classes"]):
        return False
    for name, op, val, ci in p["attrs"]:
        if name == "text":
            continue
        if not attr_ok(a.get(name), op, val, ci):
            return False
    if any(t not in (el.get("name") or "") for t in p["text"]):
        return False
    if any(compound_ok(n, el) for n in p["nots"]):
        return False
    return True


def kind_of(p: dict) -> str:
    """The signals the locator uses on the target element, joined in the order id, data (data-*), aria (aria-* /
    role), attr (any other attribute: href, title, alt, placeholder, …), class, text; "structural" if none (tag /
    position / ancestors only)."""
    names = [n for n, *_ in p["attrs"] if n != "text"]
    used = []
    if p["ids"] or "id" in names:
        used.append("id")
    if any(n.startswith("data-") for n in names):
        used.append("data")
    if any(n.startswith("aria-") or n == "role" for n in names):
        used.append("aria")
    if any(n not in ("id", "class", "role") and not n.startswith(("data-", "aria-")) for n in names):
        used.append("attr")
    if p["classes"] or "class" in names:
        used.append("class")
    if p["text"]:
        used.append("text")
    return "+".join(used) or "structural"


CHANGES = ["wrong already in May (P_now false)", "attribute missing in September", "attribute value changed",
           "text changed", "parent / position changed", "no longer unique (another element matches)",
           "unclassified (target still matches; non-candidate element)"]


def target_compound(locator: str, may_el: dict):
    """The alternative and compound of the locator that address the May target: the first selector-list alternative
    whose rightmost compound with the target's tag (or no tag) matches the May target. Falls back to the first
    alternative's last compound. Returns (parsed compound, structural: bool, alternative)."""
    alts = [a for _, a in split_top(locator, ",")]
    best = None
    for alt in alts:
        parts = split_top(alt, " >+~")
        comps = [parse_compound(c) for _, c in parts]
        structural = len(parts) > 1 or any(ps in POSITIONAL or ps == "has" for c in comps for ps in c["pseudos"])
        for c in reversed(comps):
            if c["tag"] in (None, "*", may_el["tag"]):
                if compound_ok(c, may_el):
                    return c, structural, alt
                if best is None:
                    best = (c, structural, alt)
                break
    if best is None:
        parts = split_top(alts[0], " >+~")
        best = (parse_compound(parts[-1][1]), True, alts[0])
    return best


def parent_of(xpath: str) -> str:
    return xpath.rsplit("/", 1)[0]


def why_broken(r: dict, may_el: dict, sept_el: dict, sept_cands: list[dict]) -> tuple[str, str, dict]:
    loc = r["locator_raw"].split(":", 1)[1] if r["locator_raw"].startswith("css:") else r["locator_raw"]
    c, structural, _ = target_compound(loc, may_el)
    kind = kind_of(c)
    detail = {}
    if not r["P_now"]:
        return kind, CHANGES[0], detail
    ma = {k.lower(): v for k, v in may_el["attrs"].items() if not k.startswith("$")}
    sa = {k.lower(): v for k, v in sept_el["attrs"].items() if not k.startswith("$")}
    used = [("id", None, i, False) for i in c["ids"]] + [(n, op, v, ci) for n, op, v, ci in c["attrs"] if n != "text"]
    for cl in c["classes"]:
        used.append(("class", "~=", cl, False))
    missing = [n for n, op, v, ci in used if attr_ok(ma.get(n), op, v, ci) and sa.get(n) is None]
    if missing:
        detail["attrs"] = sorted(set(missing))
        return kind, CHANGES[1], detail
    changed = [n for n, op, v, ci in used if attr_ok(ma.get(n), op, v, ci) and not attr_ok(sa.get(n), op, v, ci)]
    if changed:
        detail["attrs"] = sorted(set(changed))
        return kind, CHANGES[2], detail
    if any(t not in (sept_el.get("name") or "") for t in c["text"]):
        return kind, CHANGES[3], detail
    others = [x for x in sept_cands if x["xpath"] != sept_el["xpath"] and compound_ok(c, x)]
    if structural and (parent_of(may_el["xpath"]) != parent_of(sept_el["xpath"])
                       or may_el["xpath"].rsplit("/", 1)[1] != sept_el["xpath"].rsplit("/", 1)[1]):
        return kind, CHANGES[4], detail
    if others:
        detail["other_matches"] = len(others)
        return kind, CHANGES[5], detail
    if structural:
        return kind, CHANGES[4], detail
    return kind, CHANGES[6], detail


# data

def load():
    pin = PA.load_pinned()
    recs, exp = PA.load_records(PA.RECORDS_DIR, pin)
    rows = PA.outcome_rows(recs, exp, pin)
    by_key = {r["event_key"]: r for r in rows.values()}
    tsv = PA.SURVIVAL_TSV
    lines = tsv.read_text(encoding="utf-8").splitlines()
    assert lines[0] == PA.SURVIVAL_HEADER
    surv = {}
    for ln in lines[1:]:
        k, lsha, um, mt, status, *_ = ln.split("\t")
        assert lsha == hashlib.sha256(by_key[k]["locator_raw"].encode("utf-8")).hexdigest(), k
        surv[k] = status
    return pin, recs, rows, by_key, surv, PA.sha256(tsv)


def probe(dir_: pathlib.Path, key: str) -> dict:
    return json.loads((dir_ / f"{key}.probe.json").read_text(encoding="utf-8"))


def probes_sha(dir_: pathlib.Path, keys) -> str:
    h = hashlib.sha256()
    for k in sorted(keys):
        h.update(k.encode() + b"\0" + hashlib.sha256((dir_ / f"{k}.probe.json").read_bytes()).digest())
    return h.hexdigest()


# analyses

def survival_by_outcome(rows, surv, stratum=None):
    out = []
    for enc in PA.ENCODINGS:
        for cell in PA.CELLS:
            sel = [r for (p, t, e, c), r in rows.items() if e == enc and c == cell and surv.get(r["event_key"]) in
                   ("survived", "broken") and (stratum is None or r["stratum"] == stratum)]
            for m in PA.METRICS:
                t = [r for r in sel if r[m]]
                f = [r for r in sel if not r[m]]
                kt = sum(surv[r["event_key"]] == "survived" for r in t)
                kf = sum(surv[r["event_key"]] == "survived" for r in f)
                d, lo, hi = newcombe(kt, len(t), kf, len(f))
                out.append({"encoding": enc, "cell": cell, "metric": m, "n_true": len(t), "survived_true": kt,
                            "share_true": kt / len(t) * 100 if t else float("nan"),
                            "ci_true": [x * 100 for x in wilson(kt, len(t))], "n_false": len(f), "survived_false": kf,
                            "share_false": kf / len(f) * 100 if f else float("nan"),
                            "ci_false": [x * 100 for x in wilson(kf, len(f))],
                            "diff_pp": d * 100, "diff_ci": [lo * 100, hi * 100]})
    return out


def broken_summary(rows, surv):
    broken = [r for r in rows.values() if surv.get(r["event_key"]) == "broken"]
    per_cell = collections.Counter(f"{r['encoding']}|{r['cell']}" for r in broken)
    return {"broken": len(broken), "wrong_in_may": sum(not r["P_now"] for r in broken),
            "per_cell": {f"{e}|{c}": per_cell[f"{e}|{c}"] for e in PA.ENCODINGS for c in PA.CELLS},
            "per_site": dict(collections.Counter(r["page"] for r in broken).most_common())}


def probe_inputs(inputs) -> str:
    if inputs.get("may_probes_sha256") is None:
        return "May / September probe candidates not available"
    return (f"May / September probe candidates (RP_CACHE `probe/`, `survival_probe_1/`; combined sha256 "
            f"`{inputs['may_probes_sha256'][:16]}…` / `{inputs['sept_probes_sha256'][:16]}…`)")


def broken_reasons(pin, rows, surv):
    st = json.loads((PA.RP_DIR / "survival_targets.json").read_text(encoding="utf-8"))
    sept_x = {(f"{t['rank']:04d}_{t['domain']}", t["marker"]): t["sept_xpath"] for t in st["items"] if t["status"] == "unique"}
    tg = json.loads((PA.RP_DIR / "targets.json").read_text(encoding="utf-8"))["items"]
    may_x = {(f"{t['rank']:04d}_{t['domain']}", t["marker"]): t["xpath"] for t in tg}
    cache_may, cache_sept = {}, {}
    out = []
    for r in rows.values():
        if surv.get(r["event_key"]) != "broken":
            continue
        site, task = r["page"], r["task_id"]
        if site not in cache_may:
            cache_may[site] = {c["xpath"]: c for c in probe(MAY_PROBE, site)["candidates"]["candidates"]}
            cache_sept[site] = probe(SEPT_PROBE, site)["candidates"]["candidates"]
        may_el = cache_may[site][may_x[(site, task)]]
        sept_cands = cache_sept[site]
        sept_el = next(c for c in sept_cands if c["xpath"] == sept_x[(site, task)])
        kind, change, detail = why_broken(r, may_el, sept_el, sept_cands)
        out.append({"event_key": r["event_key"], "site": site, "task_id": task, "encoding": r["encoding"],
                    "cell": r["cell"], "P5": r["P5"], "P_now": r["P_now"], "kind": kind, "change": change, **detail})
    return out, sorted(cache_may)


def delta_p5(rows, enc, sites=None):
    p = PA.pairs_of(rows, "B_full", "B_noVolatile", enc, PA.HAS)
    p = [x for x in p if sites is None or x[0] in sites]
    a = np.array([x[2]["P5"] for x in p]); b = np.array([x[3]["P5"] for x in p])
    return (b.sum() - a.sum()) / len(p) * 100, len(p), p


def loso(rows, site_order):
    out = {}
    for enc in PA.ENCODINGS:
        full, n, pairs = delta_p5(rows, enc)
        drops = []
        for s in site_order:
            d, m, _ = delta_p5(rows, enc, set(site_order) - {s})
            drops.append({"left_out": s, "delta_pp": d, "n": m, "shift_pp": d - full})
        per_site = collections.defaultdict(lambda: [0, 0, 0])
        for site, task, a, b in pairs:
            per_site[site][0] += 1; per_site[site][1] += a["P5"]; per_site[site][2] += b["P5"]
        sign = collections.Counter()
        site_rows = []
        for s in site_order:
            n_s, f, sec = per_site[s]
            d = sec - f
            sign["> 0" if d > 0 else ("= 0" if d == 0 else "< 0")] += 1
            site_rows.append({"site": s, "n": n_s, "B_full": f, "B_noVolatile": sec, "delta_count": d})
        out[enc] = {"full_delta_pp": full, "n": n, "loso": drops,
                    "min": min(drops, key=lambda x: x["delta_pp"]), "max": max(drops, key=lambda x: x["delta_pp"]),
                    "sign": dict(sign), "per_site": site_rows}
    return out


def survival_paired(rows, surv):
    out = []
    for enc in PA.ENCODINGS:
        a, b, n_pairs = [], [], 0
        for (p, t, e, c), r in rows.items():
            if e != enc or c != "B_full":
                continue
            o = rows.get((p, t, enc, "B_noVolatile"))
            if o is None:
                continue
            sa, sb = surv.get(r["event_key"]), surv.get(o["event_key"])
            if sa in ("survived", "broken") and sb in ("survived", "broken"):
                a.append(sa == "survived"); b.append(sb == "survived")
        res = mcnemar(np.array(a), np.array(b))
        out.append({"encoding": enc, **res})
    return out


def tokens(rows, recs):
    out = {}
    for enc in PA.ENCODINGS:
        for cell in PA.CELLS:
            sel = [r for (p, t, e, c), r in rows.items() if e == enc and c == cell]
            called = [r for r in sel if not r["reused"]]
            out[(enc, cell)] = {"n": len(sel), "obs_mean": float(np.mean([r["observation_tokens"] for r in sel])),
                                "obs_median": float(np.median([r["observation_tokens"] for r in sel])),
                                "n_called": len(called),
                                "prompt_mean_called": float(np.mean([r["prompt_tokens"] for r in called])) if called else float("nan")}
    # per-target savings (same target), median as a robustness view of the mean-based saving
    paired = {}
    for cell in PA.CELLS:
        r = [1 - rows[(p, t, "F3", cell)]["observation_tokens"] / rows[(p, t, "F1", cell)]["observation_tokens"]
             for (p, t, e, c) in rows if e == "F1" and c == cell]
        paired[f"F3 vs F1, {cell}"] = float(np.median(r) * 100)
    for enc in PA.ENCODINGS:
        for second in ("B_noVolatile", "class_only"):
            r = [1 - rows[(p, t, enc, second)]["observation_tokens"] / rows[(p, t, enc, "B_full")]["observation_tokens"]
                 for (p, t, e, c) in rows if e == enc and c == "B_full"]
            paired[f"{second} vs B_full, {enc}"] = float(np.median(r) * 100)
    return out, paired


def survival_correct_in_may(rows, surv):
    """6: determined locators with P_now = true in May; survival of P5 = true vs P5 = false."""
    def block(sel, label_enc, label_cell, scope):
        t = [r for r in sel if r["P5"]]
        f = [r for r in sel if not r["P5"]]
        kt = sum(surv[r["event_key"]] == "survived" for r in t)
        kf = sum(surv[r["event_key"]] == "survived" for r in f)
        d, lo, hi = newcombe(kt, len(t), kf, len(f))
        p = float(fisher_exact([[kt, len(t) - kt], [kf, len(f) - kf]])[1]) if t and f else float("nan")
        return {"encoding": label_enc, "cell": label_cell, "scope": scope, "n_true": len(t), "survived_true": kt,
                "share_true": kt / len(t) * 100 if t else float("nan"), "n_false": len(f), "survived_false": kf,
                "share_false": kf / len(f) * 100 if f else float("nan"), "diff_pp": d * 100,
                "diff_ci": [lo * 100, hi * 100], "fisher_p": p,
                "p5_false_failure_modes": dict(collections.Counter(r["failure_mode"] for r in f)),
                "p5_false_no_signal": sum(r["stratum"] != PA.HAS for r in f)}
    det = [r for r in rows.values() if r["P_now"] and surv.get(r["event_key"]) in ("survived", "broken")]
    out = [block([r for r in det if r["encoding"] == e and r["cell"] == c], e, c, "all strata")
           for e in PA.ENCODINGS for c in PA.CELLS]
    out.append(block(det, "all", "all cells", "all strata"))
    out.append(block([r for r in det if r["stratum"] == PA.HAS], "all", "all cells", "has stable signal"))
    return out


def cop_vs_naive(rows, site_order):
    """7: B_noVolatile × F3 (COP) vs B_full × F1 (naive), same target, stratum "has stable signal"."""
    pairs = sorted(((p, t, r, rows[(p, t, "F3", "B_noVolatile")]) for (p, t, e, c), r in rows.items()
                    if e == "F1" and c == "B_full" and r["stratum"] == PA.HAS), key=lambda x: (x[0], x[1]))
    out = {"n": len(pairs), "metrics": {}}
    for m in PA.METRICS:
        a = np.array([x[2][m] for x in pairs], dtype=bool)
        b = np.array([x[3][m] for x in pairs], dtype=bool)
        res = mcnemar(a, b)
        res.update(PA.site_bootstrap(site_order, [(x[0], bool(x[2][m]), bool(x[3][m])) for x in pairs]))
        out["metrics"][m] = res
    for lab, key in (("obs", "observation_tokens"), ("prompt", "prompt_tokens")):
        naive = np.array([x[2][key] for x in pairs], dtype=float)
        cop = np.array([x[3][key] for x in pairs], dtype=float)
        out[lab] = {"naive_mean": float(naive.mean()), "naive_median": float(np.median(naive)),
                    "cop_mean": float(cop.mean()), "cop_median": float(np.median(cop)),
                    "saving_mean_pct": float((1 - cop.mean() / naive.mean()) * 100),
                    "saving_median_per_target_pct": float(np.median(1 - cop / naive) * 100)}
    return out


# render

def f1(x):
    return "n/a" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.1f}"


def ci1(lo, hi):
    return "n/a" if math.isnan(lo) else f"[{lo:.1f}, {hi:.1f}]"


def cid(lo, hi):
    return "n/a" if math.isnan(lo) else f"[{lo:+.1f}, {hi:+.1f}]"


def broken_breakdown(br) -> list[str]:
    L = ["Locator kind = the signals the locator uses on the target element: id, data (data-*), aria (aria-* / role), "
         "attr (any other attribute: href, title, alt, placeholder, …), class, text; structural = none of these. "
         "Change = the first that holds, in this order: the locator was not "
         "P_now in May (it never resolved uniquely to the target); a used attribute present on the May target is "
         "absent on the September target; its value no longer satisfies the locator; the text condition fails; the "
         "locator has ancestors / position and the target's parent or index changed; another September candidate "
         "matches the target compound; otherwise unclassified. Attributes from the probe candidates (interactive "
         "elements only); ancestors are compared by XPath only.", ""]
    ct = collections.Counter((b["kind"], b["change"]) for b in br)
    kinds = [k for k, _ in collections.Counter(b["kind"] for b in br).most_common()]
    short = ["wrong in May", "attr missing", "value changed", "text changed", "parent / position", "not unique",
             "unclassified"]
    L += ["Columns: " + "; ".join(f"{a} = {b}" for a, b in zip(short, CHANGES)) + ".", ""]
    L += md_table(["kind \\ change", *short, "total"],
                  [[k, *[ct[(k, ch)] for ch in CHANGES], sum(ct[(k, ch)] for ch in CHANGES)] for k in kinds] +
                  [["**total**", *[sum(ct[(k, ch)] for k in kinds) for ch in CHANGES], len(br)]])
    L += ["", "Broken locators that were correct in May (P_now true): " +
          ", ".join(f"{s} {sum(ct[(k, ch)] for k in kinds)}" for s, ch in zip(short[1:], CHANGES[1:])) + "."]
    attrs = collections.Counter(a for b in br if b["change"] in CHANGES[1:3] for a in b.get("attrs", []))
    L += ["", f"Attributes behind \"missing\" / \"value changed\": {dict(attrs.most_common())}.", ""]
    return L


def render(res) -> str:
    L = [f"# Real-site pilot — exploratory analysis", "", f"**{LABEL}.**", "",
         "Not part of the registered analysis (`pilot_analysis.md`); no new model calls; the registered script is "
         "unchanged. Inputs: records `batch_runs_pilot/` (pins and checks of `revision1_pilot_analysis.py`), "
         f"`pilot_survival.tsv` (sha256 `{res['inputs']['survival_tsv_sha256']}`), " + probe_inputs(res["inputs"]) +
         ". Determined survival = survived + broken (no-reference drom.ru and undefined targets excluded).", ""]

    L += ["## 1. Survival by May outcome", "",
          "Share survived (%) among determined locators whose May record had the predicate true vs false. Wilson 95% "
          "CI per share; difference (true − false, pp) with the Newcombe hybrid-score 95% CI. All strata.", ""]
    for m in PA.METRICS:
        L += [f"**{m}**", ""]
        L += md_table(["enc", "cell", f"n {m}=T", "surv % (CI)", f"n {m}=F", "surv % (CI)", "Δ pp [95% CI]"],
                      [[x["encoding"], x["cell"], x["n_true"], f"{f1(x['share_true'])} {ci1(*x['ci_true'])}",
                        x["n_false"], f"{f1(x['share_false'])} {ci1(*x['ci_false'])}",
                        f"{x['diff_pp']:+.1f} {cid(*x['diff_ci'])}"]
                       for x in res["survival_by_outcome"] if x["metric"] == m])
        L += [""]
    L += ["Same, stratum \"has stable signal\" only (P5):", ""]
    L += md_table(["enc", "cell", "n P5=T", "surv % (CI)", "n P5=F", "surv % (CI)", "Δ pp [95% CI]"],
                  [[x["encoding"], x["cell"], x["n_true"], f"{f1(x['share_true'])} {ci1(*x['ci_true'])}",
                    x["n_false"], f"{f1(x['share_false'])} {ci1(*x['ci_false'])}", f"{x['diff_pp']:+.1f} {cid(*x['diff_ci'])}"]
                   for x in res["survival_by_outcome_has_signal"] if x["metric"] == "P5"])

    bsum = res["broken_summary"]
    L += ["", f"## 2. Why {bsum['broken']} locators broke", "",
          f"{bsum['broken']} locators broke on the September pages; {bsum['wrong_in_may']} of them were already wrong "
          "in May (P_now false).", ""]
    bc, bs = bsum["per_cell"], collections.Counter(bsum["per_site"])
    L += ["Broken per cell: " + ", ".join(f"{e} {c} {bc[f'{e}|{c}']}" for e in PA.ENCODINGS for c in PA.CELLS) + ".", ""]
    L += ["Broken per site (top 10): " + ", ".join(f"{s} {n}" for s, n in bs.most_common(10)) + ".", ""]
    br = res["broken"]
    if br is None:
        L += [PROBES_MISSING + ".", ""]
    else:
        L += broken_breakdown(br)


    L += ["## 3. Leave-one-site-out — Δ P5 (B_noVolatile − B_full), stratum \"has stable signal\"", ""]
    rows3 = []
    for enc, x in res["loso"].items():
        top = sorted(x["loso"], key=lambda d: d["shift_pp"])[:3]
        rows3.append([enc, x["n"], f"{x['full_delta_pp']:+.2f}",
                      f"{x['min']['delta_pp']:+.2f} (without {x['min']['left_out']})",
                      f"{x['max']['delta_pp']:+.2f} (without {x['max']['left_out']})",
                      ", ".join(f"{d['left_out']} ({d['shift_pp']:+.2f})" for d in top),
                      f"{x['sign'].get('> 0', 0)} / {x['sign'].get('= 0', 0)} / {x['sign'].get('< 0', 0)}"])
    L += md_table(["enc", "pairs", "Δ all pp", "LOSO min", "LOSO max", "sites driving Δ (shift when left out)",
                   "sites Δ>0 / =0 / <0"], rows3)
    L += ["", "Per-site paired P5 counts (sites with Δ ≠ 0):", ""]
    L += md_table(["site", *[f"{e} B_full / NVC (Δ)" for e in PA.ENCODINGS]],
                  [[s, *[f"{d['B_full']} / {d['B_noVolatile']} ({d['delta_count']:+d})" for d in
                         (next(y for y in res["loso"][e]["per_site"] if y["site"] == s) for e in PA.ENCODINGS)]]
                   for s in [y["site"] for y in res["loso"]["F1"]["per_site"]]
                   if any(next(y for y in res["loso"][e]["per_site"] if y["site"] == s)["delta_count"] for e in PA.ENCODINGS)])

    L += ["", "## 4. Survival paired — B_full vs B_noVolatile (same target, both determined)", "",
          "b = survived only with B_noVolatile, c = survived only with B_full; McNemar uncorrected χ² and exact p; "
          "OR = b/c with the exact conditional CI.", ""]
    L += md_table(["enc", "pairs", "B_full surv %", "NVC surv %", "Δ pp", "b/c", "OR [95% CI]", "p χ²", "p exact"],
                  [[x["encoding"], x["n"], f1(x["rate_first_pct"]), f1(x["rate_second_pct"]), f"{x['delta_pp']:+.2f}",
                    f"{x['b_second_only']}/{x['c_first_only']}",
                    f"{fmt_or(x['odds_ratio'])} [{fmt_or(x['or_ci_lo'])}, {fmt_or(x['or_ci_hi'])}]" if x["b_second_only"] + x["c_first_only"] else "n/a",
                    fmt_p(x["p"]), fmt_p(x["p_exact"])] for x in res["survival_paired"]])

    t = res["tokens"]
    L += ["", "## 5. Input tokens per cell", "",
          "observation_tokens = the observation measured with the fixed tokenizer (o200k_base), every record (326 per "
          "cell; a reused class_only record carries its byte-identical observation). Prompt tokens = API prompt "
          "tokens of called records only.", ""]
    L += md_table(["enc", "cell", "n", "mean obs tokens", "median obs tokens", "called", "mean API prompt tokens"],
                  [[e, c, t[f"{e}|{c}"]["n"], f"{t[f'{e}|{c}']['obs_mean']:,.0f}", f"{t[f'{e}|{c}']['obs_median']:,.0f}",
                    t[f"{e}|{c}"]["n_called"], f"{t[f'{e}|{c}']['prompt_mean_called']:,.0f}"]
                   for e in PA.ENCODINGS for c in PA.CELLS])
    sv = res["savings"]
    L += ["", "Saving = 1 − mean(second) / mean(first) on the observation tokens; also the median of the per-target "
              "savings (same target, 1 − second / first).", ""]
    L += md_table(["comparison", "saving %", "median per target %"],
                  [[k, f"{v['mean_based']:.1f}", f"{v['median_per_target']:.1f}"] for k, v in sv.items()])

    L += ["", "## 6. Survival among locators correct in May (P_now = true): P5 = true vs P5 = false", "",
          f"**{LABEL}.** Determined locators only. Δ = survived % (P5 true) − survived % (P5 false), Newcombe "
          "hybrid-score 95% CI; Fisher exact two-sided p. P5 = false with P_now = true means the locator resolved to "
          "the target but failed condition 3 / 4 (volatile or positional: \"grabbed\") or condition 5 (no-signal "
          "targets). The pooled rows count each target once per cell (up to 6 times), so they are not independent; "
          "their CI and p are descriptive.", ""]
    L += md_table(["enc", "cell", "scope", "n P5=T", "surv %", "n P5=F", "surv %", "Δ pp [95% CI]", "Fisher p",
                   "P5=F: no-signal / grabbed"],
                  [[x["encoding"], x["cell"], x["scope"], x["n_true"], f1(x["share_true"]), x["n_false"],
                    f1(x["share_false"]), f"{x['diff_pp']:+.1f} {cid(*x['diff_ci'])}", fmt_p(x["fisher_p"]),
                    f"{x['p5_false_no_signal']} / {x['p5_false_failure_modes'].get(GRABBED, 0)}"]
                   for x in res["survival_correct_in_may"]])

    cv = res["cop_vs_naive"]
    L += ["", "## 7. COP (B_noVolatile × F3) vs naive (B_full × F1) — paired, stratum \"has stable signal\"", "",
          f"**{LABEL}.** **This comparison is not in the registered plan** (the plan compares bundles within one "
          "encoding); it changes bundle and encoding at once. Same target in both arms. Δ = COP − naive (pp); McNemar "
          "b = COP-only, c = naive-only, exact p; 95% CI = site-clustered percentile bootstrap (10,000, seed 42, 33 "
          "sites in Tranco order), as in the registered analysis.", ""]
    L += md_table(["metric", "n", "naive %", "COP %", "Δ pp", "95% CI (pp)", "b/c", "OR [95% CI]", "p exact", "p χ²"],
                  [[m, x["n"], f1(x["rate_first_pct"]), f1(x["rate_second_pct"]), f"{x['delta_pp']:+.2f}",
                    f"[{x['ci_lo']:+.2f}, {x['ci_hi']:+.2f}]", f"{x['b_second_only']}/{x['c_first_only']}",
                    f"{fmt_or(x['odds_ratio'])} [{fmt_or(x['or_ci_lo'])}, {fmt_or(x['or_ci_hi'])}]",
                    fmt_p(x["p_exact"]), fmt_p(x["p"])] for m, x in cv["metrics"].items()])
    L += ["", "Input tokens over the same pairs (observation = fixed tokenizer o200k_base; API prompt tokens, both "
              "arms called):", ""]
    L += md_table(["tokens", "naive mean", "naive median", "COP mean", "COP median", "saving % (means)",
                   "median per-target saving %"],
                  [[lab, f"{cv[k]['naive_mean']:,.0f}", f"{cv[k]['naive_median']:,.0f}", f"{cv[k]['cop_mean']:,.0f}",
                    f"{cv[k]['cop_median']:,.0f}", f"{cv[k]['saving_mean_pct']:.1f}",
                    f"{cv[k]['saving_median_per_target_pct']:.1f}"]
                   for lab, k in (("observation", "obs"), ("API prompt", "prompt"))])
    return "\n".join(L) + "\n"


def main() -> int:
    pin, recs, rows, by_key, surv, tsv_sha = load()
    bsum = broken_summary(rows, surv)
    assert bsum["broken"] == sum(v == "broken" for v in surv.values()) == 353, bsum["broken"]
    have_probes = MAY_PROBE.is_dir() and SEPT_PROBE.is_dir()
    if have_probes:
        br, _ = broken_reasons(pin, rows, surv)
        assert len(br) == bsum["broken"] and sum(b["change"] == CHANGES[0] for b in br) == bsum["wrong_in_may"]
    else:
        br = None
        print(PROBES_MISSING + ".")
    tok, paired = tokens(rows, recs)
    savings = {}
    for cell in PA.CELLS:
        savings[f"F3 vs F1, {cell}"] = {"mean_based": (1 - tok[("F3", cell)]["obs_mean"] / tok[("F1", cell)]["obs_mean"]) * 100,
                                         "median_per_target": paired[f"F3 vs F1, {cell}"]}
    for enc in PA.ENCODINGS:
        for second in ("B_noVolatile", "class_only"):
            savings[f"{second} vs B_full, {enc}"] = {
                "mean_based": (1 - tok[(enc, second)]["obs_mean"] / tok[(enc, "B_full")]["obs_mean"]) * 100,
                "median_per_target": paired[f"{second} vs B_full, {enc}"]}
    res = {
        "label": LABEL, "registered_commit": REGISTERED_COMMIT,
        "inputs": {"survival_tsv_sha256": tsv_sha, "pins": PA.PINS,
                   "may_probes_sha256": probes_sha(MAY_PROBE, pin["site_order"]) if have_probes else None,
                   "sept_probes_sha256": probes_sha(SEPT_PROBE, pin["site_order"]) if have_probes else None},
        "survival_by_outcome": survival_by_outcome(rows, surv),
        "survival_by_outcome_has_signal": survival_by_outcome(rows, surv, PA.HAS),
        "broken_summary": bsum,
        "broken": br,
        "loso": loso(rows, pin["site_order"]),
        "survival_paired": survival_paired(rows, surv),
        "tokens": {f"{e}|{c}": v for (e, c), v in tok.items()},
        "savings": savings,
        "survival_correct_in_may": survival_correct_in_may(rows, surv),
        "cop_vs_naive": cop_vs_naive(rows, pin["site_order"]),
    }
    OUT_PREFIX.with_suffix(".json").write_text(json.dumps(jsonable(res), ensure_ascii=False, indent=1) + "\n",
                                               encoding="utf-8", newline="\n")
    OUT_PREFIX.with_suffix(".md").write_text(render(res), encoding="utf-8", newline="\n")
    print(f"wrote {OUT_PREFIX}.md and .json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
