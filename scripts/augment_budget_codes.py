#!/usr/bin/env python3
"""
Augment confirmed_digital_budget_codes.csv with:
- Top 10 expense categories (with percentages)
- Top 10 vendors (with percentages)
Based on FY2025 transaction data.
"""

import pandas as pd
import re

# Load the budget codes file
budget_codes_path = 'data/outputs/confirmed_digital_budget_codes.csv'
raw_data_path = 'data/raw/fy2025_full.csv'

print("Loading confirmed digital budget codes...")
budget_df = pd.read_csv(budget_codes_path)
print(f"Found {len(budget_df)} budget codes")

print("Loading FY2025 raw transaction data...")
raw_df = pd.read_csv(raw_data_path, low_memory=False)
print(f"Loaded {len(raw_df):,} transactions")

# Columns: agency, payee_name, check_amount, fiscal_year, industry, spending_category,
#          contract_id, department, expense_category, budget_code, sub_vendor, associated_prime_vendor

# The budget code column contains values like "8811 (MYCITY PROJECT)"
# We need to extract just the code part to match
def extract_budget_code(full_code):
    """Extract budget code from format like '8811 (MYCITY PROJECT)'"""
    if pd.isna(full_code):
        return None
    match = re.match(r'^(\w+)\s*\(', str(full_code))
    if match:
        return match.group(1)
    return str(full_code).strip()

# Apply extraction to raw data
raw_df['budget_code_extracted'] = raw_df['budget_code'].apply(extract_budget_code)

# Get the list of budget codes we need to analyze
codes_to_analyze = budget_df['budget_code'].tolist()
print(f"Analyzing {len(codes_to_analyze)} codes: {codes_to_analyze[:5]}...")

# For each budget code, calculate top 10 expense categories and top 10 vendors
top_expense_categories = []
top_vendors = []

for code in codes_to_analyze:
    # Filter transactions for this budget code
    code_df = raw_df[raw_df['budget_code_extracted'] == code]
    total_spending = code_df['check_amount'].sum()

    if total_spending == 0:
        top_expense_categories.append("No FY2025 data")
        top_vendors.append("No FY2025 data")
        continue

    # Top 10 expense categories
    expense_agg = code_df.groupby('expense_category')['check_amount'].sum()
    expense_agg = expense_agg.sort_values(ascending=False).head(10)
    expense_strs = []
    for cat, amount in expense_agg.items():
        pct = (amount / total_spending) * 100
        expense_strs.append(f"{cat} ({pct:.0f}%)")
    top_expense_categories.append("; ".join(expense_strs))

    # Top 10 vendors
    vendor_agg = code_df.groupby('payee_name')['check_amount'].sum()
    vendor_agg = vendor_agg.sort_values(ascending=False).head(10)
    vendor_strs = []
    for vendor, amount in vendor_agg.items():
        pct = (amount / total_spending) * 100
        vendor_strs.append(f"{vendor} ({pct:.0f}%)")
    top_vendors.append("; ".join(vendor_strs))

    print(f"Processed {code}: ${total_spending:,.0f}")

# Add new columns
budget_df['top_expense_categories_fy25'] = top_expense_categories
budget_df['top_vendors_fy25'] = top_vendors

# Save updated file
budget_df.to_csv(budget_codes_path, index=False)
print(f"\nSaved updated file to {budget_codes_path}")
print("Done!")
