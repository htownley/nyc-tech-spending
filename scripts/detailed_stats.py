#!/usr/bin/env python3
"""
Detailed statistics on FY2024 NYC Spending
"""

import pandas as pd
import numpy as np

print("=" * 80)
print("FY2024 NYC SPENDING - DETAILED STATISTICS")
print("=" * 80)

df = pd.read_csv('data/archive/fy2024_sample_100k.csv')

print(f"\nDataset: {len(df):,} transactions from FY2024")
print(f"Total value: ${df['check_amount'].sum():,.2f}\n")

# === SPENDING BY AGENCY ===
print("=" * 80)
print("TOP 20 AGENCIES BY TOTAL SPENDING")
print("=" * 80)

agency_spending = df.groupby('agency')['check_amount'].agg(['sum', 'count', 'mean']).reset_index()
agency_spending.columns = ['agency', 'total_spending', 'num_transactions', 'avg_transaction']
agency_spending = agency_spending.sort_values('total_spending', ascending=False)

print(f"{'Rank':<6} {'Agency':<55} {'Total Spending':>20} {'Txns':>8}")
print("-" * 90)
for idx, row in agency_spending.head(20).iterrows():
    print(f"{idx+1:<6} {row['agency'][:55]:<55} ${row['total_spending']:>19,.2f} {row['num_transactions']:>7,}")

# === SPENDING CATEGORIES ===
print("\n" + "=" * 80)
print("SPENDING BY CATEGORY")
print("=" * 80)

cat_spending = df.groupby('spending_category')['check_amount'].agg(['sum', 'count']).reset_index()
cat_spending.columns = ['category', 'total_spending', 'num_transactions']
cat_spending = cat_spending.sort_values('total_spending', ascending=False)

print(f"{'Category':<40} {'Total Spending':>20} {'Txns':>10} {'% of Total':>10}")
print("-" * 80)
total = df['check_amount'].sum()
for _, row in cat_spending.iterrows():
    pct = (row['total_spending'] / total) * 100
    print(f"{row['category']:<40} ${row['total_spending']:>19,.2f} {row['num_transactions']:>9,} {pct:>9.1f}%")

# === INDUSTRY BREAKDOWN ===
print("\n" + "=" * 80)
print("SPENDING BY INDUSTRY (Non-blank only)")
print("=" * 80)

df_with_industry = df[df['industry'].notna() & (df['industry'] != '')]
if len(df_with_industry) > 0:
    industry_spending = df_with_industry.groupby('industry')['check_amount'].agg(['sum', 'count']).reset_index()
    industry_spending.columns = ['industry', 'total_spending', 'num_transactions']
    industry_spending = industry_spending.sort_values('total_spending', ascending=False)

    print(f"{'Industry':<40} {'Total Spending':>20} {'Txns':>10}")
    print("-" * 70)
    for _, row in industry_spending.iterrows():
        print(f"{row['industry']:<40} ${row['total_spending']:>19,.2f} {row['num_transactions']:>9,}")

    print(f"\nNote: {len(df) - len(df_with_industry):,} transactions ({(len(df) - len(df_with_industry))/len(df)*100:.1f}%) have blank industry")
else:
    print("No industry data available in sample")

# === TRANSACTION SIZE DISTRIBUTION ===
print("\n" + "=" * 80)
print("TRANSACTION SIZE DISTRIBUTION")
print("=" * 80)

print(f"Minimum transaction: ${df['check_amount'].min():,.2f}")
print(f"Maximum transaction: ${df['check_amount'].max():,.2f}")
print(f"Median transaction: ${df['check_amount'].median():,.2f}")
print(f"Mean transaction: ${df['check_amount'].mean():,.2f}")
print(f"\nPercentiles:")
for p in [10, 25, 50, 75, 90, 95, 99]:
    val = df['check_amount'].quantile(p/100)
    print(f"  {p}th percentile: ${val:,.2f}")

# === CONTRACT vs NON-CONTRACT ===
print("\n" + "=" * 80)
print("CONTRACT-RELATED SPENDING")
print("=" * 80)

has_contract = df['contract_id'].notna() & (df['contract_id'] != '')
contract_spending = df[has_contract]['check_amount'].sum()
non_contract_spending = df[~has_contract]['check_amount'].sum()
contract_pct = (contract_spending / total) * 100
non_contract_pct = (non_contract_spending / total) * 100

print(f"With contract ID: ${contract_spending:,.2f} ({contract_pct:.1f}%) - {has_contract.sum():,} transactions")
print(f"No contract ID: ${non_contract_spending:,.2f} ({non_contract_pct:.1f}%) - {(~has_contract).sum():,} transactions")

# === EXPENSE CATEGORIES ===
print("\n" + "=" * 80)
print("TOP 15 EXPENSE CATEGORIES")
print("=" * 80)

df_with_expense = df[df['expense_category'].notna() & (df['expense_category'] != '')]
if len(df_with_expense) > 0:
    expense_spending = df_with_expense.groupby('expense_category')['check_amount'].agg(['sum', 'count']).reset_index()
    expense_spending.columns = ['expense_category', 'total_spending', 'num_transactions']
    expense_spending = expense_spending.sort_values('total_spending', ascending=False)

    print(f"{'Expense Category':<50} {'Total Spending':>20} {'Txns':>8}")
    print("-" * 80)
    for _, row in expense_spending.head(15).iterrows():
        print(f"{row['expense_category'][:50]:<50} ${row['total_spending']:>19,.2f} {row['num_transactions']:>7,}")

print("\n" + "=" * 80)
