# shared/tokenizer

Fixed, pinned tokenizer for cost measurement. C# (SharpToken, a tiktoken port).

Token count is the **sole cost unit** — never converted to dollars or seconds.
The tokenizer is pinned at `o200k_base` (GPT-4.1 family). Bumping the version
requires an explicit decision and must be recorded in every run's metadata.

## Usage

```csharp
using BoundedAgents.Shared.Tokenizer;

int n = TokenCounter.CountTokens("some text");
string v = TokenCounter.TokenizerVersion();   // "o200k_base"
```
