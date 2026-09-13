# shared/harness

Observation builder, LLM client, and the run loop. C# / .NET (Playwright).

## Modules

- `Config.cs` — loads `.env` (`BAR_`-prefixed vars), typed accessors for endpoints/seed
- `LlmClient.cs` — multi-provider client (Azure OpenAI, Azure Inference, Anthropic via Azure); `temperature=0` for GPT-4.1/GPT-4.1-nano, omitted for o-series and for Anthropic (see below)
- `Observation.cs` — DOM walk (JS via Playwright), bundle application (Axis A), encoding (Axis B, F0–F4)
- `GroundingRunner.cs` — `RunOneAsync(task × bundle × encoding × regime × model × repetition) → GroundingRecord`
- `models/*.cs` — Anthropic request/response DTOs + `LlmClientType` enum (extracted out of `LlmClient.cs`)

## Invariants (§6)

- `temperature = 0` for GPT-4.1/GPT-4.1-nano only, locked in `LlmClient.cs`, not a parameter — o-series (o1/o3/o4) reject the field so it is omitted; the Anthropic path never sends `temperature` at all, so Claude runs at the provider's own default, not 0
- Canonical prompt has **no strategy coaching** — no attribute hints, no few-shot examples naming attributes
- One `GroundingRecord` per invocation of `RunOneAsync`
