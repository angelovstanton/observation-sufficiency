"""
rp_survival.py — secondary measure "survival" of the real-site pilot (pilot_analysis_plan.md, "Secondary: survival").
Zero LLM, zero network (the C# adapter loads cached HTML offline, experiments/RealPilotOffline.cs).

  python rp_survival.py prep
      Outcome-independent; run before any pilot record is read. Decodes the September record (CC-MAIN-2026-39)
      of each of the 33 sites as the May record was decoded, runs the adapter probe twice in separate processes,
      and maps each May target to the September candidate with the same role (pilot_rule.md §5) and accessible
      name if exactly one exists, else "absent" / "ambiguous". Both probes must agree or prep stops.
      Writes real_pilot/survival_targets.json (pinned by experiments/analysis/revision1_pilot_analysis.py).

  python rp_survival.py run --records <dir> --out <tsv>
      After the paid pilot. Each record's locator is resolved (Oracle.EvaluateLocatorAsync, resolution only) on a
      fresh load of the September page inside a mutation window, ≤ 5 attempts: survived / broken / undetermined
      (addendum (д), pilot_addendum_scoring_a3.md). Addendum (е): an attempt proceeds only if the B_full × F1
      walk hash equals the site's survival_reference.json entry; sites without a stable reference give
      "undetermined_no_reference" (е′). Exits 5 / 6 on the load rule of (е) point 3 or when more than 5% of the
      locators are undetermined (е″ point 4). Writes the TSV and <out>.run.json.

  python rp_survival.py reference [--sites k1,k2,...]
      Addenda (е), (е′), (е″): the September reference of each site from 3 cold loads
      (RealPilotOffline.SeptemberPreHashAsync); valid only if the 3 hashes are identical. At most 3 generations,
      only while the pilot records are unopened; every generation is kept in survival_reference.json.
"""
import argparse
import collections
import csv
import datetime
import hashlib
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from rp_common import RP_CACHE, decoded_html, dry_run, read_tsv, role_of, run_mode, site_key  # noqa: E402

SEPT = "CC-MAIN-2026-39"
SITES_JSON = HERE / "pilot_sites.json"
TARGETS_JSON = HERE / "targets.json"
OUT_JSON = HERE / "survival_targets.json"
REF_JSON = HERE / "survival_reference.json"
SURVIVAL_TARGETS_SHA = "6bdd67be22b43caa126305ab50784ff2136c46bce05e507bae8bd5dac70874db"   # as the analysis pins it
COLD_LOADS, MAX_GENERATIONS = 3, 3
WALK = ("RealPilotOffline.SeptemberPreHashAsync → Observation.BuildObservationAsync(B_full, F1) → sha256 (UTF-8); "
        "load: RealPilotOffline.SeptemberReferenceLoadAsync (survival load of (д), clock paused right after it (а‴), "
        "mutation window around the walk)")
CODE_FILES = ["experiments/RealPilotOffline.cs", "experiments/modes/RealPilotMode.cs", "experiments/results/revision1/real_pilot/rp_survival.py",
              "experiments/results/revision1/real_pilot/rp_shim_random.js", "shared/harness"]
WATCHED = ("firefox.exe", "chrome.exe", "msedge.exe", "onedrive.exe")
EXIT_LOAD_RULE, EXIT_UNDETERMINED = 5, 6
NO_REFERENCE = "undetermined (no stable reference)"            # (е′) point 3: no stable generation after 3
SITES_SHA = "15ab318758d54d820bd611628dc4c6efaf5378e5286624a5d388176444b4d0ba"
TARGETS_SHA = "e890544fcfd19789f0587e564b17e9ebb62d7877f3ad99b4d8a3070e7b243fec"


def sha256_file(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def ts_iso(ts14):
    return f"{ts14[0:4]}-{ts14[4:6]}-{ts14[6:8]}T{ts14[8:10]}:{ts14[10:12]}:{ts14[12:14]}Z"


def load_pinned():
    assert sha256_file(SITES_JSON) == SITES_SHA, "pilot_sites.json sha256 != pin"
    assert sha256_file(TARGETS_JSON) == TARGETS_SHA, "targets.json sha256 != pin"
    sites = json.loads(SITES_JSON.read_text(encoding="utf-8"))["sites"]
    targets = json.loads(TARGETS_JSON.read_text(encoding="utf-8"))["items"]
    return sites, targets


def machine():
    """Processes per image name (addendum (е″) point 1): counted, never touched."""
    out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, check=True).stdout
    names = collections.Counter(row[0].lower() for row in csv.reader(out.splitlines()) if row)
    counts = {n: names[n] for n in WATCHED}
    return {"quiet": not any(counts.values()), "processes": counts}


def code_commit():
    repo = HERE.parents[3]
    dirty = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--", *CODE_FILES],
                           capture_output=True, text=True, check=True).stdout.strip()
    if dirty:
        raise SystemExit(f"[reference] code files not committed:\n{dirty}")
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def september():
    assert sha256_file(OUT_JSON) == SURVIVAL_TARGETS_SHA, "survival_targets.json sha256 != pin"
    st = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    sept = {x["key"]: x for x in st["sites"]}
    for k, x in sept.items():
        assert sha256_file(RP_CACHE / "html" / SEPT / x["html_file"]) == x["html_sha256"], \
            f"{k}: September HTML sha256 != survival_targets.json"
    return st, sept


def reference(only=None):
    sites, _ = load_pinned()
    _, sept = september()
    commit = code_commit()
    doc = json.loads(REF_JSON.read_text(encoding="utf-8")) if REF_JSON.exists() else {
        "description": "September reference per site (addenda (е) a74ace4, (е′) 7cca0aa, (е″)): sha256 of the "
                       "B_full × F1 observation on the survival load, clock paused right after the load; valid only "
                       "if identical in 3 cold loads (new browser start, warm-up, reference load).",
        "crawl": SEPT, "cell": {"bundle": "B_full", "encoding": "F1"}, "walk": WALK, "cold_loads": COLD_LOADS,
        "max_generations": MAX_GENERATIONS, "survival_targets_sha256": SURVIVAL_TARGETS_SHA, "runs": [],
        "sites": [{"key": s["key"], "html_sha256": sept[s["key"]]["html_sha256"], "stable": False,
                   "reference_sha256": None, "reference_generation": None, "generations": []}
                  for s in sorted(sites, key=lambda s: s["rank"])],
    }
    entries = {e["key"]: e for e in doc["sites"]}
    keys = [k for k in entries if not entries[k]["stable"] and (only is None or k in only)]
    if only is not None and set(only) - set(entries):
        raise SystemExit(f"[reference] unknown sites: {sorted(set(only) - set(entries))}")
    over = [k for k in keys if len(entries[k]["generations"]) >= MAX_GENERATIONS]
    if over:
        raise SystemExit(f"[reference] {over}: already {MAX_GENERATIONS} generations (е″ point 2)")
    if not keys:
        print("[reference] nothing to generate")
        return
    run = {"n": len(doc["runs"]) + 1, "utc_start": utc_now(), "code_commit": commit, "sites": keys,
           "machine": machine()}
    payload = {"sites": [{"key": k, "url": sept[k]["url"], "htmlPath": str(RP_CACHE / "html" / SEPT / sept[k]["html_file"]),
                          "timestamp": sept[k]["timestamp"]} for k in keys], "coldLoads": COLD_LOADS}
    out_dir = RP_CACHE / f"reference_run_{run['n']:02d}"
    rc = run_mode("reference", payload, out_dir, "reference.log")
    if rc != 0:
        raise SystemExit(f"[reference] adapter exited {rc}")
    run["utc_end"] = utc_now()
    run["machine_end"] = machine()
    rows = collections.defaultdict(list)
    for r in read_tsv(out_dir / "reference.tsv"):
        rows[r["site"]].append(r)
    for k in keys:
        rs = sorted(rows[k], key=lambda r: int(r["cold"]))
        assert [int(r["cold"]) for r in rs] == list(range(1, COLD_LOADS + 1)), f"{k}: cold loads {rs}"
        gen = {"generation": len(entries[k]["generations"]) + 1, "run": run["n"],
               "hashes": [r["sha256"] or None for r in rs], "mutations": [int(r["mutations"]) if r["mutations"] else None
                                                                          for r in rs],
               "utc": [r["utc"] for r in rs], "errors": [r["error"] for r in rs if r["error"]]}
        gen["stable"] = len(set(gen["hashes"])) == 1 and gen["hashes"][0] is not None and not gen["errors"]
        entries[k]["generations"].append(gen)
        if gen["stable"]:
            entries[k].update(stable=True, reference_sha256=gen["hashes"][0], reference_generation=gen["generation"],
                              status="stable")
        elif gen["generation"] >= MAX_GENERATIONS:
            entries[k]["status"] = NO_REFERENCE                   # (е′) point 3, (е‴) point 3
    doc["runs"].append(run)
    doc["counts"] = {"sites": len(entries), "stable": sum(e["stable"] for e in entries.values()),
                     "not_stable": sorted(k for k, e in entries.items() if not e["stable"]),
                     "undetermined_no_stable_reference": sorted(k for k, e in entries.items()
                                                                if e.get("status") == NO_REFERENCE)}
    REF_JSON.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"[reference] run {run['n']}: {len(keys)} sites; stable {doc['counts']['stable']}/{len(entries)}; "
          f"not stable: {doc['counts']['not_stable']}")


def match(candidates, role, name):
    hits = []
    for c in candidates:
        try:
            r = role_of(c)
        except ValueError:
            continue
        if r == role and c["name"] == name:
            hits.append(c)
    if len(hits) == 1:
        return {"status": "unique", "sept_xpath": hits[0]["xpath"], "xpath_round_trip": hits[0]["xpathRoundTrip"]}
    return {"status": "absent" if not hits else "ambiguous", "matches": len(hits)}


def prep():
    sites, targets = load_pinned()
    dr = {q["domain"]: q for q in dry_run()["qualified_domains"]}
    stats = collections.Counter()
    sept_sites = []
    for s in sites:
        q = dr[s["domain"]]
        rec = q[SEPT]
        html, path, uri = decoded_html(SEPT, q, stats)
        assert site_key(q) == s["key"]
        assert uri == rec["url"], f"{s['key']}: WARC-Target-URI {uri} != index url {rec['url']}"
        body = path.read_bytes()
        sept_sites.append({"key": s["key"], "domain": s["domain"], "rank": s["rank"], "url": uri,
                           "timestamp": ts_iso(rec["timestamp"]), "html_file": path.name,
                           "html_bytes": len(body), "html_sha256": hashlib.sha256(body).hexdigest(),
                           "warc": {"crawl": SEPT, "filename": rec["filename"], "offset": int(rec["offset"]),
                                    "length": int(rec["length"]), "digest": rec["digest"]},
                           "same_digest_as_may": q.get("same_digest")})
    probes = []
    for run in (1, 2):
        out = RP_CACHE / f"survival_probe_{run}"
        payload = {"sites": [{"key": x["key"], "url": x["url"], "htmlPath": str(RP_CACHE / "html" / SEPT / x["html_file"]),
                              "timestamp": x["timestamp"], "volIds": [], "volClasses": [], "markers": [], "tasks": []}
                             for x in sept_sites],
                   "shims": True, "writeObs": False}
        rc = run_mode("probe", payload, out, "probe.log")
        if rc != 0:
            raise SystemExit(f"[prep] probe run {run}: adapter exited {rc}")
        res = {}
        for x in sept_sites:
            pr = json.loads((out / f"{x['key']}.probe.json").read_text(encoding="utf-8"))
            if not pr["ok"]:
                raise SystemExit(f"[prep] probe run {run} {x['key']}: {pr['error']}")
            res[x["key"]] = pr
        probes.append(res)
    items, by_status = [], collections.Counter()
    for t in targets:
        key = f"{t['rank']:04d}_{t['domain']}"
        m1 = match(probes[0][key]["candidates"]["candidates"], t["role"], t["name"])
        m2 = match(probes[1][key]["candidates"]["candidates"], t["role"], t["name"])
        if m1 != m2:
            raise SystemExit(f"[prep] {key} {t['marker']}: the two September probes differ ({m1} vs {m2})")
        if m1["status"] == "unique" and not m1["xpath_round_trip"]:
            raise SystemExit(f"[prep] {key} {t['marker']}: September XPath does not round-trip")
        by_status[m1["status"]] += 1
        items.append({"domain": t["domain"], "rank": t["rank"], "marker": t["marker"], "role": t["role"],
                      "name": t["name"], "stratum": t["stratum"], **{k: v for k, v in m1.items() if k != "xpath_round_trip"}})
    doc = {
        "description": "September (CC-MAIN-2026-39) target of each May pilot target for the secondary measure survival "
                       "(pilot_analysis_plan.md): the unique candidate (rp_candidates.js on the offline September load, "
                       "shims on, clock at the September record) with the same role (pilot_rule.md §5) and the identical "
                       "accessible name; otherwise survival is undefined (absent / ambiguous). Generated by rp_survival.py "
                       "prep before any pilot record was read; two independent probes agree on every target.",
        "crawl": SEPT, "targets_sha256": TARGETS_SHA, "pilot_sites_sha256": SITES_SHA,
        "decode_stats": dict(stats), "counts": dict(sorted(by_status.items())),
        "sites": sept_sites, "items": items,
    }
    OUT_JSON.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"[prep] {len(items)} targets: {dict(by_status)}; wrote {OUT_JSON.name} sha256 {sha256_file(OUT_JSON)}")


def run(records_dir, out_tsv):
    sites, _ = load_pinned()
    st, sept = september()
    if not REF_JSON.exists():
        raise SystemExit("[run] no survival_reference.json (addendum (е): the reference comes first)")
    ref = {e["key"]: e for e in json.loads(REF_JSON.read_text(encoding="utf-8"))["sites"]}
    no_ref = {k for k, e in ref.items() if not e["stable"]}
    pending = sorted(k for k in no_ref if ref[k].get("status") != NO_REFERENCE)
    if pending:
        raise SystemExit(f"[run] {pending}: no stable reference yet and fewer than {MAX_GENERATIONS} generations")
    # Addendum (д): the September target is found on every load by role + name (no XPath markers).
    unique = {(f"{t['rank']:04d}_{t['domain']}", t["marker"]): t for t in st["items"] if t["status"] == "unique"}
    locs = collections.defaultdict(list)
    lraw = {}
    for f in sorted(pathlib.Path(records_dir).glob("batch_pilot_*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if (r["page"], r["task_id"]) in unique:
                locs[r["page"]].append({"eventKey": r["event_key"], "marker": r["task_id"], "locatorRaw": r["locator_raw"]})
                lraw[r["event_key"]] = r["locator_raw"]
    payload = {"sites": [{"key": k, "url": sept[k]["url"], "htmlPath": str(RP_CACHE / "html" / SEPT / sept[k]["html_file"]),
                          "timestamp": sept[k]["timestamp"], "referenceSha": ref[k]["reference_sha256"],
                          "targets": [{"id": m, "role": t["role"], "name": t["name"]} for (p, m), t in sorted(unique.items()) if p == k],
                          "locators": locs[k]}
                         for k in (s["key"] for s in sites) if locs[k] and k not in no_ref]}
    meta = {"reference_sha256": sha256_file(REF_JSON), "code_commit": code_commit(), "utc_start": utc_now(),
            "machine": machine(), "no_reference_sites": sorted(no_ref)}
    out_dir = RP_CACHE / "survival_run"
    rc = run_mode("survival", payload, out_dir, "survival.log")
    meta.update(utc_end=utc_now(), machine_end=machine(), exit_code=rc)
    run_json = pathlib.Path(str(out_tsv) + ".run.json")
    if rc in (EXIT_LOAD_RULE, EXIT_UNDETERMINED):
        meta["stopped"] = (out_dir / "STOPPED.txt").read_text(encoding="utf-8").strip()
        run_json.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"[run] STOPPED ({meta['stopped']}); output not used, no TSV written -> {run_json}")
        raise SystemExit(rc)
    if rc != 0:
        raise SystemExit(f"[run] adapter exited {rc}")
    bad = [r for r in read_tsv(out_dir / "survival_sites.tsv") if r["ok"] != "True"]
    if bad:
        raise SystemExit(f"[run] site failures: {bad}")
    rows = read_tsv(out_dir / "survival.tsv")
    n_no_ref = sum(len(v) for k, v in locs.items() if k in no_ref)
    assert len(rows) + n_no_ref == len(lraw), f"{len(rows)} results + {n_no_ref} without reference for {len(lraw)} locators"
    out = []
    for r in rows:
        if r["status"] == "determined":
            status = "survived" if r["unique_match"] == "True" and r["matches_target"] == "True" else "broken"
        elif r["status"] == "undetermined":
            status = "undetermined"                       # addendum (д): unstable DOM after 5 attempts
        else:
            raise SystemExit(f"[run] {r['event_key']}: unknown status {r['status']!r}")
        out.append((r["event_key"], r["unique_match"], r["matches_target"], status, r["attempts"], r["pre_hashes"],
                    r["windows"]))
    for k in sorted(no_ref):
        for l in locs.get(k, []):
            out.append((l["eventKey"], "", "", "undetermined_no_reference", "0", "", ""))   # addendum (е′) point 3
    with open(out_tsv, "w", encoding="utf-8", newline="\n") as f:
        f.write("event_key\tlocator_sha256\tunique_match\tmatches_target\tstatus\tattempts\tpre_hashes\twindows\n")
        for k, um, mt, status, att, pre, win in sorted(out):
            f.write(f"{k}\t{hashlib.sha256(lraw[k].encode('utf-8')).hexdigest()}\t{um}\t{mt}\t{status}\t{att}\t{pre}\t{win}\n")
    meta["counts"] = dict(collections.Counter(o[3] for o in out))
    run_json.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"[run] {len(out)} locators -> {out_tsv}; {meta['counts']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prep", "run", "reference"])
    ap.add_argument("--records")
    ap.add_argument("--out")
    ap.add_argument("--sites", help="reference: comma-separated site keys (default: every site without a stable reference)")
    a = ap.parse_args()
    if a.cmd == "prep":
        prep()
    elif a.cmd == "reference":
        reference(a.sites.split(",") if a.sites else None)
    else:
        if not (a.records and a.out):
            ap.error("run needs --records and --out")
        run(a.records, a.out)
