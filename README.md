# NYC Digital Services Spending Analysis

**Analysis of NYC government technology spending to identify opportunities for building in-house digital service teams (e.g. 18F model)**

---

## 📊 Key Findings

NYC spends **$1-2 billion annually** on digital services vendors, depending on how "digital" is defined:

- **Primary Digital Services Vendors:** ~$500M/year (pure consulting, software, development)
- **Mixed Vendors (IT resellers + services):** ~$1B+/year (CDW, SHI, Dell bundling hardware + services)
- **IT Consulting & Custom Development:** ~$500M+/year (Accenture, Deloitte, Booz Allen, etc.)

**Opportunity:** Redirecting a fraction of this spending could fund hundreds of digital service staff throughout NYC government.

See **"Getting Current Totals"** below for how to calculate exact figures from the data.

---

## 📁 Project Structure

### **Main Outputs** (`data/outputs/`)
The final analysis files - these are what you need:

- **`digital_services_vendors.csv`** - Classified digital vendors with 10-year spending data (FY2016-2025)
- **`digital_budget_codes.csv`** - Budget codes funding digital services (Digital + Mixed classifications)
- **`digital_expense_categories.csv`** - Expense categories with digital vendor activity

### **Transaction Data** (`data/raw/`)
- `fy2015_full.csv` through `fy2025_full.csv` - Complete transaction data (11 years, ~29M transactions)
- `fy20XX_chunks/` - Raw download chunks for each year

### **Working Notes** (`notes/`)
- Research notes and methodology documentation

### **Archive** (`data/archive/`)
- `intermediate/` - Legacy vendor lists and classification intermediates
- `legacy_classifications/` - Old classification files from earlier analysis phases
- `samples/` - Sample extracts and test data

### **Scripts** (`scripts/`)
- Download and data processing scripts (run from project root directory)

---

## 🎯 Current Status

### ✅ Complete: Full 10-Year Analysis

**Data Coverage:**
- **Years:** FY2016-2025 (10 years)
- **Transactions:** ~29 million
- **Vendors Classified:** 150+ digital services vendors
- **Budget Codes Analyzed:** Top 100 codes by digital vendor usage

**Major Discoveries:**
1. **The "IT Budget Code" Misnaming Problem:** Many budget codes with IT-sounding names (e.g., "Management Information Systems," "Information Technology") primarily fund non-IT personnel (teachers, social workers, etc.). Budget code names are unreliable indicators of actual technology spending.

2. **Vendor Classification System:**
   - **Digital:** Pure digital services (consulting, software, development)
   - **Mixed:** IT resellers bundling services (CDW, SHI, Dell)

3. **Vendor Fragmentation:** NYC works with 150+ digital services vendors, ranging from major consulting firms (Accenture, Deloitte) to small MWBEs, suggesting a fragmented vendor ecosystem.

---

## 🔍 Methodology

### Data Source
NYC Checkbook API (FY2016-2025) - complete transaction-level spending data.

### Approach
1. Identified digital services vendors through analysis of top vendors by transaction volume and expense category
2. Analyzed top 100 budget codes used by these vendors
3. Examined actual vendor payments to classify budget codes (names are misleading!)
4. Calculated 10-year spending trends for vendors and codes
5. Classified vendors and budget codes as:
   - **Digital:** Pure digital services (consulting, software, development)
   - **Mixed:** Combination of digital services + hardware/infrastructure/personnel

### Key Challenge
The Checkbook API provides NO NAICS codes - only 7 broad industry categories. We pulled ALL spending data and manually classified vendors to avoid missing tech spending hidden in miscategorized transactions.

### Getting Current Totals

**Vendor spending by classification:**
```python
import pandas as pd

vendors = pd.read_csv('data/outputs/digital_services_vendors.csv')

# Count and spending by classification
for cls in ['Digital', 'Mixed']:
    subset = vendors[vendors['is_digital'] == cls]
    total = subset['fy2025_spending'].sum()
    print(f"{cls}: {len(subset)} vendors, ${total/1e6:.0f}M")
```

**Top 20 vendors:**
```python
vendors.sort_values('fy2025_spending', ascending=False)[
    ['vendor', 'is_digital', 'fy2025_spending']
].head(20)
```

**Expense categories with % going to digital vendors:**
```python
exp = pd.read_csv('data/outputs/digital_expense_categories.csv')
exp[['expense_category', 'is_digital', 'fy2025_spending', 'pct_digital_vendors_fy25']].sort_values(
    'pct_digital_vendors_fy25', ascending=False
)
```

### Limitations
- Analysis focuses on **operational budgets**; major digital projects (MyCity, DOB NOW, Next-Gen 911) likely funded through capital budgets not included here
- Cannot distinguish consulting types (staff augmentation vs. deliverables) from transaction data alone
- Some digital work occurs in general operations codes not captured in top 100 assessment

---

## 📚 Background

### Project Goal
Estimate NYC's annual technology spending that could fund in-house digital service teams, inspired by:
- **18F** - Federal government digital services team
- **NJ Office of Innovation** - State-level digital services team
- **Jennifer Pahlka's work** on government technology reform ("Recoding America")

### Why This Matters
The current vendor-dependent model has predictable failures:
- Knowledge walks out when contracts end
- Premium hourly rates vs. full-time staff costs
- Vendor lock-in and misaligned incentives (bill by the hour)
- Slow procurement cycles

Internal teams provide:
- Retained institutional knowledge
- Direct accountability to citizens
- Faster iteration and deployment
- Modern technology practices
- Long-term cost savings

---

## 🔗 Related Resources

**NYC Data Sources:**
- [NYC Checkbook](https://www.checkbooknyc.com/) - Transaction-level spending data
- [NYC Open Data](https://opendata.cityofnewyork.us/) - Budget and agency datasets

**Similar Initiatives:**
- [18F](https://18f.gsa.gov/) - Federal digital services team
- [NJ Office of Innovation](https://innovation.nj.gov/) - State digital services team
- [SF Digital Services](https://digitalservices.sfgov.org/)

---

*Last Updated: December 2025*
