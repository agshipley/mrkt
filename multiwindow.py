"""Sprint 2 Fix 7: Multi-window amplification check."""

import json
import random
import statistics

with open('data/stock_returns.json') as f:
    returns = json.load(f)
with open('data/full_extraction_results.json') as f:
    extractions = json.load(f)
with open('data/deal_outcomes.json') as f:
    outcomes = json.load(f)

data = []
for cid, ret in returns.items():
    ar7 = ret.get('abnormal_return_7d')
    ar30 = ret.get('abnormal_return_30d')
    ar90 = ret.get('abnormal_return_90d')
    ar365 = ret.get('abnormal_return_365d')
    if ar7 is None or ar30 is None or ar90 is None or ar365 is None:
        continue
    ext = extractions.get(cid, {})
    out = outcomes.get(cid, {})
    tp = ext.get('extract_termination_provisions', {})
    fee_obj = tp.get('target_termination_fee')
    fee_amt = fee_obj.get('amount_dollars') if isinstance(fee_obj, dict) else None
    deal_value = out.get('final_deal_value_dollars')
    fee_pct = (fee_amt / deal_value * 100) if fee_amt and deal_value and deal_value > 0 else None
    if fee_pct is not None:
        data.append({'fee_pct': fee_pct, 'ar7': ar7, 'ar30': ar30, 'ar90': ar90, 'ar365': ar365})

med_fee = statistics.median([d['fee_pct'] for d in data])
high = [d for d in data if d['fee_pct'] >= med_fee]
low = [d for d in data if d['fee_pct'] < med_fee]

def pearson_r(x, y):
    n = len(x)
    if n < 3: return 0
    mx, my = sum(x)/n, sum(y)/n
    num = sum((a-mx)*(b-my) for a,b in zip(x,y))
    dx = sum((a-mx)**2 for a in x)**0.5
    dy = sum((b-my)**2 for b in y)**0.5
    return num/(dx*dy) if dx and dy else 0

print('=' * 65)
print('FIX 7: MULTI-WINDOW AMPLIFICATION CHECK')
print(f'N = {len(data)}, median fee = {med_fee:.2f}%')
print(f'High-fee: {len(high)}, Low-fee: {len(low)}')
print('=' * 65)

print(f'\n{"Window":<10} {"High Mean":>10} {"Low Mean":>10} {"Spread":>10} {"Pearson r":>10}')
print('-' * 55)

windows = [('7d', 'ar7'), ('30d', 'ar30'), ('90d', 'ar90'), ('365d', 'ar365')]
spreads = []
for label, key in windows:
    h_mean = statistics.mean([d[key] for d in high])
    l_mean = statistics.mean([d[key] for d in low])
    spread = h_mean - l_mean
    r = pearson_r([d['fee_pct'] for d in data], [d[key] for d in data])
    spreads.append(spread)
    print(f'{label:<10} {h_mean:>+9.2f}% {l_mean:>+9.2f}% {spread:>+9.2f}pp {r:>+9.4f}')

print(f'\nMonotonicity check:')
monotonic = all(spreads[i] >= spreads[i+1] for i in range(len(spreads)-1))
if monotonic:
    print('  The negative spread strengthens monotonically across all four windows.')
    print('  "Amplification over time" is supported.')
else:
    print('  The spread does NOT strengthen monotonically.')
    non_mono = []
    for i in range(len(spreads)-1):
        if spreads[i] < spreads[i+1]:
            non_mono.append(f'{windows[i][0]} -> {windows[i+1][0]}')
    print(f'  Non-monotonic at: {", ".join(non_mono)}')
    print('  Recommend: replace "amplifies over time" with "the association is')
    print('  directionally present at longer horizons" or drop the temporal claim.')
