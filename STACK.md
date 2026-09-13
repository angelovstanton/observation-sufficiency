# STACK.md — technical decisions for this repository

Authoritative record of stack/tooling decisions and *why*. This document is the
current source of truth for the stack; an earlier internal note describing a
Python-only harness is superseded. When a choice here is methodologically
load-bearing, the reason is given — change it only with the reason addressed.

---

## 1. Language

- **Harness: C#** (.NET). Browser control, observation building, model calls,
  record writing. Chosen for author fluency → fewer silent errors in the
  execution phase, where velocity is the binding constraint. The harness language
  is scientifically orthogonal: cost is counted with a fixed tokenizer and success is
  evaluated from the returned CSS locator using the fixed predicate.
- **Analysis: Python.** The JSONL output is the boundary between the C# measurement
  layer and the Python analysis layer.

## 2. Browser automation — Playwright for .NET

`Microsoft.Playwright` (.NET binding). **Not** Selenium/WebDriver.

Reason (load-bearing): only Playwright produces the genuine **ARIA snapshot**
required for `B_playwrightMCP` and the `F4` YAML-ARIA encoding. The .NET binding
has `Page.AriaSnapshotAsync()` / `Locator.AriaSnapshotAsync()`, including the
`Ref` option (a reference per element) and `mode: "ai"` (snapshot optimised for
AI consumption) — which is exactly the `role + name + ref + level + state` shape
of `B_playwrightMCP`. WebDriver cannot produce this artifact; reconstructing it
makes the "compared against the Playwright MCP representation" claim refutable
(blueprint §4.2). C# does **not** force abandoning Playwright — the .NET binding
is first-class and is a neutral Microsoft library, with no conflict-of-interest
tie to any commercial automation framework.

- DOM-attribute extraction (the DOM walk for the non-AX bundles) is
  browser-agnostic injected JS (`document.evaluate`, attribute reads) — runs the
  same under Playwright.
- Locator resolution evaluates the returned CSS selector against the DOM.
  **Resolution only — never an action.**
- The 24 testbed pages are static HTML served locally (`TESTBED_BASE_URL`), so
  flakiness is low; Playwright's determinism is a bonus.

## 3. Model invocation — thin clients, no orchestration framework

**Not Semantic Kernel.** SK is an *orchestration* framework (planners, plugins,
memory, tool loops) — exactly what this study bans (one shot, temp=0, no agent, no
tool loop, no retries). Worse, SK can inject system prompts or reformat messages
you don't fully see, which contaminates the "prompt is a controlled variable"
invariant. For an experiment about the exact token content of the observation,
transparency beats convenience.

Clients (all on Azure, one cloud, one billing, API-key auth):

| Concern | Library | Notes |
|---------|---------|-------|
| OpenAI-family models (GPT-4.1, nano, o4-mini) | `Azure.AI.OpenAI` | official, thin; gives raw request/response |
| Anthropic (Claude via Azure AI Services) | raw `HttpClient` (Anthropic Messages) | `x-api-key` + `anthropic-version` headers; no `thinking` field — extended thinking off |
| Cross-family models (Llama, Phi via Foundry) | `Azure.AI.Inference` | unified Azure AI Model Inference API — same client for all catalog models, switch by deployment-name string. *Present in code but not part of the locked corpus — see §6.* |
| Auth | `AzureKeyCredential` (OpenAI) / `x-api-key` header (Anthropic) | API keys from `.env` (`BAR_AZURE_OPENAI_KEY`, `BAR_AZURE_ANTHROPIC_KEY`); no `DefaultAzureCredential` / `az login` in code |
| JSON records | `System.Text.Json` | one JSONL record per grounding event |

Call shape: single message, no tools, no retries, parse the returned CSS selector.
`temperature = 0` for GPT-4.1 and GPT-4.1-nano; omitted for o-series (the API
rejects the field) and for Anthropic (the request has no `temperature` field at
all, so Claude runs at the provider's own default, not 0). If maximum
transparency is ever needed, drop to raw `HttpClient` against the chat
completions endpoint.

## 4. Token counting — fixed reference tokenizer (methodologically critical)

- Library: **`SharpToken`** (C# tiktoken port), pinned to **one** encoding —
  recommend **`o200k_base`**. Record the encoding + library version on every run.
- **The cost metric is `token_count(observation)` under this single fixed
  tokenizer — NOT the per-model API `usage` field.** Cost is a property of the
  *representation* under a fixed reference tokenizer, which gives the same
  measurement basis across model families. This is also the answer to the
  reviewer question "why count GPT tokens for a Llama run?": because cost is a
  property of the observation, not the model.
- Native per-model `usage` tokens are logged as a **secondary sanity field**
  only; they never enter the cost comparison.

## 5. Statistics & plots

The analysis is implemented in Python. The main paired comparison uses McNemar
with an odds ratio. The page-level analysis uses the sign test and Wilcoxon
signed-rank test. The confidence interval uses a page-clustered percentile
bootstrap. The cost-success comparison uses a Pareto frontier. Publication figures
are produced from the same JSONL records.

## 6. Model slate (Azure)

Two families and a capability spread. Robustness check, **not** a leaderboard. The model's own API price is the *experiment budget*, not the paper's
cost metric (which is fixed-tokenizer observation tokens).

**Slate as run** (produced the committed `axisc_*.jsonl` corpus):

| Model | Family | Surface | Role | Why |
|-------|--------|---------|------|-----|
| **GPT-4.1** | OpenAI | Azure OpenAI | **Primary** — full sweep, derives COP | 1M context (model limit never clips before cap C → clean R1/R2); strong instruction-following; deterministic at temp=0 |
| GPT-4.1-nano | OpenAI | Azure OpenAI | Light robustness | same family as primary → lighter-tier robustness check |
| o4-mini | OpenAI | Azure OpenAI | COP-only robustness | reasoning model, but model type is not a controlled factor in this study |
| Claude Sonnet 4.6 | Anthropic | Anthropic Messages (via Azure AI Services) | Independent family (no extended thinking) | the key non-OpenAI replication; runs in standard mode, not a reasoning test |

Usage: the **primary** carries the full bundle × encoding matrix; the robustness models
run only the recommended profile + a few neighbouring points to confirm the **curve
shape** holds (o4-mini is COP-only).

## 7. Provider decision — Azure (OpenAI + Foundry), not OpenRouter

Azure is the cited source: pinned `api-version`, single known backend per model,
enterprise reproducibility — essential for a defensible dissertation ("exactly
what produced these numbers"). OpenRouter routes across providers/quantizations,
which muddies determinism and provenance; acceptable only as optional throwaway
exploration, never as a cited result. Cross-family spread is served by **Azure AI
Foundry** serverless endpoints, keeping everything in one cloud/billing.

## 8. NuGet summary

```
Microsoft.Playwright          # browser + genuine ARIA snapshot (F4 / B_playwrightMCP)
Azure.AI.OpenAI               # GPT-4.1, GPT-4.1-nano
Azure.AI.Inference            # Llama / Phi via Foundry; not part of the locked corpus
SharpToken                    # fixed o200k_base token counting (the cost metric)
MathNet.Numerics              # stats (Wilcoxon, etc.)
ScottPlot                     # optional C# plotting (else Python/matplotlib on the JSONL)
# System.Text.Json is in-box
```