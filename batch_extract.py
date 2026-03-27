"""
Mrkt — Batch extraction using the Message Batches API.
Submits all agreements × all tools as a single batch for 50% cost savings.
Polls for completion and saves results.
"""

import json
import time
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic
from tools_schema import ALL_TOOLS

load_dotenv()

client = Anthropic()

SYSTEM_PROMPT = """You are a legal document analyst specializing in M&A merger agreements.
Your task is to extract specific deal provisions from merger agreements.

CRITICAL RULES:
1. Only extract information that is EXPLICITLY stated in the agreement text.
2. If a provision is not present, return null for that field. Do NOT guess or infer.
3. Dollar amounts should be raw numbers (e.g., 197000000 not "$197 million").
4. Percentage values should be decimals (e.g., 3.5 not 0.035).

WHERE TO LOOK:
- Termination fees: Termination section (usually Article VII, VIII, or IX). Look for
  "Company Termination Fee," "Termination Fee," "Break-Up Fee," or similar.
- Reverse termination fees: Same section. Look for "Parent Termination Fee" or
  "Reverse Termination Fee."
- Go-shop / No-shop: Covenants section (usually Article V or VI). A "no solicitation"
  or "no-shop" provision means go_shop.present = false.
- Efforts standard: Covenants section, in provisions about regulatory filings,
  antitrust approvals, or HSR Act compliance.
- MAC/MAE definition: Definitions article (usually Article I or Section 1.01).
- Specific performance: General/miscellaneous provisions (usually the last article).

APPROACH:
- Extract only what is explicitly stated in the agreement.
- If you cannot find a provision, return null — do not fabricate.
"""


def build_batch_requests(contract_dir: str = "data/maud/contracts") -> list:
    """Build a list of batch requests: one per agreement per tool."""

    requests = []
    contract_files = sorted(Path(contract_dir).glob("contract_*.txt"))

    print(f"Found {len(contract_files)} agreements")

    for contract_path in contract_files:
        contract_id = contract_path.stem  # e.g., "contract_0"
        text = contract_path.read_text()

        for tool in ALL_TOOLS:
            tool_name = tool["name"]
            custom_id = f"{contract_id}__{tool_name}"

            request = {
                "custom_id": custom_id,
                "params": {
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 4096,
                    "system": SYSTEM_PROMPT,
                    "tools": [tool],
                    "tool_choice": {"type": "tool", "name": tool_name},
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                f"Extract the {tool_name.replace('extract_', '').replace('_', ' ')} "
                                f"from this merger agreement:\n\n{text}"
                            )
                        }
                    ]
                }
            }
            requests.append(request)

    print(f"Built {len(requests)} batch requests ({len(contract_files)} agreements × {len(ALL_TOOLS)} tools)")
    return requests


def submit_batch(requests: list) -> str:
    """Submit a batch and return the batch ID."""

    print("Submitting batch to Anthropic...")
    batch = client.messages.batches.create(requests=requests)
    print(f"Batch submitted: {batch.id}")
    print(f"Status: {batch.processing_status}")
    return batch.id


def poll_batch(batch_id: str, poll_interval: int = 60) -> None:
    """Poll until the batch is complete."""

    print(f"\nPolling batch {batch_id} every {poll_interval} seconds...")
    print("(You can close this terminal — the batch runs on Anthropic's servers)")
    print(f"To check status later, run: python batch_extract.py --check {batch_id}\n")

    while True:
        batch = client.messages.batches.retrieve(batch_id)
        counts = batch.request_counts

        print(
            f"  [{time.strftime('%H:%M:%S')}] "
            f"Status: {batch.processing_status} | "
            f"Succeeded: {counts.succeeded} | "
            f"Processing: {counts.processing} | "
            f"Failed: {counts.errored}"
        )

        if batch.processing_status == "ended":
            print("\nBatch complete!")
            return

        time.sleep(poll_interval)


def collect_results(batch_id: str) -> dict:
    """Download results from a completed batch and organize by contract."""

    print(f"Collecting results from batch {batch_id}...")

    results = {}

    for result in client.messages.batches.results(batch_id):
        custom_id = result.custom_id
        # custom_id format: "contract_0__extract_termination_provisions"
        parts = custom_id.split("__")
        contract_id = parts[0]
        tool_name = parts[1]

        if contract_id not in results:
            results[contract_id] = {}

        if result.result.type == "succeeded":
            message = result.result.message
            for block in message.content:
                if block.type == "tool_use":
                    results[contract_id][tool_name] = block.input
                    break
            else:
                results[contract_id][tool_name] = {"error": "No tool call in response"}
        else:
            error_msg = str(result.result.error) if hasattr(result.result, 'error') else "Unknown error"
            results[contract_id][tool_name] = {"error": error_msg}

    # Save results
    output_path = "data/full_extraction_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    # Print summary
    success_count = 0
    error_count = 0
    for contract_id, tools in sorted(results.items()):
        for tool_name, data in tools.items():
            if "error" in data:
                error_count += 1
            else:
                success_count += 1

    print(f"\nResults saved to {output_path}")
    print(f"Total extractions: {success_count + error_count}")
    print(f"Succeeded: {success_count}")
    print(f"Failed: {error_count}")

    return results


def print_summary(results: dict) -> None:
    """Print a summary table of extraction results."""

    print(f"\n{'Contract':<14} {'Term Fee':>14} {'Reverse Fee':>14} {'Go-Shop':<8} "
          f"{'Efforts (stated)':<24} {'Efforts (functional)':<24} "
          f"{'MAC#':>5} {'Spec Perf':<15}")
    print("-" * 130)

    for contract_id in sorted(results.keys(), key=lambda x: int(x.split("_")[1])):
        data = results[contract_id]

        tp = data.get("extract_termination_provisions", {})
        fee_obj = tp.get("target_termination_fee")
        fee = fee_obj.get("amount_dollars") if fee_obj and "error" not in tp else None
        rev_obj = tp.get("reverse_termination_fee")
        rev = rev_obj.get("amount_dollars") if rev_obj and "error" not in tp else None
        gs = tp.get("go_shop", {})
        gs_present = gs.get("present") if gs and "error" not in tp else None

        eff = data.get("extract_efforts_standard", {})
        stated = eff.get("stated_efforts_standard", "N/A") if "error" not in eff else "ERR"
        func = eff.get("functional_efforts_classification", "N/A") if "error" not in eff else "ERR"

        mac = data.get("extract_mac_definition", {})
        mac_count = mac.get("total_carveout_count", "N/A") if "error" not in mac else "ERR"

        sp = data.get("extract_specific_performance", {})
        sp_avail = sp.get("specific_performance_available", "N/A") if "error" not in sp else "ERR"

        fee_str = f"${fee:,.0f}" if fee else "None"
        rev_str = f"${rev:,.0f}" if rev else "None"
        gs_str = "Yes" if gs_present else "No" if gs_present is not None else "N/A"

        print(f"{contract_id:<14} {fee_str:>14} {rev_str:>14} {gs_str:<8} "
              f"{str(stated):<24} {str(func):<24} {str(mac_count):>5} {str(sp_avail):<15}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        # Check status of an existing batch
        batch_id = sys.argv[2]
        batch = client.messages.batches.retrieve(batch_id)
        print(f"Batch: {batch_id}")
        print(f"Status: {batch.processing_status}")
        print(f"Succeeded: {batch.request_counts.succeeded}")
        print(f"Failed: {batch.request_counts.errored}")
        print(f"Processing: {batch.request_counts.processing}")

        if batch.processing_status == "ended":
            results = collect_results(batch_id)
            print_summary(results)

    elif len(sys.argv) > 1 and sys.argv[1] == "--results":
        # Print summary from saved results
        with open("data/full_extraction_results.json") as f:
            results = json.load(f)
        print_summary(results)

    else:
        # Full run: build, submit, poll, collect
        requests = build_batch_requests()
        batch_id = submit_batch(requests)

        # Save batch ID so we can check later
        with open("data/batch_id.txt", "w") as f:
            f.write(batch_id)
        print(f"Batch ID saved to data/batch_id.txt")

        poll_batch(batch_id)
        results = collect_results(batch_id)
        print_summary(results)