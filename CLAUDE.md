# Mrkt — Project Conventions

## What This Project Does
Mrkt extracts structured deal terms from SEC-filed merger agreements and tests
whether those terms correlate with measurable post-transaction outcomes.

## Model Selection Rules
- Use Haiku 4.5 for straightforward extraction (termination fees, go-shop, efforts standard)
- Use Sonnet 4.6 for complex provisions (MAC definitions, ambiguous language)
- Use Sonnet 4.6 synchronously during prompt development and iteration
- Use Message Batches API for all bulk processing (50% cost savings)
- Always use prompt caching for system prompts and few-shot examples

## Extraction Conventions
- All extraction uses tool_use with JSON schemas — never ask for raw text output
- Every field that might be absent in an agreement MUST be nullable
- Use enum + "other" with other_detail string for categorical fields
- Include confidence (high/medium/low) and source_section on every extracted field
- Validate against MAUD labels when available

## Code Style
- Python 3.10+
- Type hints on all function signatures
- Docstrings on all public functions
- No print statements in library code — use logging module