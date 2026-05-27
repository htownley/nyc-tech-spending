#!/usr/bin/env python3
"""
Update spending and rank data for all fiscal years in digital_services_vendors.csv

This script:
1. Calculates actual spending and ranks from transaction data (2020-2024)
2. Compares with existing values in the CSV
3. Shows differences before updating
4. Optionally updates the CSV with corrected values

Usage:
  python3 update_vendor_yearly_data.py --compare    # Just compare, don't update
  python3 update_vendor_yearly_data.py --update     # Compare and update
"""

import pandas as pd
import sys
from pathlib import Path

def calculate_yearly_data(fiscal_years):
    """Calculate spending and ranks for all vendors across fiscal years"""

    all_vendor_data = {}

    for year in fiscal_years:
        trans_file = f'fy{year}_full.csv'
        if not Path(trans_file).exists():
            print(f"⚠ Warning: {trans_file} not found, skipping year {year}")
            continue

        print(f"Loading {trans_file}...")
        transactions = pd.read_csv(trans_file, dtype=str, low_memory=False)
        print(f"  ✓ {len(transactions):,} transactions")

        # Calculate spending by vendor
        transactions['check_amount_numeric'] = pd.to_numeric(transactions['check_amount'], errors='coerce')

        vendor_totals = transactions.groupby('payee_name').agg({
            'check_amount_numeric': 'sum'
        }).reset_index()

        vendor_totals.columns = ['vendor', f'fy{year}_spending']

        # Calculate ranks (1 = highest spending)
        vendor_totals = vendor_totals.sort_values(f'fy{year}_spending', ascending=False)
        vendor_totals[f'fy{year}_rank'] = range(1, len(vendor_totals) + 1)

        # Store in dictionary
        for _, row in vendor_totals.iterrows():
            vendor = row['vendor']
            if vendor not in all_vendor_data:
                all_vendor_data[vendor] = {}
            all_vendor_data[vendor][f'fy{year}_spending'] = row[f'fy{year}_spending']
            all_vendor_data[vendor][f'fy{year}_rank'] = row[f'fy{year}_rank']

        print(f"  ✓ Processed {len(vendor_totals):,} unique vendors")

    return all_vendor_data

def compare_and_update(compare_only=True):
    """Compare calculated data with existing CSV and optionally update"""

    # Load existing vendor data
    vendors_file = 'data/outputs/digital_services_vendors.csv'
    if not Path(vendors_file).exists():
        print(f"✗ Error: {vendors_file} not found")
        return

    vendors_df = pd.read_csv(vendors_file)
    print(f"✓ Loaded {len(vendors_df)} vendors from {vendors_file}\n")

    # Calculate actual data from transactions
    fiscal_years = ['2020', '2021', '2022', '2023', '2024']
    print("=" * 100)
    print("CALCULATING SPENDING AND RANKS FROM TRANSACTION DATA")
    print("=" * 100)
    all_vendor_data = calculate_yearly_data(fiscal_years)

    # Compare with existing data
    print("\n" + "=" * 100)
    print("COMPARING WITH EXISTING CSV DATA")
    print("=" * 100)

    differences = []

    for idx, row in vendors_df.iterrows():
        vendor = row['vendor']

        if vendor not in all_vendor_data:
            print(f"\n⚠ Vendor not found in transaction data: {vendor}")
            continue

        vendor_diffs = {'vendor': vendor}
        has_diff = False

        for year in fiscal_years:
            # Check spending
            csv_spending = pd.to_numeric(row.get(f'fy{year}_spending'), errors='coerce')
            actual_spending = all_vendor_data[vendor].get(f'fy{year}_spending', 0)

            if pd.notna(csv_spending):
                diff = abs(actual_spending - csv_spending)
                if diff >= 0.01:  # More than 1 cent difference
                    vendor_diffs[f'fy{year}_spending_csv'] = csv_spending
                    vendor_diffs[f'fy{year}_spending_actual'] = actual_spending
                    vendor_diffs[f'fy{year}_spending_diff'] = diff
                    has_diff = True
            elif actual_spending > 0:
                # CSV is blank but we have data
                vendor_diffs[f'fy{year}_spending_csv'] = 'BLANK'
                vendor_diffs[f'fy{year}_spending_actual'] = actual_spending
                has_diff = True

            # Check rank
            csv_rank = pd.to_numeric(row.get(f'fy{year}_rank'), errors='coerce')
            actual_rank = all_vendor_data[vendor].get(f'fy{year}_rank')

            if pd.notna(csv_rank):
                if csv_rank != actual_rank:
                    vendor_diffs[f'fy{year}_rank_csv'] = int(csv_rank)
                    vendor_diffs[f'fy{year}_rank_actual'] = actual_rank
                    has_diff = True
            elif actual_rank is not None:
                # CSV is blank but we have data
                vendor_diffs[f'fy{year}_rank_csv'] = 'BLANK'
                vendor_diffs[f'fy{year}_rank_actual'] = actual_rank
                has_diff = True

        if has_diff:
            differences.append(vendor_diffs)

    # Report differences
    if differences:
        print(f"\n⚠ Found differences for {len(differences)} vendors")

        # Show sample differences
        print("\nSample differences (first 5 vendors):")
        for i, diff in enumerate(differences[:5], 1):
            print(f"\n{i}. {diff['vendor']}:")
            for key, value in diff.items():
                if key != 'vendor':
                    print(f"   {key}: {value}")

        # Save all differences to CSV
        diff_df = pd.DataFrame(differences)
        diff_file = 'vendor_data_differences.csv'
        diff_df.to_csv(diff_file, index=False)
        print(f"\n✓ All differences saved to: {diff_file}")
    else:
        print("\n✓ No differences found - all data matches!")

    # Update CSV if requested
    if not compare_only:
        print("\n" + "=" * 100)
        print("UPDATING CSV WITH CALCULATED VALUES")
        print("=" * 100)

        for idx, row in vendors_df.iterrows():
            vendor = row['vendor']

            if vendor in all_vendor_data:
                for year in fiscal_years:
                    # Update spending
                    actual_spending = all_vendor_data[vendor].get(f'fy{year}_spending', 0)
                    vendors_df.at[idx, f'fy{year}_spending'] = actual_spending

                    # Update rank
                    actual_rank = all_vendor_data[vendor].get(f'fy{year}_rank')
                    if actual_rank is not None:
                        vendors_df.at[idx, f'fy{year}_rank'] = actual_rank

        # Save updated CSV
        vendors_df.to_csv(vendors_file, index=False)
        print(f"✓ Updated {vendors_file}")
        print("=" * 100)
    else:
        print("\n" + "=" * 100)
        print("COMPARISON COMPLETE (no updates made)")
        print("=" * 100)
        print("To update the CSV with calculated values, run:")
        print("  python3 update_vendor_yearly_data.py --update")
        print("=" * 100)

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 update_vendor_yearly_data.py --compare    # Just compare, don't update")
        print("  python3 update_vendor_yearly_data.py --update     # Compare and update")
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
