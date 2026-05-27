#!/usr/bin/env python3
"""
Extract OTI vendors not in the existing digital services list,
classify them by category, and save to a new CSV.

Categories: Digital, Mixed, Hardware, Nontechnical, Internal
"""

import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
RAW_FY2025   = PROJECT_ROOT / "data" / "raw" / "fy2025_full.csv"
EXISTING_CSV = PROJECT_ROOT / "data" / "outputs" / "digital_services_vendors.csv"
OUTPUT_CSV   = PROJECT_ROOT / "data" / "outputs" / "oti_vendors_for_classification.csv"

SPEND_THRESHOLD = 500_000
OTI_AGENCY = "Department of Information Technology and Telecommunications"
PRIVACY_PLACEHOLDER = "N/A (PRIVACY/SECURITY)"


def extract_vendors():
    existing = set(
        pd.read_csv(EXISTING_CSV)["vendor"].str.strip().tolist()
    )

    print(f"Reading {RAW_FY2025.name} ({RAW_FY2025.stat().st_size // 1_000_000} MB)...")
    df = pd.read_csv(
        RAW_FY2025,
        usecols=["payee_name", "agency", "check_amount", "spending_category", "expense_category"],
    )

    oti = df[df["agency"] == OTI_AGENCY].copy()
    oti = oti[oti["payee_name"].str.strip() != PRIVACY_PLACEHOLDER]
    oti = oti[~oti["payee_name"].isin(existing)]

    oti["check_amount"] = pd.to_numeric(oti["check_amount"], errors="coerce").fillna(0)

    agg = (
        oti.groupby("payee_name")
        .agg(
            fy2025_spending=("check_amount", "sum"),
            transaction_count=("check_amount", "count"),
            spending_categories=("spending_category", lambda x: "; ".join(sorted(x.dropna().unique()))),
            expense_categories=("expense_category", lambda x: "; ".join(sorted(x.dropna().unique()))),
        )
        .reset_index()
        .rename(columns={"payee_name": "vendor"})
    )

    agg = agg[agg["fy2025_spending"] > SPEND_THRESHOLD]
    agg = agg.sort_values("fy2025_spending", ascending=False).reset_index(drop=True)

    print(f"OTI vendors above ${SPEND_THRESHOLD/1e3:.0f}k not in existing list: {len(agg)}")
    return agg


CLASSIFICATIONS = {
    "TECHNOLOGY SERVICES - PS":               ("Internal",     "OTI payroll line"),
    "VERIZON BUSINESS NETWORK SERVICES LLC":  ("Hardware",     "Telecom/network carrier"),
    "AT&T CORP":                              ("Hardware",     "Telecom/network carrier"),
    "MTX GROUP INC":                          ("Digital",      "Salesforce/cloud implementation — same company as MTX B2B Solutions LLC already in main list"),
    "BROOKLYN NY II SGF LLC":                 ("Nontechnical", "OTI office real estate"),
    "311 PS":                                 ("Internal",     "311 call center payroll"),
    "911 TECHNICAL OPERATIONS- PS":           ("Internal",     "911 operations payroll"),
    "ADMIN/OPERATIONS PS":                    ("Internal",     "OTI admin payroll"),
    "CABLEVISION LIGHTPATH":                  ("Hardware",     "Fiber/telecom carrier"),
    "CELLCO PARTNERSHIP":                     ("Hardware",     "Verizon Wireless carrier"),
    "KING TELESERVICES LLC":                  ("Hardware",     "Telecom services"),
    "NEW YORK CITY CYBER COMMAND":            ("Internal",     "Internal city cyber unit"),
    "TIME WARNER CABLE NEW YORK CITY LLC":    ("Hardware",     "Cable/fiber carrier"),
    "Forest City Bridge Street Associates II LLC": ("Nontechnical", "OTI office real estate"),
    "MAYOR'S OFFICE OF MEDIA & ENTERTAINMENT": ("Internal",   "City agency, not external vendor"),
    "CenturyLInk Communications LLC":         ("Hardware",     "Telecom/fiber carrier"),
    "CITIZENS COMMITTEE FOR NEW YORK CITY INC": ("Nontechnical", "Nonprofit community programs"),
    "LANGUAGE LINE SERVICES, INC.":           ("Nontechnical", "Interpretation/translation services"),
    "T-MOBILE USA INC":                       ("Hardware",     "Mobile carrier"),
    "FORREST CITY MYRTLE ASSOCIATES LLC":     ("Nontechnical", "Real estate"),
    "CROWN CASTLE FIBER LLC":                 ("Hardware",     "Fiber/small cell infrastructure"),
    "DIGITAL REALTY TRUST LP":                ("Hardware",     "Data center/colocation"),
    "EMPIRE STATE BLDG. CO.":                 ("Nontechnical", "OTI office real estate"),
    "NYI-SIRIUS LLC":                         ("Hardware",     "Data center/colocation"),
    "BRIDGE PHILANTHROPIC CONSULTING LLC":    ("Nontechnical", "Nonprofit consulting"),
    "4TS HOLDINGS II LLC":                    ("Nontechnical", "Real estate"),
    "SAS INSTITUTE INC.":                     ("Digital",      "Major analytics/data science software platform"),
    "FREELANCERS UNION INC":                  ("Nontechnical", "Benefits/union administration"),
    "GAZELLE GLOBALIZATION GROUP LL":         ("Nontechnical", "Translation/globalization services"),
    "AVIVA SERVICES INC":                     ("Nontechnical", "Staffing agency"),
    "JP MORGAN CHASE BANK NA":                ("Nontechnical", "Banking/financial services"),
    "GLOW MEDIA AND MARKETING INC":           ("Nontechnical", "Marketing agency"),
    "TOP TEMPORARIES INC":                    ("Nontechnical", "Temp staffing"),
    "IDENTITY THEFT GUARD SOLUTIONS INC":     ("Digital",      "Identity protection software service"),
}


def main():
    vendors_df = extract_vendors()

    vendors_df["category"] = vendors_df["vendor"].map(
        lambda v: CLASSIFICATIONS.get(v, ("", ""))[0]
    )
    vendors_df["rationale"] = vendors_df["vendor"].map(
        lambda v: CLASSIFICATIONS.get(v, ("", ""))[1]
    )

    vendors_df["fy2025_spending"] = vendors_df["fy2025_spending"].round(2)

    vendors_df.to_csv(OUTPUT_CSV, index=False)
    print(f"\nSaved: {OUTPUT_CSV}")

    print("\nCategory breakdown:")
    summary = (
        vendors_df.groupby("category")
        .agg(vendors=("vendor", "count"), total_spend_M=("fy2025_spending", lambda x: round(x.sum() / 1e6, 1)))
        .reset_index()
        .sort_values("total_spend_M", ascending=False)
    )
    print(summary.to_string(index=False))

    print("\nTop vendors by spend:")
    for _, row in vendors_df.head(15).iterrows():
        print(f"  [{row['category']:12s}] {row['vendor'][:50]:<50} ${row['fy2025_spending']/1e6:.1f}M")


if __name__ == "__main__":
    main()
