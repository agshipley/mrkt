# Mrkt — Moneyball for Transactional Law

Mrkt is a research and analytics platform that tests whether negotiated terms in M&A merger agreements predict measurable post-transaction outcomes. It uses LLM-based structured extraction (Claude via the Anthropic API) to pull deal terms from SEC-filed agreements, links them to outcome data, and runs correlational analysis.

The core thesis — that deal terms carry measurable economic signal — is validated by existing academic research (Coates/Palia/Wu 2019, Denis/Macias 2013). Mrkt automates and scales what those papers did by hand.

## Sprint 1 Results

**152** merger agreements extracted (MAUD corpus, 2020–2021)  
**606/608** successful structured extractions (99.7% success rate)  
**4** term categories: termination fees, efforts standard, MAC definitions, specific performance  
**78** deals with acquirer stock return data  

### Headline Finding

Acquirers who agreed to above-median termination fees experienced significantly worse stock performance:

| Window | High Fee (≥3.03%) | Low Fee (<3.03%) | Spread |
|--------|-------------------|------------------|--------|
| 30 days | -2.94% | +5.00% | 7.95pp |
| 365 days | -2.19% | +24.81% | **27.00pp** |

The effect amplifies over time. Short-term market reaction (30-day) correlates with long-term outcome (365-day) at r = 0.42.

## Architecture
```
MAUD Corpus (152 .txt files)
    │
    ▼
Extraction Pipeline (Claude Sonnet 4.6, Message Batches API)
    │
    ├── Termination Fee Tool Schema
    ├── Efforts Standard Tool Schema (dual: stated + functional)
    ├── MAC Definition Tool Schema
    └── Specific Performance Tool Schema
    │
    ▼
Structured JSON Results (data/full_extraction_results.json)
    │
    ▼
Outcome Data Collection
    ├── Deal completion/termination (Claude + web search)
    ├── Deal metadata (Claude, cover page extraction)
    └── Stock returns (Yahoo Finance, 7/30/90/365-day windows)
    │
    ▼
Integrated Dataset (data/mrkt_integrated_dataset.csv)
    │
    ▼
Analysis (Pearson correlations, median-split comparisons)
```

## Project Structure
```
mrkt/
├── .env                          # API keys (not committed)
├── .gitignore
├── .mcp.json                     # EdgarTools MCP server config
├── CLAUDE.md                     # Project conventions for Claude Code
├── extract.py                    # Single-agreement extraction (4 tools)
├── extract_metadata.py           # Deal metadata from cover pages
├── tools_schema.py               # JSON tool schemas for all 4 extraction targets
├── batch_extract.py              # Message Batches API runner (full corpus)
├── run_batch.py                  # Sequential batch runner (testing)
├── collect_outcomes.py           # Deal outcome collection via web search
├── collect_stock_returns.py      # Acquirer stock returns from Yahoo Finance
├── analyze.py                    # Descriptive stats and correlational analysis
├── check_labels.py               # MAUD label inspection utility
└── data/                         # All data files (gitignored)
    ├── maud/
    │   ├── contracts/             # 152 merger agreement text files
    │   └── raw/                   # MAUD expert labels (main.csv)
    ├── full_extraction_results.json
    ├── deal_metadata.json
    ├── deal_outcomes.json
    ├── stock_returns.json
    └── mrkt_integrated_dataset.csv
```

## Extraction Design

### Tool Schemas

Each extraction target uses Claude's `tool_use` mechanism with forced tool selection (`tool_choice: {type: "tool", name: "..."}`). JSON schemas enforce structured output with:

- **Nullable fields** — every field that might be absent in an agreement accepts `null`, preventing fabrication
- **Enum + other pattern** — categorical fields use predefined enums plus an "other" option with a detail string
- **Confidence annotations** — each extraction includes a confidence rating (high/medium/low)
- **Source section references** — extracted data includes the article/section where the provision was found

### Dual Efforts Standard

The efforts standard schema captures both the **stated standard** (the literal contractual language, e.g., "reasonable best efforts") and the **functional classification** (the economic substance, e.g., hell-or-high-water based on unlimited divestiture obligations). This design emerged from validation against MAUD expert labels, where the stated standard and functional classification diverged.

### Pandemic Carveout Interpretation

The MAC definition schema treats "epidemics," "quarantine restrictions," and "public health emergencies" as pandemic carveouts even without the literal word "pandemic." This legal judgment — that epidemic/quarantine language in 2020–2021 agreements clearly contemplates COVID — was made during schema validation and reflects how experienced M&A lawyers read these provisions.

## Data Sources

| Source | Purpose | Cost |
|--------|---------|------|
| [MAUD](https://github.com/TheAtticusProject/maud) | 152 merger agreements + 47K expert labels | Free (CC BY 4.0) |
| Anthropic API (Sonnet 4.6) | Structured extraction, outcome collection | ~$125 total |
| Yahoo Finance | Acquirer stock returns | Free |
| [EdgarTools](https://github.com/dgunning/edgartools) | EDGAR access (configured, used for expansion) | Free (MIT) |

## Academic Foundation

The term prioritization and analytical approach are grounded in peer-reviewed research:

- **Coates, Palia & Wu (2019)** — M&A clause indices correlate with announcement returns and deal completion
- **Denis & Macias (2013)** — MAC exclusion structure predicts termination, renegotiation, and pricing
- **Officer (2003)** — Termination fees associated with higher completion rates and premiums
- **Jeon & Ligon (2011)** — Fee size as continuous variable; large fees deter competing bids
- **Butler & Sauska (2014)** — Fees above 5% of deal value associated with lower returns
- **Badawi, de Fontenay & Nyarko (2023)** — NLP methodology for M&A agreement analysis

## Known Limitations

1. **Temporal concentration** — All 152 agreements are from March 2020 to late 2021 (COVID era). Corpus expansion via EdgarTools is needed for generalizability.
2. **Missing stock data** — 46 deals have private acquirers (PE firms) with no stock data. 28 more have delisted/changed tickers. Analysis applies to strategic acquirers only.
3. **No multivariate controls** — Current findings are bivariate correlations. Deal size, sector, and buyer type may confound.
4. **Extraction cost** — Full corpus extraction cost ~$90 via Message Batches API. Token counts should be calculated precisely before future batch runs.

## Setup
```bash
git clone https://github.com/agshipley/mrkt.git
cd mrkt
python3 -m venv .venv
source .venv/bin/activate
pip install anthropic python-dotenv openpyxl edgartools yfinance
```

Create `.env`:
```
ANTHROPIC_API_KEY=your-key-here
EDGAR_IDENTITY="Your Name your.email@example.com"
```

Download the MAUD dataset from [TheAtticusProject/maud](https://github.com/TheAtticusProject/maud) and place in `data/maud/`.

## Usage
```bash
# Extract from a single agreement
python extract.py

# Run batch extraction across all agreements (uses Message Batches API)
python batch_extract.py

# Check batch status
python batch_extract.py --check <batch_id>

# Collect deal outcomes
python collect_outcomes.py

# Collect stock returns (free, Yahoo Finance)
python collect_stock_returns.py

# Run analysis
python analyze.py
```

## Next Steps

- **Corpus expansion** — Pull pre-2020 and post-2021 agreements from EDGAR via EdgarTools
- **Multivariate regression** — Add controls for deal size, sector, year, buyer type
- **Announcement date correction** — Use 8-K filing dates instead of signing dates
- **Target returns** — Add target abnormal returns where data is available
- **Interaction effects** — Test whether term combinations predict differently than individual terms

## License

This project is private research. Not licensed for redistribution.

## Author

Andrew Shipley — [agshipley](https://github.com/agshipley)
