# shared/oracle

Ground-truth element identity, the success predicate, and failure decomposition.

## Success predicate (§6) — all five must hold

1. **unique_match** — locator resolves to exactly one element
2. **matches_oracle** — the resolved element is the oracle element (matched by `data-oracle-id`)
3. **non_volatile** — locator references no hashed/auto-generated attribute values
4. **non_positional** — locator uses no positional predicates (`[1]`, `:nth-child`, etc.)
5. **stable_signal_present_in_bundle** — the bundle's observation actually contained a
   stable signal capable of identifying the oracle element

A locator that resolves correctly via a volatile identifier is a **failure by design**.

Conditions 1–4 judge the model's output; condition 5 judges the observation that was
given to it. Separating them is what makes the failure decomposition below meaningful —
without it, an unsolvable cell and a fumbled solvable cell would look identical.

## Failure decomposition (§6) — recoverable from records

- `observation_lacked_stable_signal` — the observation (after bundle filtering) contained
  no stable signal that could have identified the oracle element. **Takes priority over
  the other modes**: the classification names the root cause, not the locator's secondary
  properties.
- `output_format_unreachable` — the model emitted XPath despite the CSS-only instruction
  and the oracle element sits inside a shadow root, where XPath cannot reach. Expected to
  be rare; retained to detect prompt non-compliance.
- `model_grabbed_brittle_signal` — a stable signal was present but the model generated a
  locator using a volatile or positional signal instead.
