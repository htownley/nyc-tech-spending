#!/usr/bin/env python3
"""
Analyze NYC FY2024 Spending - Find Digital Service Opportunity
Inspired by Jennifer Pahlka's vision for government digital capacity
"""

import pandas as pd
import numpy as np

# Load the data
print("=" * 80)
print("NYC DIGITAL SERVICE OPPORTUNITY - Initial Analysis")
print("=" * 80)
print("\nLoading FY2024 spending data...")

df = pd.read_csv('data/archive/fy2024_sample_100k.csv')

print(f"✓ Loaded {len(df):,} spending transactions\n")

# Basic stats
print("=" * 80)
print("DATASET OVERVIEW")
print("=" * 80)
print(f"Total transactions: {len(df):,}")
print(f"Date range: FY{df['fiscal_year'].unique()}")
print(f"Total spending: ${df['check_amount'].sum():,.2f}")
print(f"Unique vendors: {df['payee_name'].nunique():,}")
print(f"Unique agencies: {df['agency'].nunique():,}")

# Check data quality
print(f"\nMissing values:")
print(df.isnull().sum())

# Aggregate by vendor
print("\n" + "=" * 80)
print("VENDOR ANALYSIS - Finding the Opportunity")
print("=" * 80)

vendor_totals = df.groupby('payee_name').agg({
    'check_amount': 'sum',
    'contract_id': 'nunique',
    'agency': lambda x: ', '.join(x.unique()[:3]) + ('...' if x.nunique() > 3 else '')
}).reset_index()

vendor_totals.columns = ['vendor', 'total_spending', 'num_contracts', 'agencies']
vendor_totals = vendor_totals.sort_values('total_spending', ascending=False).reset_index(drop=True)

print(f"\nTotal unique vendors: {len(vendor_totals):,}")
print(f"Total spending: ${vendor_totals['total_spending'].sum():,.2f}\n")

# Concentration analysis
print("SPENDING CONCENTRATION:")
top_10_pct = vendor_totals.head(10)['total_spending'].sum() / vendor_totals['total_spending'].sum() * 100
top_50_pct = vendor_totals.head(50)['total_spending'].sum() / vendor_totals['total_spending'].sum() * 100
top_100_pct = vendor_totals.head(100)['total_spending'].sum() / vendor_totals['total_spending'].sum() * 100
top_200_pct = vendor_totals.head(200)['total_spending'].sum() / vendor_totals['total_spending'].sum() * 100

print(f"Top 10 vendors: ${vendor_totals.head(10)['total_spending'].sum():,.2f} ({top_10_pct:.1f}%)")
print(f"Top 50 vendors: ${vendor_totals.head(50)['total_spending'].sum():,.2f} ({top_50_pct:.1f}%)")
print(f"Top 100 vendors: ${vendor_totals.head(100)['total_spending'].sum():,.2f} ({top_100_pct:.1f}%)")
print(f"Top 200 vendors: ${vendor_totals.head(200)['total_spending'].sum():,.2f} ({top_200_pct:.1f}%)")

# Show top 20 vendors
print("\n" + "=" * 80)
print("TOP 20 VENDORS BY SPENDING")
print("=" * 80)
print(f"{'Rank':<6} {'Vendor':<60} {'Spending':>20}")
print("-" * 86)

for idx, row in vendor_totals.head(20).iterrows():
    print(f"{idx+1:<6} {row['vendor'][:60]:<60} ${row['total_spending']:>19,.2f}")

# Save top 200 for manual classification
print("\n" + "=" * 80)
print("PREPARING FOR MANUAL CLASSIFICATION")
print("=" * 80)

top_200 = vendor_totals.head(200).copy()
top_200['digital_service'] = ''  # Empty column for Yes/Maybe/No classification
top_200['notes'] = ''  # For research notes

output_file = 'data/archive/top_200_vendors_for_classification.csv'
top_200.to_csv(output_file, index=False)

print(f"\n✓ Saved top 200 vendors to: {output_file}")
print(f"  Total spending in top 200: ${top_200['total_spending'].sum():,.2f} ({top_200_pct:.1f}% of all spending)")
print(f"\nNext step: Classify these vendors as 'Yes', 'Maybe', or 'No' for digital services")
print("Then we'll calculate NYC's digital service opportunity!")

print("\n" + "=" * 80)
