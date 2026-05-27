#!/usr/bin/env python3
"""
Merge downloaded chunks for a specific fiscal year into a single CSV file

Usage:
  python3 merge_fiscal_year.py 2024
  python3 merge_fiscal_year.py 2023
"""

import pandas as pd
import glob
import json
import sys
from datetime import datetime

def main():
    # Get fiscal year from command line
    if len(sys.argv) < 2:
        print("Usage: python3 merge_fiscal_year.py <fiscal_year>")
        print("Example: python3 merge_fiscal_year.py 2024")
        sys.exit(1)

    fiscal_year = sys.argv[1]

    # Setup file paths
    chunks_dir = f"fy{fiscal_year}_chunks"
    progress_file = f"download_progress_fy{fiscal_year}.json"
    output_file = f"fy{fiscal_year}_full.csv"

    print("=" * 80)
    print(f"MERGING FY{fiscal_year} CHUNKS")
    print("=" * 80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Load progress to verify download is complete
    try:
        with open(progress_file, 'r') as f:
            progress = json.load(f)
    except FileNotFoundError:
        print(f"✗ Error: No download progress file found for FY{fiscal_year}")
        print(f"  Run download_fiscal_year.py {fiscal_year} first")
        return

    # Find all chunk files
    chunk_files = sorted(glob.glob(f"{chunks_dir}/chunk_*.csv"))

    if not chunk_files:
        print(f"✗ Error: No chunk files found in {chunks_dir}/")
        return

    print(f"✓ Found {len(chunk_files)} chunk files")
    print(f"✓ Expected chunks: {len(progress['chunks_completed'])}")

    if len(chunk_files) != len(progress['chunks_completed']):
        print("⚠ Warning: Chunk count mismatch - download may be incomplete")

    # Merge chunks
    print(f"\nMerging chunks into {output_file}...")
    all_data = []

    for i, chunk_file in enumerate(chunk_files, 1):
        print(f"  [{i}/{len(chunk_files)}] Reading {chunk_file}...", end=" ")
        try:
            df = pd.read_csv(chunk_file)
            all_data.append(df)
            print(f"✓ {len(df):,} records")
        except Exception as e:
            print(f"✗ Error: {e}")
            return

    # Combine all chunks
    print(f"\nCombining all chunks...")
    full_df = pd.concat(all_data, ignore_index=True)

    print(f"✓ Total records: {len(full_df):,}")

    # Verify against expected
    if progress['total_records']:
        expected = progress['total_records']
        actual = len(full_df)
        if actual == expected:
            print(f"✓ Record count matches expected: {expected:,}")
        else:
            print(f"⚠ Record count mismatch:")
            print(f"  Expected: {expected:,}")
            print(f"  Actual: {actual:,}")
            print(f"  Difference: {abs(expected - actual):,}")

    # Save to single file
    print(f"\nSaving to {output_file}...")
    full_df.to_csv(output_file, index=False)

    print(f"✓ Saved {len(full_df):,} records")

    # Show summary
    print("\n" + "=" * 80)
    print(f"FY{fiscal_year} MERGE COMPLETE!")
    print("=" * 80)
    print(f"✓ Output file: {output_file}")
    print(f"✓ Total records: {len(full_df):,}")
    print(f"✓ Total spending: ${full_df['check_amount'].sum():,.2f}")
    print(f"✓ File size: {full_df.memory_usage(deep=True).sum() / 1024 / 1024:.1f} MB (in memory)")

    print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

if __name__ == "__main__":
    main()
