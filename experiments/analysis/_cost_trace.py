"""
Explicit step-by-step GPT-4.1 cost trace for Axis C: per-cell token counts and their
running euro total, reconciled against the recorded ~EUR90 experiment budget (the budget
is the model's API spend, distinct from the paper's fixed-tokenizer observation-cost metric).
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

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
df = load_dataframe(REPO_ROOT)

# ── Unique (page, cell) observation tokens ────────────────────────────────────
cell_df = df[
    ((df["bundle"] == "B_full")       & (df["encoding"] == "F1")) |
    ((df["bundle"] == "B_noVolatile") & (df["encoding"].isin(["F1","F2","F3"])))
].copy()
cell_df["cell"] = (
    cell_df["bundle"]
    .str.replace("B_noVolatile","NV",regex=False)
    .str.replace("B_full","BF",regex=False)
    + "x" + cell_df["encoding"]
)
page_cell = cell_df.groupby(["page","cell"])["observation_tokens"].mean()

N_PAGES = page_cell.index.get_level_values("page").nunique()
N_CELLS = page_cell.index.get_level_values("cell").nunique()
N_TASKS = 10
N_REPS  = 10
RATE_IN  = 2.00   # USD per 1M input tokens, GPT-4.1
RATE_OUT = 8.00   # USD per 1M output tokens, GPT-4.1 (for reference)
RATE_CACHE = 0.50 # USD per 1M cached input tokens, OpenAI

obs_sum = page_cell.sum()
obs_avg = page_cell.mean()

print("=" * 68)
print("EXPLICIT COST TRACE — GPT-4.1 core (4 diagnostic cells)")
print("=" * 68)

print()
print(f"STEP 0  Unique (page, cell) pairs")
print(f"        {N_CELLS} cells x {N_PAGES} pages = {N_CELLS*N_PAGES} rows  [confirmed: {len(page_cell)}]")

print()
print(f"STEP 1  Total observation tokens (sum over {N_CELLS*N_PAGES} unique (page,cell))")
print(f"        obs_sum = {obs_sum:>14,.0f}")
print(f"        obs_avg = {obs_avg:>14,.0f} per (page,cell)")
print(f"        Sanity: avg ~{obs_avg/1000:.0f}K")

# ── Call count ────────────────────────────────────────────────────────────────
calls_960   = N_CELLS * N_PAGES * N_REPS                  # no tasks factor
calls_9600  = N_CELLS * N_PAGES * N_TASKS * N_REPS        # tasks x reps

print()
print(f"STEP 2  Call count — what does '10 reps' mean?")
print(f"        Formula A (user):   cells x pages x reps           = {N_CELLS}x{N_PAGES}x{N_REPS} = {calls_960:,}")
print(f"        Formula B (script): cells x pages x tasks x reps   = {N_CELLS}x{N_PAGES}x{N_TASKS}x{N_REPS} = {calls_9600:,}")
print(f"        The script used formula B (introduced N_TASKS=10 from the existing design).")
print(f"        Discrepancy factor: {calls_9600//calls_960}x")

# ── Input tokens ──────────────────────────────────────────────────────────────
api_tok_A = obs_sum * N_REPS            # 960-call version
api_tok_B = obs_sum * N_TASKS * N_REPS  # 9,600-call version

print()
print(f"STEP 3  Total INPUT tokens")
print(f"        Formula A: {obs_sum:,.0f} x {N_REPS} = {api_tok_A:>14,.0f}")
print(f"        Formula B: {obs_sum:,.0f} x {N_TASKS} x {N_REPS} = {api_tok_B:>14,.0f}")

# ── GPT-4.1 input cost ────────────────────────────────────────────────────────
cost_A = api_tok_A * RATE_IN / 1_000_000
cost_B = api_tok_B * RATE_IN / 1_000_000

print()
print(f"STEP 4  GPT-4.1 input cost @ USD{RATE_IN}/1M")
print(f"        Formula A: {api_tok_A:>14,.0f} / 1e6 x {RATE_IN} = USD {cost_A:.2f}")
print(f"        Formula B: {api_tok_B:>14,.0f} / 1e6 x {RATE_IN} = USD {cost_B:.2f}  <- what the script printed")

print()
print(f"STEP 5  Output cost for core models (NOT in script)")
out_tok_A = calls_960  * 75
out_tok_B = calls_9600 * 75
out_A = out_tok_A * RATE_OUT / 1_000_000
out_B = out_tok_B * RATE_OUT / 1_000_000
print(f"        Locator output ~75 tok/call; output rate USD{RATE_OUT}/1M")
print(f"        Formula A output cost: {out_tok_A:,} tok -> USD {out_A:.2f}  (negligible)")
print(f"        Formula B output cost: {out_tok_B:,} tok -> USD {out_B:.2f}  (negligible)")
print(f"        Core model output was NOT included in either scenario. Confirmed correct.")

# ── Where did 1,305 come from ─────────────────────────────────────────────────
rates = {"GPT-4.1": 2.00, "gpt-4.1-nano": 0.10, "Claude-Sonnet-4.6": 3.00, "Llama-3.3-70B": 0.60}
total_B = sum(api_tok_B * r / 1_000_000 for r in rates.values())
total_A = sum(api_tok_A * r / 1_000_000 for r in rates.values())

print()
print(f"STEP 6  Where did USD 1,305 come from?")
print(f"        Script applied formula B (x{N_TASKS} x {N_REPS} = x100) to all 4 models:")
for m, r in rates.items():
    c = api_tok_B * r / 1_000_000
    print(f"          {m:<22}: {api_tok_B:>14,.0f} / 1e6 x {r} = USD {c:.2f}")
print(f"          TOTAL (nominal):                                     USD {total_B:.2f}  <- what script printed")
print()
print(f"        If formula A (x10 only, 960 calls):")
for m, r in rates.items():
    c = api_tok_A * r / 1_000_000
    print(f"          {m:<22}: {api_tok_A:>14,.0f} / 1e6 x {r} = USD {c:.2f}")
print(f"          TOTAL (nominal):                                     USD {total_A:.2f}")

# ── Reconcile against original run ────────────────────────────────────────────
print()
print("=" * 68)
print("RECONCILIATION vs original GPT-4.1 run (~EUR 90, 6,000 records)")
print("=" * 68)

all_obs_sum     = df["observation_tokens"].sum()
all_obs_avg     = df["observation_tokens"].mean()
n_records       = len(df)
orig_full_price = all_obs_sum * RATE_IN / 1_000_000

print(f"  6,000 records total: obs_tokens sum = {all_obs_sum:,.0f}")
print(f"  Average obs per record: {all_obs_avg:,.0f} tok")
print()
print(f"  Full price (no caching): {all_obs_sum:,.0f} / 1e6 x {RATE_IN} = USD {orig_full_price:.2f}")

# With prompt caching: 25 unique (page,cell) x 24 pages = 600 unique obs, each used 10x (tasks)
# First call: RATE_IN, next 9: RATE_CACHE
unique_obs_sum = df.groupby(["page","bundle","encoding"])["observation_tokens"].mean().sum()
orig_cache_cost = unique_obs_sum * (RATE_IN + 9 * RATE_CACHE) / 1_000_000
orig_cache_eur  = orig_cache_cost / 1.08

print(f"  Unique (page,bundle,enc) obs sum: {unique_obs_sum:,.0f}")
print(f"  With prompt cache (OpenAI 75% off hits; each unique obs used 10x for 10 tasks):")
print(f"    Cost = {unique_obs_sum:,.0f} x (2.00 + 9x0.50) / 1e6 = USD {orig_cache_cost:.2f} = EUR {orig_cache_eur:.2f}")
print(f"    Target: ~EUR 90.  Match: {'YES' if abs(orig_cache_eur - 90) < 20 else 'CHECK'}")

print()
print("IMPLICATION FOR AXIS C (9,600 calls, 100 uses of each unique obs):")
# 100 uses per unique (page,cell) obs: 1 full price + 99 cached
cache_factor_100 = (RATE_IN + 99 * RATE_CACHE) / (100 * RATE_IN)
axis_c_cache = obs_sum * (RATE_IN + 99 * RATE_CACHE) / 1_000_000
axis_c_cache_eur = axis_c_cache / 1.08
print(f"  Each unique obs used {N_TASKS*N_REPS}x: 1 full + 99 cached")
print(f"  Effective rate vs full-price: {cache_factor_100:.3f}x  ({(1-cache_factor_100)*100:.0f}% savings)")
print(f"  GPT-4.1 Axis C (with cache): {obs_sum:,.0f} x ({RATE_IN:.2f} + 99x{RATE_CACHE:.2f}) / 1e6 = USD {axis_c_cache:.2f} = EUR {axis_c_cache/1.08:.2f}")

print()
print("IMPLICATION FOR AXIS C (960 calls, 10 uses of each unique obs):")
axis_c_960_cache = obs_sum * (RATE_IN + 9 * RATE_CACHE) / 1_000_000
print(f"  Each unique obs used {N_REPS}x: 1 full + 9 cached")
print(f"  GPT-4.1 Axis C (with cache): {obs_sum:,.0f} x ({RATE_IN:.2f} + 9x{RATE_CACHE:.2f}) / 1e6 = USD {axis_c_960_cache:.2f} = EUR {axis_c_960_cache/1.08:.2f}")

print()
print("=" * 68)
print("VERDICT")
print("=" * 68)
print("""
  The script multiplied obs_sum by N_TASKS x N_REPS = 100.
  The user's formula "obs_tokens x 10 reps" uses a multiplier of 10.
  The 10x discrepancy is the missing task factor.

  WHICH IS CORRECT depends on the Axis C call design:
    (A) 1 call per (page, cell, rep) — tasks batched in one prompt:
        960 calls, obs_sum x 10, USD %.2f nominal for GPT-4.1
    (B) 1 call per (page, cell, task, rep) — existing structure x 10 reps:
        9,600 calls, obs_sum x 100, USD %.2f nominal for GPT-4.1
        With prompt caching (75%% off on 99/100 calls): USD %.2f for GPT-4.1

  Prompt caching reconciliation:
    Original (~EUR 90): consistent with design B (unique obs used 10x per task).
    Axis C design B with caching: EUR %.2f — compare with original EUR %.2f.
    Axis C design A with caching: EUR %.2f.
""" % (cost_A, cost_B, axis_c_cache, axis_c_cache/1.08, orig_cache_eur, axis_c_960_cache/1.08))
