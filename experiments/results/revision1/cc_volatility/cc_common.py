"""
cc_common.py — shared helpers for the Common Crawl Part A analysis (analysis_plan.md).

- extract_values(html): class tokens and id values per the plan's extraction rules
- classify(pairs): flags from the C# Oracle CLI (oracle_cli/, reflection on the Oracle's
  private value predicates; the classifier of record)
- port_flag(t, v): the Python port (revision1_volatile_nv._is_vol_class / _is_vol_id), cross-check only
"""

import json
import pathlib
import re
import subprocess
import sys
from collections import Counter
from html.parser import HTMLParser

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[3]
CACHE = pathlib.Path(__file__).resolve().parents[4].parent / "_external" / "cc_cache"
CLI_PROJ = HERE / "oracle_cli" / "OracleValueCli.csproj"
CLI_DLL = HERE / "oracle_cli" / "bin" / "Release" / "net10.0" / "OracleValueCli.dll"
ASCII_WS = re.compile(r"[ \t\n\f\r]+")

sys.path.insert(0, str(REPO / "experiments" / "analysis"))
from revision1_volatile_nv import _is_vol_class, _is_vol_id          # noqa: E402


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.classes, self.ids = Counter(), Counter()

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if v is None:
                continue
            if k == "class":
                for tok in ASCII_WS.split(v):
                    if tok:
                        self.classes[tok] += 1
            elif k == "id" and v != "":
                self.ids[v] += 1

    handle_startendtag = handle_starttag


def extract_values(html: str):
    """(class token Counter, id Counter) — class split on ASCII whitespace, ids as written, empties dropped."""
    p = _Collector()
    p.feed(html)
    p.close()
    return p.classes, p.ids


def class_tokens(value: str):
    return [t for t in ASCII_WS.split(value) if t]


def build_cli():
    r = subprocess.run(["dotnet", "build", str(CLI_PROJ), "-c", "Release", "-nologo", "-v", "q"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not CLI_DLL.exists():
        raise SystemExit(f"[cli] build failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    d = subprocess.run(["dotnet", str(CLI_DLL), "--describe"], capture_output=True, text=True, encoding="utf-8")
    return d.stdout.strip()


def classify(pairs):
    """pairs: iterable of (t, v) with t in {'class','id'}. Returns {(t, v): flag} from the C# CLI."""
    pairs = sorted(set(pairs))
    inp = "".join(json.dumps({"t": t, "v": v}, ensure_ascii=False) + "\n" for t, v in pairs)
    r = subprocess.run(["dotnet", str(CLI_DLL)], input=inp.encode("utf-8"), capture_output=True)
    if r.returncode != 0:
        raise SystemExit(f"[cli] failed: {r.stderr.decode('utf-8', 'replace')[-2000:]}")
    out = {}
    for line in r.stdout.decode("utf-8").splitlines():
        if line:
            o = json.loads(line)
            out[(o["t"], o["v"])] = bool(o["flag"])
    if len(out) != len(pairs) or any(p not in out for p in pairs):
        raise SystemExit(f"[cli] returned {len(out)} flags for {len(pairs)} values")
    return out


def port_flag(t, v):
    return _is_vol_class(v) if t == "class" else _is_vol_id(v)


def git(*args):
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


def committed(rel_path):
    """{'sha', 'committed', 'clean'} for the last commit touching rel_path."""
    out = git("log", "-1", "--format=%H|%cI", "--", rel_path)
    sha, when = out.split("|") if out else (None, None)
    return {"sha": sha, "committed": when, "clean": git("status", "--porcelain", "--", rel_path) == ""}


def md_table(headers, rows):
    out = ["| " + " | ".join(str(h) for h in headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |" for r in rows]
    return out
