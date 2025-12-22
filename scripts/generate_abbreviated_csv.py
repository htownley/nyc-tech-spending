#!/usr/bin/env python3
"""
Generate abbreviated version of digital_services_vendors.csv

Takes the full vendor CSV and creates an abbreviated version with:
- agencies: top 10 + count
- budget_codes: top 10 + count
- expense_categories: top 10 + count

Usage:
  python3 scripts/generate_abbreviated_csv.py
"""

import csv
import os

INPUT_FILE = 'data/outputs/digital_services_vendors.csv'
OUTPUT_FILE = 'data/outputs/digital_services_vendors_abbreviated.csv'

# Columns to truncate and their separators
TRUNCATE_CONFIG = {
    'agencies': {'separator': ', ', 'max_items': 10},
    'budget_codes': {'separator': '; ', 'max_items': 10},
    'expense_categories': {'separator': '; ', 'max_items': 10},
}


def truncate_list(value_str, separator, max_items):
    """Truncate a delimited list to max_items + count of remaining."""
    if not value_str or value_str == '':
        return value_str

    items = [item.strip() for item in value_str.split(separator)]

    if len(items) <= max_items:
        return value_str

    top = items[:max_items]
    remaining = len(items) - max_items
    return separator.join(top) + f' (+{remaining} more)'


def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found")
        return 1

    # Read input
    with open(INPUT_FILE, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    print(f"Read {len(rows)} vendors from {INPUT_FILE}")

    # Track changes
    changes = {col: 0 for col in TRUNCATE_CONFIG}

    # Process rows
    for row in rows:
        for col, config in TRUNCATE_CONFIG.items():
            if col in row:
                original = row[col]
                truncated = truncate_list(original, config['separator'], config['max_items'])
                if truncated != original:
                    changes[col] += 1
                row[col] = truncated

    # Write output
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Report
    print(f"\nTruncated columns:")
    for col, count in changes.items():
        print(f"  {col}: {count} vendors")

    # Size comparison
    orig_size = os.path.getsize(INPUT_FILE)
    new_size = os.path.getsize(OUTPUT_FILE)
    reduction = (1 - new_size / orig_size) * 100

    print(f"\nFile size: {orig_size:,} -> {new_size:,} bytes ({reduction:.1f}% reduction)")
    print(f"Saved to: {OUTPUT_FILE}")

    return 0


if __name__ == "__main__":
    exit(main())
