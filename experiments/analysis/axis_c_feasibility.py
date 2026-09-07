"""
axis_c_feasibility.py — Axis C feasibility map and cost dry-run. Zero LLM calls.

Cost formula: obs_tokens_sum x N_REPS x rate/1M.
  obs_tokens_sum = sum of observation_tokens across unique (page, cell) pairs.
  Each rep sends each (page, cell) observation once; the 10 task descriptions
  are minor overhead (<2K total) folded into the feasibility margin.
  Call count: N_CELLS x N_PAGES x N_REPS = 4 x 24 x 10 = 960 per model.

Core diagnostic profile (4 models): 4 cells x 24 pages x 10 reps = 960 calls.
  Cells: B_full x F1, B_noVolatile x F1, B_noVolatile x F2, B_noVolatile x F3.

Reasoning-model candidates (5th slot, COP-only): B_noVolatile x F3 only.
  o4-mini          — context 200K, input $1.10/1M, output $4.40/1M (incl. reasoning)
  DeepSeek-R1-0528 — context 128K, input $0.55/1M, output $2.19/1M (incl. thinking)
  COP call count: N_PAGES x N_REPS = 24 x 10 = 240 per reasoning model.

Reasoning tokens inflate OUTPUT cost, not input. Estimated separately.
Three total-cost scenarios reported: 4-core | 4-core+o4-mini | 4-core+DeepSeek-R1.
"""
import pathlib, sys
# UTF-8 console-independence: reconfigure stdout/stderr so Unicode glyphs
# (minus sign, x, >=, ...) print on any console (e.g. Windows cp1252) without
# requiring PYTHONUTF8. Affects output ENCODING only, never any printed value.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from load import load_dataframe
import pandas as pd

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
df = load_dataframe(REPO_ROOT)

# ── Per-(page, cell) observation token table ──────────────────────────────────
cell_df = df[
    ((df["bundle"] == "B_full")       & (df["encoding"] == "F1")) |
    ((df["bundle"] == "B_noVolatile") & (df["encoding"].isin(["F1", "F2", "F3"])))
].copy()
cell_df["cell"] = (
    cell_df["bundle"]
    .str.replace("B_noVolatile", "NV",  regex=False)
    .str.replace("B_full",       "BF",  regex=False)
    + "x" + cell_df["encoding"]
)

tok_std = (
    cell_df.groupby(["page", "cell"])["observation_tokens"]
    .std().fillna(0).max()
)
assert tok_std == 0.0, f"Token variance within (page,cell): {tok_std}"

pivot = (
    cell_df.groupby(["page", "cell"])["observation_tokens"]
    .mean()
    .unstack("cell")
    [["BFxF1", "NVxF1", "NVxF2", "NVxF3"]]
)

# ── Model specs ───────────────────────────────────────────────────────────────
#
# Core (non-reasoning) models — full 4-cell diagnostic profile.
# Rates are input-only; output for locators is ~75 tok/call — negligible
# vs 110K+ observations, so output cost is omitted for non-reasoning models.
#
# Reasoning models — COP-only (NV×F3). Output cost broken out because
# reasoning/thinking tokens are charged at OUTPUT rate and can dominate.
#
# Sources (training-data rates, confirm before deploying):
#   GPT-4.1:          openai.com/api/pricing  $2.00/1M in, $8.00/1M out
#   gpt-4.1-nano:     openai.com/api/pricing  $0.10/1M in, $0.40/1M out
#   Claude-Sonnet-4.6 anthropic.com/pricing   $3.00/1M in, $15.00/1M out
#   Llama-3.3-70B:    groq.com/pricing        $0.59/1M in  (no batch)
#   o4-mini:          openai.com/api/pricing  $1.10/1M in, $4.40/1M out
#   DeepSeek-R1-0528: deepseek.com/pricing    $0.55/1M in, $2.19/1M out
#
CORE_MODELS = {
    "GPT-4.1":           {"ctx": 1_047_576, "in_rate": 2.00, "batch": True},
    "gpt-4.1-nano":      {"ctx": 1_048_576, "in_rate": 0.10, "batch": True},
    "Claude-Sonnet-4.6": {"ctx": 1_000_000, "in_rate": 3.00, "batch": True},
    "Llama-3.3-70B":     {"ctx":   128_000, "in_rate": 0.60, "batch": False},
}

# Reasoning model candidates — COP-only profile.
# Reasoning/thinking tokens are output tokens, charged at out_rate.
# Estimates per call (conservative):
#   o4-mini:          ~500 reasoning tok + ~75 locator tok = ~575 out tok/call
#   DeepSeek-R1-0528: ~2000 thinking tok + ~75 locator tok = ~2075 out tok/call
# These drive marginal cost; flag if they make the slot disproportionately expensive.
#
REASONING_MODELS = {
    "o4-mini": {
        "ctx":              200_000,
        "in_rate":            1.10,   # $/1M input
        "out_rate":           4.40,   # $/1M output (reasoning + locator)
        "reasoning_tok_est":   500,   # reasoning tokens per call (estimate)
        "locator_tok_est":      75,   # final answer tokens per call
        "batch":              True,   # OpenAI Batch API (50% off both in + out)
        "family":           "OpenAI reasoning",
        "note":             "3rd OpenAI model in the set (GPT-4.1 + nano + o4-mini)",
    },
    "DeepSeek-R1-0528": {
        "ctx":              128_000,
        "in_rate":            0.55,   # $/1M input (cache miss)
        "out_rate":           2.19,   # $/1M output (thinking + locator)
        "reasoning_tok_est":  2000,   # thinking tokens per call (R1 is verbose)
        "locator_tok_est":      75,
        "batch":              True,   # DeepSeek Batch API (50% off in + out)
        "family":           "DeepSeek (4th distinct family)",
        "note":             "Adds architectural diversity: 4th family (OpenAI/Anthropic/Meta/DeepSeek)",
    },
}

MARGIN      = 2_000    # system prompt + task descriptions + output headroom (feasibility only)
N_REPS      = 10       # repetitions per (page, cell)
CELLS_CORE  = ["BFxF1", "NVxF1", "NVxF2", "NVxF3"]
CELL_COP    = "NVxF3"
N_PAGES     = len(pivot)

CALLS_CORE  = N_PAGES * len(CELLS_CORE) * N_REPS   # 24 * 4 * 10 = 960
CALLS_COP   = N_PAGES * N_REPS                      # 24 * 10     = 240

# ── SECTION 1: Core model feasibility ────────────────────────────────────────

print("=" * 72)
print("SECTION 1: CORE MODELS — full 4-cell diagnostic profile")
print("=" * 72)
print(f"Profile : {CELLS_CORE}  |  {CALLS_CORE:,} calls per model")
print(f"Margin  : {MARGIN:,} tok (feasibility; not added to cost)")
print()

core_costs = {}
for model, cfg in CORE_MODELS.items():
    limit  = cfg["ctx"] - MARGIN
    infeas = []
    feas   = []
    for page in pivot.index:
        for cell in CELLS_CORE:
            tok = pivot.loc[page, cell]
            (infeas if tok > limit else feas).append((page, cell, tok))

    max_obs     = pivot[CELLS_CORE].values.max()
    obs_sum     = sum(r[2] for r in feas)
    api_tok     = obs_sum * N_REPS
    nom         = api_tok * cfg["in_rate"] / 1_000_000
    disc        = nom * (0.5 if cfg["batch"] else 1.0)
    core_costs[model] = {"nominal": nom, "discounted": disc}

    print(f"--- {model}  [ctx {cfg['ctx']:,}  rate ${cfg['in_rate']}/1M] ---")
    if infeas:
        print(f"  INFEASIBLE ({len(infeas)} cells):")
        for page, cell, tok in sorted(infeas):
            print(f"    {page} x {cell}: {tok:,.0f} tok  >  limit {limit:,}  (over {tok-limit:,.0f})")
    else:
        headroom = limit - max_obs
        print(f"  ALL {N_PAGES*len(CELLS_CORE)} cells fit  |  max obs {max_obs:,.0f} tok  |  headroom {headroom:,.0f} tok ({headroom/cfg['ctx']*100:.1f}%)")
    print(f"  API input-tok: {api_tok:>15,.0f}   nominal ${nom:.2f}   batch-disc ${disc:.2f}")
    print()

# ── SECTION 2: Llama deep-dive (page_17) ─────────────────────────────────────

llama_limit = CORE_MODELS["Llama-3.3-70B"]["ctx"] - MARGIN
print("=" * 72)
print("SECTION 2: LLAMA-3.3-70B — page_17 deep-dive + fallback recommendation")
print("=" * 72)
row17 = pivot.loc["page_17"]
for cell in CELLS_CORE:
    tok   = row17[cell]
    spare = llama_limit - tok
    flag  = "OK " if tok <= llama_limit else "OVER"
    print(f"  page_17 x {cell}: {tok:>9,.0f} tok   spare {spare:>+8,.0f}   [{flag}]")

over_bf = pivot[pivot["BFxF1"] > llama_limit]
print()
if over_bf.empty:
    print(f"  VERDICT: B_full x F1 fits on ALL 24 pages  (max {pivot['BFxF1'].max():,.0f}, limit {llama_limit:,}).")
    print(f"  Full diagnostic profile runs unmodified on Llama. No fallback needed.")
else:
    print(f"  Infeasible for Llama ({len(over_bf)} pages):")
    for page, row in over_bf.iterrows():
        fb = "NVxF3" if row["NVxF3"] <= llama_limit else "NONE"
        print(f"    {page}: BFxF1={row['BFxF1']:,.0f}  ->  fallback {fb} ({row[fb]:,.0f})")
print()

# ── SECTION 3: Reasoning model feasibility + cost (COP-only) ─────────────────

cop_tokens_per_page = pivot[CELL_COP]   # NVxF3 obs tokens, one per page

print("=" * 72)
print("SECTION 3: REASONING CANDIDATES — COP-only (NVxF3), 240 calls each")
print("=" * 72)
print(f"Profile : {CELL_COP} only  |  {CALLS_COP:,} calls per model")
print(f"NVxF3 obs-token range: {cop_tokens_per_page.min():,.0f} – {cop_tokens_per_page.max():,.0f}  (max = page_17)")
print(f"Reasoning tokens are OUTPUT, charged at out_rate (NOT input).")
print()

reasoning_costs = {}
for model, cfg in REASONING_MODELS.items():
    limit    = cfg["ctx"] - MARGIN
    infeas   = [(p, CELL_COP, t) for p, t in cop_tokens_per_page.items() if t > limit]
    feas_tok = cop_tokens_per_page[cop_tokens_per_page <= limit]

    obs_tok_sum  = feas_tok.sum() * N_REPS
    out_tok_sum  = (cfg["reasoning_tok_est"] + cfg["locator_tok_est"]) * CALLS_COP

    in_nom   = obs_tok_sum * cfg["in_rate"]  / 1_000_000
    out_nom  = out_tok_sum * cfg["out_rate"] / 1_000_000
    tot_nom  = in_nom + out_nom

    disc_f   = 0.5 if cfg["batch"] else 1.0
    in_disc  = in_nom  * disc_f
    out_disc = out_nom * disc_f
    tot_disc = in_disc + out_disc

    reasoning_costs[model] = {
        "nominal": tot_nom, "discounted": tot_disc,
        "in_nom": in_nom, "out_nom": out_nom,
    }

    max_cop = cop_tokens_per_page.max()
    headroom = limit - max_cop

    print(f"--- {model}  [ctx {cfg['ctx']:,}  in ${cfg['in_rate']}/1M  out ${cfg['out_rate']}/1M] ---")
    print(f"  Family   : {cfg['family']}")
    print(f"  Note     : {cfg['note']}")
    if infeas:
        print(f"  INFEASIBLE ({len(infeas)} COP cells):")
        for page, cell, tok in infeas:
            print(f"    {page}: {tok:,.0f} tok > limit {limit:,}  (over {tok-limit:,.0f})")
    else:
        print(f"  Feasibility: ALL 24 COP cells fit  |  max obs {max_cop:,.0f}  |  headroom {headroom:,.0f} tok ({headroom/cfg['ctx']*100:.1f}%)")
    print(f"  Input  tokens: {obs_tok_sum:>12,.0f}   cost ${in_nom:>7.2f}   disc ${in_disc:>7.2f}")
    print(f"  Output tokens: {out_tok_sum:>12,.0f}   cost ${out_nom:>7.2f}   disc ${out_disc:>7.2f}")
    print(f"    (reasoning est {cfg['reasoning_tok_est']} tok/call + locator {cfg['locator_tok_est']} tok/call x {CALLS_COP:,} calls)")
    ratio = out_nom / in_nom if in_nom > 0 else float("inf")
    flag  = "  << reasoning cost is {:.0f}% of input cost — manageable".format(ratio*100) if ratio < 0.5 else \
            "  !! reasoning output adds {:.0f}% on top of input — notable".format(ratio*100)
    print(f"  Reasoning output / input ratio: {ratio:.2f}x  {flag}")
    print(f"  TOTAL  nominal ${tot_nom:.2f}   disc ${tot_disc:.2f}   batch: {'YES (50% off in+out)' if cfg['batch'] else 'NO'}")
    print()

# ── SECTION 4: Three-scenario cost summary ────────────────────────────────────

core_nom  = sum(v["nominal"]    for v in core_costs.values())
core_disc = sum(v["discounted"] for v in core_costs.values())

print("=" * 72)
print("SECTION 4: THREE-SCENARIO COST SUMMARY")
print("=" * 72)

scenarios = [
    ("(a) 4-model core only",
     core_costs, {}),
    ("(b) 4-core + o4-mini COP-only",
     core_costs, {"o4-mini": reasoning_costs["o4-mini"]}),
    ("(c) 4-core + DeepSeek-R1-0528 COP-only",
     core_costs, {"DeepSeek-R1-0528": reasoning_costs["DeepSeek-R1-0528"]}),
]

for label, c_costs, r_costs in scenarios:
    nom  = sum(v["nominal"]    for v in c_costs.values()) + sum(v["nominal"]    for v in r_costs.values())
    disc = sum(v["discounted"] for v in c_costs.values()) + sum(v["discounted"] for v in r_costs.values())
    print(f"  {label}")
    for m, v in {**c_costs, **r_costs}.items():
        tag = "[reasoning COP-only]" if m in r_costs else ""
        print(f"    {m:<22}  nom ${v['nominal']:>7.2f}   disc ${v['discounted']:>7.2f}  {tag}")
    print(f"    {'TOTAL':<22}  nom ${nom:>7.2f}   disc ${disc:>7.2f}")
    print()

# ── SECTION 5: Recommendation ─────────────────────────────────────────────────

print("=" * 72)
print("SECTION 5: REASONING MODEL RECOMMENDATION")
print("=" * 72)
o4_disc  = reasoning_costs["o4-mini"]["discounted"]
dsr_disc = reasoning_costs["DeepSeek-R1-0528"]["discounted"]
print(f"""
  o4-mini           batch cost: ${o4_disc:.2f}
  DeepSeek-R1-0528  batch cost: ${dsr_disc:.2f}
  Cost difference: ${abs(o4_disc - dsr_disc):.2f} {'in favour of DeepSeek-R1' if dsr_disc < o4_disc else 'in favour of o4-mini'}

  DIVERSITY ARGUMENT:
    o4-mini adds reasoning capability but is the 3rd OpenAI model in the set
    (GPT-4.1 + gpt-4.1-nano + o4-mini). A reviewer can argue the robustness
    claim is only within the OpenAI family.

    DeepSeek-R1-0528 adds BOTH reasoning AND a 4th distinct model family
    (OpenAI / Anthropic / Meta-Llama / DeepSeek). This directly answers the
    cross-family robustness question that Axis C is designed to address.

  CONTEXT WINDOW:
    Both fit all 24 COP pages (NVxF3 max = {cop_tokens_per_page.max():,.0f} tok):
      o4-mini:          headroom {REASONING_MODELS['o4-mini']['ctx'] - MARGIN - cop_tokens_per_page.max():,.0f} tok
      DeepSeek-R1-0528: headroom {REASONING_MODELS['DeepSeek-R1-0528']['ctx'] - MARGIN - cop_tokens_per_page.max():,.0f} tok

  REASONING OUTPUT COST:
    Both are low relative to the observation-dominated input cost:
      o4-mini:          output adds ~{reasoning_costs['o4-mini']['out_nom']/reasoning_costs['o4-mini']['in_nom']*100:.0f}% on top of input
      DeepSeek-R1-0528: output adds ~{reasoning_costs['DeepSeek-R1-0528']['out_nom']/reasoning_costs['DeepSeek-R1-0528']['in_nom']*100:.0f}% on top of input
    Reasoning output cost is NOT disproportionate for either candidate.

  RECOMMENDATION: DeepSeek-R1-0528
    Cheaper, 4th distinct family, covers reasoning diversity AND family diversity.
    o4-mini is justified only if you specifically need OpenAI ecosystem comparison
    (e.g., same tokenizer, same fine-tuning provenance) — not the case here.

  CAVEAT: Verify rates at deployment — DeepSeek pricing has fluctuated; confirm
    $0.55/1M in and $2.19/1M out at deepseek.com/pricing before running.
""")

print("=" * 72)
print("BATCH API SUMMARY")
print("=" * 72)
print("""
  GPT-4.1:           OpenAI Batch API — 50% off input+output, async, 24h SLA
  gpt-4.1-nano:      OpenAI Batch API — 50% off input+output, async, 24h SLA
  Claude-Sonnet-4.6: Anthropic Message Batches — 50% off, async
  Llama-3.3-70B:     No batch API. Groq sync ~$0.59/1M; Together ~$0.88/1M.
  o4-mini:           OpenAI Batch API — 50% off input+output, async, 24h SLA
  DeepSeek-R1-0528:  DeepSeek Batch API — 50% off input+output, async
""")
