"""
Mrkt — Term Extraction Pipeline
First target: Termination fee provisions
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

client = Anthropic()

# --- Tool Definition ---
# This is the JSON schema that forces Claude to return structured data.
# Every field that might be absent in an agreement is nullable.

TERMINATION_FEE_TOOL = {
    "name": "extract_termination_provisions",
    "description": (
        "Extracts termination fee structure from a merger agreement. "
        "Call this tool once with all termination-related provisions found in the agreement. "
        "If a provision is not present in the agreement, set its value to null. "
        "Do NOT fabricate or infer values — only extract what is explicitly stated."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "target_termination_fee": {
                "type": ["object", "null"],
                "description": "Fee payable by the target company upon termination (break-up fee)",
                "properties": {
                    "amount_dollars": {
                        "type": ["number", "null"],
                        "description": "Dollar amount of the termination fee"
                    },
                    "as_percentage_of_deal_value": {
                        "type": ["number", "null"],
                        "description": "Fee as a percentage of total deal value, if calculable"
                    },
                    "triggers": {
                        "type": ["array", "null"],
                        "description": "Events that trigger this fee",
                        "items": {
                            "type": "string",
                            "enum": [
                                "superior_proposal",
                                "board_recommendation_change",
                                "shareholder_vote_failure_after_competing_bid",
                                "regulatory_failure",
                                "financing_failure",
                                "general_breach",
                                "other"
                            ]
                        }
                    },
                    "trigger_details": {
                        "type": ["string", "null"],
                        "description": "Additional detail if trigger is 'other' or if nuance is needed"
                    }
                }
            },
            "reverse_termination_fee": {
                "type": ["object", "null"],
                "description": "Fee payable by the acquirer/parent upon termination",
                "properties": {
                    "amount_dollars": {
                        "type": ["number", "null"],
                        "description": "Dollar amount of the reverse termination fee"
                    },
                    "triggers": {
                        "type": ["array", "null"],
                        "description": "Events that trigger this fee",
                        "items": {
                            "type": "string",
                            "enum": [
                                "regulatory_failure",
                                "financing_failure",
                                "general_breach",
                                "other"
                            ]
                        }
                    },
                    "trigger_details": {
                        "type": ["string", "null"],
                        "description": "Additional detail on triggers"
                    }
                }
            },
            "go_shop": {
                "type": ["object", "null"],
                "description": "Go-shop provision allowing target to solicit competing bids after signing",
                "properties": {
                    "present": {
                        "type": "boolean",
                        "description": "Whether a go-shop provision exists"
                    },
                    "duration_days": {
                        "type": ["integer", "null"],
                        "description": "Number of days the go-shop window is open"
                    },
                    "reduced_fee_during_shop": {
                        "type": ["number", "null"],
                        "description": "Reduced termination fee amount during go-shop period, if any"
                    }
                }
            },
            "source_sections": {
                "type": ["string", "null"],
                "description": "Article/section numbers where termination fee provisions are found"
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "description": "Overall confidence in the extraction accuracy"
            }
        },
        "required": [
            "target_termination_fee",
            "reverse_termination_fee",
            "go_shop",
            "source_sections",
            "confidence"
        ]
    }
}

SYSTEM_PROMPT = """You are a legal document analyst specializing in M&A merger agreements. 
Your task is to extract specific termination fee provisions from merger agreements.

CRITICAL RULES:
1. Only extract information that is EXPLICITLY stated in the agreement text.
2. If a provision is not present, return null for that field. Do NOT guess or infer.
3. Dollar amounts should be extracted as raw numbers (e.g., 112000000 not "$112 million").
4. Percentage values should be decimals (e.g., 3.5 not 0.035).
5. Look in the Termination section (usually Article VII or VIII) for fee amounts and triggers.
6. Go-shop provisions may appear in the covenants section (usually Article V or VI).
7. A "no-shop" agreement (where the target cannot solicit competing bids) means go_shop.present = false.

EXTRACTION APPROACH:
- First, locate the termination section of the agreement.
- Identify the target termination fee (sometimes called "Company Termination Fee" or "Termination Fee").
- Identify any reverse termination fee (sometimes called "Parent Termination Fee" or "Reverse Termination Fee").
- Check for go-shop or no-shop provisions in the deal protection / covenants section.
- Note the exact sections where you found each provision.
"""


def extract_from_agreement(contract_path: str) -> dict:
    """Extract termination fee provisions from a single merger agreement."""
    
    # Read the agreement text
    text = Path(contract_path).read_text()
    
    print(f"Processing: {contract_path}")
    print(f"  Length: {len(text.split())} words")
    
    # Call Claude with the extraction tool
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[TERMINATION_FEE_TOOL],
        tool_choice={"type": "tool", "name": "extract_termination_provisions"},
        messages=[
            {
                "role": "user",
                "content": f"Extract the termination fee provisions from this merger agreement:\n\n{text}"
            }
        ]
    )
    
    # Extract the structured data from the tool call
    for block in response.content:
        if block.type == "tool_use":
            print(f"  Confidence: {block.input.get('confidence', 'unknown')}")
            print(f"  Source sections: {block.input.get('source_sections', 'unknown')}")
            return block.input
    
    print("  WARNING: No tool call in response")
    return None


def main():
    """Run extraction on a single agreement as a test."""
    
    result = extract_from_agreement("data/maud/contracts/contract_0.txt")
    
    if result:
        print("\n--- EXTRACTED DATA ---")
        print(json.dumps(result, indent=2))
    else:
        print("\nExtraction failed — no structured data returned.")


if __name__ == "__main__":
    main()