# Classifier validation — Python port vs C# Oracle CLI (corpus values)

- analysis_plan.md commit: `d8f1bc9bf81a71c9a80f51ba57eacc96a110ae73` (2026-10-12T14:32:55+03:00; working copy clean: True)
- Classifier of record: `oracle_cli/` (reflection on `Oracle.IsVolatileClass` / `Oracle.IsVolatileId`, Oracle source unchanged).
- CLI `--describe`:

```
assembly=<repo>\p1\results\revision1\cc_volatility\oracle_cli\bin\Release\net10.0\Shared.Oracle.dll
class=Boolean IsVolatileClass(System.String)
id=Boolean IsVolatileId(System.String)
```

- Values: unique class tokens (ASCII-whitespace split) and id values from the 24 static testbed pages (`shared/testbed/pages/page_*.html`, html.parser) together with the 24 runtime `observations/page_XX__B_full__F1.txt` dumps.

| type | unique values | CLI flagged | port == CLI | result |
|---|---|---|---|---|
| class | 1073 | 197 | 1073/1073 | 100% |
| id | 234 | 0 | 234/234 | 100% |

**PASSED**: 1307/1307 values agree.
