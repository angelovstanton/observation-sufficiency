"""
rp_sites.py — the real-site pilot's per-site load inputs for the experiments/batch pilot profile. No model, no network.

Writes pilot_sites.json: for each site of pilot_plan.json (Tranco-rank order) the URL and timestamp the adapter
loads the May page with, the Oracle-determined lists the observations were dumped with (sorted), the Common Crawl
WARC coordinates of the record (so the same HTML can be fetched without the local cache) and the sha256 of the
decoded HTML bytes the adapter is given. The HTML itself is not written (foreign page text).

Sources: ../_external/cc_cache/real_pilot/state.json (url, timestamp, html_path, vol lists),
cc_volatility/dry_run.json (WARC coordinates), the cached WARC records and decoded HTML files, and the inputs of
the five dumps of rp_redump.py (real_pilot/observations/input.json, redump_2..5/input.json). Every check must
pass before anything is written; the output is deterministic.

Run from the repository root:  python experiments/results/revision1/real_pilot/rp_sites.py
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import base64
import hashlib
import json
from collections import Counter

from rp_common import CACHE, HERE, HTML_DIR, REPO, RP_CACHE, CVA, committed, parse_record, read_tsv

CRAWL = "CC-MAIN-2026-21"
PLAN = "experiments/results/revision1/real_pilot/pilot_plan.json"
DRY_RUN = "experiments/results/revision1/cc_volatility/dry_run.json"
MANIFEST = "experiments/results/revision1/real_pilot/observations_manifest.tsv"


def ts14_to_iso(ts14):
    return f"{ts14[0:4]}-{ts14[4:6]}-{ts14[6:8]}T{ts14[8:10]}:{ts14[10:12]}:{ts14[12:14]}Z"


def source(rel):
    c = committed(rel)
    if not (c["sha"] and c["clean"]):
        raise SystemExit(f"[sites] {rel} not committed and clean: {c}")
    return {"path": rel, "commit": c["sha"], "sha256": hashlib.sha256((REPO / rel).read_bytes()).hexdigest()}


def main():
    sources = [source(PLAN), source(DRY_RUN), source(MANIFEST)]
    plan = json.loads((REPO / PLAN).read_text(encoding="utf-8"))
    pages = sorted({e["page"] for e in plan["events"]})
    state = {s["key"]: s for s in json.loads((RP_CACHE / "state.json").read_text(encoding="utf-8"))["sites"]}
    dry = {q["domain"]: q for q in json.loads((REPO / DRY_RUN).read_text(encoding="utf-8"))["qualified_domains"]}
    dumps = [{s["key"]: s for s in json.loads(p.read_text(encoding="utf-8"))["sites"]}
             for p in [HERE / "observations" / "input.json"] + [RP_CACHE / f"redump_{i}" / "input.json" for i in range(2, 6)]]
    manifest = {(r["domain"], r["code_bundle"], r["encoding"]): r["sha256"] for r in read_tsv(REPO / MANIFEST)}

    fails, sites = [], []
    for key in pages:
        s = state.get(key)
        if s is None:
            fails.append(f"{key}: not in state.json")
            continue
        rank, domain = s["rank"], s["domain"]
        if key != f"{rank:04d}_{domain}":
            fails.append(f"{key}: key != rank_domain")
        q = dry.get(domain, {}).get(CRAWL)
        if q is None or dry[domain]["rank"] != rank:
            fails.append(f"{key}: no {CRAWL} record in dry_run.json")
            continue
        if ts14_to_iso(q["timestamp"]) != s["timestamp"]:
            fails.append(f"{key}: timestamp {s['timestamp']} != dry_run {q['timestamp']}")
        if q["url"] != s["url"]:
            fails.append(f"{key}: url {s['url']} != dry_run {q['url']}")

        raw = (CACHE / "warc" / CRAWL / f"{key}.warc.gz").read_bytes()
        if len(raw) != int(q["length"]):
            fails.append(f"{key}: cached WARC record {len(raw)} bytes != index length {q['length']}")
        _, warc, _, http_h, payload = parse_record(raw)
        digest = "sha1:" + q["digest"]
        if warc.get("warc-payload-digest") != digest:
            fails.append(f"{key}: WARC-Payload-Digest {warc.get('warc-payload-digest')} != {digest}")
        if base64.b32encode(hashlib.sha1(payload).digest()).decode() != q["digest"]:
            fails.append(f"{key}: recomputed payload SHA-1 != index digest")
        if warc.get("warc-target-uri") != s["url"]:
            fails.append(f"{key}: WARC-Target-URI {warc.get('warc-target-uri')} != url")

        html_path = HTML_DIR / CRAWL / f"{key}.html"
        if html_path.resolve() != (HTML_DIR / CRAWL / s["html_path"].replace("\\", "/").split("/")[-1]).resolve():
            fails.append(f"{key}: state html_path {s['html_path']} is not {html_path}")
        html = html_path.read_bytes()
        if CVA.decode(payload, http_h, Counter()).encode("utf-8") != html:
            fails.append(f"{key}: decoded WARC payload != cached HTML bytes")

        vol_ids, vol_classes = sorted(set(s["vol_ids"])), sorted(set(s["vol_classes"]))
        if len(vol_ids) != len(s["vol_ids"]) or len(vol_classes) != len(s["vol_classes"]):
            fails.append(f"{key}: duplicate values in the vol lists")
        for i, d in enumerate(dumps):
            ds = d.get(key)
            if ds is None or sorted(ds["volIds"]) != vol_ids or sorted(ds["volClasses"]) != vol_classes \
                    or ds["url"] != s["url"] or ds["timestamp"] != s["timestamp"] \
                    or ds["htmlPath"] != s["html_path"]:
                fails.append(f"{key}: load inputs differ from dump {i + 1} input.json")
        for enc in ("F1", "F3"):
            if manifest[(domain, "B_full", enc)] == manifest[(domain, "B_noVolatileConsistent", enc)]:
                fails.append(f"{key}: B_full == B_noVolatile ({enc})")

        sites.append({
            "rank": rank, "domain": domain, "key": key, "url": s["url"], "timestamp": s["timestamp"],
            "warc": {"crawl": CRAWL, "filename": q["filename"], "offset": int(q["offset"]),
                     "length": int(q["length"]), "payload_digest": digest},
            "html_file": f"{key}.html", "html_bytes": len(html), "html_sha256": hashlib.sha256(html).hexdigest(),
            "vol_ids": vol_ids, "vol_classes": vol_classes,
        })

    if [x["key"] for x in sites] != pages:
        fails.append(f"{len(sites)} sites, expected the {len(pages)} pages of pilot_plan.json")
    if fails:
        print("\n".join(fails))
        raise SystemExit(f"[sites] {len(fails)} check(s) failed -> STOP, nothing written")

    sites.sort(key=lambda x: x["rank"])
    out = {
        "description": "Per-site load inputs of the real-site pilot (experiments/batch pilot profile): the May page is the "
                       "decoded HTML of the listed Common Crawl WARC record (cc_volatility_analysis.decode), loaded "
                       "offline by experiments/RealPilotOffline.cs with the clock at 'timestamp'; vol_ids / vol_classes are "
                       "the Oracle-determined lists (pilot_rule.md section 6) the observations were dumped with. "
                       "The HTML is not stored here; html_sha256 pins its bytes.",
        "generator": "experiments/results/revision1/real_pilot/rp_sites.py",
        "sources": sources,
        "crawl": CRAWL,
        "html_dir": "../_external/cc_cache/real_pilot/html/" + CRAWL,
        "count": len(sites),
        "sites": sites,
    }
    text = json.dumps(out, ensure_ascii=False, indent=1) + "\n"
    (HERE / "pilot_sites.json").write_text(text, encoding="utf-8", newline="\n")
    print(f"[sites] {len(sites)} sites, sha256 {hashlib.sha256(text.encode('utf-8')).hexdigest()}")


if __name__ == "__main__":
    main()
