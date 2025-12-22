# NYC Tech Spending Data Sources - Research Findings

## Summary
Research on available data sources for analyzing NYC government spending on tech/IT consultants and vendors.

## Key Data Sources Identified

### 1. **data-contracts** (NYC Open Data)
- **Dataset ID**: i858-z32e
- **URL**: https://data.cityofnewyork.us/City-Government/data-contracts/i858-z32e
- **Provider**: Department of Citywide Administrative Services (DCAS)
- **Update Frequency**: Daily (automated)
- **Data Dictionary**: City_Record_Online_-_Data_Dictionary_-_October_2017.xlsx (attached to dataset)

**Key Fields** (37 total):
- AgencyName
- VendorName
- VendorAddress
- ContractAmount (solicitation amount, not final spending)
- PIN (Procurement Identification Number)
- SelectionMethodDescription
- TypeOfNoticeDescription
- StartDate/EndDate/DueDate
- Contact information

**Limitations**:
- Contains City Record notices (solicitations/awards) not final spending data
- **No NAICS codes included**
- ContractAmount is bid solicitation amount, not actual payments

### 2. **Checkbook NYC**
- **URL**: https://www.checkbooknyc.com/
- **Provider**: NYC Comptroller's Office
- **Description**: Online transparency tool for NYC's day-to-day spending

**API Endpoints Available**:
- Contracts API: https://www.checkbooknyc.com/contract-api
- Spending/Budget API
- Revenue API
- Payroll API

**Access Methods**:
- Socrata Open Data API (SODA)
- OData (for Excel/Tableau)
- NYC Open Data portal integration

**Access Challenges**:
- API documentation pages appear to be JavaScript-rendered and couldn't be accessed via WebFetch
- Need direct access to explore API structure and parameters

### 3. **M/WBE Certified Business List** (NYC Open Data)
- **Dataset ID**: ci93-uc8s
- **URL**: https://data.cityofnewyork.us/Business/M-WBE-LBE-and-EBE-Certified-Business-List/ci93-uc8s
- **CSV Download**: https://data.cityofnewyork.us/api/views/ci93-uc8s/rows.csv?accessType=DOWNLOAD

**Key Fields**:
- Vendor_Formal_Name, Vendor_DBA
- ID6_digit_NAICS_code
- NAICS_Sector, NAICS_Subsector, NAICS_Title
- Business_Description
- Contact information

**Strengths**:
- **Has NAICS codes!**
- Vendor details and classifications

**Limitations**:
- Only includes M/WBE/LBE/EBE certified businesses (subset of all vendors)
- No spending/contract amounts

### 4. **PASSPort Public**
- **URL**: https://a0333-passportpublic.nyc.gov/index.html
- **Download Guide**: https://www.nyc.gov/site/mocs/passport/articles/download-data.page
- **Description**: NYC's end-to-end digital procurement platform (launched 2022)

**Available Data**:
- Contracts
- Vendors
- Solicitations
- Invoices
- Purchase Orders

**Export Format**: Excel (customizable columns)

**Access**: Public portal (no login required for browsing)

## Recommended Data Strategy

### Option A: Checkbook NYC API (Primary)
- Most comprehensive spending data
- Includes actual payments/transactions
- Covers all agencies
- **BLOCKER**: Need to access API documentation or use UI export features

### Option B: Combine Multiple Datasets
1. **data-contracts** (i858-z32e) - Get contract awards with vendor names and agencies
2. **M/WBE list** (ci93-uc8s) - Match vendor names to NAICS codes
3. Filter for tech NAICS codes
4. Calculate totals by agency

**Challenges**:
- Vendor name matching may be imperfect (DBA vs formal names)
- M/WBE list is only a subset of all vendors
- Contract amounts in data-contracts are solicitation amounts, not final spending

### Option C: PASSPort Public Export
- Manual export of contracts data
- May include vendor and spending information
- **TODO**: Explore PASSPort Public UI directly

## Next Steps

1. **Identify tech/IT NAICS codes** to use for filtering
2. **Explore PASSPort Public** portal directly (may need user assistance)
3. **Attempt Checkbook NYC data export** via UI or API
4. **Download M/WBE dataset** as a reference for NAICS mapping
5. Consider reaching out to NYC Comptroller or DCAS for bulk data access

## Technical Resources

- **Socrata/SODA Python Library**: sodapy
- **Tutorial**: https://github.com/mebauer/sodapy-tutorial-nyc-opendata
- **Blog**: https://lvngd.com/blog/accessing-nyc-open-data-with-python-and-the-socrata-open-data-api/

## Access Issues Encountered

- Checkbook NYC API documentation pages load blank (JavaScript-rendered)
- NYC Open Data portal dataset pages require direct browser access for full functionality
- May need user assistance to access specific portal features or download files
