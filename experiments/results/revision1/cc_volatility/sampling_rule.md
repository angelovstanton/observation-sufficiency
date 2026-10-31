# Sampling rule — Common Crawl Part A (pre-registered)

Written and committed before the expanded index run. No results of that run had been looked at when this rule was fixed.

## Rule

> The first 100 domains, in the order of Tranco list 4672X, that have a homepage with status 200 and mime text/html in **both** CC-MAIN-2026-21 and CC-MAIN-2026-39. Redirects, robots.txt-only and non-HTML are excluded. No manual exclusion of domains.

## Operational definitions

- **Ranking:** Tranco list `4672X` (created_on 2026-10-11T22:00, window 2026-09-12…2026-10-11). Domains are processed in ascending rank order. Processing stops when **100 qualified domains** have been found or **rank 2000** has been processed, whichever comes first.
- **Crawls:** `CC-MAIN-2026-21` (2026-05-08…05-21) and `CC-MAIN-2026-39` (2026-09-04…09-17).
- **Homepage:** the index lines whose SURT key equals `<reversed host>)/`. This means path `/` with no query string, any scheme, and a leading `www.` stripped by the SURT canonicalisation. The lines are read from each crawl's zipnum CDX index (`cluster.idx` + `cdx-*.gz` blocks on data.commoncrawl.org).
- **Qualifies in a crawl:** at least one homepage line with `status == "200"` and `mime == "text/html"`.
- **Qualifies:** qualifies in both crawls.
- **Exclusion reasons** (recorded per crawl; a domain is excluded if it fails either crawl):
  - `redirect_only`: homepage lines exist, and all of them are 3xx;
  - `non_html`: a status-200 homepage line exists, but none has mime `text/html`;
  - `other_status`: homepage lines exist, none is 200 and not all are 3xx;
  - `robots_txt_only`: no homepage line; in the fetched index block(s), the only keys for the host are `/robots.txt`;
  - `other_paths_only`: no homepage line; other paths of the host are present in the fetched block(s);
  - `host_absent`: no key for the host in the fetched block(s).
- **Record chosen for Phase 2:** per qualified domain and crawl, the latest status-200 text/html homepage line.
- **No manual exclusion:** no domain is added, removed or reordered by hand.
