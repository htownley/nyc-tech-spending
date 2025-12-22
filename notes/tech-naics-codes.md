# Digital Technology/Software NAICS Codes for NYC Spending Analysis

## Summary
This document contains the NAICS codes used to identify **digital technology and software** vendors/consultants in NYC procurement data. Focus is on software, IT consulting, and digital services (NOT telecommunications or hardware manufacturing).

## Primary IT Services Codes (Top Priority - Highest Spending)

These codes represent the core IT consulting, software development, and services sector:

| NAICS Code | Description | FY2024 Federal Spending | Notes |
|------------|-------------|------------------------|-------|
| **511210** | Software Publishers | $7.26B | Top IT spending category in 2024 |
| **541519** | Other Computer Related Services | $7.11B | IT project management, cybersecurity consulting, data recovery, cloud hosting |
| **541511** | Custom Computer Programming Services | $6.40B | Software development, mobile apps, cloud solutions, system integration |
| **541512** | Computer Systems Design Services | $3.17B | High-dollar category, systems integration |
| **541513** | Computer Facilities Management Services | N/A | On-site management of computer systems and data processing facilities |

## Data Processing & Hosting

| NAICS Code | Description | Notes |
|------------|-------------|-------|
| **518210** | Data Processing, Hosting, and Related Services | Computing infrastructure, web hosting, streaming services |

## Telecommunications

| NAICS Code | Description |
|------------|-------------|
| **517311** | Wired Telecommunications Carriers |
| **517312** | Wireless Telecommunications Carriers (except Satellite) |
| **517410** | Satellite Telecommunications |
| **517911** | Telecommunications Resellers |
| **517919** | All Other Telecommunications |

## Information Services & Internet

| NAICS Code | Description |
|------------|-------------|
| **519130** | Internet Publishing and Broadcasting and Web Search Portals |
| **519190** | All Other Information Services |

## Computer Hardware Manufacturing

| NAICS Code | Description | FY2024 Federal Spending |
|------------|-------------|------------------------|
| **334111** | Electronic Computer Manufacturing | $981M |
| **334112** | Computer Storage Device Manufacturing | N/A |
| **334118** | Computer Terminal and Other Computer Peripheral Equipment Manufacturing | N/A |

## Recommended Filtering Strategy

### **PRIMARY FOCUS: Digital Technology & Software Spending**
**Use ONLY these codes for this analysis:**
- **511210** - Software Publishers
- **541511** - Custom Computer Programming Services
- **541512** - Computer Systems Design Services
- **541513** - Computer Facilities Management Services
- **541519** - Other Computer Related Services
- **518210** - Data Processing, Hosting, and Related Services

### **OUT OF SCOPE (Do Not Include):**
- ~~517xxx - Telecommunications~~ (not digital software spending)
- ~~334xxx - Hardware Manufacturing~~ (not digital software spending)
- ~~519xxx - Internet/Information Services~~ (unless specifically needed)

## Search Patterns for NAICS Code Fields

When filtering datasets for **digital technology/software spending**:

**6-digit codes** (most specific - USE THESE):
```
511210, 541511, 541512, 541513, 541519, 518210
```

**5-digit prefixes** (broader - if 6-digit unavailable):
```
51121, 54151, 51821
```

**4-digit subsectors** (very broad - may include non-digital):
```
5112, 5415, 5182
```

**3-digit groups** (too broad - NOT RECOMMENDED):
```
511, 541, 518
```
(Note: 541 includes all professional services, not just IT)

## Notes on Application

1. **6-digit precision**: Use 6-digit codes when available for maximum accuracy
2. **Partial matches**: Some datasets may only have 4 or 5-digit NAICS codes
3. **Multiple codes**: Vendors may be classified under multiple NAICS codes
4. **Keyword augmentation**: Consider combining NAICS filtering with keyword searches for:
   - "software", "IT", "information technology"
   - "consulting", "systems", "programming"
   - "cloud", "data", "cybersecurity"
   - "network", "telecommunications", "hosting"

## Sources
- Federal spending data: FY2024 government contract awards
- NAICS structure: 2022 North American Industry Classification System
- Industry definitions: U.S. Census Bureau NAICS database
