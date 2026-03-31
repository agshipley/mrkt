"""
Collect deal outcome data using Claude with web search.
For each deal: did it close, when, and at what final price.
"""

import json
import time
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic()

OUTCOME_TOOL = {
    "name": "record_deal_outcome",
    "description": "Records the outcome of a public M&A transaction.",
    "input_schema": {
        "type": "object",
        "properties": {
            "deal_completed": {
                "type": ["boolean", "null"],
                "description": "Whether the deal ultimately closed/completed"
            },
            "completion_date": {
                "type": ["string", "null"],
                "description": "Date the deal closed, YYYY-MM-DD format"
            },
            "days_to_close": {
                "type": ["integer", "null"],
                "description": "Number of calendar days from signing to closing"
            },
            "deal_terminated": {
                "type": ["boolean", "null"],
                "description": "Whether the deal was terminated/abandoned"
            },
            "termination_reason": {
                "type": ["string", "null"],
                "enum": [
                    "regulatory_block",
                    "competing_bid",
                    "target_mae",
                    "financing_failure",
                    "mutual_agreement",
                    "litigation",
                    "other",
                    None
                ]
            },
            "final_deal_value_dollars": {
                "type": ["number", "null"],
                "description": "Final total deal value in dollars, if reported"
            },
            "price_per_share": {
                "type": ["number", "null"],
                "description": "Final price per share paid to target shareholders"
            },
            "deal_was_amended": {
                "type": ["boolean", "null"],
                "description": "Whether the deal terms were amended between signing and closing"
            },
            "acquirer_ticker": {
                "type": ["string", "null"],
                "description": "Stock ticker symbol of the acquiring company"
            },
            "target_ticker": {
                "type": ["string", "null"],
                "description": "Stock ticker symbol of the target company (pre-acquisition)"
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"]
            }
        },
        "required": ["deal_completed", "completion_date", "days_to_close",
                     "deal_terminated", "confidence"]
    }
}


def collect_outcome(acquirer: str, target: str, signing_date: str, contract_id: str) -> dict:
    """Look up the outcome of a single deal using web search."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=(
            "You are a financial research assistant. Use web search to find the outcome "
            "of the specified M&A transaction. Report factual information only. "
            "If you cannot confirm whether the deal closed, set confidence to 'low'."
        ),
        tools=[
            OUTCOME_TOOL,
            {"type": "web_search_20250305", "name": "web_search"}
        ],
        tool_choice={"type": "auto"},
        messages=[{
            "role": "user",
            "content": (
                f"What was the outcome of this M&A deal?\n\n"
                f"Acquirer: {acquirer}\n"
                f"Target: {target}\n"
                f"Signing date: {signing_date}\n\n"
                f"Did the deal close? If so, when? What was the final deal value "
                f"and price per share? Was the deal amended? What are the ticker "
                f"symbols for both companies?"
            )
        }]
    )

    # Handle the agentic loop — Claude may search first, then call the tool
    messages = [{
        "role": "user",
        "content": (
            f"What was the outcome of this M&A deal?\n\n"
            f"Acquirer: {acquirer}\n"
            f"Target: {target}\n"
            f"Signing date: {signing_date}\n\n"
            f"Did the deal close? If so, when? What was the final deal value "
            f"and price per share? Was the deal amended? What are the ticker "
            f"symbols for both companies?"
        )
    }]

    max_turns = 5
    for turn in range(max_turns):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=(
                "You are a financial research assistant. Use web search to find the outcome "
                "of the specified M&A transaction. After searching, call the record_deal_outcome "
                "tool with your findings. If you cannot confirm whether the deal closed, "
                "set confidence to 'low'."
            ),
            tools=[
                OUTCOME_TOOL,
                {"type": "web_search_20250305", "name": "web_search"}
            ],
            messages=messages
        )

        # Check what Claude returned
        tool_results = []
        outcome_data = None

        for block in response.content:
            if block.type == "tool_use" and block.name == "record_deal_outcome":
                outcome_data = block.input
            elif block.type == "tool_use" and block.name == "web_search":
                # Web search is server-side — we don't handle it
                pass

        if outcome_data:
            return outcome_data

        # If Claude didn't call the outcome tool, it probably searched.
        # Add its response to messages and continue the loop.
        if response.stop_reason == "end_turn":
            # Claude responded with text but didn't call the tool.
            # Ask it to call the tool now.
            messages.append({"role": "assistant", "content": response.content})
            messages.append({
                "role": "user",
                "content": "Now call the record_deal_outcome tool with your findings."
            })
        elif response.stop_reason == "tool_use":
            # Claude called web_search (server-side) — add response and continue
            messages.append({"role": "assistant", "content": response.content})

            # Add tool results for any server-side tool calls
            for block in response.content:
                if block.type == "tool_use" and block.name != "record_deal_outcome":
                    # Server-side tools handle themselves, but we need to
                    # continue the conversation
                    pass

            # For server-side tools, the results are already in the response
            # Just continue the loop
        else:
            break

    return {"error": "Could not extract outcome after max turns", "confidence": "low"}


def main():
    """Collect outcomes for all deals."""

    with open('data/deal_metadata.json') as f:
        metadata = json.load(f)

    # Load any existing results to allow resuming
    output_path = 'data/deal_outcomes.json'
    if Path(output_path).exists():
        with open(output_path) as f:
            outcomes = json.load(f)
        print(f"Resuming: {len(outcomes)} already collected")
    else:
        outcomes = {}

    remaining = {k: v for k, v in metadata.items() if k not in outcomes}
    print(f"Total deals: {len(metadata)}")
    print(f"Remaining: {len(remaining)}")
    print()

    for i, (contract_id, meta) in enumerate(sorted(remaining.items(),
            key=lambda x: int(x[0].split('_')[1]))):

        acquirer = meta.get('acquirer_name', 'Unknown')
        target = meta.get('target_name', 'Unknown')
        signing_date = meta.get('signing_date', 'Unknown')

        print(f"[{i+1:>3}/{len(remaining)}] {acquirer[:25]} / {target[:25]} ({signing_date})...",
              end="", flush=True)

        try:
            result = collect_outcome(acquirer, target, signing_date, contract_id)
            outcomes[contract_id] = result
            closed = result.get('deal_completed')
            conf = result.get('confidence', '?')
            print(f" {'CLOSED' if closed else 'NOT CLOSED' if closed is False else '?'} (conf: {conf})")
        except Exception as e:
            print(f" ERROR: {e}")
            outcomes[contract_id] = {"error": str(e), "confidence": "low"}

        # Save after every deal so we don't lose progress
        with open(output_path, 'w') as f:
            json.dump(outcomes, f, indent=2)

        # Small delay to avoid rate limiting
        time.sleep(2)

    print(f"\nDone. Results saved to {output_path}")

    # Summary
    completed = sum(1 for v in outcomes.values() if v.get('deal_completed') is True)
    terminated = sum(1 for v in outcomes.values() if v.get('deal_completed') is False)
    unknown = sum(1 for v in outcomes.values() if v.get('deal_completed') is None or 'error' in v)
    print(f"Completed: {completed}")
    print(f"Terminated: {terminated}")
    print(f"Unknown/Error: {unknown}")


if __name__ == "__main__":
    main()
