#!/usr/bin/env python3
"""
Standalone consistency validator for page_NN.html + page_NN.truth.json pairs.
Usage: python validate_truth.py pages/page_01.html pages/page_01.truth.json
Exit 0 = all active checks pass. Exit 1 = one or more failures.
"""

# UTF-8 console-independence: reconfigure stdout/stderr so Unicode glyphs
# (minus sign, x, >=, ...) print on any console (e.g. Windows cp1252) without
# requiring PYTHONUTF8. Affects output ENCODING only, never any printed value.
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import json
import re
import sys
from pathlib import Path


# ── helpers ──────────────────────────────────────────────────────────────────

def load_html(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_oracle_ids_from_html(html: str) -> dict[str, int]:
    """Return {oracle_id: count} for every data-oracle-id value found."""
    counts: dict[str, int] = {}
    for m in re.finditer(r'data-oracle-id=["\']([^"\']+)["\']', html):
        v = m.group(1)
        counts[v] = counts.get(v, 0) + 1
    return counts


# ── checks ────────────────────────────────────────────────────────────────────

def check_one_to_one(html_ids: dict[str, int], truth: dict) -> tuple[bool, list[str]]:
    """Each HTML data-oracle-id must have a truth entry and vice-versa."""
    json_oracles = {t["oracle"] for t in truth["targets"]}
    html_set = set(html_ids.keys())

    issues = []
    for oid in sorted(html_set - json_oracles):
        issues.append(f"  HTML has oracle '{oid}' but truth.json has no matching target")
    for oid in sorted(json_oracles - html_set):
        issues.append(f"  truth.json references oracle '{oid}' but it is absent from HTML")

    return (len(issues) == 0, issues)


def check_uniqueness(html_ids: dict[str, int]) -> tuple[bool, list[str]]:
    """Every data-oracle-id must appear exactly once in the HTML."""
    issues = []
    for oid, count in sorted(html_ids.items()):
        if count != 1:
            issues.append(f"  '{oid}' appears {count} time(s) — expected exactly 1")
    return (len(issues) == 0, issues)


# Patterns whose presence in an intent string indicates attribute leakage.
_ATTR_PATTERNS = [
    (r'aria-\w', "aria-* attribute name"),
    (r'data-\w', "data-* attribute name"),
    (r'class=', 'class= assignment'),
    (r'\bid=', 'id= assignment'),
    (r'name=', 'name= assignment'),
    (r'role=', 'role= assignment'),
    (r'href=', 'href= assignment'),
    (r'type=', 'type= assignment'),
    (r'//', 'XPath operator //'),
    (r'\[@', 'XPath predicate [@'),
    (r'\[text\(\)', 'XPath text()'),
    (r'contains\(', 'XPath contains('),
    (r'=["\']', 'attribute value syntax ="'),
]


def check_intent_blindness(truth: dict) -> tuple[bool, list[str]]:
    issues = []
    for target in truth["targets"]:
        intent = target.get("intent", "")
        tid = target["id"]
        hits = []
        for pattern, label in _ATTR_PATTERNS:
            if re.search(pattern, intent, re.IGNORECASE):
                hits.append(label)
        if hits:
            issues.append(f"  {tid}: intent leaks [{', '.join(hits)}] — \"{intent}\"")
    return (len(issues) == 0, issues)


def check_volatility_labels(html: str, truth: dict) -> tuple[bool, list[str]]:
    """Each volatility label must actually appear somewhere in the HTML source."""
    labels = truth.get("volatility_labels", {})
    issues = []

    for vid in labels.get("volatile_ids", []):
        pattern = f'id="{vid}"'
        if pattern not in html and f"id='{vid}'" not in html:
            issues.append(f"  volatile_id '{vid}' not found as id=\"{vid}\" in HTML")

    for vcls in labels.get("volatile_classes", []):
        if vcls.startswith("data-v-"):
            # Vue SFC scope marker — must appear as an attribute name token
            if vcls not in html:
                issues.append(f"  volatile scope marker '{vcls}' not found in HTML")
        else:
            # Hashed CSS class — must appear inside a class="…" value
            if vcls not in html:
                issues.append(f"  volatile class '{vcls}' not found in HTML source")

    return (len(issues) == 0, issues)


# ── runner ────────────────────────────────────────────────────────────────────

def run(html_path: Path, json_path: Path) -> int:
    html = load_html(html_path)
    truth = load_json(json_path)
    html_ids = extract_oracle_ids_from_html(html)

    checks = [
        ("1. One-to-one oracle mapping",     check_one_to_one(html_ids, truth)),
        ("2. Oracle uniqueness (exactly 1)", check_uniqueness(html_ids)),
        ("3. Intent attribute-blindness",    check_intent_blindness(truth)),
        ("4. Volatility labels in HTML",     check_volatility_labels(html, truth)),
    ]

    any_fail = False
    for name, (ok, issues) in checks:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}")
        for line in issues:
            print(line)
        if not ok:
            any_fail = True

    print()
    print("Deferred (requires the full harness):")
    print("  [ ] Strip data-oracle-* from all 5 encodings F0–F4 and confirm 0 tokens added")
    print("  [ ] Oracle resolution against raw DOM for every target")
    print("  [ ] 5-part success predicate runs deterministically with volatility_labels")
    print("  [ ] One full JSONL record produced matching experiments/docs/SCHEMA.md §1 schema")
    print("  [ ] Leak detector: no returned locator references data-oracle-*")

    print()
    if any_fail:
        print("RESULT: FAIL — one or more active checks failed.")
        return 1
    else:
        print("RESULT: PASS — all 4 active checks passed.")
        return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: python {sys.argv[0]} <page.html> <page.truth.json>")
        sys.exit(2)
    sys.exit(run(Path(sys.argv[1]), Path(sys.argv[2])))
