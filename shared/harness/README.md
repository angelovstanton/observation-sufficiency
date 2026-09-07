# shared/harness

Observation builder, LLM client, and the run loop. C# / .NET (Playwright).

## Modules

- `Config.cs` — loads `.env` (`BAR_`-prefixed vars), typed accessors for endpoints/seed
- `LlmClient.cs` — multi-provider client (Azure OpenAI, Azure Inference, Anthropic via Azure); `temperature=0` enforced as invariant
- `Observation.cs` — DOM walk (JS via Playwright), bundle application (Axis A), encoding (Axis B, F0–F4)
- `GroundingRunner.cs` — `RunOneAsync(task × bundle × encoding × regime × model × repetition) → GroundingRecord`
- `models/*.cs` — Anthropic request/response DTOs + `LlmClientType` enum (extracted out of `LlmClient.cs`)

## Invariants (§6)

- `temperature = 0` — locked in `LlmClient.cs`, not a parameter (reasoning models omit it entirely — they reject it)
- Canonical prompt has **no strategy coaching** — no attribute hints, no few-shot examples naming attributes
- One `GroundingRecord` per invocation of `RunOneAsync`
