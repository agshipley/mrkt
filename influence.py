"""Sprint 2 Fix 3: Influence diagnostics on the 365-day fee split."""

import json
import statistics

with open('data/stock_returns.json') as f:
    returns = json.load(f)
with open('data/full_extraction_results.json') as f:
    extractions = json.load(f)
with open('data/deal_outcomes.json') as f:
    outcomes = json.load(f)
with open('data/deal_metadata.json') as f:
    metadata = json.load(f)

data = []
for cid, ret in returns.items():
    ar365 = ret.get('abnormal_return_365d')
    ar30 = ret.get('abnormal_return_30d')
    if ar365 is None:
        continue
    ext = extractions.get(cid, {})
    out = outcomes.get(cid, {})
    meta_d = metadata.get(cid, {})
    tp = ext.get('extract_termination_provisions', {})
    fee_obj = tp.get('target_termination_fee')
    fee_amt = fee_obj.get('amount_dollars') if isinstance(fee_obj, dict) else None
    deal_value = out.get('final_deal_value_dollars')
    fee_pct = (fee_amt / deal_value * 100) if fee_amt and deal_value and deal_value > 0 else None
    if fee_pct is not None:
        data.append({
            'cid': cid,
            'acquirer': meta_d.get('acquirer_name', '?')[:30],
            'target': meta_d.get('target_name', '?')[:30],
            'fee_pct': fee_pct,
            'ar30': ar30,
            'ar365': ar365,
        })

med_fee = statistics.median([d['fee_pct'] for d in data])

def compute_spread(dataset):
    high = [d['ar365'] for d in dataset if d['fee_pct'] >= med_fee]
    low = [d['ar365'] for d in dataset if d['fee_pct'] < med_fee]
    if not high or not low:
        return 0
    return statistics.mean(high) - statistics.mean(low)

full_spread = compute_spread(data)

print('=' * 70)
print('FIX 3: INFLUENCE DIAGNOSTICS (LEAVE-ONE-OUT)')
print(f'N = {len(data)}, Full 365-day spread = {full_spread:+.2f}pp')
print('=' * 70)

# Leave-one-out
results = []
for i, d in enumerate(data):
    reduced = data[:i] + data[i+1:]
    spread = compute_spread(reduced)
    change = spread - full_spread
    results.append({
        'cid': d['cid'],
        'acquirer': d['acquirer'],
        'target': d['target'],
        'fee_pct': d['fee_pct'],
        'ar365': d['ar365'],
        'group': 'HIGH' if d['fee_pct'] >= med_fee else 'LOW',
        'spread_without': spread,
        'change': change,
    })

# Sort by absolute influence
results.sort(key=lambda x: abs(x['change']), reverse=True)

print(f'\nTop 15 most influential observations:')
print(f'{"Rank":<5} {"Contract":<14} {"Acquirer":<25} {"Fee%":>6} {"AR365":>8} {"Group":<5} {"Spread w/o":>11} {"Change":>8}')
print('-' * 90)
for i, r in enumerate(results[:15]):
    print(f'{i+1:<5} {r["cid"]:<14} {r["acquirer"]:<25} {r["fee_pct"]:>5.2f}% {r["ar365"]:>+7.2f}% {r["group"]:<5} {r["spread_without"]:>+10.2f}pp {r["change"]:>+7.2f}pp')

# Summary
print(f'\nSpread range after removing any single observation:')
spreads = [r['spread_without'] for r in results]
print(f'  Min spread:  {min(spreads):+.2f}pp')
print(f'  Max spread:  {max(spreads):+.2f}pp')
print(f'  Full spread: {full_spread:+.2f}pp')

sign_flips = sum(1 for s in spreads if s > 0)
print(f'\n  Sign flips (spread turns positive): {sign_flips} / {len(spreads)}')
if sign_flips == 0:
    print('  Result: No single observation drives the sign of the result.')
else:
    print(f'  Result: {sign_flips} observation(s) can flip the sign. Finding is fragile.')
