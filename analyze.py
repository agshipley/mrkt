"""
Mrkt — First regression analysis.
Merges extraction results, metadata, and outcomes into one dataset.
Tests whether deal terms predict deal outcomes.
"""

import json
import csv
import statistics
from pathlib import Path


def load_data():
    """Load and merge all data sources into one dataset."""

    with open('data/full_extraction_results.json') as f:
        extractions = json.load(f)

    with open('data/deal_metadata.json') as f:
        metadata = json.load(f)

    with open('data/deal_outcomes.json') as f:
        outcomes = json.load(f)

    deals = []
    for contract_id in sorted(extractions.keys(), key=lambda x: int(x.split('_')[1])):
        ext = extractions.get(contract_id, {})
        meta = metadata.get(contract_id, {})
        out = outcomes.get(contract_id, {})

        # Termination fee extraction
        tp = ext.get('extract_termination_provisions', {})
        fee_obj = tp.get('target_termination_fee')
        fee_amt = fee_obj.get('amount_dollars') if isinstance(fee_obj, dict) else None
        rev_obj = tp.get('reverse_termination_fee')
        rev_amt = rev_obj.get('amount_dollars') if isinstance(rev_obj, dict) else None
        gs = tp.get('go_shop', {})
        go_shop = gs.get('present') if isinstance(gs, dict) else None

        # Efforts standard
        eff = ext.get('extract_efforts_standard', {})
        stated = eff.get('stated_efforts_standard') if isinstance(eff, dict) else None
        functional = eff.get('functional_efforts_classification') if isinstance(eff, dict) else None
        divestiture = eff.get('unlimited_divestiture_obligation') if isinstance(eff, dict) else None

        # MAC definition
        mac = ext.get('extract_mac_definition', {})
        mac_count = mac.get('total_carveout_count') if isinstance(mac, dict) else None

        # Specific performance
        sp = ext.get('extract_specific_performance', {})
        sp_avail = sp.get('specific_performance_available') if isinstance(sp, dict) else None

        # Outcome data
        completed = out.get('deal_completed')
        days = out.get('days_to_close')
        deal_value = out.get('final_deal_value_dollars')
        amended = out.get('deal_was_amended')
        acquirer_ticker = out.get('acquirer_ticker')

        # Compute termination fee as percentage of deal value
        fee_pct = None
        if fee_amt and deal_value and deal_value > 0:
            fee_pct = (fee_amt / deal_value) * 100

        # Has reverse fee (binary)
        has_reverse = rev_amt is not None and rev_amt > 0

        # Reverse fee ratio
        rev_ratio = None
        if rev_amt and fee_amt and fee_amt > 0:
            rev_ratio = rev_amt / fee_amt

        # Year
        signing_date = meta.get('signing_date', '')
        try:
            year = int(signing_date[:4]) if signing_date and signing_date[0].isdigit() else None
        except (ValueError, IndexError):
            year = None

        # Agreement type
        agreement_type = meta.get('agreement_type')

        deal = {
            'contract_id': contract_id,
            'acquirer': meta.get('acquirer_name', ''),
            'target': meta.get('target_name', ''),
            'signing_date': signing_date,
            'year': year,
            'agreement_type': agreement_type,
            'deal_value': deal_value,
            'fee_amount': fee_amt,
            'fee_pct': fee_pct,
            'has_reverse_fee': has_reverse,
            'reverse_fee_amount': rev_amt,
            'reverse_fee_ratio': rev_ratio,
            'go_shop': go_shop,
            'stated_efforts': stated,
            'functional_efforts': functional,
            'unlimited_divestiture': divestiture,
            'mac_carveout_count': mac_count,
            'specific_performance': sp_avail,
            'deal_completed': completed,
            'days_to_close': days,
            'deal_amended': amended,
            'acquirer_ticker': acquirer_ticker,
        }
        deals.append(deal)

    return deals


def descriptive_stats(deals):
    """Print descriptive statistics for the dataset."""

    print("=" * 70)
    print("MRKT — DESCRIPTIVE STATISTICS")
    print(f"Total deals: {len(deals)}")
    print("=" * 70)

    # Deal completion
    completed = [d for d in deals if d['deal_completed'] is True]
    terminated = [d for d in deals if d['deal_completed'] is False]
    print(f"\nDeal Outcomes:")
    print(f"  Completed: {len(completed)} ({len(completed)/len(deals)*100:.1f}%)")
    print(f"  Terminated: {len(terminated)} ({len(terminated)/len(deals)*100:.1f}%)")

    # Termination fees
    fees = [d['fee_pct'] for d in deals if d['fee_pct'] is not None]
    if fees:
        print(f"\nTermination Fee (% of deal value):")
        print(f"  N: {len(fees)}")
        print(f"  Mean: {statistics.mean(fees):.2f}%")
        print(f"  Median: {statistics.median(fees):.2f}%")
        print(f"  Std Dev: {statistics.stdev(fees):.2f}%")
        print(f"  Min: {min(fees):.2f}%")
        print(f"  Max: {max(fees):.2f}%")

    # Reverse fees
    has_rev = sum(1 for d in deals if d['has_reverse_fee'])
    print(f"\nReverse Termination Fee:")
    print(f"  Present: {has_rev} ({has_rev/len(deals)*100:.1f}%)")
    ratios = [d['reverse_fee_ratio'] for d in deals if d['reverse_fee_ratio'] is not None]
    if ratios:
        print(f"  Mean ratio (reverse/forward): {statistics.mean(ratios):.2f}x")
        print(f"  Median ratio: {statistics.median(ratios):.2f}x")

    # Go-shop
    go_shops = sum(1 for d in deals if d['go_shop'] is True)
    print(f"\nGo-Shop Provisions:")
    print(f"  Present: {go_shops} ({go_shops/len(deals)*100:.1f}%)")

    # Efforts standard
    print(f"\nStated Efforts Standard:")
    efforts_counts = {}
    for d in deals:
        e = d['stated_efforts'] or 'unknown'
        efforts_counts[e] = efforts_counts.get(e, 0) + 1
    for k, v in sorted(efforts_counts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v} ({v/len(deals)*100:.1f}%)")

    print(f"\nFunctional Efforts Classification:")
    func_counts = {}
    for d in deals:
        e = d['functional_efforts'] or 'unknown'
        func_counts[e] = func_counts.get(e, 0) + 1
    for k, v in sorted(func_counts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v} ({v/len(deals)*100:.1f}%)")

    # MAC carveouts
    macs = [d['mac_carveout_count'] for d in deals if d['mac_carveout_count'] is not None]
    if macs:
        print(f"\nMAC Carveout Count:")
        print(f"  Mean: {statistics.mean(macs):.1f}")
        print(f"  Median: {statistics.median(macs):.1f}")
        print(f"  Min: {min(macs)}, Max: {max(macs)}")

    # Days to close
    days = [d['days_to_close'] for d in deals if d['days_to_close'] is not None]
    if days:
        print(f"\nDays to Close (completed deals):")
        print(f"  N: {len(days)}")
        print(f"  Mean: {statistics.mean(days):.0f} days")
        print(f"  Median: {statistics.median(days):.0f} days")
        print(f"  Min: {min(days)}, Max: {max(days)}")

    # Year distribution
    print(f"\nYear Distribution:")
    year_counts = {}
    for d in deals:
        y = d['year'] or 'unknown'
        year_counts[y] = year_counts.get(y, 0) + 1
    for k, v in sorted(year_counts.items(), key=lambda x: str(x[0])):
        print(f"  {k}: {v}")


def correlation_analysis(deals):
    """Run correlational analyses between deal terms and outcomes."""

    print("\n" + "=" * 70)
    print("MRKT — CORRELATIONAL ANALYSIS")
    print("=" * 70)

    # ── Analysis 1: Fee percentage vs days to close ──
    paired = [(d['fee_pct'], d['days_to_close'])
              for d in deals
              if d['fee_pct'] is not None and d['days_to_close'] is not None]

    if len(paired) >= 10:
        x = [p[0] for p in paired]
        y = [p[1] for p in paired]
        r = pearson_r(x, y)
        print(f"\n1. Termination Fee (%) vs Days to Close")
        print(f"   N = {len(paired)}")
        print(f"   Pearson r = {r:.4f}")
        print(f"   Interpretation: {'Positive' if r > 0 else 'Negative'} correlation")
        print(f"   {'Weak' if abs(r) < 0.3 else 'Moderate' if abs(r) < 0.5 else 'Strong'} effect")

    # ── Analysis 2: Functional efforts vs days to close ──
    print(f"\n2. Functional Efforts Classification vs Days to Close")
    efforts_groups = {}
    for d in deals:
        if d['functional_efforts'] and d['days_to_close'] is not None:
            group = d['functional_efforts']
            if group not in efforts_groups:
                efforts_groups[group] = []
            efforts_groups[group].append(d['days_to_close'])

    for group, days in sorted(efforts_groups.items()):
        if len(days) >= 3:
            print(f"   {group}: N={len(days)}, "
                  f"Mean={statistics.mean(days):.0f} days, "
                  f"Median={statistics.median(days):.0f} days")

    # ── Analysis 3: MAC carveout count vs days to close ──
    paired = [(d['mac_carveout_count'], d['days_to_close'])
              for d in deals
              if d['mac_carveout_count'] is not None and d['days_to_close'] is not None]

    if len(paired) >= 10:
        x = [p[0] for p in paired]
        y = [p[1] for p in paired]
        r = pearson_r(x, y)
        print(f"\n3. MAC Carveout Count vs Days to Close")
        print(f"   N = {len(paired)}")
        print(f"   Pearson r = {r:.4f}")
        print(f"   Interpretation: {'Positive' if r > 0 else 'Negative'} correlation")
        print(f"   {'Weak' if abs(r) < 0.3 else 'Moderate' if abs(r) < 0.5 else 'Strong'} effect")

    # ── Analysis 4: Reverse fee presence vs days to close ──
    print(f"\n4. Reverse Fee Presence vs Days to Close")
    with_rev = [d['days_to_close'] for d in deals
                if d['has_reverse_fee'] and d['days_to_close'] is not None]
    without_rev = [d['days_to_close'] for d in deals
                   if not d['has_reverse_fee'] and d['days_to_close'] is not None]

    if with_rev and without_rev:
        print(f"   With reverse fee: N={len(with_rev)}, "
              f"Mean={statistics.mean(with_rev):.0f} days, "
              f"Median={statistics.median(with_rev):.0f} days")
        print(f"   Without reverse fee: N={len(without_rev)}, "
              f"Mean={statistics.mean(without_rev):.0f} days, "
              f"Median={statistics.median(without_rev):.0f} days")
        diff = statistics.mean(with_rev) - statistics.mean(without_rev)
        print(f"   Difference: {diff:+.0f} days")

    # ── Analysis 5: Go-shop vs days to close ──
    print(f"\n5. Go-Shop Presence vs Days to Close")
    with_gs = [d['days_to_close'] for d in deals
               if d['go_shop'] is True and d['days_to_close'] is not None]
    without_gs = [d['days_to_close'] for d in deals
                  if d['go_shop'] is False and d['days_to_close'] is not None]

    if with_gs and without_gs:
        print(f"   With go-shop: N={len(with_gs)}, "
              f"Mean={statistics.mean(with_gs):.0f} days, "
              f"Median={statistics.median(with_gs):.0f} days")
        print(f"   Without go-shop: N={len(without_gs)}, "
              f"Mean={statistics.mean(without_gs):.0f} days, "
              f"Median={statistics.median(without_gs):.0f} days")

    # ── Analysis 6: Fee percentage — high vs low ──
    fees_with_days = [(d['fee_pct'], d['days_to_close'])
                      for d in deals
                      if d['fee_pct'] is not None and d['days_to_close'] is not None]

    if len(fees_with_days) >= 20:
        median_fee = statistics.median([f[0] for f in fees_with_days])
        high_fee = [f[1] for f in fees_with_days if f[0] >= median_fee]
        low_fee = [f[1] for f in fees_with_days if f[0] < median_fee]

        print(f"\n6. Termination Fee Split (median = {median_fee:.2f}%) vs Days to Close")
        print(f"   High fee (>= {median_fee:.2f}%): N={len(high_fee)}, "
              f"Mean={statistics.mean(high_fee):.0f} days")
        print(f"   Low fee (< {median_fee:.2f}%): N={len(low_fee)}, "
              f"Mean={statistics.mean(low_fee):.0f} days")

    # ── Analysis 7: Reverse fee ratio vs days to close ──
    paired = [(d['reverse_fee_ratio'], d['days_to_close'])
              for d in deals
              if d['reverse_fee_ratio'] is not None and d['days_to_close'] is not None]

    if len(paired) >= 10:
        x = [p[0] for p in paired]
        y = [p[1] for p in paired]
        r = pearson_r(x, y)
        print(f"\n7. Reverse/Forward Fee Ratio vs Days to Close")
        print(f"   N = {len(paired)}")
        print(f"   Pearson r = {r:.4f}")
        print(f"   Interpretation: {'Positive' if r > 0 else 'Negative'} correlation")

    # ── Analysis 8: Functional efforts vs deal amended ──
    print(f"\n8. Functional Efforts vs Deal Amended")
    for eff_type in ['hell_or_high_water', 'limited_divestiture_obligation', 'no_divestiture_obligation']:
        group = [d for d in deals if d['functional_efforts'] == eff_type and d['deal_amended'] is not None]
        if group:
            amended = sum(1 for d in group if d['deal_amended'] is True)
            print(f"   {eff_type}: {amended}/{len(group)} amended ({amended/len(group)*100:.1f}%)")


def pearson_r(x, y):
    """Calculate Pearson correlation coefficient."""
    n = len(x)
    if n < 3:
        return 0

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    den_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
    den_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5

    if den_x == 0 or den_y == 0:
        return 0

    return num / (den_x * den_y)


def export_csv(deals):
    """Export the integrated dataset to CSV for external analysis."""

    output_path = 'data/mrkt_integrated_dataset.csv'
    fields = [
        'contract_id', 'acquirer', 'target', 'signing_date', 'year',
        'agreement_type', 'deal_value', 'fee_amount', 'fee_pct',
        'has_reverse_fee', 'reverse_fee_amount', 'reverse_fee_ratio',
        'go_shop', 'stated_efforts', 'functional_efforts',
        'unlimited_divestiture', 'mac_carveout_count', 'specific_performance',
        'deal_completed', 'days_to_close', 'deal_amended', 'acquirer_ticker'
    ]

    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for deal in deals:
            row = {k: deal.get(k, '') for k in fields}
            writer.writerow(row)

    print(f"\nIntegrated dataset exported to {output_path}")
    print(f"  {len(deals)} rows, {len(fields)} columns")


if __name__ == "__main__":
    deals = load_data()
    descriptive_stats(deals)
    correlation_analysis(deals)
    export_csv(deals)
