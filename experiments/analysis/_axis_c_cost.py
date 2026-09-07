"""
Axis C cost reconciliation — final 4-model slate (no Llama).
GPT-4.1 reuses existing matrix data; nano + o4-mini + Claude are new spend.
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

REPO = pathlib.Path(__file__).parent.parent.parent
df   = load_dataframe(REPO)

# ── Unique (page, cell) observation token means, then summed ──────────────
CELLS_4  = {('B_full','F1'), ('B_noVolatile','F1'), ('B_noVolatile','F2'), ('B_noVolatile','F3')}
CELLS_COP = {('B_noVolatile','F3')}

def obs_sum(cell_set):
    mask = df.apply(lambda r: (r['bundle'], r['encoding']) in cell_set, axis=1)
    return df[mask].groupby(['page','bundle','encoding'])['observation_tokens'].mean().sum()

OBS_4   = obs_sum(CELLS_4)
OBS_COP = obs_sum(CELLS_COP)
N_REPS  = 10
EUR     = 1.08   # 1 EUR = 1.08 USD

RATES = {
    'gpt-4.1':           {'in': 2.00, 'cache': 1.00, 'out': 8.00},
    'gpt-4.1-nano':      {'in': 0.10, 'cache': 0.05, 'out': 0.40},
    'o4-mini':           {'in': 1.10, 'cache': 0.55, 'out': 4.40},
    'claude-sonnet-4-6': {'in': 3.00, 'cache': 3.00, 'out': 15.00},
}

print('=' * 72)
print('AXIS C COST RECONCILIATION — final 4-model slate')
print('=' * 72)
print(f'4-cell obs sum : {OBS_4:>12,.0f} tok  ({int(OBS_4/1e6*1000)/1000:.3f}M)')
print(f'COP obs sum    : {OBS_COP:>12,.0f} tok  ({int(OBS_COP/1e6*1000)/1000:.3f}M)')
print(f'N_REPS = {N_REPS}  |  EUR/USD = {EUR}')
print()

# (model_label, obs, n_cells, key, new_spend, has_cache)
MODELS = [
    ('GPT-4.1 (REUSE)',    OBS_4,   4, 'gpt-4.1',           False, True),
    ('gpt-4.1-nano',       OBS_4,   4, 'gpt-4.1-nano',      True,  True),
    ('o4-mini (COP only)', OBS_COP, 1, 'o4-mini',           True,  True),
    ('claude-sonnet-4-6',  OBS_4,   4, 'claude-sonnet-4-6', True,  False),
]

HDR = f"{'Model':<24} {'Cells':>5} {'Input tok':>13}  {'Naive $':>8}  {'Cache $':>8}  {'NaiveEUR':>9}  {'CacheEUR':>9}  Spend"
print(HDR)
print('-' * len(HDR))

total_naive_all = total_cache_all = 0.0
total_naive_new = total_cache_new = 0.0

for label, obs, nc, key, is_new, use_cache in MODELS:
    r       = RATES[key]
    in_tok  = obs * N_REPS                    # total input tokens
    n_calls = 24 * nc * N_REPS

    # Output tokens: reasoning models ~500 tok/call; others ~75 tok/call
    out_est = 500 if 'o4' in key else 75
    out_tok = n_calls * out_est

    naive_in  = in_tok  * r['in']  / 1e6
    naive_out = out_tok * r['out'] / 1e6
    naive     = naive_in + naive_out

    # Cache-adjusted: each unique (page,cell) obs sent N_REPS times
    # → 1 full-price call + (N_REPS-1) cached calls
    eff_in_rate = (r['in'] + (N_REPS - 1) * r['cache']) / N_REPS if use_cache else r['in']
    cache       = obs * N_REPS * eff_in_rate / 1e6 + naive_out

    tag = 'NEW' if is_new else 'reuse'
    print(f"{label:<24} {nc:>5} {int(in_tok):>13,}  ${naive:>7.2f}  ${cache:>7.2f}  {naive/EUR:>8.2f}€  {cache/EUR:>8.2f}€  {tag}")

    total_naive_all += naive
    total_cache_all += cache
    if is_new:
        total_naive_new += naive
        total_cache_new += cache

print('-' * len(HDR))
print(f"{'TOTAL  (all 4 models)':<24} {'':>5} {'':>13}  ${total_naive_all:>7.2f}  ${total_cache_all:>7.2f}  {total_naive_all/EUR:>8.2f}€  {total_cache_all/EUR:>8.2f}€")
print(f"{'NEW SPEND ONLY':<24} {'':>5} {'':>13}  ${total_naive_new:>7.2f}  ${total_cache_new:>7.2f}  {total_naive_new/EUR:>8.2f}€  {total_cache_new/EUR:>8.2f}€")

print()
print('Calculation notes:')
print(f'  GPT-4.1 reuse  : existing 960-call corpus already run; zero marginal cost.')
print(f'  Cache formula  : eff_rate = (in_rate + 9×cache_rate) / 10')
print(f'    nano         : ({RATES["gpt-4.1-nano"]["in"]:.2f} + 9×{RATES["gpt-4.1-nano"]["cache"]:.2f})/10 = {(RATES["gpt-4.1-nano"]["in"]+9*RATES["gpt-4.1-nano"]["cache"])/10:.4f} $/1M eff')
print(f'    o4-mini      : ({RATES["o4-mini"]["in"]:.2f} + 9×{RATES["o4-mini"]["cache"]:.2f})/10 = {(RATES["o4-mini"]["in"]+9*RATES["o4-mini"]["cache"])/10:.4f} $/1M eff')
print(f'  Claude         : no cache (conservative); Azure Anthropic endpoint caching TBC.')
print(f'  o4-mini output : ~500 reasoning tok/call × {24*1*N_REPS} calls × ${RATES["o4-mini"]["out"]}/1M = ${24*N_REPS*500*RATES["o4-mini"]["out"]/1e6:.2f}')
print(f'  nano output    : ~75 tok/call × {24*4*N_REPS} calls × ${RATES["gpt-4.1-nano"]["out"]}/1M = ${24*4*N_REPS*75*RATES["gpt-4.1-nano"]["out"]/1e6:.3f} (negligible)')
print(f'  Claude output  : ~75 tok/call × {24*4*N_REPS} calls × ${RATES["claude-sonnet-4-6"]["out"]}/1M = ${24*4*N_REPS*75*RATES["claude-sonnet-4-6"]["out"]/1e6:.2f} (modest)')
