# Common Crawl Part A — volatility analysis (per analysis_plan.md)

- **analysis_plan.md commit `d8f1bc9bf81a71c9a80f51ba57eacc96a110ae73`** (2026-10-12T14:32:55+03:00; working copy clean: True). Sampling rule: `sampling_rule.md` (commit `4cb40ce`).
- Crawls: May `CC-MAIN-2026-21` → September `CC-MAIN-2026-39`; 100 domains (dry_run.json → qualified_domains).
- Integrity: required checks 200/200; WARC-Payload-Digest == index digest 200/200; recomputed SHA-1 200/200; target URI 200/200; WARC-Truncated 0; gzip Content-Encoding 0.
- Classifier of record: C# CLI (reflection on `Oracle.IsVolatileClass` / `Oracle.IsVolatileId`, Oracle source unchanged). Python port agreement: corpus {"class": 1073, "id": 234}; Common Crawl values 30089/30089.
- Extraction: html.parser; decoding {"charset_http": 149, "charset_meta": 45, "charset_default_utf8": 6} (HTTP charset → meta charset → UTF-8, errors replaced).
- Bootstrap: domain-clustered percentile, 10,000 replicates, seed 42; clusters = domains with ≥1 unit of the type; replicates with undefined Δ are excluded and counted.
- Limitation (pre-registered): Common Crawl stores server HTML, not the rendered DOM. Classes generated in the browser are missing, so prevalence is underestimated.

## Primary metric: Δ = P(vanish | flagged) − P(vanish | unflagged)

| type | domains | flagged vanished | unflagged vanished | Δ | 95% CI | undefined replicates | pre-registered interpretation |
|---|---|---|---|---|---|---|---|
| class | 94 | 1517/3268 (46.4%) | 2656/19349 (13.7%) | **0.327** | [0.107, 0.555] | 0 | support (95% CI lower bound > 0) |
| id | 94 | 3/49 (6.1%) | 1157/4748 (24.4%) | **-0.182** | [-0.290, -0.082] | 0 | no support by the pre-registered criterion (95% CI lower bound ≤ 0 or undefined); reported as is |

## Pre-specified sensitivity analyses

| type | sensitivity | domains | flagged vanished | unflagged vanished | Δ | 95% CI | undefined replicates |
|---|---|---|---|---|---|---|---|
| class | without 4 identical-digest domains | 91 | 1517/3268 | 2656/19272 | 0.326 | [0.097, 0.556] | 0 |
| class | without 9 domains with class Jaccard < 0.2 | 85 | 441/2129 | 1640/18215 | 0.117 | [0.008, 0.273] | 0 |
| id | without 4 identical-digest domains | 91 | 3/49 | 1157/4714 | -0.184 | [-0.289, -0.080] | 0 |
| id | without 9 domains with class Jaccard < 0.2 | 85 | 2/47 | 836/4011 | -0.166 | [-0.272, -0.070] | 0 |

- (a) identical-digest domains: google.cn, ipify.org, nic.ru, quickconnect.to
- (b) class-token Jaccard < 0.2: adobe.com, dnsmadeeasy.com, ea.com, intuit.com, publicnode.com, reg.ru, stanford.edu, tradingview.com, ui.com

## Secondary metrics

| type | units | flagged | vanished | flagged ∩ vanished | precision | recall | prevalence (domains with ≥1 flagged) |
|---|---|---|---|---|---|---|---|
| class | 22617 | 3268 | 4173 | 1517 | 46.4% | 36.4% | 37 of 94 |
| id | 4797 | 49 | 1160 | 3 | 6.1% | 0.3% | 26 of 94 |

## Exclusion (count only; no manual removal)

- Domains with no class units: 6; with no id units: 6; with neither: 2.

## Flagged values that do not vanish — class (top 50 of 1662; full list in the json)

Ordered by number of domains holding the value, then by May occurrences.

| # | value | domains | May occurrences | domains (first 5) |
|---|---|---|---|---|
| 1 | `hf-lv5cx6u` | 2 | 52 | afternic.com, godaddy.com |
| 2 | `hf-m15cvwti` | 2 | 52 | afternic.com, godaddy.com |
| 3 | `hf-ln3msan` | 2 | 49 | afternic.com, godaddy.com |
| 4 | `hf-p1u0inax` | 2 | 49 | afternic.com, godaddy.com |
| 5 | `hf-ppl2bc7` | 2 | 49 | afternic.com, godaddy.com |
| 6 | `hf-i1q4o4xg` | 2 | 46 | afternic.com, godaddy.com |
| 7 | `hf-t1ij7wf4` | 2 | 46 | afternic.com, godaddy.com |
| 8 | `aem-GridColumn` | 2 | 37 | cisco.com, webex.com |
| 9 | `aem-GridColumn--default--12` | 2 | 37 | cisco.com, webex.com |
| 10 | `core-h17vrswi` | 2 | 29 | afternic.com, godaddy.com |
| 11 | `core-b15fsowq` | 2 | 24 | afternic.com, godaddy.com |
| 12 | `core-s1804idb` | 2 | 23 | afternic.com, godaddy.com |
| 13 | `core-hcnpz2u` | 2 | 20 | afternic.com, godaddy.com |
| 14 | `core-s1su50ie` | 2 | 20 | afternic.com, godaddy.com |
| 15 | `core-sxkv74n` | 2 | 20 | afternic.com, godaddy.com |
| 16 | `core-too7oxc` | 2 | 20 | afternic.com, godaddy.com |
| 17 | `hf-mudrw4` | 2 | 20 | afternic.com, godaddy.com |
| 18 | `utils-la6fqgq` | 2 | 20 | afternic.com, godaddy.com |
| 19 | `hf-p1xu2113` | 2 | 19 | afternic.com, godaddy.com |
| 20 | `core-b13z7tp` | 2 | 15 | afternic.com, godaddy.com |
| 21 | `core-c3duzvn` | 2 | 14 | afternic.com, godaddy.com |
| 22 | `core-a1h184dg` | 2 | 12 | afternic.com, godaddy.com |
| 23 | `hf-f1h68os2` | 2 | 11 | afternic.com, godaddy.com |
| 24 | `hf-clcl7vw` | 2 | 10 | afternic.com, godaddy.com |
| 25 | `hf-l7spyb0` | 2 | 10 | afternic.com, godaddy.com |
| 26 | `hf-lqu3uao` | 2 | 10 | afternic.com, godaddy.com |
| 27 | `core-icc1n5l` | 2 | 9 | afternic.com, godaddy.com |
| 28 | `hf-b9y7avr` | 2 | 8 | afternic.com, godaddy.com |
| 29 | `hf-c114sg9p` | 2 | 8 | afternic.com, godaddy.com |
| 30 | `hf-f16iarpm` | 2 | 8 | afternic.com, godaddy.com |
| 31 | `hf-l1ii7a7y` | 2 | 8 | afternic.com, godaddy.com |
| 32 | `hf-pod6hzb` | 2 | 8 | afternic.com, godaddy.com |
| 33 | `hf-pvbr9ud` | 2 | 8 | afternic.com, godaddy.com |
| 34 | `hf-slmd4st` | 2 | 8 | afternic.com, godaddy.com |
| 35 | `hf-t1h32llk` | 2 | 8 | afternic.com, godaddy.com |
| 36 | `hf-te5vngw` | 2 | 8 | afternic.com, godaddy.com |
| 37 | `hf-tf8kz14` | 2 | 8 | afternic.com, godaddy.com |
| 38 | `core-c1y6sif5` | 2 | 7 | afternic.com, godaddy.com |
| 39 | `pl-c1drraik` | 2 | 6 | afternic.com, godaddy.com |
| 40 | `pl-chz7pee` | 2 | 6 | afternic.com, godaddy.com |
| 41 | `pl-hj2p61o` | 2 | 6 | afternic.com, godaddy.com |
| 42 | `pl-nzn4cn3` | 2 | 6 | afternic.com, godaddy.com |
| 43 | `pl-i18fuk58` | 2 | 5 | afternic.com, godaddy.com |
| 44 | `hf-a12u7o5h` | 2 | 4 | afternic.com, godaddy.com |
| 45 | `hf-a6182l0` | 2 | 4 | afternic.com, godaddy.com |
| 46 | `hf-aseww77` | 2 | 4 | afternic.com, godaddy.com |
| 47 | `hf-l6yp8fo` | 2 | 4 | afternic.com, godaddy.com |
| 48 | `hf-sqlzn88` | 2 | 4 | afternic.com, godaddy.com |
| 49 | `hf-ag0hwu5` | 2 | 2 | afternic.com, godaddy.com |
| 50 | `hf-avb2oz` | 2 | 2 | afternic.com, godaddy.com |

## Flagged values that do not vanish — id (top 50 of 36; full list in the json)

Ordered by number of domains holding the value, then by May occurrences.

| # | value | domains | May occurrences | domains (first 5) |
|---|---|---|---|---|
| 1 | `root` | 11 | 11 | alibaba.com, alidns.com, brave.com, dropbox.com, icloud.com |
| 2 | `header-780805927` | 1 | 2 | zendesk.com |
| 3 | `logotyperow-2040651129` | 1 | 2 | zendesk.com |
| 4 | `registrar` | 1 | 2 | afternic.com |
| 5 | `brxe-700350` | 1 | 1 | cpanel.net |
| 6 | `card-1580811885` | 1 | 1 | zendesk.com |
| 7 | `card-476884257` | 1 | 1 | zendesk.com |
| 8 | `cardborderhomepage-119069955` | 1 | 1 | zendesk.com |
| 9 | `cardborderhomepage-527894180` | 1 | 1 | zendesk.com |
| 10 | `footer-1719023883` | 1 | 1 | zendesk.com |
| 11 | `grid-2033195130` | 1 | 1 | zendesk.com |
| 12 | `grid-255158047` | 1 | 1 | zendesk.com |
| 13 | `linkgroup-1095665584` | 1 | 1 | zendesk.com |
| 14 | `linkgroup-2068739669` | 1 | 1 | zendesk.com |
| 15 | `module-2089378850` | 1 | 1 | hichina.com |
| 16 | `module-2253284990` | 1 | 1 | hichina.com |
| 17 | `module-4963038160` | 1 | 1 | hichina.com |
| 18 | `module-5408573160` | 1 | 1 | hichina.com |
| 19 | `module-6277917400` | 1 | 1 | hichina.com |
| 20 | `module-7020789490` | 1 | 1 | hichina.com |
| 21 | `module-8002707080` | 1 | 1 | hichina.com |
| 22 | `popmake-872473` | 1 | 1 | nasa.gov |
| 23 | `post-128943` | 1 | 1 | nasa.gov |
| 24 | `post-400042` | 1 | 1 | criteo.com |
| 25 | `post-408017` | 1 | 1 | criteo.com |
| 26 | `post-417529` | 1 | 1 | criteo.com |
| 27 | `pum-872473` | 1 | 1 | nasa.gov |
| 28 | `reddit` | 1 | 1 | android.com |
| 29 | `regionSelector` | 1 | 1 | shopify.com |
| 30 | `related` | 1 | 1 | youtube.com |
| 31 | `requestId` | 1 | 1 | yandex.com |
| 32 | `resolveID` | 1 | 1 | doi.org |
| 33 | `resources` | 1 | 1 | zendesk.com |
| 34 | `reverse` | 1 | 1 | taboola.com |
| 35 | `reviews` | 1 | 1 | netangels.ru |
| 36 | `statshomepage-535691094` | 1 | 1 | zendesk.com |
