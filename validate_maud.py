"""Sprint 2 Fix 5: Full MAUD validation across all 152 agreements."""

import json
import csv

with open('data/full_extraction_results.json') as f:
    extractions = json.load(f)

# Load MAUD labels
maud_rows = {}
with open('data/maud/raw/main.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        anon = row['Filename (anon)'].replace('.pdf', '')
        maud_rows[anon] = row

print('=' * 70)
print('FIX 5: FULL MAUD VALIDATION (152 AGREEMENTS)')
print('=' * 70)

# Validation 1: No-Shop vs our go_shop.present
print('\n1. No-Shop Validation')
print('   MAUD: "No-Shop" column text → does it describe a no-shop or go-shop?')
print('   Ours: go_shop.present (True = go-shop exists, False = no-shop)')

match = 0
mismatch = 0
missing = 0
details = []

for cid, ext in sorted(extractions.items(), key=lambda x: int(x[0].split('_')[1])):
    tp = ext.get('extract_termination_provisions', {})
    gs = tp.get('go_shop', {})
    our_goshop = gs.get('present') if isinstance(gs, dict) else None

    maud = maud_rows.get(cid, {})
    maud_noshop_text = maud.get('No-Shop', '')

    if not maud_noshop_text or our_goshop is None:
        missing += 1
        continue

    # MAUD labels go-shops by including "Go-Shop" in the section title
    maud_has_goshop = 'go-shop' in maud_noshop_text.lower() or 'go shop' in maud_noshop_text.lower()

    if our_goshop == maud_has_goshop:
        match += 1
    else:
        mismatch += 1
        details.append((cid, our_goshop, maud_has_goshop))

total = match + mismatch
print(f'   Matched: {match}/{total} ({match/total*100:.1f}%)')
print(f'   Mismatched: {mismatch}/{total}')
if details:
    for cid, ours, theirs in details[:10]:
        print(f'     {cid}: Ours={ours}, MAUD={theirs}')

# Validation 2: Antitrust Efforts Standard
print('\n2. Antitrust Efforts Standard Validation')
print('   MAUD column: "General Antitrust Efforts Standard-Answer"')

efforts_match = 0
efforts_mismatch = 0
efforts_details = []

# Map MAUD labels to our categories
maud_to_ours = {
    'Reasonable best efforts standard': 'reasonable_best_efforts',
    'Best efforts standard': 'best_efforts',
    'Commercially reasonable efforts standard': 'commercially_reasonable_efforts',
}

for cid, ext in sorted(extractions.items(), key=lambda x: int(x[0].split('_')[1])):
    eff = ext.get('extract_efforts_standard', {})
    our_stated = eff.get('stated_efforts_standard') if isinstance(eff, dict) else None
    our_functional = eff.get('functional_efforts_classification') if isinstance(eff, dict) else None

    maud = maud_rows.get(cid, {})
    maud_efforts = maud.get('General Antitrust Efforts Standard-Answer', '')
    maud_limitations = maud.get('Limitations on Antitrust Efforts-Answer', '')

    if not maud_efforts or our_stated is None:
        continue

    # Check stated standard match
    expected_stated = None
    for maud_label, our_label in maud_to_ours.items():
        if maud_label.lower() in maud_efforts.lower():
            expected_stated = our_label
            break

    # Check if MAUD says HOHW
    maud_is_hohw = 'hell or high water' in maud_limitations.lower() if maud_limitations else False

    if expected_stated and our_stated == expected_stated:
        efforts_match += 1
    elif expected_stated:
        efforts_mismatch += 1
        efforts_details.append((cid, our_stated, expected_stated, our_functional,
                               'HOHW' if maud_is_hohw else 'not-HOHW'))

total_eff = efforts_match + efforts_mismatch
if total_eff > 0:
    print(f'   Stated standard matched: {efforts_match}/{total_eff} ({efforts_match/total_eff*100:.1f}%)')
    print(f'   Mismatched: {efforts_mismatch}/{total_eff}')
    if efforts_details:
        print(f'   First 10 mismatches:')
        for cid, ours, expected, func, hohw in efforts_details[:10]:
            print(f'     {cid}: Ours={ours}, MAUD={expected}, Our functional={func}, MAUD HOHW={hohw}')

# Validation 3: Specific Performance
print('\n3. Specific Performance Validation')
print('   MAUD column: "Specific Performance-Answer"')

sp_match = 0
sp_mismatch = 0
sp_details = []

for cid, ext in sorted(extractions.items(), key=lambda x: int(x[0].split('_')[1])):
    sp = ext.get('extract_specific_performance', {})
    our_sp = sp.get('specific_performance_available') if isinstance(sp, dict) else None

    maud = maud_rows.get(cid, {})
    maud_sp = maud.get('Specific Performance-Answer', '')

    if not maud_sp or our_sp is None:
        continue

    # Map MAUD to our categories
    maud_entitled = 'entitled' in maud_sp.lower()
    our_entitled = our_sp in ('entitled_to', 'mutual_entitled_to')

    if maud_entitled == our_entitled:
        sp_match += 1
    else:
        sp_mismatch += 1
        sp_details.append((cid, our_sp, maud_sp[:60]))

total_sp = sp_match + sp_mismatch
if total_sp > 0:
    print(f'   Matched: {sp_match}/{total_sp} ({sp_match/total_sp*100:.1f}%)')
    print(f'   Mismatched: {sp_mismatch}/{total_sp}')
    if sp_details:
        for cid, ours, theirs in sp_details[:10]:
            print(f'     {cid}: Ours={ours}, MAUD={theirs}')

# Validation 4: MAC pandemic carveout
print('\n4. Pandemic Carveout Validation')
print('   MAUD column: "Pandemic or other public health event-Answer (Y/N)"')

pan_match = 0
pan_mismatch = 0
pan_details = []

for cid, ext in sorted(extractions.items(), key=lambda x: int(x[0].split('_')[1])):
    mac = ext.get('extract_mac_definition', {})
    carveouts = mac.get('carveouts', {}) if isinstance(mac, dict) else {}
    pandemic = carveouts.get('pandemic', {}) if isinstance(carveouts, dict) else {}
    our_pandemic = pandemic.get('present') if isinstance(pandemic, dict) else None

    maud = maud_rows.get(cid, {})
    maud_pandemic = maud.get('Pandemic or other public health event-Answer (Y/N)', '')

    if not maud_pandemic or our_pandemic is None:
        continue

    maud_yes = maud_pandemic.strip().lower() == 'yes'

    if our_pandemic == maud_yes:
        pan_match += 1
    else:
        pan_mismatch += 1
        pan_details.append((cid, our_pandemic, maud_pandemic.strip()))

total_pan = pan_match + pan_mismatch
if total_pan > 0:
    print(f'   Matched: {pan_match}/{total_pan} ({pan_match/total_pan*100:.1f}%)')
    print(f'   Mismatched: {pan_mismatch}/{total_pan}')
    if pan_details:
        for cid, ours, theirs in pan_details[:10]:
            print(f'     {cid}: Ours={ours}, MAUD={theirs}')

# Summary
print('\n' + '=' * 70)
print('VALIDATION SUMMARY')
print('=' * 70)
print(f'  No-shop/Go-shop:      {match}/{total} ({match/total*100:.1f}%)')
if total_eff > 0:
    print(f'  Efforts standard:     {efforts_match}/{total_eff} ({efforts_match/total_eff*100:.1f}%)')
if total_sp > 0:
    print(f'  Specific performance: {sp_match}/{total_sp} ({sp_match/total_sp*100:.1f}%)')
if total_pan > 0:
    print(f'  Pandemic carveout:    {pan_match}/{total_pan} ({pan_match/total_pan*100:.1f}%)')