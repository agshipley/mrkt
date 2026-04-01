"""Sprint 2 Fix 2: Nonparametric robustness checks on the fee split."""

import json
import random
import statistics

with open('data/stock_returns.json') as f:
    returns = json.load(f)
with open('data/full_extraction_results.json') as f:
    extractions = json.load(f)
with open('data/deal_outcomes.json') as f:
    outcomes = json.load(f)

# Build the fee-return pairs
data = []
for cid, ret in returns.items():
    ar30 = ret.get('abnormal_return_30d')
    ar365 = ret.get('abnormal_return_365d')
    if ar30 is None or ar365 is None:
        continue
    ext = extractions.get(cid, {})
    out = outcomes.get(cid, {})
    tp = ext.get('extract_termination_provisions', {})
    fee_obj = tp.get('target_termination_fee')
    fee_amt = fee_obj.get('amount_dollars') if isinstance(fee_obj, dict) else None
    deal_value = out.get('final_deal_value_dollars')
    fee_pct = (fee_amt / deal_value * 100) if fee_amt and deal_value and deal_value > 0 else None
    if fee_pct is not None:
        data.append({'fee_pct': fee_pct, 'ar30': ar30, 'ar365': ar365})

med_fee = statistics.median([d['fee_pct'] for d in data])
high = [d for d in data if d['fee_pct'] >= med_fee]
low = [d for d in data if d['fee_pct'] < med_fee]

observed_spread_30 = statistics.mean([d['ar30'] for d in high]) - statistics.mean([d['ar30'] for d in low])
observed_spread_365 = statistics.mean([d['ar365'] for d in high]) - statistics.mean([d['ar365'] for d in low])

print('=' * 65)
print('FIX 2: NONPARAMETRIC ROBUSTNESS ON FEE SPLIT')
print(f'N = {len(data)}, median fee = {med_fee:.2f}%')
print(f'High-fee group: {len(high)}, Low-fee group: {len(low)}')
print('=' * 65)
print(f'\nObserved spread (30d):  {observed_spread_30:+.2f}pp')
print(f'Observed spread (365d): {observed_spread_365:+.2f}pp')

# Permutation test
random.seed(42)
n_perm = 10000
ar30_all = [d['ar30'] for d in data]
ar365_all = [d['ar365'] for d in data]
n_high = len(high)

perm_spreads_30 = []
perm_spreads_365 = []
for _ in range(n_perm):
    idx = list(range(len(data)))
    random.shuffle(idx)
    h_idx = idx[:n_high]
    l_idx = idx[n_high:]
    s30 = statistics.mean([ar30_all[i] for i in h_idx]) - statistics.mean([ar30_all[i] for i in l_idx])
    s365 = statistics.mean([ar365_all[i] for i in h_idx]) - statistics.mean([ar365_all[i] for i in l_idx])
    perm_spreads_30.append(s30)
    perm_spreads_365.append(s365)

p_30 = sum(1 for s in perm_spreads_30 if s <= observed_spread_30) / n_perm
p_365 = sum(1 for s in perm_spreads_365 if s <= observed_spread_365) / n_perm

print(f'\n-- Permutation Test (10,000 reshuffles) --')
print(f'  30-day:  p = {p_30:.4f} (one-tailed, testing for negative spread)')
print(f'  365-day: p = {p_365:.4f} (one-tailed, testing for negative spread)')

# Bootstrap CI
random.seed(42)
n_boot = 10000
boot_spreads_30 = []
boot_spreads_365 = []
for _ in range(n_boot):
    h_sample = random.choices(high, k=len(high))
    l_sample = random.choices(low, k=len(low))
    s30 = statistics.mean([d['ar30'] for d in h_sample]) - statistics.mean([d['ar30'] for d in l_sample])
    s365 = statistics.mean([d['ar365'] for d in h_sample]) - statistics.mean([d['ar365'] for d in l_sample])
    boot_spreads_30.append(s30)
    boot_spreads_365.append(s365)

boot_spreads_30.sort()
boot_spreads_365.sort()
ci_30_lo = boot_spreads_30[int(0.025 * n_boot)]
ci_30_hi = boot_spreads_30[int(0.975 * n_boot)]
ci_365_lo = boot_spreads_365[int(0.025 * n_boot)]
ci_365_hi = boot_spreads_365[int(0.975 * n_boot)]

print(f'\n-- Bootstrap 95% CI (10,000 resamples) --')
print(f'  30-day spread:  [{ci_30_lo:+.2f}pp, {ci_30_hi:+.2f}pp]')
print(f'  365-day spread: [{ci_365_lo:+.2f}pp, {ci_365_hi:+.2f}pp]')

# Spearman rank correlation
def spearman_r(x, y):
    n = len(x)
    rx = [sorted(x).index(v) for v in x]
    ry = [sorted(y).index(v) for v in y]
    mx_r, my_r = sum(rx)/n, sum(ry)/n
    num = sum((a-mx_r)*(b-my_r) for a, b in zip(rx, ry))
    dx = sum((a-mx_r)**2 for a in rx)**0.5
    dy = sum((b-my_r)**2 for b in ry)**0.5
    return num/(dx*dy) if dx and dy else 0

fees = [d['fee_pct'] for d in data]
rho_30 = spearman_r(fees, [d['ar30'] for d in data])
rho_365 = spearman_r(fees, [d['ar365'] for d in data])

print(f'\n-- Spearman Rank Correlation --')
print(f'  Fee % vs 30d AR:  rho = {rho_30:.4f}')
print(f'  Fee % vs 365d AR: rho = {rho_365:.4f}')

# Alternative cutpoints
print(f'\n-- Alternative Cutpoints (365-day spread) --')
sorted_fees = sorted(fees)
cutpoints = [
    ('25th pct', sorted_fees[len(sorted_fees)//4]),
    ('Median', med_fee),
    ('75th pct', sorted_fees[3*len(sorted_fees)//4]),
    ('3.0%', 3.0),
    ('3.5%', 3.5),
    ('5.0%', 5.0),
]
for cut_name, cut_val in cutpoints:
    h = [d['ar365'] for d in data if d['fee_pct'] >= cut_val]
    l = [d['ar365'] for d in data if d['fee_pct'] < cut_val]
    if len(h) >= 5 and len(l) >= 5:
        spread = statistics.mean(h) - statistics.mean(l)
        print(f'  {cut_name} ({cut_val:.2f}%): N={len(h)}/{len(l)}, spread = {spread:+.2f}pp')
    else:
        print(f'  {cut_name} ({cut_val:.2f}%): insufficient group size')

# Winsorized
def winsorize(vals, pct):
    s = sorted(vals)
    n = len(s)
    lo = int(pct * n)
    hi = n - lo - 1
    return [max(s[lo], min(v, s[hi])) for v in vals]

print(f'\n-- Winsorized 365-Day Analysis --')
for pct in [0.01, 0.05, 0.10]:
    w_ar365 = winsorize([d['ar365'] for d in data], pct)
    w_high = [w_ar365[i] for i in range(len(data)) if data[i]['fee_pct'] >= med_fee]
    w_low = [w_ar365[i] for i in range(len(data)) if data[i]['fee_pct'] < med_fee]
    spread = statistics.mean(w_high) - statistics.mean(w_low)
    print(f'  {int(pct*100)}% winsorized: spread = {spread:+.2f}pp')
