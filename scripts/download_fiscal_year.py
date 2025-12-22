#!/usr/bin/env python3
"""
Incremental Download of NYC Spending Data by Fiscal Year
Resume-safe: Can restart if interrupted without losing progress

Usage:
  python3 download_fiscal_year.py 2024
  python3 download_fiscal_year.py 2023
  python3 download_fiscal_year.py 2022
"""

import requests
import xml.etree.ElementTree as ET
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

API_URL = "https://www.checkbooknyc.com/api"
RECORDS_PER_API_CALL = 20000  # API max per request
CHUNK_SIZE = 100000  # Save every 100k records

def make_api_request(records_from, max_records, fiscal_year):
    """Make a single API call for spending data"""
    request_xml = f"""<request>
  <type_of_data>Spending</type_of_data>
  <records_from>{records_from}</records_from>
  <max_records>{max_records}</max_records>
  <search_criteria>
    <criteria>
      <name>fiscal_year</name>
      <type>value</type>
      <value>{fiscal_year}</value>
    </criteria>
  </search_criteria>
  <response_columns>
    <column>agency</column>
    <column>payee_name</column>
    <column>check_amount</column>
    <column>fiscal_year</column>
    <column>industry</column>
    <column>spending_category</column>
    <column>contract_id</column>
    <column>department</column>
    <column>expense_category</column>
    <column>budget_code</column>
    <column>sub_vendor</column>
    <column>associated_prime_vendor</column>
  </response_columns>
</request>"""

    response = requests.post(
        API_URL,
        data=request_xml,
        headers={'Content-Type': 'application/xml'},
        timeout=120
    )

    return response

def parse_transactions(xml_text):
    """Parse XML response and extract transactions"""
    root = ET.fromstring(xml_text)

    # Check for errors
    status = root.find('.//status/result')
    if status is not None and status.text != 'success':
        messages = root.findall('.//messages/message')
        if messages:
            for msg in messages:
                desc = msg.find('description')
                print(f"API Error: {desc.text if desc is not None else 'Unknown error'}")
        return None, 0

    # Get total record count
    record_count_elem = root.find('.//record_count')
    total_records = int(record_count_elem.text) if record_count_elem is not None else 0

    # Parse transactions
    transactions = []
    for trans in root.findall('.//spending_transactions/transaction'):
        record = {}
        for field in trans:
            record[field.tag] = field.text if field.text else ""
        transactions.append(record)

    return transactions, total_records

def load_progress(progress_file):
    """Load download progress from file"""
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            return json.load(f)
    return {
        'total_records': None,
        'last_record_downloaded': 0,
        'chunks_completed': [],
        'started_at': None,
        'last_updated': None
    }

def save_progress(progress, progress_file):
    """Save download progress to file"""
    progress['last_updated'] = datetime.now().isoformat()
    with open(progress_file, 'w') as f:
        json.dump(progress, indent=2, fp=f)

def save_chunk(chunk_records, chunk_num, fieldnames, chunks_dir):
    """Save a chunk of records to CSV"""
    chunk_file = f"{chunks_dir}/chunk_{chunk_num:04d}.csv"
    with open(chunk_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(chunk_records)
    return chunk_file

def main():
    # Get fiscal year from command line
    if len(sys.argv) < 2:
        print("Usage: python3 download_fiscal_year.py <fiscal_year>")
        print("Example: python3 download_fiscal_year.py 2024")
        sys.exit(1)

    fiscal_year = sys.argv[1]

    # Setup file paths for this fiscal year
    chunks_dir = f"fy{fiscal_year}_chunks"
    progress_file = f"download_progress_fy{fiscal_year}.json"

    print("=" * 80)
    print(f"NYC FY{fiscal_year} SPENDING - INCREMENTAL DOWNLOAD")
    print("=" * 80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Create chunks directory
    Path(chunks_dir).mkdir(exist_ok=True)

    # Load progress
    progress = load_progress(progress_file)

    if progress['last_record_downloaded'] > 0:
        print(f"\n✓ RESUMING from record {progress['last_record_downloaded']:,}")
        print(f"✓ {len(progress['chunks_completed'])} chunks already completed")
    else:
        print("\n✓ Starting fresh download")

    # Get total record count if we don't have it
    if progress['total_records'] is None:
        print(f"\nGetting total record count for FY{fiscal_year}...")
        response = make_api_request(1, 1, fiscal_year)
        if response.status_code != 200:
            print(f"✗ Error: API returned status {response.status_code}")
            return
        _, total_records = parse_transactions(response.text)

        if total_records == 0:
            print(f"✗ Error: No records found for FY{fiscal_year}")
            print(f"   Check if FY{fiscal_year} is a valid fiscal year")
            return

        progress['total_records'] = total_records
        progress['started_at'] = datetime.now().isoformat()
        save_progress(progress, progress_file)
        print(f"✓ Total records available: {total_records:,}")
    else:
        total_records = progress['total_records']
        print(f"\n✓ Total records: {total_records:,}")

    # Calculate chunks
    total_chunks = (total_records + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"✓ Total chunks: {total_chunks} (at {CHUNK_SIZE:,} records per chunk)")
    print(f"✓ Chunk directory: {chunks_dir}/\n")

    # Field names
    fieldnames = ['agency', 'payee_name', 'check_amount', 'fiscal_year', 'industry',
                  'spending_category', 'contract_id', 'department', 'expense_category', 'budget_code',
                  'sub_vendor', 'associated_prime_vendor']

    # Download chunks
    current_chunk = len(progress['chunks_completed']) + 1

    while progress['last_record_downloaded'] < total_records:
        chunk_start = progress['last_record_downloaded'] + 1
        chunk_end = min(chunk_start + CHUNK_SIZE - 1, total_records)

        print("=" * 80)
        print(f"CHUNK {current_chunk}/{total_chunks}")
        print(f"Records {chunk_start:,} to {chunk_end:,}")
        print("=" * 80)

        chunk_records = []
        records_to_download = chunk_end - chunk_start + 1
        records_in_chunk = 0

        # Download this chunk (multiple API calls of 20k each)
        current_record = chunk_start
        while current_record <= chunk_end:
            batch_size = min(RECORDS_PER_API_CALL, chunk_end - current_record + 1)

            print(f"  Fetching records {current_record:,} to {current_record + batch_size - 1:,}...", end=" ")

            try:
                response = make_api_request(current_record, batch_size, fiscal_year)

                if response.status_code == 200:
                    transactions, _ = parse_transactions(response.text)

                    if transactions:
                        chunk_records.extend(transactions)
                        records_in_chunk += len(transactions)
                        print(f"✓ {len(transactions):,} records")
                    else:
                        print("⚠ No records returned")
                        break
                else:
                    print(f"✗ Error: Status {response.status_code}")
                    print(f"  Progress saved. Run script again to resume from record {progress['last_record_downloaded'] + 1:,}")
                    return

            except Exception as e:
                print(f"✗ Error: {e}")
                print(f"  Progress saved. Run script again to resume from record {progress['last_record_downloaded'] + 1:,}")
                return

            current_record += batch_size

            # Rate limiting
            import time
            time.sleep(1)

        # Save chunk
        if chunk_records:
            chunk_file = save_chunk(chunk_records, current_chunk, fieldnames, chunks_dir)
            progress['last_record_downloaded'] = chunk_end
            progress['chunks_completed'].append(chunk_file)
            save_progress(progress, progress_file)

            print(f"\n✓ Chunk {current_chunk} saved: {chunk_file}")
            print(f"✓ Total records in chunk: {len(chunk_records):,}")
            print(f"✓ Progress: {progress['last_record_downloaded']:,}/{total_records:,} ({progress['last_record_downloaded']/total_records*100:.1f}%)")

        current_chunk += 1

    # Complete
    print("\n" + "=" * 80)
    print(f"FY{fiscal_year} DOWNLOAD COMPLETE!")
    print("=" * 80)
    print(f"✓ Total records downloaded: {progress['last_record_downloaded']:,}")
    print(f"✓ Total chunks: {len(progress['chunks_completed'])}")
    print(f"✓ Chunks saved in: {chunks_dir}/")
    print(f"\nEnd time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nNext step: Run merge script to combine all chunks")
    print(f"  python3 merge_fiscal_year.py {fiscal_year}")
    print("=" * 80)

if __name__ == "__main__":
    main()
