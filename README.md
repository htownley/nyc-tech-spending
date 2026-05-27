# NYC Technology Spending Data

A dataset and visualizations of NYC government technology spending, FY2016–2025, derived from [NYC Checkbook](https://www.checkbooknyc.com/) public transaction data.

## Files

- **`data/outputs/`** — final CSV outputs (vendor classifications, budget codes, expense categories) and a project-spending chart
- **`scripts/`** — Python scripts to download fiscal-year transaction data from Checkbook NYC, merge chunks, and produce the outputs
- **`graph.html`** — vendor / agency network visualization
- **`visualizations.html`** — chart deck rendering the headline numbers from the dataset
- **`requirements.txt`** — Python deps

## Run

```bash
pip install -r requirements.txt
bash scripts/download_all_years.sh    # pulls FY2015–FY2025 from Checkbook
python3 scripts/merge_fiscal_year.py 2025
python3 scripts/analyze_full_dataset.py
```

Outputs land in `data/outputs/`. Open `graph.html` or `visualizations.html` directly in a browser.

## Data scope

- **Years:** FY2016–FY2025 (~29M transactions)
- **Source:** Checkbook NYC transaction-level spending data, publicly available
- **Derived classifications:** vendors classified by sector based on description, agency, and spending patterns

## Methodology notes

- Vendor classification is a research output, based on public spending data and vendor descriptions. Categories: `Digital` (primarily software/consulting), `Mixed` (digital services bundled with hardware/infrastructure), and unclassified.
- Budget code names in NYC's accounting are not always descriptive of actual spending category (an "Information Technology" code may fund non-IT personnel and vice-versa); analysis cross-references vendor classifications against budget code usage.
- Spending figures are check-amount totals from Checkbook transaction data.
