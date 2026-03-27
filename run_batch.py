"""Run full extraction across multiple agreements and save results."""

import json
from pathlib import Path
from extract import extract_from_agreement

def run_batch(start: int = 0, count: int = 10):
    """Extract all terms from a batch of agreements."""
    
    results = {}
    
    for i in range(start, start + count):
        path = f"data/maud/contracts/contract_{i}.txt"
        if not Path(path).exists():
            print(f"  Skipping {path} — file not found")
            continue
        
        try:
            result = extract_from_agreement(path)
            results[f"contract_{i}"] = result
            
            # Print summary
            term_fee = result.get("extract_termination_provisions", {})
            fee_obj = term_fee.get("target_termination_fee") if term_fee else None
            fee_amt = fee_obj.get("amount_dollars") if fee_obj else None
            
            efforts = result.get("extract_efforts_standard", {})
            stated = efforts.get("stated_efforts_standard") if efforts else None
            functional = efforts.get("functional_efforts_classification") if efforts else None
            
            mac = result.get("extract_mac_definition", {})
            carveout_count = mac.get("total_carveout_count") if mac else None
            
            sp = result.get("extract_specific_performance", {})
            sp_avail = sp.get("specific_performance_available") if sp else None
            
            print(f"  SUMMARY: Fee=${fee_amt:,.0f}" if fee_amt else "  SUMMARY: Fee=None", end="")
            print(f" | Efforts={stated}/{functional}", end="")
            print(f" | MAC carveouts={carveout_count}", end="")
            print(f" | SpecPerf={sp_avail}")
            print()
            
        except Exception as e:
            print(f"  ERROR on contract_{i}: {e}")
            results[f"contract_{i}"] = {"error": str(e)}
    
    # Save all results
    output_path = f"data/batch_{start}_to_{start+count-1}.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")
    print(f"Successfully extracted: {sum(1 for v in results.values() if 'error' not in v)}/{count}")

if __name__ == "__main__":
    run_batch(0, 10)
