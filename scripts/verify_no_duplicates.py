#!/usr/bin/env python3
"""
Verify there are no duplicate transactions after merging chunks
Run this after merge_chunks.py completes
"""

import pandas as pd
import hashlib

def main():
    print("=" * 80)
    print("VERIFYING NO DUPLICATES IN MERGED DATA")
    print("=" * 80)

    filename = "fy2024_full.csv"

    print(f"\nReading {filename}...")
    df = pd.read_csv(filename)

    print(f"✓ Total records: {len(df):,}")

    # Create a hash for each row (all columns combined)
    print("\nCreating hash for each transaction...")
    df['row_hash'] = df.apply(lambda row: hashlib.md5(
        '|'.join(str(x) for x in row.values).encode()
    ).hexdigest(), axis=1)

    # Check for duplicates
    print("Checking for duplicate transactions...")

    total_records = len(df)
    unique_hashes = df['row_hash'].nunique()
    duplicates = total_records - unique_hashes

    print(f"\n{'=' * 80}")
    print("RESULTS")
    print("=" * 80)
    print(f"Total records:        {total_records:,}")
    print(f"Unique transactions:  {unique_hashes:,}")
    print(f"Duplicates found:     {duplicates:,}")

    if duplicates == 0:
        print("\n✓ SUCCESS: No duplicate transactions found!")
        print("  All chunks merged cleanly with no overlaps")
    else:
        print(f"\n⚠ WARNING: Found {duplicates:,} duplicate transactions")
        print("  This suggests overlapping chunks or API inconsistency")

        # Show some duplicate examples
        duplicate_rows = df[df.duplicated(subset=['row_hash'], keep=False)]
        if len(duplicate_rows) > 0:
            print(f"\nExample duplicates (first 10):")
            print(duplicate_rows.head(10)[['agency', 'payee_name', 'check_amount']])

    print("=" * 80)

if __name__ == "__main__":
    main()
