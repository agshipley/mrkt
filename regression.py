"""Sprint 2: Multivariate regression — fee % vs 365-day AR with controls."""
import json, statistics, math

with open('data/stock_returns.json') as f: returns = json.load(f)
with open('data/full_extraction_results.json') as f: extractions = json.load(f)
with open('data/deal_outcomes.json') as f: outcomes = json.load(f)
with open('data/deal_metadata.json') as f: metadata = json.load(f)

data = []
for cid, ret in returns.items():
    ar365 = ret.get('abnormal_return_365d')
    if ar365 is None: continue
    ext = extractions.get(cid, {})
    out = outcomes.get(cid, {})
    meta_d = metadata.get(cid, {})
    tp = ext.get('extract_termination_provisions', {})
    fee_obj = tp.get('target_termination_fee')
    fee_amt = fee_obj.get('amount_dollars') if isinstance(fee_obj, dict) else None
    deal_value = out.get('final_deal_value_dollars')
    fee_pct = (fee_amt / deal_value * 100) if fee_amt and deal_value and deal_value > 0 else None
    signing = meta_d.get('signing_date', '')
    try: year = int(signing[:4]) if signing and signing[0].isdigit() else None
    except: year = None
    agreement_type = meta_d.get('agreement_type', '')
    acquirer = meta_d.get('acquirer_name', '')
    pe_signals = ['parent', 'holdings', 'merger sub', 'acquisition', 'bidco', 'buyer', 'investor', 'partners']
    is_financial = any(s in acquirer.lower() for s in pe_signals)
    if fee_pct is not None and deal_value is not None and deal_value > 0 and year is not None:
        data.append({'cid': cid, 'acquirer': acquirer[:30], 'ar365': ar365,
            'fee_pct': fee_pct, 'log_dv': math.log(deal_value),
            'yr21': 1 if year == 2021 else 0, 'tender': 1 if 'tender' in agreement_type.lower() else 0,
            'fin': 1 if is_financial else 0})

print(f'N = {len(data)}')
ar_sorted = sorted([d['ar365'] for d in data])
lo = ar_sorted[int(0.05*len(ar_sorted))]
hi = ar_sorted[int(0.95*len(ar_sorted))]
for d in data: d['ar365w'] = max(lo, min(d['ar365'], hi))
print(f'Winsorize caps: [{lo:.1f}%, {hi:.1f}%]')

def ols(y, X):
    n, k = len(y), len(X[0])
    XtX = [[sum(X[i][a]*X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    Xty = [sum(X[i][j]*y[i] for i in range(n)) for j in range(k)]
    aug = [XtX[i][:] + [1 if i==j else 0 for j in range(k)] for i in range(k)]
    for col in range(k):
        mr = max(range(col,k), key=lambda r: abs(aug[r][col]))
        aug[col], aug[mr] = aug[mr], aug[col]
        piv = aug[col][col]
        if abs(piv) < 1e-12: return None
        for j in range(2*k): aug[col][j] /= piv
        for row in range(k):
            if row != col:
                f = aug[row][col]
                for j in range(2*k): aug[row][j] -= f * aug[col][j]
    inv = [aug[i][k:] for i in range(k)]
    b = [sum(inv[i][j]*Xty[j] for j in range(k)) for i in range(k)]
    res = [y[i] - sum(b[j]*X[i][j] for j in range(k)) for i in range(n)]
    meat = [[sum(res[i]**2 * X[i][a]*X[i][bb] for i in range(n))*(n/(n-k)) for bb in range(k)] for a in range(k)]
    tmp = [[sum(inv[i][m]*meat[m][j] for m in range(k)) for j in range(k)] for i in range(k)]
    V = [[sum(tmp[i][m]*inv[m][j] for m in range(k)) for j in range(k)] for i in range(k)]
    se = [V[i][i]**0.5 for i in range(k)]
    t = [b[i]/se[i] if se[i]>0 else 0 for i in range(k)]
    ym = sum(y)/n
    r2 = 1 - sum(r**2 for r in res)/sum((yi-ym)**2 for yi in y) if sum((yi-ym)**2 for yi in y)>0 else 0
    return b, se, t, r2

def run(title, y, X, names):
    r = ols(y, X)
    if not r: print(f'{title}: FAILED'); return
    b, se, t, r2 = r
    print(f'\n{"="*60}\n{title}\nN={len(y)}, R2={r2:.4f}\n{"="*60}')
    print(f'{"Var":<20} {"Coeff":>9} {"SE":>9} {"t":>8}')
    print('-'*50)
    for i,v in enumerate(names):
        sig = '***' if abs(t[i])>2.576 else '**' if abs(t[i])>1.96 else '*' if abs(t[i])>1.645 else ''
        print(f'{v:<20} {b[i]:>+9.4f} {se[i]:>9.4f} {t[i]:>+8.3f} {sig}')

y_raw = [d['ar365'] for d in data]
y_win = [d['ar365w'] for d in data]

run('M1: Fee only', y_raw, [[1, d['fee_pct']] for d in data], ['intercept','fee_pct'])
run('M2: Fee + deal size', y_raw, [[1, d['fee_pct'], d['log_dv']] for d in data], ['intercept','fee_pct','log_deal_val'])
run('M3: Fee + size + year + buyer', y_raw, [[1, d['fee_pct'], d['log_dv'], d['yr21'], d['fin']] for d in data], ['intercept','fee_pct','log_deal_val','year_2021','is_financial'])
run('M4: Fee only (winsorized)', y_win, [[1, d['fee_pct']] for d in data], ['intercept','fee_pct'])
run('M5: Fee + size (winsorized)', y_win, [[1, d['fee_pct'], d['log_dv']] for d in data], ['intercept','fee_pct','log_deal_val'])
run('M6: Fee + size + year + buyer (winsorized)', y_win, [[1, d['fee_pct'], d['log_dv'], d['yr21'], d['fin']] for d in data], ['intercept','fee_pct','log_deal_val','year_2021','is_financial'])

print('\nKEY: fee_pct coeff = change in AR365 per 1pp fee increase')
print('Negative = higher fees -> worse returns')
print('t > 1.96 = sig at 5%. Question: does fee survive controls?')