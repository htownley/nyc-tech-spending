#!/usr/bin/env python3
"""
Update spending data for all fiscal years in confirmed_digital_budget_codes.csv

This script:
1. Calculates actual spending from transaction data (2020-2024) for each budget code
2. Compares with existing values in the CSV
3. Shows differences before updating
4. Optionally updates the CSV with corrected values

Usage:
  python3 update_budget_code_yearly_data.py --compare    # Just compare, don't update
  python3 update_budget_code_yearly_data.py --update     # Compare and update
"""

import pandas as pd
import sys
from pathlib import Path

def calculate_yearly_spending(fiscal_years, budget_codes):
    """Calculate spending for each budget code across fiscal years"""

    all_budget_data = {}

    for year in fiscal_years:
        trans_file = f'fy{year}_full.csv'
        if not Path(trans_file).exists():
            print(f"⚠ Warning: {trans_file} not found, skipping year {year}")
            continue

        print(f"Loading {trans_file}...")
        transactions = pd.read_csv(trans_file, dtype=str, low_memory=False)
        print(f"  ✓ {len(transactions):,} transactions")

        # For each budget code, calculate spending
        for code in budget_codes:
            # Filter transactions containing this budget code
            code_transactions = transactions[transactions['budget_code'].str.contains(str(code), na=False, regex=False)]

            # Sum the spending
            total = pd.to_numeric(code_transactions['check_amount'], errors='coerce').sum()

            if code not in all_budget_data:
                all_budget_data[code] = {}
            all_budget_data[code][f'fy{year}_spending'] = total

        print(f"  ✓ Processed {len(budget_codes)} budget codes")

    return all_budget_data

def compare_and_update(compare_only=True):
    """Compare calculated data with existing CSV and optionally update"""

    # Load existing budget code data
    budget_file = 'data/confirmed_digital_budget_codes.csv'
    if not Path(budget_file).exists():
        print(f"✗ Error: {budget_file} not found")
        return

    budget_df = pd.read_csv(budget_file)
    print(f"✓ Loaded {len(budget_df)} budget codes from {budget_file}\n")

    # Get list of budget codes
    budget_codes = budget_df['budget_code'].tolist()

    # Calculate actual data from transactions
    fiscal_years = ['2020', '2021', '2022', '2023', '2024']
    print("=" * 100)
    print("CALCULATING SPENDING FROM TRANSACTION DATA")
    print("=" * 100)
    all_budget_data = calculate_yearly_spending(fiscal_years, budget_codes)

    # Compare with existing data and build updated dataframe
    print("\n" + "=" * 100)
    print("COMPARING WITH EXISTING CSV DATA")
    print("=" * 100)

    differences = []

    # Add new columns to dataframe if they don't exist
    for year in fiscal_years:
        col = f'fy{year}_spending'
        if col not in budget_df.columns:
            budget_df[col] = None

    for idx, row in budget_df.iterrows():
        code = row['budget_code']

        if code not in all_budget_data:
            print(f"\n⚠ Budget code not found in transaction data: {code}")
            continue

        code_diffs = {'budget_code': code, 'budget_name': row['budget_name']}
        has_diff = False

        for year in fiscal_years:
            col = f'fy{year}_spending'

            # Get existing value
            existing = row.get(col)
            if pd.notna(existing):
                # Remove dollar sign and commas if present
                if isinstance(existing, str):
                    existing = existing.replace('$', '').replace(',', '')
                existing = pd.to_numeric(existing, errors='coerce')

            # Get calculated value
            actual = all_budget_data[code].get(col, 0)

            # Check for differences
            if pd.notna(existing):
                diff = abs(actual - existing)
                if diff >= 0.01:  # More than 1 cent difference
                    code_diffs[f'{col}_csv'] = existing
                    code_diffs[f'{col}_actual'] = actual
                    code_diffs[f'{col}_diff'] = diff
                    has_diff = True
            elif actual > 0:
                # CSV is blank but we have data
                code_diffs[f'{col}_csv'] = 'BLANK'
                code_diffs[f'{col}_actual'] = actual
                has_diff = True

            # Update dataframe with actual value
            budget_df.at[idx, col] = actual

        if has_diff:
            differences.append(code_diffs)

    # Report differences
    if differences:
        print(f"\n⚠ Found differences for {len(differences)} budget codes")

        # Show all differences
        print("\nAll differences:")
        for i, diff in enumerate(differences, 1):
            print(f"\n{i}. {diff['budget_code']} - {diff['budget_name']}:")
            for key, value in diff.items():
                if key not in ['budget_code', 'budget_name']:
                    if isinstance(value, float):
                        print(f"   {key}: ${value:,.2f}")
                    else:
                        print(f"   {key}: {value}")

        # Save all differences to CSV
        diff_df = pd.DataFrame(differences)
        diff_file = 'budget_code_differences.csv'
        diff_df.to_csv(diff_file, index=False)
        print(f"\n✓ All differences saved to: {diff_file}")
    else:
        print("\n✓ No differences found - all data matches!")

    # Show summary by fiscal year
    print("\n" + "=" * 100)
    print("SPENDING SUMMARY BY FISCAL YEAR")
    print("=" * 100)
    for year in fiscal_years:
        col = f'fy{year}_spending'
        total = budget_df[col].sum()
        print(f"FY{year}: ${total:,.2f}")

    total_all_years = sum(budget_df[f'fy{year}_spending'].sum() for year in fiscal_years)
    print(f"\nTotal across all years: ${total_all_years:,.2f}")

    # Update CSV if requested
    if not compare_only:
        print("\n" + "=" * 100)
        print("UPDATING CSV WITH CALCULATED VALUES")
        print("=" * 100)

        # Format spending columns as currency strings
        for year in fiscal_years:
            col = f'fy{year}_spending'
            budget_df[col] = budget_df[col].apply(lambda x: f'${x:,.2f}' if pd.notna(x) and x > 0 else '')

        # Save updated CSV
        budget_df.to_csv(budget_file, index=False)
        print(f"✓ Updated {budget_file}")
        print("=" * 100)
    else:
        print("\n" + "=" * 100)
        print("COMPARISON COMPLETE (no updates made)")
        print("=" * 100)
        print("To update the CSV with calculated values, run:")
        print("  python3 update_budget_code_yearly_data.py --update")
        print("=" * 100)

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 update_budget_code_yearly_data.py --compare    # Just compare, don't update")
        print("  python3 update_budget_code_yearly_data.py --update     # Compare and update")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == '--compare':
        compare_and_update(compare_only=True)
    elif mode == '--update':
        compare_and_update(compare_only=False)
    else:
        print(f"✗ Unknown mode: {mode}")
        print("Use --compare or --update")
        sys.exit(1)

if __name__ == "__main__":
    main()
