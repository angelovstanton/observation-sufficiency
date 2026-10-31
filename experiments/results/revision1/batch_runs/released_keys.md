# Released keys — Revision 1 batch (plan 567c370855a2)

Every operator release (`BAR_BATCH_RELEASE`) of a request with unknown outcome. The released key is called again on the next run; whether the provider billed the original request is unknown (at most the reservation below + output).
Generated from `journal.jsonl` (pending / error / released lines); times UTC.

| # | key | pending (UTC) | error type | reserved input tokens | released (UTC) | release |
|---|-----|---------------|------------|----------------------:|----------------|---------|
| 1 | `gpt-4.1\|B_full_minus_volClass\|F1\|page_06\|t_03\|0` | 2026-10-13T17:18:42.9832393+00:00 | transport: ClientResultException "An error occurred while sending the request"; after 429 on the same key | 63969 | 2026-10-13T17:45:42.7641159+00:00 | manual |
| 2 | `gpt-4.1\|B_noVolatile\|F1\|page_09\|t_01\|1` | 2026-10-13T19:46:53.6560350+00:00 | client process terminated mid-request | 44313 | 2026-10-13T20:44:32.1057202+00:00 | manual |
| 3 | `gpt-4.1\|B_noVolatile\|F1\|page_22\|t_10\|1` | 2026-10-14T09:30:04.8484102+00:00 | transport: ClientResultException "An error occurred while sending the request" | 37117 | 2026-10-14T09:45:36.7722231+00:00 | manual |
| 4 | `o4-mini\|B_full\|F1\|page_01\|t_10\|0` | 2026-10-14T11:11:19.2862979+00:00 | HTTP 500: The server is overloaded or not ready yet. Please try again later. (service_unavailable_error) | 19111 | 2026-10-14T11:54:28.6457997+00:00 | manual |
| 5 | `o4-mini\|B_full\|F1\|page_02\|t_09\|0` | 2026-10-14T12:09:42.1608496+00:00 | timeout: TaskCanceledException (client NetworkTimeout 0:01:40) | 3340 | 2026-10-14T12:16:59.8742365+00:00 | manual |

Total: 5 releases (0 automatic); reserved input tokens 167850.
