"""
cc_fetch_warc.py — analysis_plan.md, Snapshots + Integrity: fetch the 200 chosen WARC records
(dry_run.json -> qualified_domains, one per domain per crawl) from data.commoncrawl.org and
check their integrity. Raw records are stored only in ../_external/cc_cache/warc/.

Run from the repository root:

    python -I experiments/results/revision1/cc_volatility/cc_fetch_warc.py            # fetch / resume, then check
    python -I experiments/results/revision1/cc_volatility/cc_fetch_warc.py --offline  # check cached records only

Network rules: User-Agent UA below; ≥ 2 s between requests, one process; on 5xx /
timeout / connection error wait 30 s, 60 s, 120 s, then stop with a resume point; 403 / 429 /
block page -> stop, no circumvention. Cached records are not fetched again. PID in
cc_cache/fetch.pid.

Integrity per record: WARC-Payload-Digest == "sha1:" + index digest (required); recomputed base32
SHA-1 of the payload; WARC-Target-URI == index url; WARC-Type response; HTTP status 200.
Writes fetch_integrity.md / .json next to this file (no HTML). Exit 1 if any required check fails.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import base64
import datetime as dt
import gzip
import hashlib
import http.client
import json
import os
import pathlib
import subprocess
import time
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[3]
CACHE = pathlib.Path(__file__).resolve().parents[4].parent / "_external" / "cc_cache"
WARC_DIR = CACHE / "warc"
DATA = "https://data.commoncrawl.org"
UA = "academic research (TU Sofia PhD), antonsangelov@tu-sofia.bg"
MIN_GAP = 2.05
WAITS = [30, 60, 120]
TIMEOUT = 120
BLOCK_MARKERS = ("unusual traffic", "blocked", "rate limit")
OFFLINE = "--offline" in sys.argv
RUN_ID = "fetch-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
_last = [0.0]


class Stop(Exception):
    pass


def request(url, headers):
    attempt = 0
    while True:
        attempt += 1
        wait = _last[0] + MIN_GAP - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()
        t0 = time.monotonic()
        wall = dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")
        status, body, err = None, b"", None
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, **headers})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                status, body = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, body = e.code, e.read() or b""
        except (OSError, http.client.HTTPException) as e:
            err = f"{type(e).__name__}: {e}"
        head = body[:2000].decode("utf-8", errors="replace").lower() if status not in (200, 206) else ""
        blocked = status in (403, 429) or any(m in head for m in BLOCK_MARKERS)
        with (CACHE / "requests_log.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"run_id": RUN_ID, "t_utc": wall, "kind": "warc_range", "url": url,
                                 "range": headers.get("Range"), "attempt": attempt, "status": status,
                                 "error": err, "elapsed_s": round(time.monotonic() - t0, 3),
                                 "bytes": len(body), "blocked": blocked}) + "\n")
        if blocked:
            raise Stop(f"HTTP {status} at {url} — stopped, no circumvention")
        if err is None and status is not None and status < 500:
            return status, body
        if attempt > len(WAITS):
            raise Stop(f"{status or err} after {attempt} attempts at {url} {headers.get('Range')}")
        print(f"[wait] {status or err} -> {WAITS[attempt - 1]} s", flush=True)
        time.sleep(WAITS[attempt - 1])


def parse_record(raw_gz: bytes):
    data = gzip.decompress(raw_gz)
    h_end = data.index(b"\r\n\r\n")
    warc_lines = data[:h_end].decode("utf-8", errors="replace").split("\r\n")
    warc = {}
    for line in warc_lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            warc[k.strip().lower()] = v.strip()
    block = data[h_end + 4:]
    clen = int(warc.get("content-length", len(block)))
    block = block[:clen]
    hh_end = block.index(b"\r\n\r\n")
    http_lines = block[:hh_end].decode("iso-8859-1").split("\r\n")
    status = int(http_lines[0].split()[1]) if len(http_lines[0].split()) > 1 else None
    http_h = {}
    for line in http_lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            http_h.setdefault(k.strip().lower(), v.strip())
    payload = block[hh_end + 4:]
    return warc_lines[0], warc, status, http_h, payload


def main():
    dry = json.loads((HERE / "dry_run.json").read_text(encoding="utf-8"))
    crawls = dry["crawls"]
    plan = subprocess.run(["git", "-C", str(REPO), "log", "-1", "--format=%H|%cI", "--",
                           "experiments/results/revision1/cc_volatility/analysis_plan.md"],
                          capture_output=True, text=True).stdout.strip().split("|")
    jobs = []
    for q in dry["qualified_domains"]:
        for c in crawls:
            r = q[c]
            jobs.append({"rank": q["rank"], "domain": q["domain"], "crawl": c, "url": r["url"],
                         "filename": r["filename"], "offset": int(r["offset"]), "length": int(r["length"]),
                         "digest": r["digest"],
                         "path": WARC_DIR / c / f"{q['rank']:04d}_{q['domain']}.warc.gz"})
    if len(jobs) != 200:
        raise SystemExit(f"expected 200 records, found {len(jobs)}")
    stopped, fetched = None, 0
    pid_file = CACHE / "fetch.pid"
    if not OFFLINE:
        pid_file.write_text(str(os.getpid()), encoding="utf-8")
    print(f"[start] {RUN_ID} pid {os.getpid()} offline={OFFLINE}", flush=True)
    try:
        for j in jobs:
            if j["path"].exists() or OFFLINE:
                continue
            st, body = request(f"{DATA}/{j['filename']}",
                               {"Range": f"bytes={j['offset']}-{j['offset'] + j['length'] - 1}"})
            if st != 206 or len(body) != j["length"]:
                raise Stop(f"{j['domain']} {j['crawl']}: HTTP {st}, {len(body)} of {j['length']} bytes")
            j["path"].parent.mkdir(parents=True, exist_ok=True)
            tmp = j["path"].with_suffix(".part")
            tmp.write_bytes(body)
            tmp.replace(j["path"])
            fetched += 1
            print(f"[warc] {j['rank']:4d} {j['domain']:28s} {j['crawl']} {len(body)}", flush=True)
    except Stop as e:
        stopped = str(e)
        print("[STOP]", e, flush=True)
    finally:
        if not OFFLINE and pid_file.exists():
            pid_file.unlink()

    rows = []
    for j in jobs:
        row = {k: j[k] for k in ("rank", "domain", "crawl", "url", "length", "digest")}
        if not j["path"].exists():
            row["present"] = False
            rows.append(row)
            continue
        raw = j["path"].read_bytes()
        first, warc, status, http_h, payload = parse_record(raw)
        recomputed = base64.b32encode(hashlib.sha1(payload).digest()).decode()
        row.update({
            "present": True, "bytes_on_disk": len(raw), "size_ok": len(raw) == j["length"],
            "warc_version": first, "warc_type": warc.get("warc-type"),
            "payload_digest_header": warc.get("warc-payload-digest"),
            "digest_header_ok": warc.get("warc-payload-digest") == "sha1:" + j["digest"],
            "digest_recomputed_ok": recomputed == j["digest"],
            "target_uri_ok": warc.get("warc-target-uri") == j["url"],
            "http_status": status, "truncated": warc.get("warc-truncated"),
            "content_encoding": http_h.get("content-encoding"),
            "x_crawler_content_encoding": http_h.get("x-crawler-content-encoding"),
            "content_type": http_h.get("content-type"), "payload_bytes": len(payload),
        })
        row["required_ok"] = (row["size_ok"] and row["digest_header_ok"] and row["warc_type"] == "response"
                              and row["target_uri_ok"] and status == 200)
        rows.append(row)
    present = [r for r in rows if r.get("present")]
    req_ok = sum(1 for r in present if r["required_ok"])
    out = {"run_id": RUN_ID, "offline": OFFLINE, "stopped": stopped, "fetched_this_run": fetched,
           "analysis_plan_commit": {"sha": plan[0] if plan else None, "committed": plan[1] if len(plan) > 1 else None},
           "user_agent": UA, "records": len(rows), "present": len(present),
           "digest_header_ok": sum(r["digest_header_ok"] for r in present),
           "digest_recomputed_ok": sum(r["digest_recomputed_ok"] for r in present),
           "target_uri_ok": sum(r["target_uri_ok"] for r in present),
           "warc_type_response": sum(r["warc_type"] == "response" for r in present),
           "http_200": sum(r["http_status"] == 200 for r in present),
           "size_ok": sum(r["size_ok"] for r in present),
           "required_ok": req_ok, "truncated": sum(1 for r in present if r["truncated"]),
           "content_encoding_gzip": sum(1 for r in present if (r["content_encoding"] or "").lower() == "gzip"),
           "total_bytes": sum(r["bytes_on_disk"] for r in present), "rows": rows}
    (HERE / "fetch_integrity.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n",
                                               encoding="utf-8", newline="\n")
    L = ["# WARC fetch and integrity (200 records)", ""]
    if stopped:
        L += [f"**Stopped:** {stopped}. Re-run to resume; cached records are not fetched again.", ""]
    L += [f"- analysis_plan.md commit: `{out['analysis_plan_commit']['sha']}` "
          f"({out['analysis_plan_commit']['committed']})",
          f"- Run `{RUN_ID}` (offline: {OFFLINE}); fetched this run: {fetched}. User-Agent `{UA}`; ≥ {MIN_GAP} s "
          f"between requests; 5xx waits {WAITS} s.",
          "- Raw records only in `<repo>\\..\\_external\\cc_cache\\warc\\` (not in the repository).", ""]
    L += [
        "| check | records |", "|---|---|",
        f"| present in cache | {out['present']}/200 |",
        f"| size == index length | {out['size_ok']}/200 |",
        f"| **WARC-Payload-Digest == sha1:+index digest (required)** | **{out['digest_header_ok']}/200** |",
        f"| recomputed base32 SHA-1 of payload == index digest | {out['digest_recomputed_ok']}/200 |",
        f"| WARC-Target-URI == index url | {out['target_uri_ok']}/200 |",
        f"| WARC-Type response | {out['warc_type_response']}/200 |",
        f"| HTTP status 200 | {out['http_200']}/200 |",
        f"| all required checks | {out['required_ok']}/200 |",
        f"| WARC-Truncated present | {out['truncated']} |",
        f"| HTTP Content-Encoding gzip | {out['content_encoding_gzip']} |",
        f"| bytes on disk | {out['total_bytes']:,} |",
    ]
    bad = [r for r in rows if not r.get("present") or not r.get("required_ok") or not r.get("digest_recomputed_ok")]
    if bad:
        L += ["", "Records failing any check:", "", "| rank | domain | crawl | present | required | header digest | "
              "recomputed digest | uri | status |", "|---|---|---|---|---|---|---|---|---|"]
        L += [f"| {r['rank']} | {r['domain']} | {r['crawl']} | {r.get('present')} | {r.get('required_ok')} | "
              f"{r.get('digest_header_ok')} | {r.get('digest_recomputed_ok')} | {r.get('target_uri_ok')} | "
              f"{r.get('http_status')} |" for r in bad]
    (HERE / "fetch_integrity.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print(f"[integrity] present {out['present']}/200 header-digest {out['digest_header_ok']}/200 "
          f"recomputed {out['digest_recomputed_ok']}/200 required {req_ok}/200 stopped={stopped}")
    sys.exit(0 if (req_ok == 200 and not stopped) else 1)


if __name__ == "__main__":
    main()
