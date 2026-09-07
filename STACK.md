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
  is scientifically orthogonal: cost is tokens under a fixed tokenizer, success is
  a static XPath parse — neither depends on the language.
- **Analysis: C# (Math.NET) by default, Python/R optional on the same JSONL.**
  The JSONL output is the boundary; anything can read it. Author has prior
  experience with `MathNet.Numerics`, so C# analysis is viable. Python/R stays available where its plotting/stats
  ecosystem is stronger and where reviewers expect those figures.

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
- Locator resolution (evaluating a returned XPath against the DOM) is also
  injected JS. **Resolution only — never an action.**
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
| Anthropic (Claude via Azure AI Services) | raw `HttpClient` (Anthropic Messages) | `x-api-key` + `anthropic-version` headers; extended thinking on |
| Cross-family models (Llama, Phi via Foundry) | `Azure.AI.Inference` | unified Azure AI Model Inference API — same client for all catalog models, switch by deployment-name string. *Present in code but not part of the locked corpus — see §6.* |
| Auth | `AzureKeyCredential` (OpenAI) / `x-api-key` header (Anthropic) | API keys from `.env` (`BAR_AZURE_OPENAI_KEY`, `BAR_AZURE_ANTHROPIC_KEY`); no `DefaultAzureCredential` / `az login` in code |
| JSON records | `System.Text.Json` | one JSONL record per grounding event |

Call shape: single message, `temperature = 0`, no tools, no retries, parse the
returned XPath. If maximum transparency is ever needed, drop to raw `HttpClient`
against the chat completions endpoint.

## 4. Token counting — fixed reference tokenizer (methodologically critical)

- Library: **`SharpToken`** (C# tiktoken port), pinned to **one** encoding —
  recommend **`o200k_base`**. Record the encoding + library version on every run.
- **The cost metric is `token_count(observation)` under this single fixed
  tokenizer — NOT the per-model API `usage` field.** Cost is a property of the
  *representation* under a canonical reference tokenizer, which is what makes it
  model-agnostic and comparable across families. This is also the answer to the
  reviewer question "why count GPT tokens for a Llama run?": because cost is a
  property of the observation, not the model.
- Native per-model `usage` tokens are logged as a **secondary sanity field**
  only; they never enter the cost comparison.

## 5. Statistics & plots

- `MathNet.Numerics` for what it covers (e.g. Wilcoxon signed-rank).
- Implement the small remainder in C# and validate against a reference:
  **McNemar** (simple formula), **Cliff's Delta** (trivial), **bootstrap 95% CIs**
  (resampling loop). α = 0.05. Statistical unit = the grounding event.
- Plots: **ScottPlot** if staying single-language in C#; **matplotlib/seaborn
  (Python)** if richer publication figures are wanted — both read the JSONL.

## 6. Model slate (Azure)

Two families, capability spread, and a reasoning contrast. Robustness check, **not** a
leaderboard. The model's own API price is the *experiment budget*, not the paper's
cost metric (which is fixed-tokenizer observation tokens).

**Slate as run** (produced the committed `axisc_*.jsonl` corpus):

| Model | Family | Surface | Role | Why |
|-------|--------|---------|------|-----|
| **GPT-4.1** | OpenAI | Azure OpenAI | **Primary** — full sweep, derives COP | 1M context (model limit never clips before cap C → clean R1/R2); strong instruction-following; deterministic at temp=0 |
| GPT-4.1-nano | OpenAI | Azure OpenAI | Light robustness | same family as primary → isolates the capability axis cleanly |
| o4-mini | OpenAI | Azure OpenAI | Reasoning contrast (COP-only) | reasoning model; tests whether internal reasoning reaches the COP ceiling |
| Claude Sonnet 4.6 | Anthropic | Anthropic Messages (via Azure AI Services) | Reasoning (thinking ON) + independent family | the key non-OpenAI replication; tests whether reasoning compensates for a poor observation |

Usage: the **primary** carries the full bundle × encoding matrix; the robustness models
run only the recommended profile + a few neighbouring points to confirm the **curve
shape** holds (o4-mini is COP-only).

> **Superseded plan (why the slate changed).** The original slate named Llama 3.x 70B and
> Phi-4 as open-weight cross-family points and excluded reasoning models to keep one-shot
> temp=0 clean. In practice the Azure Foundry serverless TPM quota (~20K TPM) is exceeded by
> large-page observations, so those models could not process the heavy pages; o4-mini was
> substituted, and the reasoning-vs-instruction contrast became a finding rather than a
> confound. Reasoning models are handled explicitly in `LlmClient` (temperature omitted,
> `max_tokens` omitted for o-series). See `experiments/FINDINGS.md:111` for the coverage decision and
> `experiments/FINDINGS.md:87` for the reasoning finding. Hidden thinking tokens are output, not
> observation input, so they never touch the fixed-tokenizer cost metric.

Notes / open confirmations:
- Verify exact current deployment names + Foundry serverless pricing in the Azure
  portal at setup (catalog and rates move independently of this doc).
- **Claude Sonnet 4.6 is the reasoning contrast point**, run with extended
  thinking ON. Same three conditions as every other model: the canonical *simple*
  prompt, one shot, no retry. The "reasoning" must come from the model's internal
  thinking, never from prompt strategy or a retry loop — otherwise it recreates
  the confounded production setup. It answers "does reasoning compensate for a
  poor observation?" and doubles as a 4th family.
  - Cost metric is unaffected: hidden reasoning tokens are output/thinking, not
    observation input, so they never touch the fixed-tokenizer input cost.
  - Determinism caveat: reasoning models may not honour temp=0 the same way (some
    require temp=1 when thinking is on). Pin a seed where available and run a few
    repetitions to confirm stability; report it as a robustness point, not an
    exact-number cell.
  - Confirm at setup whether Foundry's Claude deployment exposes extended thinking
    via the unified Inference API; if not, fall back to the Anthropic-native call
    shape for this one model.
- GPT-5 / GPT-5-nano exist and are cheaper on input; GPT-4.1 is preferred as
  primary for the 1M context + clearly non-reasoning, controlled one-shot
  behaviour. Revisit only if a current flagship is wanted and is confirmed to be a
  standard (non-hidden-reasoning) model.

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
Azure.AI.Inference            # Llama / Phi / Claude via Foundry (unified API)
Azure.Identity                # DefaultAzureCredential (Entra ID)
SharpToken                    # fixed o200k_base token counting (the cost metric)
MathNet.Numerics              # stats (Wilcoxon, etc.)
ScottPlot                     # optional C# plotting (else Python/matplotlib on the JSONL)
# System.Text.Json is in-box
```
