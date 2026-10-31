# Common Crawl Part A — Phase 1 (expanded) dry-run: index only, no HTML downloaded

- Sampling rule: `sampling_rule.md`, committed **4cb40ce8475356dc5c1edb23b06ff2dc0cf80a6d** at 2026-10-12T13:46:22+03:00 (working copy unchanged: True), before this run.
- Run `20261012T111619Z` (offline report: False); wall time 491 s.
- Tranco **4672X** (created_on 2026-10-11T22:00:02.355906), ranks 1–2000; crawls `CC-MAIN-2026-21`, `CC-MAIN-2026-39`.
- Index: zipnum CDX on data.commoncrawl.org (cached `cluster.idx`; one range request per cdx block, each block fetched at most once and shared by all domains whose homepage key falls in it).
- Network rules: User-Agent `academic research (TU Sofia PhD), antonsangelov@tu-sofia.bg`; ≥ 2.05 s between requests, one process, no parallel requests; 5xx/timeout → waits [30, 60, 120] s then stop with resume point; 403/429/block → stop.
- Earlier runs (2026-10-12, same cache): the CDX-server attempt (504 on every query) and the first zipnum run (stopped on 503 at `CC-MAIN-2026-21/cdx-00079.gz`, ranks 94–100 not processed) used an earlier contact address in the User-Agent and a 1 s interval.
- Cache: `<repo>\..\_external\cc_cache\`. Script: `cc_index_scan.py`. No LLM calls.

## Result

| measure | value |
|---|---|
| domains processed (rank order) | 423 (last rank 423) |
| **qualified (both crawls, status 200 + text/html homepage)** | **100** of target 100 |

## By rank interval

| ranks | processed | qualified | excl: redirect_only | excl: non_html | excl: other_status | excl: robots_txt_only | excl: other_paths_only | excl: host_absent |
|---|---|---|---|---|---|---|---|---|
| 1–100 | 100 | 18 | 22 | 0 | 2 | 21 | 14 | 34 |
| 101–500 | 323 | 82 | 47 | 1 | 14 | 44 | 40 | 130 |
| 501–1000 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 1001–2000 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

An excluded domain is counted under every reason that applies to it in either crawl, so the reason columns can sum to more than the excluded count.

## Exclusion reasons (combined over both crawls, per domain)

| reason(s) | domains |
|---|---|
| host_absent | 141 |
| redirect_only | 53 |
| robots_txt_only | 43 |
| other_paths_only | 30 |
| host_absent + robots_txt_only | 9 |
| other_status | 9 |
| other_paths_only + robots_txt_only | 8 |
| other_paths_only + redirect_only | 8 |
| host_absent + other_paths_only | 6 |
| host_absent + redirect_only | 5 |
| redirect_only + robots_txt_only | 3 |
| host_absent + other_status | 3 |
| other_status + robots_txt_only | 2 |
| other_paths_only + other_status | 2 |
| non_html | 1 |

Per crawl:

| class | CC-MAIN-2026-21 | CC-MAIN-2026-39 |
|---|---|---|
| qualified | 108 | 108 |
| redirect_only | 58 | 61 |
| non_html | 1 | 1 |
| other_status | 13 | 11 |
| robots_txt_only | 52 | 51 |
| other_paths_only | 37 | 41 |
| host_absent | 154 | 150 |

## Requests

| measure | this run | all runs (requests_log.jsonl) |
|---|---|---|
| HTTP requests (incl. retries) | 162 | 863 |
| by kind / status | {"block_range 206": 158, "block_range None": 1, "block_range 503": 3} | {"cluster_head 200": 2, "cluster_get 200": 2, "block_range 206": 820, "block_range 503": 35, "tranco_list 200": 1, "block_range None": 3} |
| retries | 4 |  |
| blocks fetched / read from cache | 158 / 686 |  |
| block bytes fetched | 38,107,227 |  |
| time spent in 5xx waits (s) | 120 |  |
| min gap between consecutive requests (s) | 2.039 |  |

## Phase 2 estimate (not downloaded)

| measure | value |
|---|---|
| WARC records (1 per qualified domain per crawl, latest) | 200 |
| sum of `length` (compressed) | 9,179,041 bytes (9.18 MB) |
| range requests to data.commoncrawl.org | 200 (≥ 410 s at the current interval) |

## Qualified domains

| # | rank | domain | CC-MAIN-2026-21 url | ts | length | CC-MAIN-2026-39 url | ts | length | same digest |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2 | cloudflare.com | https://www.cloudflare.com/ | 20260521142116 | 295235 | https://www.cloudflare.com/ | 20260917043037 | 275733 | no |
| 2 | 9 | apple.com | https://www.apple.com/ | 20260521204528 | 44924 | https://www.apple.com/ | 20260916193231 | 44655 | no |
| 3 | 10 | youtube.com | https://www.youtube.com/ | 20260521195828 | 204551 | https://www.youtube.com/ | 20260917031918 | 253967 | no |
| 4 | 29 | github.com | https://github.com/ | 20260521173904 | 127208 | https://github.com/ | 20260917000141 | 117585 | no |
| 5 | 31 | wikipedia.org | https://www.wikipedia.org/ | 20260521163013 | 31780 | https://www.wikipedia.org/ | 20260917041305 | 30068 | no |
| 6 | 35 | bing.com | http://www.bing.com/ | 20260521194755 | 24635 | https://www.bing.com/ | 20260916212412 | 25858 | no |
| 7 | 49 | wordpress.org | https://wordpress.org/ | 20260521102440 | 33842 | https://wordpress.org/ | 20260916215042 | 34134 | no |
| 8 | 51 | icloud.com | https://www.icloud.com/ | 20260520193612 | 12382 | https://www.icloud.com/ | 20260915160649 | 12558 | no |
| 9 | 52 | digicert.com | https://www.digicert.com/ | 20260519154908 | 1386 | https://www.digicert.com/ | 20260914120647 | 1323 | no |
| 10 | 57 | whatsapp.com | https://www.whatsapp.com/ | 20260521020752 | 54058 | https://www.whatsapp.com/ | 20260917041739 | 59648 | no |
| 11 | 63 | adobe.com | https://www.adobe.com/ | 20260521071522 | 5437 | https://www.adobe.com/ | 20260917010238 | 9372 | no |
| 12 | 66 | roblox.com | https://www.roblox.com/ | 20260521023257 | 14368 | https://www.roblox.com/ | 20260913194358 | 14649 | no |
| 13 | 75 | opera.com | https://www.opera.com/ | 20260521144521 | 23047 | https://www.opera.com/ | 20260916121505 | 23411 | no |
| 14 | 77 | ntp.org | https://www.ntp.org/ | 20260520034835 | 3369 | https://www.ntp.org/ | 20260914061037 | 3408 | no |
| 15 | 78 | nginx.org | http://nginx.org/ | 20260519061939 | 2870 | http://nginx.org/ | 20260911232258 | 2812 | no |
| 16 | 81 | qq.com | https://www.qq.com/ | 20260521173157 | 26839 | https://www.qq.com/ | 20260916072648 | 25942 | no |
| 17 | 86 | f5.com | https://www.f5.com/ | 20260515065652 | 112413 | https://www.f5.com/ | 20260916130826 | 160917 | no |
| 18 | 98 | yuga.com | https://yuga.com/ | 20260521101258 | 2975 | https://yuga.com/ | 20260911210745 | 3342 | no |
| 19 | 108 | nic.ru | https://www.nic.ru/ | 20260521171255 | 8963 | https://www.nic.ru/ | 20260916062742 | 8943 | yes |
| 20 | 109 | triplinkintl.com | https://www.triplinkintl.com/ | 20260521173357 | 10912 | https://www.triplinkintl.com/ | 20260907234451 | 10928 | no |
| 21 | 110 | ui.com | https://ui.com/ | 20260516020600 | 5668 | https://www.ui.com/ | 20260917035413 | 64277 | no |
| 22 | 124 | reg.ru | https://www.reg.ru/ | 20260521200559 | 46633 | https://www.reg.ru/ | 20260917004214 | 8943 | no |
| 23 | 129 | dropbox.com | https://www.dropbox.com/ | 20260521175752 | 69722 | https://www.dropbox.com/ | 20260917045054 | 75546 | no |
| 24 | 131 | intuit.com | https://www.intuit.com/ | 20260521165355 | 78725 | https://www.intuit.com/ | 20260915064653 | 60532 | no |
| 25 | 133 | apache.org | https://apache.org/ | 20260518220835 | 10957 | https://www.apache.org/ | 20260915025223 | 11307 | no |
| 26 | 142 | afternic.com | https://www.afternic.com/ | 20260521105332 | 30485 | https://www.afternic.com/ | 20260916151205 | 32696 | no |
| 27 | 143 | archive.org | http://archive.org/ | 20260521051013 | 2477 | https://archive.org/ | 20260916214102 | 1899 | no |
| 28 | 146 | kaspersky.com | https://www.kaspersky.com/ | 20260520135504 | 159194 | https://www.kaspersky.com/ | 20260917044752 | 113267 | no |
| 29 | 150 | godaddy.com | https://www.godaddy.com/ | 20260520193314 | 75508 | https://www.godaddy.com/ | 20260917010023 | 73559 | no |
| 30 | 153 | ipify.org | https://www.ipify.org/ | 20260517220138 | 8059 | https://www.ipify.org/ | 20260914174701 | 8043 | yes |
| 31 | 160 | criteo.com | https://www.criteo.com/ | 20260521010116 | 47600 | https://www.criteo.com/ | 20260914153701 | 74769 | no |
| 32 | 162 | webex.com | https://www.webex.com/ | 20260516232417 | 22842 | https://www.webex.com/ | 20260913110558 | 23490 | no |
| 33 | 163 | android.com | https://www.android.com/ | 20260515144634 | 48825 | https://www.android.com/ | 20260907055952 | 58345 | no |
| 34 | 167 | hichina.com | http://www.hichina.com/ | 20260512031820 | 10425 | http://www.hichina.com/ | 20260905142441 | 10391 | no |
| 35 | 168 | example.com | https://example.com/ | 20260521192853 | 946 | https://example.com/ | 20260917030433 | 951 | no |
| 36 | 170 | shopify.com | https://www.shopify.com/ | 20260521103654 | 82963 | https://www.shopify.com/ | 20260917015104 | 123862 | no |
| 37 | 176 | discord.com | https://discord.com/ | 20260521203302 | 28491 | https://discord.com/ | 20260916215537 | 29293 | no |
| 38 | 181 | w3.org | https://www.w3.org/ | 20260520231100 | 10985 | https://www.w3.org/ | 20260916193228 | 11033 | no |
| 39 | 192 | creativecommons.org | https://creativecommons.org/ | 20260520041740 | 14576 | https://creativecommons.org/ | 20260915003020 | 13003 | no |
| 40 | 194 | ubuntu.com | https://ubuntu.com/ | 20260521071246 | 33699 | https://ubuntu.com/ | 20260915220313 | 33725 | no |
| 41 | 206 | telegram.org | https://telegram.org/ | 20260521202335 | 6766 | https://telegram.org/ | 20260917035518 | 6753 | no |
| 42 | 208 | oracle.com | https://www.oracle.com/ | 20260521212738 | 15463 | https://www.oracle.com/ | 20260916164430 | 15593 | no |
| 43 | 212 | doi.org | https://www.doi.org/ | 20260521083309 | 8004 | https://www.doi.org/ | 20260915192500 | 8016 | no |
| 44 | 218 | samsungcloud.com | https://www.samsungcloud.com/ | 20260519003544 | 7925 | https://www.samsungcloud.com/ | 20260906145745 | 8905 | no |
| 45 | 222 | dns.google | https://dns.google/ | 20260521194603 | 1638 | https://dns.google/ | 20260917033841 | 1625 | no |
| 46 | 223 | mit.edu | https://www.mit.edu/ | 20260518064645 | 12711 | https://www.mit.edu/ | 20260915235402 | 12437 | no |
| 47 | 224 | twitch.tv | https://www.twitch.tv/ | 20260521200403 | 67961 | https://www.twitch.tv/ | 20260916220655 | 71341 | no |
| 48 | 227 | cisco.com | https://www.cisco.com/ | 20260521110525 | 26145 | https://www.cisco.com/ | 20260917004621 | 26574 | no |
| 49 | 229 | wikimedia.org | https://www.wikimedia.org/ | 20260521141200 | 11432 | https://www.wikimedia.org/ | 20260916061316 | 11762 | no |
| 50 | 230 | cpanel.net | https://www.cpanel.net/ | 20260517060459 | 70828 | https://www.cpanel.net/ | 20260915213001 | 70379 | no |
| 51 | 232 | nist.gov | https://www.nist.gov/ | 20260519230432 | 26741 | https://www.nist.gov/ | 20260911014105 | 27349 | no |
| 52 | 237 | stripe.com | https://stripe.com/ | 20260521072634 | 148849 | https://stripe.com/ | 20260916122611 | 168859 | no |
| 53 | 240 | alidns.com | http://alidns.com/ | 20260514225748 | 7633 | http://www.alidns.com/ | 20260907204234 | 7625 | no |
| 54 | 256 | hubspot.com | https://www.hubspot.com/ | 20260520170534 | 91662 | https://www.hubspot.com/ | 20260916180843 | 94938 | no |
| 55 | 266 | spectrum.com | https://www.spectrum.com/ | 20260517064250 | 86303 | https://www.spectrum.com/ | 20260906201934 | 82736 | no |
| 56 | 272 | taboola.com | https://www.taboola.com/ | 20260520015528 | 35301 | https://www.taboola.com/ | 20260915084718 | 35334 | no |
| 57 | 278 | dnsmadeeasy.com | https://dnsmadeeasy.com/ | 20260515073604 | 30886 | https://dnsmadeeasy.com/ | 20260906050636 | 14076 | no |
| 58 | 288 | amplitude.com | https://www.amplitude.com/ | 20260517054929 | 78737 | https://amplitude.com/ | 20260915173021 | 93162 | no |
| 59 | 293 | tinyurl.com | https://tinyurl.com/ | 20260521071748 | 6875 | https://tinyurl.com/ | 20260916093546 | 6863 | no |
| 60 | 295 | ip-api.com | https://ip-api.com/ | 20260518113929 | 4619 | https://ip-api.com/ | 20260915212409 | 4602 | no |
| 61 | 302 | www.gov.uk | https://www.gov.uk/ | 20260520172454 | 14541 | https://www.gov.uk/ | 20260916000443 | 14548 | no |
| 62 | 309 | inmobi.com | https://www.inmobi.com/ | 20260518145527 | 6383 | https://www.inmobi.com/ | 20260910065347 | 6380 | no |
| 63 | 310 | miit.gov.cn | https://www.miit.gov.cn/ | 20260514222256 | 14392 | https://www.miit.gov.cn/ | 20260909041531 | 14567 | no |
| 64 | 314 | ok.ru | https://ok.ru/ | 20260519122733 | 53520 | https://ok.ru/ | 20260915214419 | 68405 | no |
| 65 | 315 | harvard.edu | https://www.harvard.edu/ | 20260521141345 | 22735 | https://www.harvard.edu/ | 20260915023515 | 29865 | no |
| 66 | 317 | alibaba.com | https://www.alibaba.com/ | 20260519110728 | 27458 | https://www.alibaba.com/ | 20260916084403 | 41604 | no |
| 67 | 318 | debian.org | https://www.debian.org/ | 20260521134529 | 4979 | https://www.debian.org/ | 20260916212526 | 5045 | no |
| 68 | 324 | appsflyer.com | https://www.appsflyer.com/ | 20260521194845 | 66091 | https://www.appsflyer.com/ | 20260917035256 | 64854 | no |
| 69 | 329 | php.net | https://www.php.net/ | 20260521191235 | 8766 | https://www.php.net/ | 20260917032946 | 9340 | no |
| 70 | 331 | publicnode.com | https://www.publicnode.com/ | 20260512085423 | 199395 | https://publicnode.com/ | 20260908011057 | 138307 | no |
| 71 | 336 | crpt.ru | https://crpt.ru/ | 20260519010032 | 6543 | https://crpt.ru/ | 20260909193001 | 7758 | no |
| 72 | 337 | drom.ru | https://www.drom.ru/ | 20260521112346 | 38142 | https://www.drom.ru/ | 20260914181634 | 38734 | no |
| 73 | 338 | name.com | https://www.name.com/ | 20260516141515 | 55748 | https://www.name.com/ | 20260913210209 | 74367 | no |
| 74 | 339 | weebly.com | https://www.weebly.com/ | 20260521130736 | 26562 | https://www.weebly.com/ | 20260916114959 | 26516 | no |
| 75 | 350 | slack.com | https://slack.com/ | 20260521051750 | 32702 | https://slack.com/ | 20260916090129 | 36588 | no |
| 76 | 351 | naver.com | https://www.naver.com/ | 20260521112336 | 35340 | https://www.naver.com/ | 20260915213200 | 37033 | no |
| 77 | 353 | ea.com | https://www.ea.com/ | 20260516054022 | 19294 | https://www.ea.com/ | 20260915034829 | 83527 | no |
| 78 | 356 | nasa.gov | https://www.nasa.gov/ | 20260520122959 | 44968 | https://www.nasa.gov/ | 20260913075746 | 50496 | no |
| 79 | 357 | mobile.de | https://www.mobile.de/ | 20260520231955 | 78139 | https://www.mobile.de/ | 20260916091006 | 79123 | no |
| 80 | 359 | cdc.gov | https://www.cdc.gov/ | 20260521052324 | 10178 | https://www.cdc.gov/ | 20260914111358 | 10492 | no |
| 81 | 363 | un.org | https://www.un.org/ | 20260520064655 | 3442 | https://www.un.org/ | 20260917004828 | 3771 | no |
| 82 | 365 | checkpoint.com | https://www.checkpoint.com/ | 20260521043454 | 26883 | https://www.checkpoint.com/ | 20260916215825 | 30600 | no |
| 83 | 370 | brave.com | https://brave.com/ | 20260519181402 | 26095 | https://brave.com/ | 20260915220025 | 26493 | no |
| 84 | 371 | tradingview.com | https://www.tradingview.com/ | 20260517182342 | 223333 | https://www.tradingview.com/ | 20260917041325 | 224916 | no |
| 85 | 375 | zendesk.com | https://www.zendesk.com/ | 20260520231612 | 105035 | https://www.zendesk.com/ | 20260914232000 | 103990 | no |
| 86 | 376 | selectel.ru | https://selectel.ru/ | 20260520223815 | 138826 | https://selectel.ru/ | 20260913051010 | 144166 | no |
| 87 | 377 | opendns.com | https://www.opendns.com/ | 20260521144341 | 4239 | https://www.opendns.com/ | 20260912144159 | 4221 | no |
| 88 | 378 | netangels.ru | https://www.netangels.ru/ | 20260519102846 | 32024 | https://www.netangels.ru/ | 20260915033841 | 30198 | no |
| 89 | 379 | plesk.com | https://www.plesk.com/ | 20260515045531 | 68692 | https://www.plesk.com/ | 20260913045811 | 93390 | no |
| 90 | 381 | issuu.com | https://issuu.com/ | 20260518182142 | 26050 | https://issuu.com/ | 20260905195622 | 25824 | no |
| 91 | 382 | datadoghq.com | https://www.datadoghq.com/ | 20260519122109 | 59319 | https://www.datadoghq.com/ | 20260916023604 | 58527 | no |
| 92 | 385 | stanford.edu | https://www.stanford.edu/ | 20260520192659 | 18295 | https://www.stanford.edu/? | 20260913043855 | 107552 | no |
| 93 | 394 | google.cn | http://www.google.cn/ | 20260517060334 | 1566 | http://www.google.cn/ | 20260913203354 | 1550 | yes |
| 94 | 396 | quickconnect.to | http://quickconnect.to/ | 20260514064832 | 44657 | http://quickconnect.to/ | 20260913230149 | 44646 | yes |
| 95 | 399 | doubleverify.com | https://doubleverify.com/ | 20260517060338 | 24359 | https://doubleverify.com/ | 20260914211914 | 24514 | no |
| 96 | 400 | yandex.com | https://yandex.com/ | 20260519221947 | 82480 | https://yandex.com/ | 20260912052047 | 85254 | no |
| 97 | 401 | amazontrust.com | https://www.amazontrust.com/ | 20260515174356 | 4928 | https://www.amazontrust.com/ | 20260912231139 | 4980 | no |
| 98 | 418 | unsplash.com | https://unsplash.com/ | 20260521113853 | 126377 | https://unsplash.com/ | 20260917033057 | 126035 | no |
| 99 | 422 | dropcatch.com | https://www.dropcatch.com/ | 20260518070231 | 13966 | https://www.dropcatch.com/ | 20260911140644 | 13828 | no |
| 100 | 423 | 163.com | http://www.163.com/ | 20260519191021 | 48029 | http://www.163.com/ | 20260916162606 | 49000 | no |

Per-domain classification of every processed domain (incl. excluded): `dry_run.json` → `rows`.

## Run history (all on 2026-10-12, from `cc_cache/requests_log.jsonl`)

| run | requests | min gap (s) | period (UTC) | outcome |
|---|---|---|---|---|
| first zipnum run (1 s interval, earlier UA contact) | 197 | 1.039 | 10:07:50–10:13:09 | 2 cluster.idx HEAD + 2 GET 200; 178 × 206, 15 × 503; stopped on 503 at `CC-MAIN-2026-21/cdx-00079.gz` |
| expanded run `20261012T104825Z` | 504 | 2.036 | 10:48:26–11:15:16 | Tranco top-2000 200; 484 × 206, 17 × 503 (each recovered after a 30 s or 60 s wait), 2 × DNS error `getaddrinfo failed` (recovered). The process ended at about rank 339 on an uncaught `http.client.IncompleteRead` from a range response, which is not in the log. No report was written. The script was changed to treat `IncompleteRead` and other `OSError` / `HTTPException` as transient (same 30/60/120 s waits). |
| expanded run `20261012T111619Z` (resume from cache) | 162 | 2.039 | 11:16:33–11:24:30 | 158 × 206, 3 × 503 and 1 × `IncompleteRead`, all recovered after a 30 s wait. Completed: 100 qualified at rank 423. |

- No request returned 403 or 429, and no block page was detected.
- No HTML or WARC record was requested.
