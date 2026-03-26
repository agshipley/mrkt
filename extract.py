"""
Mrkt — Term Extraction Pipeline
Extracts termination fees, efforts standard, MAC definition, and specific performance.
"""

import json
import os
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
  antitrust approvals, or HSR Act compliance. Look for "reasonable best efforts,"
  "best efforts," "commercially reasonable efforts," or "hell or high water."
- MAC/MAE definition: Definitions article (usually Article I or Section 1.01).
  Look for "Material Adverse Effect" or "Material Adverse Change."
- Specific performance: General/miscellaneous provisions (usually the last article).
  Look for "Specific Performance," "Injunctive Relief," or "Equitable Relief."

APPROACH:
- Call each extraction tool exactly once.
- For each tool, extract only what is explicitly stated in the agreement.
- If you cannot find a provision, return null — do not fabricate.
"""


def extract_from_agreement(contract_path: str) -> dict:
    """Extract all deal terms from a single merger agreement."""

    text = Path(contract_path).read_text()

    print(f"Processing: {contract_path}")
    print(f"  Length: {len(text.split())} words")

    results = {}

    for tool in ALL_TOOLS:
        tool_name = tool["name"]
        print(f"  Extracting: {tool_name}...")

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[
                {
                    "role": "user",
                    "content": f"Extract the {tool_name.replace('extract_', '').replace('_', ' ')} from this merger agreement:\n\n{text}"
                }
            ]
        )

        for block in response.content:
            if block.type == "tool_use":
                results[tool_name] = block.input
                print(f"    Confidence: {block.input.get('confidence', 'unknown')}")
                break
        else:
            print(f"    WARNING: No tool call returned for {tool_name}")
            results[tool_name] = None

    return results


def main():
    """Run full extraction on a single agreement as a test."""

    result = extract_from_agreement("data/maud/contracts/contract_0.txt")

    print("\n--- EXTRACTED DATA ---")
    print(json.dumps(result, indent=2))

    # Save result
    Path("data").mkdir(exist_ok=True)
    with open("data/contract_0_full_extraction.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\nSaved to data/contract_0_full_extraction.json")


if __name__ == "__main__":
    main()