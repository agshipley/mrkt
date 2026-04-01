"""Sprint 2 Fix 4: Selection bias table — included vs excluded deals."""

import json
import statistics

with open('data/full_extraction_results.json') as f:
    extractions = json.load(f)
with open('data/deal_outcomes.json') as f:
    outcomes = json.load(f)
with open('data/stock_returns.json') as f:
    returns = json.load(f)
with open('data/deal_metadata.json') as f:
    metadata = json.load(f)

def safe_mean(vals):
    v = [x for x in vals if x is not None]
    return statistics.mean(v) if v else None

def safe_median(vals):
    v = [x for x in vals if x is not None]
    return statistics.median(v) if v else None

included = []
excluded = []

for cid in extractions.keys():
    ret = returns.get(cid, {})
    out = outcomes.get(cid, {})
    ext = extractions.get(cid, {})
    meta_d = metadata.get(cid, {})

    tp = ext.get('extract_termination_provisions', {})
    fee_obj = tp.get('target_termination_fee')
    fee_amt = fee_obj.get('amount_dollars') if isinstance(fee_obj, dict) else None
    rev_obj = tp.get('reverse_termination_fee')
    rev_amt = rev_obj.get('amount_dollars') if isinstance(rev_obj, dict) else None
    gs = tp.get('go_shop', {})
    go_shop = gs.get('present') if isinstance(gs, dict) else None

    eff = ext.get('extract_efforts_standard', {})
    functional = eff.get('functional_efforts_classification') if isinstance(eff, dict) else None

    mac = ext.get('extract_mac_definition', {})
    mac_count = mac.get('total_carveout_count') if isinstance(mac, dict) else None

    deal_value = out.get('final_deal_value_dollars')
    fee_pct = (fee_amt / deal_value * 100) if fee_amt and deal_value and deal_value > 0 else None
    has_reverse = rev_amt is not None and rev_amt > 0
    days = out.get('days_to_close')
    agreement_type = meta_d.get('agreement_type')

    record = {
        'fee_pct': fee_pct, 'fee_amt': fee_amt, 'has_reverse': has_reverse,
        'go_shop': go_shop, 'functional': functional, 'mac_count': mac_count,
        'days_to_close': days, 'deal_value': deal_value, 'agreement_type': agreement_type,
    }

    if ret.get('abnormal_return_30d') is not None:
        included.append(record)
    else:
        excluded.append(record)

print('=' * 70)
print('FIX 4: SELECTION BIAS TABLE')
print(f'Included (has stock data): {len(included)}')
print(f'Excluded (no stock data):  {len(excluded)}')
print('=' * 70)

def fmt(v):
    if v is None:
        return "       N/A"
    return f"{v:>10.1f}"

def fmtd(v):
    if v is None:
        return "       N/A"
    return f"{v:>+10.1f}"

rows = [
    ('Fee % of deal value', [d['fee_pct'] for d in included], [d['fee_pct'] for d in excluded]),
    ('Fee amount ($M)', [d['fee_amt']/1e6 if d['fee_amt'] else None for d in included],
                        [d['fee_amt']/1e6 if d['fee_amt'] else None for d in excluded]),
    ('Deal value ($M)', [d['deal_value']/1e6 if d['deal_value'] else None for d in included],
                        [d['deal_value']/1e6 if d['deal_value'] else None for d in excluded]),
    ('Has reverse fee (%)', [100 if d['has_reverse'] else 0 for d in included],
                            [100 if d['has_reverse'] else 0 for d in excluded]),
    ('Go-shop present (%)', [100 if d['go_shop'] else 0 for d in included],
                            [100 if d['go_shop'] else 0 for d in excluded]),
    ('MAC carveout count', [d['mac_count'] for d in included], [d['mac_count'] for d in excluded]),
    ('Days to close', [d['days_to_close'] for d in included], [d['days_to_close'] for d in excluded]),
]

print(f"\n{'Variable':<25} {'Inc Mean':>10} {'Inc Med':>10} {'Exc Mean':>10} {'Exc Med':>10} {'Diff':>10}")
print('-' * 80)
for label, inc_vals, exc_vals in rows:
    im = safe_mean(inc_vals)
    imed = safe_median(inc_vals)
    em = safe_mean(exc_vals)
    emed = safe_median(exc_vals)
    diff = im - em if im is not None and em is not None else None
    print(f"{label:<25} {fmt(im)} {fmt(imed)} {fmt(em)} {fmt(emed)} {fmtd(diff)}")

print(f"\nFunctional Efforts Distribution:")
for eff in ['hell_or_high_water', 'limited_divestiture_obligation', 'no_divestiture_obligation']:
    ic = sum(1 for d in included if d['functional'] == eff)
    ec = sum(1 for d in excluded if d['functional'] == eff)
    print(f"  {eff:<35} Inc: {ic:>3} ({ic/len(included)*100:>5.1f}%)  Exc: {ec:>3} ({ec/len(excluded)*100:>5.1f}%)")

print(f"\nAgreement Type Distribution:")
for at in ['merger', 'tender_offer_and_merger']:
    ic = sum(1 for d in included if d['agreement_type'] == at)
    ec = sum(1 for d in excluded if d['agreement_type'] == at)
    print(f"  {at:<35} Inc: {ic:>3} ({ic/len(included)*100:>5.1f}%)  Exc: {ec:>3} ({ec/len(excluded)*100:>5.1f}%)")