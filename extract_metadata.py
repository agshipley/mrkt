"""
Extract deal metadata (parties, date, consideration type) from agreement cover pages.
Uses only the first 1000 characters of each agreement to minimize token cost.
"""

import csv
import json
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic()

# Load the MAUD filename mapping
def load_mapping():
    mapping = {}
    with open('data/maud/raw/main.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            anon = row['Filename (anon)'].replace('.pdf', '')
            mapping[anon] = row['Filename'].replace('.pdf', '').replace('_', ' ')
    return mapping

METADATA_TOOL = {
    "name": "extract_deal_metadata",
    "description": "Extracts basic deal metadata from a merger agreement cover page.",
    "input_schema": {
        "type": "object",
        "properties": {
            "acquirer_name": {
                "type": ["string", "null"],
                "description": "Name of the acquiring company (usually the first or second named party, the parent)"
            },
            "target_name": {
                "type": ["string", "null"],
                "description": "Name of the target/acquired company"
            },
            "merger_sub_name": {
                "type": ["string", "null"],
                "description": "Name of the merger subsidiary if present (usually contains 'Merger Sub' or 'Acquisition')"
            },
            "signing_date": {
                "type": ["string", "null"],
                "description": "Date the agreement was signed, in YYYY-MM-DD format"
            },
            "agreement_type": {
                "type": ["string", "null"],
                "enum": [
                    "merger",
                    "tender_offer_and_merger",
                    "asset_purchase",
                    "stock_purchase",
                    "other",
                    None
                ]
            }
        },
        "required": ["acquirer_name", "target_name", "signing_date", "agreement_type"]
    }
}

def extract_metadata_batch():
    """Extract metadata from all agreements using minimal token input."""
    
    mapping = load_mapping()
    results = {}
    contract_files = sorted(Path('data/maud/contracts').glob('contract_*.txt'))
    
    print(f"Extracting metadata from {len(contract_files)} agreements...")
    print("(Using only first 1000 chars of each — minimal token cost)")
    print()
    
    for i, path in enumerate(contract_files):
        contract_id = path.stem
        text_preview = path.read_text()[:1000]
        maud_name = mapping.get(contract_id, "Unknown")
        
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system="Extract deal metadata from this merger agreement cover page. Return structured data only.",
                tools=[METADATA_TOOL],
                tool_choice={"type": "tool", "name": "extract_deal_metadata"},
                messages=[{
                    "role": "user",
                    "content": f"MAUD filename: {maud_name}\n\nAgreement text:\n{text_preview}"
                }]
            )
            
            for block in response.content:
                if block.type == "tool_use":
                    results[contract_id] = block.input
                    print(f"  [{i+1:>3}/{len(contract_files)}] {contract_id}: "
                          f"{block.input.get('acquirer_name', '?')} / "
                          f"{block.input.get('target_name', '?')} "
                          f"({block.input.get('signing_date', '?')})")
                    break
        except Exception as e:
            print(f"  [{i+1:>3}/{len(contract_files)}] {contract_id}: ERROR - {e}")
            results[contract_id] = {"error": str(e)}
    
    # Save results
    with open('data/deal_metadata.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nSaved to data/deal_metadata.json")
    print(f"Succeeded: {sum(1 for v in results.values() if 'error' not in v)}")
    print(f"Failed: {sum(1 for v in results.values() if 'error' in v)}")

if __name__ == "__main__":
    extract_metadata_batch()
