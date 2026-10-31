"""
revision1_volatile_nv.py — volatile-flagged locators under B_noVolatile.

Scope: B_noVolatile records with failure_mode = grabbed and predicate_non_volatile = false
(plus the volatile success->grabbed regressions of B_full -> B_noVolatile).

Per record: the locator token and Oracle.cs rule that fired the volatile check (Python port
of Oracle.LocatorUsesVolatileSignal, first validated against predicate_non_volatile on all
6,000 corpus records; any disagreement stops); whether that token occurs in the observation
rebuilt by the C# encoder (`--replay ... --dump-obs`, o200k_base count must equal the stored
observation_tokens); the field it occurs in; and a class: leak, invented by the model, other.

Output: experiments/results/revision1/volatile_in_noVolatile.md / .json, replay/volatile_nv/
Run:    python experiments/analysis/revision1_volatile_nv.py
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import json
import pathlib
import re
import shutil
import subprocess
from html.parser import HTMLParser

import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from load import load_dataframe, DOM_ENCODINGS                      # noqa: E402
from revision1_diagnostics import (                                  # noqa: E402
    REPO, OUT_DIR, TRUTH_DIR, GRABBED, REPLAY_ATTEMPTS,
    protected_state, jsonable, md_table, parse_f2_keymap, state_of,
)

WORK_DIR = OUT_DIR / "replay" / "volatile_nv"
OBS_DIR  = WORK_DIR / "observations"


# Python port of Oracle.LocatorUsesVolatileSignal (CSS branch)
# Patterns copied verbatim from shared/oracle/Oracle.cs.  The rule order is the
# order of the checks in the C# method; the C# method returns at the first hit.

VOLATILE_CLASS_RE = re.compile(
    r"[a-z]{1,3}-(?=[a-zA-Z0-9]*[A-Z0-9])[a-zA-Z0-9]{6,}"
    r"|[A-Za-z]+_[A-Za-z0-9]{5,}__"
    r"|_ngcontent-[a-z]+-[a-z0-9]+"
    r"|data-v-[a-f0-9]+")
VOLATILE_ID_RE = re.compile(r"^:?[rR][a-zA-Z0-9]+$|^[a-z]+-[0-9]{4,}$")

RULES = [
    ("R1 #id",                    re.compile(r"#([a-zA-Z0-9_-]+)")),
    ("R2 [id*=|^=\"X\"]",          re.compile(r"\[id[\*\^]=[\"']([^\"']+)[\"']\]")),
    ("R3 [id=X]",                 re.compile(r"\[id\s*=\s*(?:[\"']([^\"']+)[\"']|([a-zA-Z0-9_-]+))\]")),
    ("R4 .class",                 re.compile(r"\.([a-zA-Z][a-zA-Z0-9_-]*)")),
    ("R5 [class*=|^=\"X\"]",       re.compile(r"\[class[\*\^]=[\"']([^\"']+)[\"']\]")),
    ("R6 [class~=\"X\"]",          re.compile(r"\[class~=[\"']([^\"']+)[\"']\]")),
    ("R7 [class=\"X\"]",           re.compile(r"\[class\s*=\s*[\"']([^\"']+)[\"']\]")),
    ("R8 [class?=X] unquoted",    re.compile(r"\[class[\*\^\~\$\|]?\s*=\s*([a-zA-Z0-9_-]+)\]")),
    ("R9 [volatile-attr-name]",   re.compile(r"\[([a-zA-Z_][a-zA-Z0-9_-]*)(?:\]|[~\*\^\$\|]?=)")),
    ("R10 state",                 re.compile(r":checked|:disabled|\[(value|checked|selected|disabled)[=\]]")),
]


def _is_vol_class(v):
    return VOLATILE_CLASS_RE.search(v) is not None


def _is_vol_id(v):
    return VOLATILE_ID_RE.search(v.strip()) is not None


def _bem_base(tok, vcls):
    return any(vc.startswith(tok + "--") or vc.startswith(tok + "__") for vc in vcls)


def _prefix_of(tok, listed):
    t = tok.lower()
    return any(x.lower().startswith(t) for x in listed)


def volatile_hits(locator: str, vids: set, vcls: set) -> list[dict]:
    """Every (rule, token, reason) that the C# CSS branch would flag, in C# check order."""
    hits = []
    for name, rx in RULES:
        for m in rx.finditer(locator):
            if name.startswith("R10"):
                hits.append({"rule": name, "token": m.group(0), "reason": "state attribute / pseudo-class",
                             "span": m.span()})
                continue
            tok = next(g for g in m.groups() if g is not None) if m.groups() else m.group(0)
            reasons = []
            if name.startswith(("R1", "R2", "R3")):
                if _is_vol_id(tok):
                    reasons.append("VolatileIdRe")
                if tok in vids:
                    reasons.append("truth volatile_ids")
                if name.startswith("R2") and _prefix_of(tok, vids):
                    reasons.append("prefix of a listed volatile id")
            elif name.startswith("R9"):
                if tok in ("class", "id"):
                    continue
                if tok in vcls:
                    reasons.append("attribute name listed in truth volatile_classes")
            else:
                if _is_vol_class(tok):
                    reasons.append("VolatileClassRe")
                if tok in vcls:
                    reasons.append("truth volatile_classes")
                if name.startswith(("R5", "R8")) and _prefix_of(tok, vcls):
                    reasons.append("prefix of a listed volatile class")
                if name.startswith(("R4", "R6", "R7", "R8")) and _bem_base(tok, vcls):
                    reasons.append("BEM base of a listed volatile class")
            if reasons:
                hits.append({"rule": name, "token": tok, "reason": " + ".join(dict.fromkeys(reasons)),
                             "span": m.span()})
    return hits


# Observation parsing (F0–F3) into element dicts

class _F0Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append({"tag": tag, **{k: (v or "") for k, v in attrs}})

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self.elements and data.strip():
            self.elements[-1]["text"] = self.elements[-1].get("text", "") + data


F3_TEXT_RE = re.compile(r" \{((?:[^\\}]|\\.)*)\}$")
F3_KV_RE   = re.compile(r'([^\s=]+)=("(?:[^"\\]|\\.)*"|\S+)')


def parse_observation(text: str, encoding: str, reverse_keymap: dict) -> list[dict]:
    if encoding == "F1":
        return json.loads(text)
    if encoding == "F2":
        return [{reverse_keymap.get(k.lower(), k): v for k, v in el.items()} for el in json.loads(text)]
    if encoding == "F0":
        p = _F0Parser()
        p.feed(text)
        return p.elements
    if encoding == "F3":
        out = []
        for line in text.splitlines():
            el = {}
            if line.startswith("[S] "):
                el["is_shadow"] = "true"
                line = line[4:]
            m = F3_TEXT_RE.search(line)
            if m:
                el["text"] = m.group(1)
                line = line[:m.start()]
            tag, _, rest = line.partition(" ")
            el["tag"] = tag
            for k, v in F3_KV_RE.findall(rest):
                el[k] = json.loads(v) if v.startswith('"') else v
            out.append(el)
        return out
    raise ValueError(encoding)


def locate(token: str, rule: str, elements: list[dict]) -> dict:
    """Where does `token` occur in the parsed observation, relative to the field the rule targets?"""
    in_target_field, elsewhere = [], []
    for el in elements:
        for k, v in el.items():
            if k == "tag":
                continue
            v = str(v)
            if rule.startswith(("R1", "R3")):
                if k == "id" and v == token:
                    in_target_field.append("id")
                    continue
            elif rule.startswith("R2"):
                if k == "id" and token in v:
                    in_target_field.append("id (substring)")
                    continue
            elif rule.startswith(("R4", "R6", "R8")):
                if k == "class" and token in v.split():
                    in_target_field.append("class token")
                    continue
            elif rule.startswith("R7"):
                if k == "class" and set(token.split()) <= set(v.split()):
                    in_target_field.append("class tokens")
                    continue
            elif rule.startswith("R5"):
                if k == "class" and any(token in c for c in v.split()):
                    in_target_field.append("class token (substring)")
                    continue
            elif rule.startswith("R9"):
                if k == token:
                    in_target_field.append(f"attribute name {k}")
                    continue
            elif rule.startswith("R10"):
                name = token.strip("[]=:")
                if k == name:
                    in_target_field.append(f"state attribute {k}")
                    continue
            if token in v or token == k:
                elsewhere.append(k if token in v else f"{k} (as key)")
    return {"in_target_field": sorted(set(in_target_field)),
            "n_elements_target_field": len(in_target_field),
            "elsewhere_fields": sorted(set(elsewhere))}


def bundle_vs_predicate(hit: dict, vids: set, vcls: set) -> str:
    """Compare the B_noVolatile removal rule with the predicate rule that fired."""
    r, tok = hit["rule"], hit["token"]
    if r.startswith("R10"):
        return ("state attribute: ApplyBundleNoVolatile keeps every BundleFull attribute except listed "
                "volatile id/class values, and BundleFull includes disabled/checked/selected/value; "
                "the predicate treats state attributes and :checked/:disabled as volatile")
    if r.startswith(("R1", "R2", "R3")):
        if tok in vids:
            return "id is listed in truth volatile_ids, which ApplyBundleNoVolatile removes"
        return ("id matches the predicate's VolatileIdRe (or is a prefix of a listed id) but is not listed "
                "in truth volatile_ids; ApplyBundleNoVolatile removes only listed ids")
    if r.startswith("R9"):
        return "attribute name listed in truth volatile_classes; such names are not in BundleFull"
    if tok in vcls or _bem_base(tok, vcls):
        return ("class token is listed in truth volatile_classes (or is a BEM base of one), which "
                "ApplyBundleNoVolatile removes")
    return ("class token matches the predicate's VolatileClassRe (or is a prefix of a listed class) but is "
            "neither listed in truth volatile_classes nor a BEM base of a listed class; "
            "ApplyBundleNoVolatile removes only listed tokens and their BEM bases")


def classify(hit: dict, loc: dict, literal_present: bool) -> str:
    if loc["in_target_field"]:
        return "(i) leak into observation"
    if not literal_present:
        return "(ii) invented by model"
    return "(iii) other"


# Replay with observation dump

def replay_with_dump(records: pd.DataFrame) -> pd.DataFrame:
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    in_dir = WORK_DIR / "in"
    in_dir.mkdir(parents=True)
    OBS_DIR.mkdir(parents=True)
    out_file = WORK_DIR / "out.jsonl"
    with open(in_dir / "records.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for _, r in records.iterrows():
            fh.write(json.dumps({"page": r["testbed_page"], "bundle": r["bundle"], "encoding": r["encoding"],
                                 "task_id": r["task_id"], "locator_raw": r["locator_raw"]},
                                ensure_ascii=False) + "\n")
    cmd = ["dotnet", "run", "--project", "experiments", "-c", "Release", "--",
           "--replay", str(in_dir), "--replay-out", str(out_file), "--dump-obs", str(OBS_DIR)]
    log = []
    for attempt in range(1, REPLAY_ATTEMPTS + 1):
        for f in [out_file, *OBS_DIR.glob("*")]:
            f.unlink(missing_ok=True)
        proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8")
        log.append(f"===== attempt {attempt} (exit {proc.returncode}) =====\n{proc.stdout}{proc.stderr}")
        if proc.returncode == 0 and out_file.exists():
            break
    (WORK_DIR / "log.txt").write_text("\n".join(log), encoding="utf-8")
    if proc.returncode != 0 or not out_file.exists():
        raise SystemExit(f"[replay] failed {REPLAY_ATTEMPTS} times; see {WORK_DIR / 'log.txt'}")
    return pd.read_json(out_file, lines=True)


# Main

def main():
    before = protected_state()
    df = load_dataframe(REPO)
    truth = {}
    for tf in sorted(TRUTH_DIR.glob("*.truth.json")):
        tj = json.loads(tf.read_text(encoding="utf-8"))
        truth[tj["page_id"]] = (set(tj["volatility_labels"]["volatile_ids"]),
                                set(tj["volatility_labels"]["volatile_classes"]))

    # 1. Validate the Python port against the stored predicate on the whole corpus.
    assert set(df["locator_type"]) == {"css"}, "port covers the CSS branch only"
    port_flag = [bool(volatile_hits(v, *truth[p])) for v, p in zip(df["locator_value"], df["page"])]
    stored = ~df["predicate_non_volatile"].astype(bool)
    disagree = df[pd.Series(port_flag, index=df.index) != stored]
    print(f"[port] Oracle volatile-rule port vs stored predicate_non_volatile: "
          f"{len(df) - len(disagree)}/{len(df)} agree")
    if len(disagree):
        print(disagree[["page", "bundle", "encoding", "task_id", "locator_value",
                        "predicate_non_volatile"]].to_string())
        raise SystemExit("[port] disagreement with the stored predicate — stopping")

    # 2. Scope.
    nv = df[(df["bundle"] == "B_noVolatile") & df["encoding"].isin(DOM_ENCODINGS)]
    scope = nv[(nv["failure_mode"] == GRABBED) & ~nv["predicate_non_volatile"].astype(bool)]
    scope = scope.sort_values(["page", "encoding", "task_id"]).reset_index(drop=True)
    key = ["page", "task_id", "encoding", "repetition"]
    bf = df[(df["bundle"] == "B_full") & df["encoding"].isin(DOM_ENCODINGS)]
    pr = bf[key + ["success", "failure_mode"]].merge(
        nv[key + ["success", "failure_mode", "predicate_non_volatile"]], on=key, suffixes=("_bf", "_nv"))
    pr["s_bf"] = [state_of(s, f) for s, f in zip(pr["success_bf"], pr["failure_mode_bf"])]
    pr["s_nv"] = [state_of(s, f) for s, f in zip(pr["success_nv"], pr["failure_mode_nv"])]
    regr = pr[(pr["s_bf"] == "success") & (pr["s_nv"] == "grabbed") & ~pr["predicate_non_volatile"].astype(bool)]
    scope_keys = set(map(tuple, scope[key].values))
    regr_keys = [tuple(r) for r in regr[key].values]
    regr_in_scope = sum(k in scope_keys for k in regr_keys)
    nv_vol_not_grabbed = nv[~nv["predicate_non_volatile"].astype(bool) & (nv["failure_mode"] != GRABBED)]
    print(f"[scope] {len(scope)} grabbed + volatile under B_noVolatile; volatile regressions: "
          f"{len(regr)} (in scope: {regr_in_scope})")

    # 3. Rebuild the observations with the C# encoder and replay the locators.
    rep = replay_with_dump(scope)
    manifest = pd.read_csv(OBS_DIR / "manifest.tsv", sep="\t", names=["page", "bundle", "encoding", "tokens"])
    stored_tok = scope.groupby(["page", "encoding"])["observation_tokens"].agg(["min", "max"])
    assert (stored_tok["min"] == stored_tok["max"]).all(), "observation_tokens vary within a cell"
    tok_check = manifest.merge(stored_tok.reset_index(), on=["page", "encoding"])
    tok_mismatch = tok_check[tok_check["tokens"] != tok_check["min"]]
    print(f"[obs] {len(manifest)} observations rebuilt; token count == stored observation_tokens on "
          f"{len(manifest) - len(tok_mismatch)}/{len(manifest)}")
    if len(tok_mismatch):
        print(tok_mismatch.to_string())
        raise SystemExit("[obs] rebuilt observation differs from the one given to the model — stopping")
    fields = ["success", "predicate_unique_match", "predicate_matches_oracle", "predicate_non_volatile",
              "predicate_non_positional", "stable_signal_present_in_bundle"]
    chk = scope.rename(columns={"testbed_page": "page_path"}).merge(
        rep.rename(columns={"page": "page_path"})[["page_path", "bundle", "encoding", "task_id"] + fields],
        on=["page_path", "bundle", "encoding", "task_id"], suffixes=("", "_replay"))
    assert len(chk) == len(scope)
    pred_mismatch = int(sum((chk[f] != chk[f + "_replay"]).sum() for f in fields))
    print(f"[replay] predicate fields re-scored identically: {pred_mismatch == 0} ({pred_mismatch} mismatches)")
    if pred_mismatch:
        raise SystemExit("[replay] predicate mismatch — stopping")

    # 4. Per-record attribution.
    reverse = {v.lower(): k for k, v in parse_f2_keymap().items()}
    obs_cache = {}
    rows = []
    for _, r in scope.iterrows():
        vids, vcls = truth[r["page"]]
        hits = volatile_hits(r["locator_value"], vids, vcls)
        trigger = hits[0]
        okey = (r["page"], r["encoding"])
        if okey not in obs_cache:
            text = (OBS_DIR / f"{r['page']}__B_noVolatile__{r['encoding']}.txt").read_text(encoding="utf-8")
            obs_cache[okey] = (text, parse_observation(text, r["encoding"], reverse))
        text, elements = obs_cache[okey]
        literal = trigger["token"] in text
        loc = locate(trigger["token"], trigger["rule"], elements)
        cls = classify(trigger, loc, literal)
        rows.append({
            "page": r["page"], "encoding": r["encoding"], "task_id": r["task_id"],
            "regression_from_B_full_success": (r["page"], r["task_id"], r["encoding"], r["repetition"]) in set(regr_keys),
            "locator": r["locator_value"],
            "trigger_rule": trigger["rule"], "trigger_token": trigger["token"], "trigger_reason": trigger["reason"],
            "all_hits": [{k: h[k] for k in ("rule", "token", "reason")} for h in hits],
            "token_literally_in_observation": literal,
            "in_target_field": loc["in_target_field"], "n_elements_with_token_in_target_field":
                loc["n_elements_target_field"], "elsewhere_fields": loc["elsewhere_fields"],
            "token_in_truth_volatile_list": trigger["token"] in vids or trigger["token"] in vcls,
            "bundle_vs_predicate": bundle_vs_predicate(trigger, vids, vcls) if loc["in_target_field"] else "",
            "class": cls,
        })
    res = pd.DataFrame(rows)

    # 5. Report.
    classes = ["(i) leak into observation", "(ii) invented by model", "(iii) other"]
    by_class = res["class"].value_counts().reindex(classes, fill_value=0)
    by_class_enc = pd.crosstab(res["class"], res["encoding"]).reindex(index=classes, fill_value=0)
    by_class_page = pd.crosstab(res["page"], res["class"]).reindex(columns=classes, fill_value=0)
    by_rule = pd.crosstab(res["trigger_rule"] + " — " + res["trigger_reason"], res["class"]).reindex(
        columns=classes, fill_value=0)
    leak = res[res["class"] == classes[0]]
    why = leak["bundle_vs_predicate"].value_counts()

    out = {
        "scope": {"grabbed_and_volatile_under_B_noVolatile": len(scope),
                  "volatile_regressions_success_to_grabbed": len(regr),
                  "volatile_regressions_contained_in_scope": regr_in_scope,
                  "B_noVolatile_volatile_but_not_grabbed (lacked, outside scope)": len(nv_vol_not_grabbed)},
        "port_validation": {"records": len(df), "agree_with_stored_predicate_non_volatile": len(df) - len(disagree)},
        "observation_rebuild": {"observations": len(manifest), "token_count_matches_stored": len(manifest) - len(tok_mismatch),
                                "replay_predicate_mismatches": pred_mismatch},
        "by_class": by_class.to_dict(), "by_class_encoding": by_class_enc.to_dict(orient="index"),
        "by_page": by_class_page.to_dict(orient="index"), "by_rule": by_rule.to_dict(orient="index"),
        "leak_bundle_vs_predicate": why.to_dict(),
        "records": rows,
    }
    (OUT_DIR / "volatile_in_noVolatile.json").write_text(
        json.dumps(jsonable(out), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    md = ["# Volatile-flagged locators under B_noVolatile", "",
          "Generated by `python experiments/analysis/revision1_volatile_nv.py`. Facts only; neither the bundle nor the "
          "predicate was modified.", "",
          "## Scope and checks", ""]
    md += md_table(["quantity", "value"], [
        ["B_noVolatile records (F0–F3) with failure_mode = grabbed and predicate_non_volatile = false", len(scope)],
        ["success→grabbed regressions (B_full → B_noVolatile) that are volatile", len(regr)],
        ["… of which contained in the set above", regr_in_scope],
        ["B_noVolatile records volatile-flagged but not grabbed (lacked; outside scope)", len(nv_vol_not_grabbed)],
        ["Python port of Oracle.LocatorUsesVolatileSignal agrees with stored predicate_non_volatile",
         f"{len(df) - len(disagree)} / {len(df)} records"],
        ["observations rebuilt with Observation.BuildObservationAsync (C#)", len(manifest)],
        ["… o200k_base token count equal to stored observation_tokens", f"{len(manifest) - len(tok_mismatch)} / {len(manifest)}"],
        ["replay of the locators: predicate-field mismatches vs stored", pred_mismatch],
    ])
    md += ["", "Trigger = the first check in `Oracle.LocatorUsesVolatileSignal` (C# check order) that flags the "
           "locator; the C# method returns at that point. Class definitions:", "",
           "- **(i) leak into observation** — the trigger token occurs in the rebuilt observation in the field the "
           "rule targets (id value for id rules, class token for class rules, attribute name for state / "
           "attribute-name rules);",
           "- **(ii) invented by model** — the trigger token does not occur anywhere in the observation text;",
           "- **(iii) other** — the token occurs in the observation, but not in the field the rule targets "
           "(e.g. inside another attribute's value or in text), or the trigger is a pseudo-class.", ""]
    md += ["## By class", ""]
    md += md_table(["class", "n"], [[c, int(by_class[c])] for c in classes])
    md += ["", "## By class × encoding", ""]
    md += md_table(["class"] + list(by_class_enc.columns),
                   [[c] + [int(v) for v in by_class_enc.loc[c]] for c in classes])
    md += ["", "## By page", ""]
    md += md_table(["page"] + classes, [[p] + [int(v) for v in row] for p, row in by_class_page.iterrows()])
    md += ["", "## By trigger rule and reason", ""]
    md += md_table(["rule — reason"] + classes, [[k] + [int(v) for v in row] for k, row in by_rule.iterrows()])
    md += ["", "## Class (i): bundle removal rule vs predicate rule", ""]
    md += md_table(["comparison", "n"], [[k, int(v)] for k, v in why.items()])
    md += ["", "## Examples (up to 5 per class)", ""]
    for c in classes:
        ex = res[res["class"] == c].head(5)
        md += [f"### {c}", ""]
        if ex.empty:
            md += ["none", ""]
            continue
        md += md_table(["page", "enc", "task", "locator", "trigger (rule — token — reason)", "in observation",
                        "field(s)"],
                       [[e.page, e.encoding, e.task_id, f"`{e.locator}`",
                         f"{e.trigger_rule} — `{e.trigger_token}` — {e.trigger_reason}",
                         "yes" if e.token_literally_in_observation else "no",
                         ", ".join(e.in_target_field) or (", ".join(e.elsewhere_fields) or "—")]
                        for e in ex.itertuples()])
        md += [""]
    md += ["## Volatile regressions (success under B_full → grabbed under B_noVolatile)", ""]
    md += md_table(["page", "enc", "task", "locator", "trigger", "class"],
                   [[e["page"], e["encoding"], e["task_id"], f"`{e['locator']}`",
                     f"{e['trigger_rule']} — `{e['trigger_token']}`", e["class"]]
                    for _, e in res[res["regression_from_B_full_success"]].iterrows()])
    md += ["", f"All {len(res)} records with locator, trigger, all hits, field and class: "
           "`volatile_in_noVolatile.json`. Rebuilt observations: `replay/volatile_nv/observations/`."]
    (OUT_DIR / "volatile_in_noVolatile.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")

    after = protected_state()
    if after != before:
        raise SystemExit("[guard] protected files changed during the run")
    print(f"[out] {(OUT_DIR / 'volatile_in_noVolatile.md').relative_to(REPO)}")
    print("[by class] " + ", ".join(f"{c}: {int(by_class[c])}" for c in classes))


if __name__ == "__main__":
    main()
