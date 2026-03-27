import csv

with open('data/maud/raw/main.csv', 'r') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

row = rows[0]
print("CONTRACT 0 - MAUD LABELS")
print()

print("=== NO-SHOP ===")
for key in row:
    if "No-Shop" in key or "no-shop" in key:
        print(f"  {key}: {row[key]}")

print()
print("=== ANTITRUST EFFORTS ===")
for key in row:
    if "Antitrust" in key:
        print(f"  {key}: {row[key]}")

print()
print("=== MAC DEFINITION (selected fields) ===")
for key in row:
    if key.startswith("MAE") or "disproportionate" in key.lower() or "Pandemic" in key:
        val = row[key]
        if len(str(val)) > 200:
            val = str(val)[:200] + "..."
        print(f"  {key}: {val}")

print()
print("=== SPECIFIC PERFORMANCE ===")
for key in row:
    if "Specific Performance" in key:
        print(f"  {key}: {row[key]}")
