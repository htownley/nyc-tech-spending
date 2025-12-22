# NYC Digital Services Spending Data

Analysis of NYC government technology spending (FY2016-2025) to identify digital services expenditures.

**Source:** [NYC Checkbook](https://www.checkbooknyc.com/) transaction-level data

---

## Files

### `digital_services_vendors.csv`
151 vendors classified as providing digital services to NYC agencies.

| Column | Description |
|--------|-------------|
| vendor | Vendor name |
| is_digital | `Digital` (pure software/consulting) or `Mixed` (IT reseller bundling hardware + services) |
| agencies | NYC agencies this vendor serves (semicolon-separated) |
| description | Description of vendor's digital services |
| transaction_count | Number of transactions in dataset |
| fy20XX_spending | Total spending by fiscal year |
| budget_codes_fy25 | Top budget codes with % breakdown |
| expense_categories_fy25 | Top expense categories with % breakdown |
| pct_confirmed_digital_fy25 | % of spending through high-confidence digital expense categories |

### `digital_budget_codes.csv`
51 budget codes that fund digital services work.

| Column | Description |
|--------|-------------|
| budget_code | NYC budget code identifier |
| budget_name | Budget code name |
| is_digital | `Digital` or `Mixed` classification |
| description | What this budget code funds and why it's classified as digital |
| fy20XX_spending | Total spending by fiscal year |
| top_expense_categories_fy25 | Top expense categories with % breakdown |
| top_vendors_fy25 | Top vendors with % breakdown |
| pct_confirmed_digital_fy25 | % of spending through high-confidence digital expense categories |

### `digital_expense_categories.csv`
17 expense categories with significant digital services activity.

| Column | Description |
|--------|-------------|
| expense_category | NYC expense category name |
| is_digital | `Digital` or `Mixed` classification |
| description | What this category funds |
| fy20XX_spending | Total spending by fiscal year (all vendors, not just digital) |
| pct_digital_vendors_fy25 | % of category spending going to classified digital vendors |
| top_vendors_fy25 | Top vendors with % breakdown |
| top_budget_codes_fy25 | Top budget codes with % breakdown |

---

## Key Totals (FY2025)

| Metric | Amount |
|--------|--------|
| All classified vendors | $2.2B |
| Digital vendors only | $566M |
| Mixed vendors only | $1.6B |
| **Confirmed digital spending** | **$397M** |

**Confirmed digital spending** = vendor spending weighted by `pct_confirmed_digital_fy25`, representing spending through the three highest-confidence expense categories.

---

## Classification System

### Vendors
- **Digital**: Pure digital services (consulting, custom software, SaaS)
- **Mixed**: IT resellers bundling hardware + software + services (CDW, SHI, Dell)

### Expense Categories (by % to digital vendors)
- **Digital** (93%+): PROF SERV COMPUTER SERVICES, SBITA categories
- **Mixed** (1-88%): Categories with significant non-digital spending

### Budget Codes
- **Digital**: Codes funding specific digital projects or IT operations
- **Mixed**: Codes with substantial personnel or non-IT spending

---

## Methodology Notes

1. **Budget code names are misleading** - Many codes named "Information Technology" or "Management Information Systems" primarily fund personnel, not technology. We classified based on actual vendor payments, not names.

2. **SBITA = Subscription-Based IT Arrangements** - Cloud services and SaaS subscriptions. Highest confidence digital spending.

3. **"N/A (PRIVACY/SECURITY)"** in vendor lists indicates redacted vendor names in source data.

4. **Fiscal years** run July 1 - June 30 (e.g., FY2025 = July 2024 - June 2025).

*Data current as of December 2024*
