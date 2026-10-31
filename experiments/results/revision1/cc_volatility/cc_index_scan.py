"""
cc_index_scan.py — Common Crawl Part A, expanded Phase 1 (index only, no HTML / WARC).

Applies the pre-registered rule in sampling_rule.md (committed in RULE_COMMIT before the run):
walk Tranco 4672X in rank order and take the first 100 domains whose homepage has a status-200
text/html index line in both CC-MAIN-2026-21 and CC-MAIN-2026-39; stop at 100 qualified or
after rank 2000.

Index access: zipnum CDX on data.commoncrawl.org (cluster.idx, cached) + one HTTP range request
per cdx block. Every block is cached and fetched at most once; domains whose homepage keys fall
in the same block share that request.

Run from the repository root (stdlib only; one process, no parallel requests):

    python -I experiments/results/revision1/cc_volatility/cc_index_scan.py            # network run / resume
    python -I experiments/results/revision1/cc_volatility/cc_index_scan.py --offline  # report from cache only

Network rules: User-Agent UA below; ≥ 2 s between requests; on 503 / other 5xx / timeout wait
30 s, 60 s, 120 s and retry, then stop with a resume point; 403 / 429 / block page -> stop, no
circumvention. Resuming is a re-run: fetched data is read from the cache. The PID is written to
cc_cache/scan.pid.

Cache (outside the repository): ../_external/cc_cache/
No LLM calls. Writes dry_run.md / dry_run.json next to this file.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import bisect
import datetime as dt
import gzip
import http.client
import json
import os
import pathlib
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[3]
CACHE = pathlib.Path(__file__).resolve().parents[4].parent / "_external" / "cc_cache"
DATA = "https://data.commoncrawl.org"
UA = "academic research (TU Sofia PhD), antonsangelov@tu-sofia.bg"
MIN_GAP = 2.05
WAITS = [30, 60, 120]
TIMEOUT = 120
TRANCO_ID = "4672X"
CRAWLS = ["CC-MAIN-2026-21", "CC-MAIN-2026-39"]
TARGET_QUALIFIED = 100
MAX_RANK = 2000
INTERVALS = [(1, 100), (101, 500), (501, 1000), (1001, 2000)]
RULE_FILE = HERE / "sampling_rule.md"
BLOCK_MARKERS = ("unusual traffic", "blocked", "rate limit")

OFFLINE = "--offline" in sys.argv
RUN_ID = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
_last = [0.0]
STATS = Counter()


class Stop(Exception):
    pass


def log_request(entry):
    with (CACHE / "requests_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def throttle():
    wait = _last[0] + MIN_GAP - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.monotonic()


def request(url, kind, headers=None):
    if OFFLINE:
        raise Stop(f"offline: {kind} not in cache ({url}) — no request made")
    attempt = 0
    while True:
        attempt += 1
        throttle()
        t0 = time.monotonic()
        wall = dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")
        status, body, err = None, b"", None
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                status, body = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, body = e.code, e.read() or b""
        except (OSError, http.client.HTTPException) as e:     # URLError, timeout, IncompleteRead, reset …
            err = f"{type(e).__name__}: {e}"
        head = body[:2000].decode("utf-8", errors="replace").lower()
        blocked = status in (403, 429) or (status not in (200, 206) and any(m in head for m in BLOCK_MARKERS))
        log_request({"run_id": RUN_ID, "t_utc": wall, "kind": kind, "url": url,
                     "range": (headers or {}).get("Range"), "attempt": attempt, "status": status, "error": err,
                     "elapsed_s": round(time.monotonic() - t0, 3), "bytes": len(body), "blocked": blocked})
        STATS["requests"] += 1
        STATS[f"status_{status}"] += 1
        if attempt > 1:
            STATS["retries"] += 1
        if blocked:
            raise Stop(f"{kind}: HTTP {status} at {url} — stopped, no circumvention")
        retryable = err is not None or (status is not None and status >= 500)
        if not retryable:
            return status, body
        if attempt > len(WAITS):
            raise Stop(f"{kind}: HTTP {status or err} after {attempt} attempts "
                       f"(waits {WAITS} s) at {url} {(headers or {}).get('Range', '')}")
        STATS["wait_s"] += WAITS[attempt - 1]
        print(f"[wait] {status or err} -> {WAITS[attempt - 1]} s", flush=True)
        time.sleep(WAITS[attempt - 1])


# Inputs

def tranco_ranks():
    path = CACHE / f"tranco_{TRANCO_ID}_top{MAX_RANK}.csv"
    if not path.exists():
        st, body = request(f"https://tranco-list.eu/download/{TRANCO_ID}/{MAX_RANK}", "tranco_list")
        text = body.decode("utf-8")
        if st != 200 or len([l for l in text.splitlines() if l.strip()]) < MAX_RANK:
            raise Stop(f"Tranco top-{MAX_RANK} download: HTTP {st}")
        path.write_text(text, encoding="utf-8", newline="\n")
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r, d = line.strip().split(",", 1)
            rows.append((int(r), d))
    rows.sort()
    top100 = []
    for line in (CACHE / f"tranco_{TRANCO_ID}.csv").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r, d = line.strip().split(",", 1)
            top100.append((int(r), d))
    if rows[:100] != sorted(top100):
        raise SystemExit("[tranco] top-2000 file does not start with the cached top-100 list")
    meta = json.loads((CACHE / f"tranco_{TRANCO_ID}_meta.json").read_text(encoding="utf-8"))
    return meta, rows[:MAX_RANK]


def load_cluster(crawl):
    path = CACHE / "cluster" / f"{crawl}.cluster.idx"
    keys, entries = [], []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            key_ts, cdx_file, offset, length, _ = line.rstrip("\n").split("\t")
            keys.append(key_ts.rsplit(" ", 1)[0])
            entries.append((cdx_file, int(offset), int(length)))
    return keys, entries


_block_mem = {}


def block_lines(crawl, cdx_file, offset, length):
    k = (crawl, cdx_file, offset)
    if k in _block_mem:
        return _block_mem[k]
    path = CACHE / "blocks" / crawl / f"{cdx_file}_{offset}.gz"
    if path.exists():
        data = path.read_bytes()
        STATS["blocks_cache"] += 1
    else:
        url = f"{DATA}/cc-index/collections/{crawl}/indexes/{cdx_file}"
        st, data = request(url, "block_range", headers={"Range": f"bytes={offset}-{offset + length - 1}"})
        if st != 206 or len(data) != length:
            raise Stop(f"range {cdx_file}@{offset}: HTTP {st}, {len(data)} of {length} bytes")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        STATS["blocks_fetched"] += 1
        STATS["block_bytes"] += length
    lines = gzip.decompress(data).decode("utf-8", errors="replace").splitlines()
    if len(_block_mem) > 64:
        _block_mem.clear()
    _block_mem[k] = lines
    return lines


def surt_host(domain):
    host = domain.lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return ",".join(reversed(host.split(".")))


def lookup(crawl, keys, entries, domain):
    """Homepage lines for the domain plus the host's other keys seen in the fetched block(s)."""
    host = surt_host(domain)
    target, prefix = host + ")/", host + ")/"
    i = bisect.bisect_left(keys, target)
    j = max(i - 1, 0)
    home, other_keys, blocks = [], Counter(), []
    while j < len(entries):
        cdx_file, off, ln = entries[j]
        blocks.append(f"{cdx_file}@{off}")
        for line in block_lines(crawl, cdx_file, off, ln):
            k, ts, js = line.split(" ", 2)
            if k == target:
                rec = json.loads(js)
                rec.setdefault("timestamp", ts)
                home.append(rec)
            elif k.startswith(prefix):
                other_keys["robots.txt" if k == prefix + "robots.txt" else "other"] += 1
        if j + 1 >= len(entries) or keys[j + 1] > target:
            break
        j += 1
    return home, other_keys, blocks


def classify(home, other_keys):
    if any(str(r.get("status")) == "200" and r.get("mime") == "text/html" for r in home):
        return "qualified"
    if home:
        statuses = [str(r.get("status")) for r in home]
        if any(s == "200" for s in statuses):
            return "non_html"
        if all(s.startswith("3") for s in statuses):
            return "redirect_only"
        return "other_status"
    if other_keys.get("other"):
        return "other_paths_only"
    if other_keys.get("robots.txt"):
        return "robots_txt_only"
    return "host_absent"


def latest_ok(home):
    ok = [r for r in home if str(r.get("status")) == "200" and r.get("mime") == "text/html"]
    return max(ok, key=lambda r: r["timestamp"]) if ok else None


# Main

def rule_commit():
    out = subprocess.run(["git", "-C", str(REPO), "log", "-1", "--format=%H|%cI", "--",
                          str(RULE_FILE.relative_to(REPO)).replace("\\", "/")],
                         capture_output=True, text=True, encoding="utf-8").stdout.strip()
    dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--",
                            str(RULE_FILE.relative_to(REPO)).replace("\\", "/")],
                           capture_output=True, text=True, encoding="utf-8").stdout.strip()
    sha, when = out.split("|") if out else (None, None)
    return {"sha": sha, "committed": when, "working_copy_clean": dirty == ""}


def main():
    rc = rule_commit()
    if not rc["sha"] or not rc["working_copy_clean"]:
        raise SystemExit(f"[rule] sampling_rule.md must be committed and unchanged: {rc}")
    pid_file = CACHE / "scan.pid"
    if not OFFLINE:
        pid_file.write_text(str(os.getpid()), encoding="utf-8")
    print(f"[start] run {RUN_ID} pid {os.getpid()} offline={OFFLINE} rule {rc['sha'][:7]}", flush=True)
    started = time.monotonic()
    stopped, resume, rows = None, None, []
    meta = json.loads((CACHE / f"tranco_{TRANCO_ID}_meta.json").read_text(encoding="utf-8"))
    try:
        meta, ranks = tranco_ranks()
        idx = {c: load_cluster(c) for c in CRAWLS}
        qualified = 0
        for rank, dom in ranks:
            if qualified >= TARGET_QUALIFIED:
                break
            row = {"rank": rank, "domain": dom}
            for c in CRAWLS:
                try:
                    home, other, blocks = lookup(c, *idx[c], dom)
                except Stop:
                    resume = {"rank": rank, "domain": dom, "crawl": c}
                    raise
                ch = latest_ok(home)
                row[c] = {"class": classify(home, other), "homepage_lines": len(home),
                          "status_mime": dict(Counter(f"{r.get('status')}/{r.get('mime')}" for r in home)),
                          "other_host_keys": dict(other), "blocks": blocks,
                          "chosen": {k: ch.get(k) for k in ("url", "timestamp", "filename", "offset", "length",
                                                             "digest", "mime-detected")} if ch else None}
            row["qualified"] = all(row[c]["class"] == "qualified" for c in CRAWLS)
            qualified += row["qualified"]
            rows.append(row)
            print(f"[rank] {rank:4d} {dom:30s} " + " ".join(row[c]["class"][:12].ljust(12) for c in CRAWLS)
                  + f" q={qualified}", flush=True)
    except Stop as e:
        stopped = str(e)
        print("[STOP]", e, flush=True)
    finally:
        if not OFFLINE and pid_file.exists():
            pid_file.unlink()
    report(meta, rc, rows, stopped, resume, time.monotonic() - started)


def interval_of(rank):
    return next(f"{a}–{b}" for a, b in INTERVALS if a <= rank <= b)


def report(meta, rc, rows, stopped, resume, wall):
    qual = [r for r in rows if r["qualified"]]
    excl_reason = Counter()
    by_int = {f"{a}–{b}": Counter() for a, b in INTERVALS}
    for r in rows:
        iv = by_int[interval_of(r["rank"])]
        iv["processed"] += 1
        if r["qualified"]:
            iv["qualified"] += 1
        else:
            reasons = sorted({r[c]["class"] for c in CRAWLS if r[c]["class"] != "qualified"})
            for x in reasons:
                iv[f"excl:{x}"] += 1
            excl_reason[" + ".join(reasons)] += 1
    per_crawl = {c: dict(Counter(r[c]["class"] for r in rows)) for c in CRAWLS}
    rec_len = sum(int(r[c]["chosen"]["length"]) for r in qual for c in CRAWLS)
    log = [json.loads(l) for l in (CACHE / "requests_log.jsonl").read_text(encoding="utf-8").splitlines() if l]
    this = [e for e in log if e.get("run_id") == RUN_ID]
    gaps = []
    for a, b in zip(this, this[1:]):
        gaps.append((dt.datetime.fromisoformat(b["t_utc"]) - dt.datetime.fromisoformat(a["t_utc"])).total_seconds())
    out = {
        "run_id": RUN_ID, "offline": OFFLINE, "sampling_rule_commit": rc, "user_agent": UA,
        "tranco": {"list_id": meta["list_id"], "created_on": meta.get("created_on")},
        "crawls": CRAWLS, "target_qualified": TARGET_QUALIFIED, "max_rank": MAX_RANK,
        "stopped": stopped, "resume_point": resume, "wall_s": wall,
        "processed": len(rows), "qualified": len(qual), "last_rank_processed": rows[-1]["rank"] if rows else None,
        "by_interval": {k: dict(v) for k, v in by_int.items()},
        "exclusion_reasons": dict(excl_reason.most_common()), "per_crawl_class": per_crawl,
        "requests_this_run": {"total": len(this), "by_kind_status": dict(Counter(f"{e['kind']} {e['status']}"
                                                                                 for e in this)),
                              "retries": sum(e["attempt"] > 1 for e in this),
                              "min_gap_s": min(gaps) if gaps else None, **{k: v for k, v in STATS.items()}},
        "requests_all_runs": {"total": len(log), "by_kind_status": dict(Counter(f"{e['kind']} {e['status']}"
                                                                                for e in log))},
        "phase2_estimate": {"records": 2 * len(qual), "length_bytes": rec_len, "range_requests": 2 * len(qual)},
        "qualified_domains": [{"rank": r["rank"], "domain": r["domain"],
                               **{c: r[c]["chosen"] for c in CRAWLS},
                               "same_digest": r[CRAWLS[0]]["chosen"]["digest"] == r[CRAWLS[1]]["chosen"]["digest"]}
                              for r in qual],
        "rows": rows,
    }
    (HERE / "dry_run.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n",
                                       encoding="utf-8", newline="\n")
    write_md(out)
    print(f"[done] processed={len(rows)} qualified={len(qual)} records={2 * len(qual)} "
          f"MB={rec_len / 1e6:.2f} requests={len(this)} stopped={stopped}", flush=True)


def md_table(headers, rows):
    out = ["| " + " | ".join(str(h) for h in headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |" for r in rows]
    return out


def write_md(o):
    rc, rq, est = o["sampling_rule_commit"], o["requests_this_run"], o["phase2_estimate"]
    c0, c1 = CRAWLS
    L = ["# Common Crawl Part A — Phase 1 (expanded) dry-run: index only, no HTML downloaded", ""]
    if o["stopped"]:
        L += [f"**Stopped:** {o['stopped']}", "",
              f"**Resume point:** {json.dumps(o['resume_point'])} — re-run the script; cached blocks are not "
              "fetched again.", ""]
    L += [f"- Sampling rule: `sampling_rule.md`, committed **{rc['sha']}** at {rc['committed']} "
          f"(working copy unchanged: {rc['working_copy_clean']}), before this run.",
          f"- Run `{o['run_id']}` (offline report: {o['offline']}); wall time {o['wall_s']:.0f} s.",
          f"- Tranco **{o['tranco']['list_id']}** (created_on {o['tranco']['created_on']}), ranks 1–{o['max_rank']}; "
          f"crawls `{c0}`, `{c1}`.",
          "- Index: zipnum CDX on data.commoncrawl.org (cached `cluster.idx`; one range request per cdx block, each "
          "block fetched at most once and shared by all domains whose homepage key falls in it).",
          f"- Network rules: User-Agent `{o['user_agent']}`; ≥ {MIN_GAP} s between requests, one process, no "
          f"parallel requests; 5xx/timeout → waits {WAITS} s then stop with resume point; 403/429/block → stop.",
          "- Earlier runs (2026-10-12, same cache): the CDX-server attempt (504 on every query) and the first zipnum "
          "run (stopped on 503 at `CC-MAIN-2026-21/cdx-00079.gz`, ranks 94–100 not processed) used an earlier "
          "contact address in the User-Agent and a 1 s interval.",
          "- Cache: `<repo>\\..\\_external\\cc_cache\\`. Script: `cc_index_scan.py`. No LLM calls.", "",
          "## Result", ""]
    L += md_table(["measure", "value"], [
        ["domains processed (rank order)", f"{o['processed']} (last rank {o['last_rank_processed']})"],
        ["**qualified (both crawls, status 200 + text/html homepage)**", f"**{o['qualified']}** "
                                                                          f"of target {o['target_qualified']}"],
    ])
    L += ["", "## By rank interval", ""]
    reasons = ["redirect_only", "non_html", "other_status", "robots_txt_only", "other_paths_only", "host_absent"]
    L += md_table(["ranks", "processed", "qualified"] + [f"excl: {x}" for x in reasons],
                  [[k, v.get("processed", 0), v.get("qualified", 0)] + [v.get(f"excl:{x}", 0) for x in reasons]
                   for k, v in o["by_interval"].items()])
    L += ["", "An excluded domain is counted under every reason that applies to it in either crawl, so the reason "
          "columns can sum to more than the excluded count.", "",
          "## Exclusion reasons (combined over both crawls, per domain)", ""]
    L += md_table(["reason(s)", "domains"], [[k, v] for k, v in o["exclusion_reasons"].items()])
    L += ["", "Per crawl:", ""]
    L += md_table(["class", c0, c1], [[k, o["per_crawl_class"][c0].get(k, 0), o["per_crawl_class"][c1].get(k, 0)]
                                      for k in ["qualified"] + reasons])
    L += ["", "## Requests", ""]
    L += md_table(["measure", "this run", "all runs (requests_log.jsonl)"], [
        ["HTTP requests (incl. retries)", rq["total"], o["requests_all_runs"]["total"]],
        ["by kind / status", json.dumps(rq["by_kind_status"]), json.dumps(o["requests_all_runs"]["by_kind_status"])],
        ["retries", rq["retries"], ""],
        ["blocks fetched / read from cache", f"{rq.get('blocks_fetched', 0)} / {rq.get('blocks_cache', 0)}", ""],
        ["block bytes fetched", f"{rq.get('block_bytes', 0):,}", ""],
        ["time spent in 5xx waits (s)", rq.get("wait_s", 0), ""],
        ["min gap between consecutive requests (s)",
         f"{rq['min_gap_s']:.3f}" if rq["min_gap_s"] is not None else "n/a", ""],
    ])
    L += ["", "## Phase 2 estimate (not downloaded)", ""]
    L += md_table(["measure", "value"], [
        ["WARC records (1 per qualified domain per crawl, latest)", est["records"]],
        ["sum of `length` (compressed)", f"{est['length_bytes']:,} bytes ({est['length_bytes'] / 1e6:.2f} MB)"],
        ["range requests to data.commoncrawl.org", f"{est['range_requests']} (≥ {est['range_requests'] * MIN_GAP:.0f} s "
                                                   f"at the current interval)"],
    ])
    L += ["", "## Qualified domains", ""]
    L += md_table(["#", "rank", "domain", f"{c0} url", "ts", "length", f"{c1} url", "ts", "length", "same digest"],
                  [[i + 1, q["rank"], q["domain"], q[c0]["url"], q[c0]["timestamp"], q[c0]["length"],
                    q[c1]["url"], q[c1]["timestamp"], q[c1]["length"], "yes" if q["same_digest"] else "no"]
                   for i, q in enumerate(o["qualified_domains"])])
    L += ["", "Per-domain classification of every processed domain (incl. excluded): `dry_run.json` → `rows`."]
    (HERE / "dry_run.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
