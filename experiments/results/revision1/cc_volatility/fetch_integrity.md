# WARC fetch and integrity (200 records)

- analysis_plan.md commit: `d8f1bc9bf81a71c9a80f51ba57eacc96a110ae73` (2026-10-12T14:32:55+03:00)
- Run `fetch-20261012T113522Z` (offline: False); fetched this run: 200. User-Agent `academic research (TU Sofia PhD), antonsangelov@tu-sofia.bg`; ≥ 2.05 s between requests; 5xx waits [30, 60, 120] s.
- Raw records only in `<repo>\..\_external\cc_cache\warc\` (not in the repository).

| check | records |
|---|---|
| present in cache | 200/200 |
| size == index length | 200/200 |
| **WARC-Payload-Digest == sha1:+index digest (required)** | **200/200** |
| recomputed base32 SHA-1 of payload == index digest | 200/200 |
| WARC-Target-URI == index url | 200/200 |
| WARC-Type response | 200/200 |
| HTTP status 200 | 200/200 |
| all required checks | 200/200 |
| WARC-Truncated present | 0 |
| HTTP Content-Encoding gzip | 0 |
| bytes on disk | 9,179,041 |
