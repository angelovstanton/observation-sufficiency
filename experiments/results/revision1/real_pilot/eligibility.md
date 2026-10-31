# Real-site pilot: step 1, site eligibility

- pilot_rule.md commit: `1a16fa142d9ca2814cf0c2acc4c66448ffee9d79` (2026-10-13T00:43:46+03:00); pilot_analysis_plan.md: `9ead395da9c2f0a7ad85a427a23a283932cfaf05`
- Shim check (24 corpus pages × 6 cells, with vs without shims): 144 cells, **0 differ**. Adapter vs stored corpus dump (`batch_observations/manifest.tsv`, F1 cells): 72/72 identical.
- Decoding (May payloads): {'charset_http': 74, 'charset_meta': 23, 'charset_default_utf8': 3}
- Criterion (б) re-applied under the observation protocol of the pilot_rule.md addendum (2026-10-13, commit 1a16fa1): every cell on a fresh load, 5 independent dumps, to the 33 sites that passed (а), (в) and (г) (`rp_redump.py`). Probe, Oracle lists and target selection unchanged. The other sites keep their recorded reason; the shim check above is under the same protocol.

**Eligible sites: 33 of 100.**

## Counts by first failing criterion

| criterion | sites |
|---|---|
| (а) | 63 |
| (в) | 1 |
| (г) | 3 |
| eligible | 33 |

(г) exclusions, largest-cell prompt size:

| rank | domain | max prompt tokens |
|---|---|---|
| 331 | publicnode.com | 187,357 |
| 371 | tradingview.com | 192,804 |
| 375 | zendesk.com | 128,720 |

## All sites

| domain | rank | (а) | (б) | (в) | (г) | eligible | reason |
|---|---|---|---|---|---|---|---|
| cloudflare.com | 2 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| apple.com | 9 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| youtube.com | 10 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| github.com | 29 | yes | yes | yes (145) | yes (52,494) | yes |  |
| wikipedia.org | 31 | yes | yes | yes (378) | yes (23,840) | yes |  |
| bing.com | 35 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| wordpress.org | 49 | yes | yes | yes (52) | yes (12,010) | yes |  |
| icloud.com | 51 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| digicert.com | 52 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| whatsapp.com | 57 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| adobe.com | 63 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| roblox.com | 66 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| opera.com | 75 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| ntp.org | 77 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| nginx.org | 78 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| qq.com | 81 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| f5.com | 86 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| yuga.com | 98 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| nic.ru | 108 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| triplinkintl.com | 109 | yes | yes | yes (10) | yes (4,961) | yes |  |
| ui.com | 110 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| reg.ru | 124 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| dropbox.com | 129 | yes | yes | yes (58) | yes (87,555) | yes |  |
| intuit.com | 131 | yes | yes | yes (70) | yes (55,876) | yes |  |
| apache.org | 133 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| afternic.com | 142 | yes | yes | yes (17) | yes (11,938) | yes |  |
| archive.org | 143 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| kaspersky.com | 146 | yes | yes | yes (74) | yes (51,514) | yes |  |
| godaddy.com | 150 | yes | yes | yes (149) | yes (47,803) | yes |  |
| ipify.org | 153 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| criteo.com | 160 | yes | yes | yes (76) | yes (46,006) | yes |  |
| webex.com | 162 | yes | yes | yes (95) | yes (28,839) | yes |  |
| android.com | 163 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| hichina.com | 167 | yes | yes | yes (6) | yes (22,786) | yes |  |
| example.com | 168 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| shopify.com | 170 | yes | yes | yes (109) | yes (77,028) | yes |  |
| discord.com | 176 | yes | yes | yes (93) | yes (33,424) | yes |  |
| w3.org | 181 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| creativecommons.org | 192 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| ubuntu.com | 194 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| telegram.org | 206 | yes | yes | yes (43) | yes (8,159) | yes |  |
| oracle.com | 208 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| doi.org | 212 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| samsungcloud.com | 218 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| dns.google | 222 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| mit.edu | 223 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| twitch.tv | 224 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| cisco.com | 227 | yes | yes | yes (84) | yes (28,904) | yes |  |
| wikimedia.org | 229 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| cpanel.net | 230 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| nist.gov | 232 | yes | yes | yes (142) | yes (16,236) | yes |  |
| stripe.com | 237 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| alidns.com | 240 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| hubspot.com | 256 | yes | yes | yes (94) | yes (66,602) | yes |  |
| spectrum.com | 266 | yes | yes | yes (51) | yes (37,400) | yes |  |
| taboola.com | 272 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| dnsmadeeasy.com | 278 | yes | yes | yes (37) | yes (43,430) | yes |  |
| amplitude.com | 288 | yes | yes | no (0) | – | no | (в) 0 eligible targets < 5 |
| tinyurl.com | 293 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| ip-api.com | 295 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| www.gov.uk | 302 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| inmobi.com | 309 | yes | yes | yes (15) | yes (3,785) | yes |  |
| miit.gov.cn | 310 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| ok.ru | 314 | yes | yes | yes (43) | yes (10,072) | yes |  |
| harvard.edu | 315 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| alibaba.com | 317 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| debian.org | 318 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| appsflyer.com | 324 | yes | yes | yes (87) | yes (25,636) | yes |  |
| php.net | 329 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| publicnode.com | 331 | yes | yes | yes (198) | no (187,357) | no | (г) largest-cell prompt 187,357 > 128,000 tokens |
| crpt.ru | 336 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| drom.ru | 337 | yes | yes | yes (183) | yes (85,306) | yes |  |
| name.com | 338 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| weebly.com | 339 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| slack.com | 350 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| naver.com | 351 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| ea.com | 353 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| nasa.gov | 356 | yes | yes | yes (153) | yes (53,311) | yes |  |
| mobile.de | 357 | yes | yes | yes (187) | yes (89,774) | yes |  |
| cdc.gov | 359 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| un.org | 363 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| checkpoint.com | 365 | yes | yes | yes (185) | yes (22,064) | yes |  |
| brave.com | 370 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| tradingview.com | 371 | yes | yes | yes (352) | no (192,804) | no | (г) largest-cell prompt 192,804 > 128,000 tokens |
| zendesk.com | 375 | yes | yes | yes (100) | no (128,720) | no | (г) largest-cell prompt 128,720 > 128,000 tokens |
| selectel.ru | 376 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| opendns.com | 377 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| netangels.ru | 378 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| plesk.com | 379 | yes | yes | yes (62) | yes (81,327) | yes |  |
| issuu.com | 381 | yes | yes | yes (50) | yes (12,998) | yes |  |
| datadoghq.com | 382 | yes | yes | yes (58) | yes (45,059) | yes |  |
| stanford.edu | 385 | yes | yes | yes (96) | yes (12,106) | yes |  |
| google.cn | 394 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| quickconnect.to | 396 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| doubleverify.com | 399 | yes | yes | yes (56) | yes (28,338) | yes |  |
| yandex.com | 400 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| amazontrust.com | 401 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| unsplash.com | 418 | yes | yes | yes (70) | yes (48,166) | yes |  |
| dropcatch.com | 422 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
| 163.com | 423 | no | – | – | – | no | (а) no flagged class token: B_full ≡ B_noVolatile by construction |
