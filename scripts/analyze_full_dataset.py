#!/usr/bin/env python3
"""
Analyze FULL FY2024 Dataset - Find All Vendors
Compare with our 100k sample classifications
"""

import pandas as pd

print("=" * 80)
print("FULL FY2024 DATASET ANALYSIS")
print("=" * 80)

# Load full dataset
print("\nLoading full FY2024 dataset (3.2M records)...")
df = pd.read_csv('fy2024_full.csv')
print(f"✓ Loaded {len(df):,} transactions")
print(f"✓ Total spending: ${df['check_amount'].sum():,.2f}")

# Aggregate by vendor
print("\nAggregating by vendor...")
vendor_totals = df.groupby('payee_name').agg({
    'check_amount': 'sum',
    'contract_id': 'nunique',
    'agency': lambda x: ', '.join(x.unique()[:3]) + ('...' if x.nunique() > 3 else ''),
    'budget_code': lambda x: '; '.join(sorted([str(v) for v in x.dropna().unique() if v])) if x.notna().any() else None,
    'expense_category': lambda x: '; '.join(sorted([str(v) for v in x.dropna().unique() if v])) if x.notna().any() else None,
    'sub_vendor': lambda x: 'Yes' if 'Yes' in x.values else 'No',
    'associated_prime_vendor': lambda x: '; '.join(sorted([str(v) for v in x.dropna().unique() if v])) if x.notna().any() else None
}).reset_index()

vendor_totals.columns = ['vendor', 'total_spending', 'num_contracts', 'agencies', 'budget_codes', 'expense_categories', 'is_subvendor', 'prime_vendors']
vendor_totals = vendor_totals.sort_values('total_spending', ascending=False).reset_index(drop=True)
vendor_totals['rank'] = range(1, len(vendor_totals) + 1)

print(f"✓ Total unique vendors: {len(vendor_totals):,}")

# Save complete vendor list with budget codes
output_file = 'data/all_vendors_fy2024.csv'
vendor_totals.to_csv(output_file, index=False)
print(f"✓ Saved complete vendor list to {output_file}")

# Summary statistics
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

overall_total = vendor_totals['total_spending'].sum()
top_200_total = vendor_totals.head(200)['total_spending'].sum()
top_200_pct = (top_200_total / overall_total) * 100

print(f"Full dataset: {len(df):,} transactions")
print(f"Total spending: ${overall_total:,.2f}")
print(f"Unique vendors: {len(vendor_totals):,}")
print(f"Top 200 vendors: ${top_200_total:,.2f} ({top_200_pct:.1f}%)")

# Count subvendors
subvendor_count = (vendor_totals['is_subvendor'] == 'Yes').sum()
print(f"Subvendors: {subvendor_count:,}")
print(f"Prime vendors: {len(vendor_totals) - subvendor_count:,}")

print("=" * 80)
