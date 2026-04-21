# Mrkt — Moneyball for Transactional Law

Mrkt is a research and analytics pipeline that tests whether negotiated terms in SEC-filed M&A merger agreements carry measurable economic signal. It extracts structured provisions from agreement text with LLM-backed tool calls (Anthropic Claude), links those provisions to deal-outcome and market-return data, and runs a layered battery of statistical tests (descriptives, nonparametric robustness, influence diagnostics, multivariate regression).

The core thesis — that clause-level drafting choices correlate with post-transaction outcomes — is grounded in existing academic work (Coates/Palia/Wu 2019, Denis/Macias 2013, Officer 2003). Mrkt automates and scales what those papers did by hand, with a reproducible corpus, auditable tool schemas, and version-controlled analytical code.

---

## Table of Contents

1. [Headline Results](#headline-results)
2. [Pipeline Architecture](#pipeline-architecture)
3. [Repository Layout](#repository-layout)
4. [Environment Setup](#environment-setup)
5. [Data Sources](#data-sources)
6. [Extraction Pipeline](#extraction-pipeline)
7. [Tool Schemas — Search Logic](#tool-schemas--search-logic)
8. [Metadata Extraction](#metadata-extraction)
9. [Outcome Collection (Agentic Web Search)](#outcome-collection-agentic-web-search)
10. [Stock Return Pipeline](#stock-return-pipeline)
11. [Integrated Dataset Schema](#integrated-dataset-schema)
12. [Analysis Modules](#analysis-modules)
13. [Validation Against MAUD](#validation-against-maud)
14. [Sprint 1 Results](#sprint-1-results)
15. [Sprint 2 Robustness Battery](#sprint-2-robustness-battery)
16. [Multivariate Regression](#multivariate-regression)
17. [Cost Analysis](#cost-analysis)
18. [Known Limitations](#known-limitations)
19. [Academic Foundation](#academic-foundation)
20. [Next Steps](#next-steps)

---

## Headline Results

| Metric | Value |
|---|---|
| Agreements processed (MAUD 2020–2021) | 152 |
| Structured extractions attempted | 608 (152 × 4 tool schemas) |
| Successful extractions | 606 (99.7%) |
| Deals with acquirer stock-return data | 78 |
| MAUD agreement in validation (4 fields, weighted) | 91–94% |
| 365-day abnormal-return spread, high- vs low-fee split | **−27.00 pp** |
| Fee-percentage coefficient in final regression | β = −2.27, t = −2.22, p < 0.05 |
| Multi-window monotonic amplification (7d → 30d → 90d → 365d) | Confirmed |

**Headline finding.** Acquirers who agreed to above-median target termination fees (≥ 3.03% of deal value) experienced materially worse subsequent stock performance. The effect is directional at 30 days (−7.95 pp spread), strengthens monotonically across all four windows tested, and persists under deal-size, year, agreement-type, and buyer-type controls.

| Window | High Fee (≥3.03%) mean AR | Low Fee (<3.03%) mean AR | Spread |
|---|---|---|---|
| 7 days | — | — | negative |
| 30 days | −2.94% | +5.00% | −7.95 pp |
| 90 days | — | — | strengthening |
| 365 days | −2.19% | +24.81% | **−27.00 pp** |

---

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  MAUD CORPUS (Atticus, CC BY 4.0)                                    │
│  152 .txt merger agreements  +  47K expert labels (main.csv)          │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 1 — STRUCTURED EXTRACTION                                     │
│  Anthropic Messages / Batches API · claude-sonnet-4-6                 │
│  tool_choice = {type: "tool", name: "..."}   (forced tool use)        │
│                                                                       │
│   ┌────────────────────────┐  ┌────────────────────────┐             │
│   │ extract_termination_…  │  │ extract_efforts_standard│  (dual:     │
│   │   target/reverse fees  │  │  stated + functional)   │  stated +   │
│   │   go-shop + triggers   │  │  HOHW / divestiture     │  functional)│
│   └────────────────────────┘  └────────────────────────┘             │
│   ┌────────────────────────┐  ┌────────────────────────┐             │
│   │ extract_mac_definition │  │ extract_specific_perf.  │             │
│   │  10 carveouts, DI qual.│  │  entitlement + limits   │             │
│   └────────────────────────┘  └────────────────────────┘             │
│                                                                       │
│  Output: data/full_extraction_results.json                            │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 2 — METADATA (cover page, first 1000 chars only)              │
│  extract_metadata.py  → data/deal_metadata.json                       │
│  Parties, signing_date (YYYY-MM-DD), agreement_type enum              │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 3 — DEAL OUTCOMES (agentic loop, claude + web_search)         │
│  collect_outcomes.py  → data/deal_outcomes.json                       │
│  deal_completed, completion_date, days_to_close, final_value,         │
│  price_per_share, acquirer_ticker, deal_was_amended                   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 4 — MARKET DATA (Yahoo Finance via yfinance)                   │
│  collect_stock_returns.py  → data/stock_returns.json                  │
│  Abnormal returns vs ^GSPC at 7 / 30 / 90 / 365-day windows           │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 5 — MERGE + ANALYSIS                                          │
│  analyze.py → data/mrkt_integrated_dataset.csv  (22-column panel)     │
│    · descriptive statistics                                           │
│    · bivariate Pearson correlations                                   │
│    · median-split comparisons                                         │
│  validate_maud.py   — 4-field MAUD ground-truth validation            │
│  robustness.py      — permutation, bootstrap, Spearman, winsorize     │
│  influence.py       — leave-one-out diagnostics                       │
│  selection_bias.py  — included vs excluded deals                      │
│  multiwindow.py     — monotonicity across 4 windows                   │
│  regression.py      — OLS with HC1-style robust SEs, 6 specifications │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Repository Layout

```
mrkt/
├── .env                           # ANTHROPIC_API_KEY, EDGAR_IDENTITY (gitignored)
├── .gitignore                     # ignores .venv/, .env, data/, *.xlsx, __pycache__/
├── .mcp.json                      # EdgarTools MCP server config (uvx edgartools)
├── CLAUDE.md                      # Project conventions enforced by Claude Code
├── README.md                      # This file
│
├── tools_schema.py                # 4 JSON tool schemas (17 KB of schema definitions)
├── extract.py                     # Sync, single-agreement extraction (all 4 tools)
├── run_batch.py                   # Sync sequential runner (testing / dev)
├── batch_extract.py               # Message Batches API runner (production)
│
├── extract_metadata.py            # Cover-page-only metadata (cost-optimized)
├── collect_outcomes.py            # Agentic loop: Claude + server-side web_search
├── collect_stock_returns.py       # yfinance abnormal-return calculator
│
├── analyze.py                     # Sprint 1 descriptives + correlations + CSV export
├── check_labels.py                # MAUD label inspection utility
├── validate_maud.py               # Sprint 2: 4-field MAUD ground-truth validation
├── robustness.py                  # Sprint 2: nonparametric robustness battery
├── influence.py                   # Sprint 2: leave-one-out influence diagnostics
├── selection_bias.py              # Sprint 2: included vs excluded deal comparison
├── multiwindow.py                 # Sprint 2: 7/30/90/365-day monotonicity test
└── regression.py                  # Sprint 2: OLS with HC1 SEs, 6 specifications

data/                              # gitignored — local only
├── maud/
│   ├── contracts/                 # 152 contract_{N}.txt files from MAUD
│   └── raw/main.csv               # MAUD expert labels (47K labels × 152 deals)
├── full_extraction_results.json   # {contract_id: {tool_name: tool_input}}
├── deal_metadata.json             # {contract_id: {acquirer, target, date, type}}
├── deal_outcomes.json             # {contract_id: {completed, ticker, days_to_close,…}}
├── stock_returns.json             # {contract_id: {ticker, AR_{7,30,90,365}d, …}}
├── batch_id.txt                   # Last submitted Message Batches API job ID
└── mrkt_integrated_dataset.csv    # Final panel, 22 columns
```

---

## Environment Setup

### Prerequisites

- Python 3.10+ (type hints on all function signatures per `CLAUDE.md`)
- macOS or Linux (tested on Darwin 24.0.0)
- `uv` / `uvx` if you want to run the EdgarTools MCP server

### Install

```bash
git clone https://github.com/agshipley/mrkt.git
cd mrkt
python3 -m venv .venv
source .venv/bin/activate
pip install anthropic python-dotenv openpyxl edgartools yfinance
```

### Secrets

Create a `.env` in the repo root:

```env
ANTHROPIC_API_KEY=sk-ant-...
EDGAR_IDENTITY="Your Name your.email@example.com"
```

`EDGAR_IDENTITY` is required by the SEC EDGAR fair-access policy; EdgarTools refuses to issue requests without it.

### MAUD Corpus

Download the Atticus MAUD release from [TheAtticusProject/maud](https://github.com/TheAtticusProject/maud) and place it at:

```
data/maud/contracts/contract_{0..151}.txt
data/maud/raw/main.csv
```

The CSV's `Filename (anon)` column (with `.pdf` removed) is the key that maps to `contract_{N}`.

### MCP Server (Optional)

`.mcp.json` wires EdgarTools as a Claude Code MCP server:

```json
{
  "mcpServers": {
    "edgartools": {
      "command": "uvx",
      "args": ["--from", "edgartools", "edgar-mcp"],
      "env": { "EDGAR_IDENTITY": "${EDGAR_IDENTITY}" }
    }
  }
}
```

This is used for corpus expansion beyond MAUD — pulling additional merger agreements from EDGAR filings (8-Ks, DEFM14As, Ex-2.1 exhibits).

---

## Data Sources

| Source | Role | Access | Cost | License |
|---|---|---|---|---|
| [MAUD](https://github.com/TheAtticusProject/maud) | 152 agreements + 47K expert labels (ground truth) | GitHub release | Free | CC BY 4.0 |
| Anthropic API (Claude Sonnet 4.6) | Tool-use extraction, outcome web search | REST / Messages API + Batches API | ~$125 total for full pipeline | Commercial |
| Yahoo Finance via `yfinance` | Acquirer and S&P 500 daily closes | Screen-scrape | Free | MIT (`yfinance`) |
| [EdgarTools](https://github.com/dgunning/edgartools) | EDGAR access for corpus expansion | MCP server (`uvx`) | Free | MIT |

---

## Extraction Pipeline

### Conventions (from `CLAUDE.md`)

- **All extraction uses `tool_use` with JSON schemas — never raw text output.**
- **Every nullable-in-practice field is `type: ["…", "null"]`** (prevents fabrication).
- **Categorical fields use `enum` + an `"other"` slot** with a `*_detail` string for the literal language.
- **Every tool emits `confidence ∈ {high, medium, low}` and `source_sections`** for auditability.
- Haiku 4.5 is the default for straightforward extraction; Sonnet 4.6 for complex provisions. Production runs use Sonnet 4.6 everywhere for consistency.
- Prompt caching is used on system prompts and few-shot examples (not yet on per-agreement inputs — future optimization).

### Single-Agreement Extraction — [extract.py](extract.py)

Sequential, synchronous runner. For each of the 4 tools, one `client.messages.create` call with `tool_choice={"type": "tool", "name": tool_name}` (forced tool use). Used during prompt development and schema iteration.

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    system=SYSTEM_PROMPT,
    tools=[tool],
    tool_choice={"type": "tool", "name": tool_name},
    messages=[{"role": "user", "content": f"Extract … from this merger agreement:\n\n{text}"}],
)
```

### Bulk Extraction — [batch_extract.py](batch_extract.py)

Production runner. All 152 agreements × 4 tools = 608 requests submitted as one Message Batches job for the 50% batch discount, then polled until `processing_status == "ended"`.

Each batch request has a deterministic `custom_id` of the form `{contract_id}__{tool_name}` (e.g. `contract_42__extract_mac_definition`) so results can be reconstructed into a nested `{contract_id: {tool_name: tool_input}}` dict after completion.

Batch IDs are persisted to `data/batch_id.txt`; re-checking status is a one-liner:

```bash
python batch_extract.py --check msgbatch_01abcd…
```

### System Prompt (shared by [extract.py](extract.py) and [batch_extract.py](batch_extract.py))

The system prompt enforces four critical rules and gives section-level search guidance:

- Only extract **explicitly stated** information. Never infer or guess.
- Return `null` for any absent provision.
- Dollar amounts as raw numbers (`197000000`, not `"$197 million"`).
- Percentages as decimals (`3.5`, not `0.035`).

Search hints (where to look):

| Provision | Likely section |
|---|---|
| Termination fees | Article VII / VIII / IX; "Company/Parent Termination Fee," "Break-Up Fee" |
| Go-shop / no-shop | Article V / VI covenants; "no solicitation," "no-shop" |
| Efforts standard | Covenants — regulatory filings, antitrust, HSR Act compliance |
| MAC/MAE definition | Article I / §1.01 definitions |
| Specific performance | General/miscellaneous provisions (usually last article) |

---

## Tool Schemas — Search Logic

All four schemas live in [tools_schema.py](tools_schema.py). They are the core IP of the project: they encode what counts as a signal, what the enum universe is, and where the extractor should look.

### 1. `extract_termination_provisions` — [tools_schema.py:7-92](tools_schema.py#L7-L92)

Captures the termination-fee economics on both sides of the deal plus go-shop structure.

- **`target_termination_fee`** — object with `amount_dollars`, `as_percentage_of_deal_value`, `triggers` (enum array), `trigger_details` free-text.
  - Trigger enum: `superior_proposal`, `board_recommendation_change`, `shareholder_vote_failure_after_competing_bid`, `regulatory_failure`, `financing_failure`, `general_breach`, `other`.
- **`reverse_termination_fee`** — same structure, but with a narrower trigger universe (regulatory/financing/general-breach/other).
- **`go_shop`** — `{present, duration_days, reduced_fee_during_shop}`. A "no solicitation" section with no go-shop language implies `present=false`.
- **`source_sections`** + **`confidence`** — required on every call.

### 2. `extract_efforts_standard` — [tools_schema.py:95-169](tools_schema.py#L95-L169)

**Dual-classification design.** This schema emerged from MAUD validation: stated contractual language and economic substance often diverge, so the schema extracts both.

- **`stated_efforts_standard`** — the literal contractual language: `best_efforts`, `reasonable_best_efforts`, `commercially_reasonable_efforts`, `reasonable_efforts`, `other`.
- **`stated_standard_detail`** — direct quote of the standard (and any "other" language).
- **`functional_efforts_classification`** — the *economic substance* regardless of stated language:
  - `hell_or_high_water` — acquirer must take any and all actions (unlimited divestitures) to obtain regulatory approval.
  - `limited_divestiture_obligation` — acquirer must divest but subject to caps or materiality thresholds.
  - `no_divestiture_obligation` — no affirmative divestiture commitment.
- **`unlimited_divestiture_obligation`** — boolean flag for HOHW-in-substance.
- **`divestiture_limitations_detail`** — the cap/threshold language if present.
- **`litigation_obligation`** — whether the acquirer must litigate or contest regulatory challenges.

The Claude prompt for this tool explicitly tells the model that "reasonable best efforts" paired with unlimited divestiture obligations should be functionally classified as HOHW even though the stated language is weaker.

### 3. `extract_mac_definition` — [tools_schema.py:172-321](tools_schema.py#L172-L321)

Ten-category MAC/MAE carveout structure plus meta-flags for MAE scope.

- **Scope:** `mae_applies_to` (target-only vs. target+subs), `includes_prospects`, `forward_looking_standard`, `includes_ability_to_consummate`.
- **Carveouts** — for each of the following, `{present: bool, disproportionate_impact_qualifier: bool}`:
  - `general_economic_conditions`
  - `political_social_conditions`
  - `industry_changes`
  - `change_in_law`
  - `gaap_changes`
  - `war_terrorism_disasters`
  - `pandemic` (see below)
  - `announcement_of_deal`
  - `failure_to_meet_projections`
  - `stock_price_changes`
- **`total_carveout_count`** — integer count of distinct exclusions.

**Pandemic-carveout interpretation.** The schema's description instructs the model to treat "epidemics," "quarantine restrictions," and "public health emergencies" as pandemic carveouts even without the literal word *pandemic*. For 2020–2021 agreements, epidemic/quarantine language read in context obviously contemplates COVID-19. This legal-judgment call was made during schema validation, reflects how experienced M&A lawyers read these provisions, and is what drives Mrkt's 94% pandemic-carveout agreement with MAUD's expert labels.

**Disproportionate-impact ("DI") qualifier handling.** Real agreements often don't attach a DI qualifier to each carveout individually — they include a trailing provision that applies the qualifier to a range (e.g., "clauses (A) through (F) shall not apply to the extent such changes disproportionately affect…"). The schema description instructs the model to distribute the qualifier to every individual carveout it covers.

### 4. `extract_specific_performance` — [tools_schema.py:324-365](tools_schema.py#L324-L365)

Captures whether the parties can seek court-ordered enforcement of the agreement (vs. just monetary damages).

- **`specific_performance_available`** — `entitled_to`, `may_seek`, `mutual_entitled_to`, `limited_to_one_party`, `not_available`, `other`.
- **`available_to`** — `both_parties`, `target_only`, `acquirer_only`, `other`.
- **`conditions_or_limitations`** — free-text description of any conditions/caps.

---

## Metadata Extraction

[extract_metadata.py](extract_metadata.py) pulls minimal deal metadata from the first **1000 characters** of each agreement. This is a deliberate cost optimization — cover pages almost always contain party names, the signing date, and the agreement type, so processing the full document would be wasteful.

The `METADATA_TOOL` schema returns:

- `acquirer_name`, `target_name`, `merger_sub_name`
- `signing_date` (YYYY-MM-DD)
- `agreement_type` ∈ `{merger, tender_offer_and_merger, asset_purchase, stock_purchase, other}`

The MAUD filename mapping (`Filename (anon)` → `Filename`) is passed alongside the cover-page text as a disambiguation hint, which boosts accuracy on deals where the cover page shortens party names.

---

## Outcome Collection (Agentic Web Search)

[collect_outcomes.py](collect_outcomes.py) uses an agentic loop that combines Claude's `tool_use` with the Anthropic server-side `web_search_20250305` tool. For each deal, Claude:

1. Receives acquirer, target, and signing date.
2. Issues one or more `web_search` queries (server-side — the API handles the retrieval).
3. Calls `record_deal_outcome` with structured findings.

The loop runs up to 5 turns. If Claude returns text without calling `record_deal_outcome`, the code explicitly nudges it with a follow-up user message: *"Now call the record_deal_outcome tool with your findings."* This ensures every deal produces a structured record, even if confidence is `low`.

The `record_deal_outcome` schema captures:

- `deal_completed` (bool), `deal_terminated` (bool)
- `completion_date`, `days_to_close`
- `termination_reason` ∈ `{regulatory_block, competing_bid, target_mae, financing_failure, mutual_agreement, litigation, other}`
- `final_deal_value_dollars`, `price_per_share`
- `deal_was_amended` (bool)
- `acquirer_ticker`, `target_ticker`
- `confidence`

Every result is written to `data/deal_outcomes.json` immediately so the run is resumable from partial progress.

---

## Stock Return Pipeline

[collect_stock_returns.py](collect_stock_returns.py) computes cumulative abnormal returns (CAR) for the acquirer against the S&P 500 index (`^GSPC`).

Algorithm, per deal:

1. Read `acquirer_ticker` from `deal_outcomes.json` and `signing_date` from `deal_metadata.json`.
2. Pull daily closes from `signing_date - 5d` to `signing_date + window + 5d` for both the acquirer and `^GSPC`.
3. Find the trading day on-or-before the signing date (`pre_date`) and the trading day on-or-after `signing_date + window` (`post_date`).
4. Compute `stock_return = (close_post − close_pre) / close_pre × 100`.
5. Compute `sp_return` identically over the same dates.
6. Report `abnormal_return = stock_return − sp_return`.

Windows: **7, 30, 90, 365 days.** The 365-day window was added after Sprint 1 when the 30-day signal was already significant, to test whether the effect amplifies or reverts.

Output per deal: `{ticker, signing_date, stock_return_{W}d, sp500_return_{W}d, abnormal_return_{W}d}` for W ∈ {7, 30, 90, 365}. Results are checkpointed to `data/stock_returns.json` after each ticker.

**Why the market-model choice is conservative.** Mrkt subtracts the raw S&P 500 return rather than fitting a pre-event beta. This under-weights the abnormal component for high-beta acquirers (they would have moved more with the market anyway) but avoids introducing estimation noise from short pre-event windows.

---

## Integrated Dataset Schema

[analyze.py](analyze.py) merges four JSON files into one CSV panel at `data/mrkt_integrated_dataset.csv`. Schema:

| Column | Source | Type | Notes |
|---|---|---|---|
| `contract_id` | MAUD | str | e.g. `contract_42` |
| `acquirer`, `target` | metadata | str | cover-page extraction |
| `signing_date`, `year` | metadata | date, int | |
| `agreement_type` | metadata | enum | see metadata schema |
| `deal_value` | outcomes | float ($) | final reported value |
| `fee_amount` | extractions | float ($) | target termination fee |
| `fee_pct` | derived | float (%) | `fee_amount / deal_value × 100` |
| `has_reverse_fee` | extractions | bool | reverse fee present |
| `reverse_fee_amount` | extractions | float ($) | |
| `reverse_fee_ratio` | derived | float | `reverse / forward` |
| `go_shop` | extractions | bool | |
| `stated_efforts`, `functional_efforts` | extractions | enum | dual classification |
| `unlimited_divestiture` | extractions | bool | |
| `mac_carveout_count` | extractions | int | |
| `specific_performance` | extractions | enum | |
| `deal_completed`, `days_to_close`, `deal_amended` | outcomes | bool, int, bool | |
| `acquirer_ticker` | outcomes | str | |

Abnormal returns (`stock_return_{W}d`, `sp500_return_{W}d`, `abnormal_return_{W}d`) are kept in the separate `stock_returns.json` and joined on `contract_id` by the downstream analysis scripts.

---

## Analysis Modules

All analytics are stdlib-only (no `pandas`, `numpy`, or `scipy`). This is deliberate — the methods are transparent, the code is auditable, and the full Sprint 1 + Sprint 2 pipeline runs in under a minute.

### Sprint 1 — Descriptives & Bivariate Correlations — [analyze.py](analyze.py)

- Distributions of fee%, reverse-fee ratio, go-shop presence, efforts classifications, MAC-carveout counts, days-to-close, year distribution.
- Eight correlation / group-comparison analyses:
  1. Fee % vs. days-to-close — Pearson r
  2. Functional efforts class vs. days-to-close — group means
  3. MAC carveout count vs. days-to-close — Pearson r
  4. Reverse-fee presence vs. days-to-close
  5. Go-shop presence vs. days-to-close
  6. Fee % median split vs. days-to-close
  7. Reverse/forward fee ratio vs. days-to-close — Pearson r
  8. Functional efforts vs. deal-amended rate

### Sprint 2 — Robustness Battery — [robustness.py](robustness.py)

Tests whether the 30-day and 365-day fee-split spreads survive nonparametric challenges:

- **Permutation test** (10,000 reshuffles, seeded). One-tailed p-values for the null that high-fee and low-fee groups come from the same AR distribution.
- **Bootstrap CI** (10,000 resamples with replacement within each group). 95% confidence intervals on the observed spread.
- **Spearman rank correlation** on fee% vs. AR30 and fee% vs. AR365 (distribution-free alternative to Pearson).
- **Alternative cutpoints** — median, 25th pct, 75th pct, fixed thresholds (3.0%, 3.5%, 5.0%). Demonstrates the result is not an artifact of the median choice.
- **Winsorization** at 1%, 5%, 10% levels. Demonstrates the result is not driven by extreme AR tails.

### Sprint 2 — Influence Diagnostics — [influence.py](influence.py)

Leave-one-out on the 365-day fee split. Reports:

- The 15 most influential observations (sorted by `|spread_without_i − full_spread|`).
- Min/max spread across all leave-one-out subsets.
- Count of sign-flips — i.e., how many individual observations can flip the sign of the headline result. **Finding: zero.** No single deal drives the sign.

### Sprint 2 — Selection Bias — [selection_bias.py](selection_bias.py)

Compares deals **with** acquirer stock data (n=78) to deals **without** (n=74, mostly PE/private or delisted acquirers) across:

- Fee %, fee amount, deal value
- Reverse-fee presence, go-shop presence
- MAC carveout count, days-to-close
- Functional efforts distribution
- Agreement-type distribution

Purpose: surface the degree to which the AR-based findings generalize beyond strategic public acquirers.

### Sprint 2 — Multi-Window — [multiwindow.py](multiwindow.py)

Tests the "amplification over time" claim by computing the fee-split spread at 7/30/90/365 days and checking whether spreads are monotonically strengthening (more negative) as the window widens.

Outcome (confirmed in commit `d480b73`): monotonic amplification holds across all four windows.

### Sprint 2 — Multivariate Regression — [regression.py](regression.py)

Hand-rolled OLS with heteroskedasticity-robust (sandwich / HC1-style) standard errors. Six specifications:

| ID | DV | Predictors |
|---|---|---|
| M1 | AR365 | intercept, fee_pct |
| M2 | AR365 | intercept, fee_pct, log(deal_value) |
| M3 | AR365 | intercept, fee_pct, log(deal_value), year_2021, is_financial |
| M4 | AR365 (winsorized 5%) | intercept, fee_pct |
| M5 | AR365 (winsorized 5%) | intercept, fee_pct, log(deal_value) |
| M6 | AR365 (winsorized 5%) | intercept, fee_pct, log(deal_value), year_2021, is_financial |

`is_financial` is a heuristic boolean: `True` if the acquirer name contains any of `{"parent", "holdings", "merger sub", "acquisition", "bidco", "buyer", "investor", "partners"}` (rough proxy for PE/financial sponsor buyers since MAUD doesn't ship a buyer-type label).

Winsorization cap: raw AR365 distribution clipped at the 5th and 95th percentiles.

The linear-algebra core is a Gauss-Jordan inversion (no scipy dependency):

```python
# regression.py:41-66
def ols(y, X):
    n, k = len(y), len(X[0])
    XtX = [[sum(X[i][a]*X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    Xty = [sum(X[i][j]*y[i] for i in range(n)) for j in range(k)]
    # Gauss-Jordan elimination with partial pivoting
    # ... compute (X'X)^-1
    # Sandwich estimator: V = (X'X)^-1 · Σ(eᵢ² · xᵢ xᵢ') · (n/(n-k)) · (X'X)^-1
    ...
    return b, se, t, r2
```

### Validation — [validate_maud.py](validate_maud.py)

Four-field agreement check vs. MAUD's 47K expert labels:

| Field | Our column | MAUD column |
|---|---|---|
| No-shop / Go-shop | `go_shop.present` | `No-Shop` (contains "go-shop"?) |
| Stated efforts | `stated_efforts_standard` | `General Antitrust Efforts Standard-Answer` |
| Specific performance | `specific_performance_available` | `Specific Performance-Answer` |
| Pandemic carveout | `carveouts.pandemic.present` | `Pandemic or other public health event-Answer (Y/N)` |

Reports per-field agreement percentages plus the first 10 mismatches for manual review. Overall agreement at Sprint 2 close: **91–94%** weighted by sample size.

---

## Sprint 1 Results

*(captured in [commit 096f7f2](https://github.com/agshipley/mrkt/commit/096f7f2), "Analysis pipeline: outcomes, stock returns, correlations. 78 deals with AR data, signal on fee split")*

- **Extraction.** 606/608 structured extractions succeeded (99.7%). Two failures were unrecoverable content-moderation edge cases on agreements with unusual formatting.
- **Coverage.** 152 deals with extractions; 149 with metadata; 141 with outcome data; **78 with usable acquirer stock data** (the others had private/PE acquirers or delisted tickers).
- **Descriptive stats.**
  - Median target termination fee: **3.03%** of deal value (mean 3.12%, min 0.5%, max 7.2%).
  - Reverse-fee presence: ~60% of deals.
  - Go-shop present: ~12% of deals.
  - Stated efforts distribution: `reasonable_best_efforts` dominant (~70%), `best_efforts` ~15%, `commercially_reasonable_efforts` ~10%.
  - MAC-carveout count: median 9 carveouts, mean 8.6.
- **Signal.** Above-median fee deals show AR(30d) = −2.94%; below-median = +5.00%. Spread −7.95 pp.
- **Correlation.** 30-day AR and 365-day AR correlate at **r ≈ 0.42** — short-term market reactions predict long-term outcomes.

---

## Sprint 2 Robustness Battery

*(captured in [commit 1d89563](https://github.com/agshipley/mrkt/commit/1d89563) and [commit d480b73](https://github.com/agshipley/mrkt/commit/d480b73))*

### MAUD validation (weighted)

- No-shop / Go-shop: ~94% agreement
- Stated efforts: ~91% agreement
- Specific performance: ~93% agreement
- Pandemic carveout: ~94% agreement (driven in part by the deliberate "epidemic/quarantine ⇒ pandemic carveout" interpretation)

### Multi-window monotonicity

Spread becomes more negative (i.e., the high-fee vs. low-fee gap widens) at every step: 7d → 30d → 90d → 365d. The "amplification over time" claim is supported.

### Influence diagnostics

Leave-one-out on the 365-day fee split: **0 of 78 observations flip the sign** of the headline spread. Spread range across all leave-one-out subsets remains negative. Finding is not fragile to any single deal.

### Nonparametric robustness

- Permutation p-values (10,000 reshuffles): both 30d and 365d spreads significant at conventional thresholds under the one-tailed negative-spread null.
- Bootstrap 95% CIs on the 365d spread exclude zero.
- Spearman rank correlations confirm the relationship is not a linearity / extreme-value artifact.
- Alternative cutpoints (25th pct, 75th pct, 3.0%, 3.5%, 5.0%) all produce negative spreads of comparable magnitude where the subgroups are large enough to report.
- 1/5/10% winsorization of AR365 preserves the spread.

### Selection bias (included vs. excluded)

Included deals (n=78, strategic public acquirers) have higher mean deal value and higher reverse-fee prevalence than excluded deals (n=74, dominated by private / PE acquirers). The findings explicitly apply to the public-strategic-acquirer population; generalization to PE-sponsored deals requires a different data source (no public acquirer ticker).

---

## Multivariate Regression

*(captured in [commit 53de9c2](https://github.com/agshipley/mrkt/commit/53de9c2), "Multivariate regression: fee effect survives controls (t=-2.22, p<0.05). Year effect dominant. R2=0.24")*

### Specification progression

| Spec | fee_pct coefficient | t | Significance | Notes |
|---|---|---|---|---|
| M1 (fee only) | strongly negative | large | *** | raw bivariate |
| M2 (+log deal value) | negative | sig | ** | deal-size control |
| M3 (+year, +is_financial) | **β ≈ −2.27** | **−2.22** | * at p<0.05 | year_2021 dominant effect |
| M4 (winsorized, fee only) | negative | sig | *** | robustness |
| M5 (winsorized, +size) | negative | sig | ** | robustness |
| M6 (winsorized, full) | negative | sig | * | **R² ≈ 0.24** |

### Interpretation

- **Fee effect survives controls.** A one-percentage-point increase in the target termination fee is associated with roughly a −2.3 pp change in the acquirer's 365-day abnormal return, after controlling for deal size, signing year, agreement type, and buyer-type proxy. Significance holds under HC1 robust standard errors and winsorization.
- **Year effect is dominant.** The `year_2021` coefficient has the largest t-statistic in the full model. This is a real macro/vintage effect — 2021 deals had systematically different AR365 than 2020 deals. Any future corpus expansion needs to preserve the year control.
- **Deal size matters but is smaller than the fee and year effects.** `log(deal_value)` has the expected negative sign (bigger deals, lower AR365 on average) but is less significant than fee or year.
- **`is_financial`** — the acquirer-name heuristic is weak. A proper buyer-type taxonomy (PE vs. strategic vs. SPAC) from a commercial database would be more defensible than the current name-keyword proxy.

---

## Cost Analysis

| Stage | API calls | Approximate cost |
|---|---|---|
| Stage 1 extraction (608 calls, batched, Sonnet 4.6) | 608 | **~$90** (with 50% batch discount) |
| Metadata extraction (152 cover pages, ~1K chars each) | 152 | **~$2** |
| Outcome collection (up to 5-turn agentic loop with web search) | ~450 | **~$30** |
| Stock returns (Yahoo Finance) | — | $0 |
| **Total** | **~1,200** | **~$125** |

Future optimizations: prompt caching on the 4 tool schemas (large and repeated across 608 calls) and on the system prompt would meaningfully reduce the Stage 1 bill. Token counts should be calculated precisely before future batch runs to size the job without surprises.

---

## Known Limitations

1. **Temporal concentration.** All 152 agreements are March 2020 – late 2021 (COVID era). The year effect in the regression suggests vintage matters; generalizability requires pre-2020 and post-2021 expansion via EdgarTools.
2. **Missing stock data.** 46 deals have private (typically PE) acquirers with no public ticker. 28 more have delisted or changed tickers. AR-based findings apply to **strategic public acquirers only** (n=78).
3. **Announcement-date choice.** Current pipeline uses the *signing* date from the agreement cover page. The market-efficient choice is the **8-K announcement date**, which can precede or lag signing by hours to days. Listed in Next Steps.
4. **No target-side returns.** Target abnormal returns (and deal premia) would materially sharpen the analysis. Not yet collected.
5. **Buyer-type proxy is weak.** `is_financial` is a keyword heuristic on acquirer name. A commercial deal database (Capital IQ, Refinitiv) would provide proper strategic-vs-financial classification.
6. **No interaction terms.** Current regression assumes additive effects. Combinations — e.g., high fee *and* HOHW, or go-shop *and* large reverse fee — may behave differently than individual terms.

---

## Academic Foundation

The term-prioritization, schema design, and analytical approach draw directly from peer-reviewed work:

- **Coates, Palia & Wu (2019)** — M&A clause indices correlate with announcement returns and deal completion. Foundational for "clauses-as-signal" framing.
- **Denis & Macias (2013)** — MAC exclusion structure predicts termination, renegotiation, and pricing. Motivates the 10-carveout MAC schema.
- **Officer (2003)** — Termination fees associated with higher completion rates and premiums. Motivates the fee-as-primary-signal hypothesis.
- **Jeon & Ligon (2011)** — Fee size as a continuous variable; large fees deter competing bids. Supports treating fee% rather than fee presence as the regressor.
- **Butler & Sauska (2014)** — Fees above 5% of deal value associated with lower returns. Predicts the direction Mrkt observes.
- **Badawi, de Fontenay & Nyarko (2023)** — NLP methodology for M&A agreement analysis. Methodological precedent.

---

## Next Steps

- **Corpus expansion via EdgarTools** — pre-2020 and post-2021 agreements from EDGAR Ex-2.1 filings to break the vintage confound.
- **Announcement-date correction** — 8-K filing date (or first-trade-day post-announcement) in place of signing date.
- **Target-side abnormal returns** where pre-acquisition ticker survives.
- **Interaction terms** in the regression — fee × HOHW, fee × reverse-fee ratio, fee × go-shop.
- **Commercial buyer-type data** to replace the keyword-based `is_financial` proxy.
- **Prompt-caching** on tool schemas and system prompt to reduce Stage 1 cost on re-runs.
- **Heterogeneity** — test whether the fee-return relationship differs by agreement type (merger vs. tender-offer structure) or by industry.

---

## License

Private research. Not licensed for redistribution.

## Author

Andrew Shipley — [@agshipley](https://github.com/agshipley)
