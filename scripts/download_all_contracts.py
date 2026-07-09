#!/usr/bin/env python3
"""
Download ALL registered expense contracts (FY2015-2026) from Checkbook NYC.

Contract records carry purpose text, award method, contract type, ceiling
amounts, and spent-to-date. Used to backfill purposes for spending checks
whose own contract_purpose field is empty (joined on contract_id), and for
vendor-classification verification.

Resume-safe per fiscal year. Output: data/raw/contracts_all_years.csv

Usage:
  python3 scripts/download_all_contracts.py
"""

import csv
import json
import os
import sys
import time
import xml.etree.ElementTree as ET

import requests

API_URL = "https://www.checkbooknyc.com/api"
RECORDS_PER_API_CALL = 20000
YEARS = [str(y) for y in range(2015, 2027)]

COLUMNS = [
    "prime_contract_id", "prime_vendor", "prime_contracting_agency",
    "prime_contract_purpose", "prime_contract_type", "prime_contract_industry",
    "prime_contract_award_method", "prime_contract_original_amount",
    "prime_contract_current_amount", "prime_vendor_spent_to_date",
    "prime_contract_start_date", "prime_contract_end_date",
    "prime_contract_registration_date", "prime_contract_pin",
    "prime_vendor_mwbe_category", "document_code", "parent_contract_id",
    "prime_contract_version", "year",
]

OUTPUT_FILE = "data/raw/contracts_all_years.csv"
PROGRESS_FILE = "data/raw/contracts_all_years_progress.json"


def make_api_request(fiscal_year, records_from, max_records):
    columns_xml = "\n".join(f"    <column>{c}</column>" for c in COLUMNS)
    request_xml = f"""<request>
  <type_of_data>Contracts</type_of_data>
  <records_from>{records_from}</records_from>
  <max_records>{max_records}</max_records>
  <search_criteria>
    <criteria>
      <name>status</name>
      <type>value</type>
      <value>registered</value>
    </criteria>
    <criteria>
      <name>category</name>
      <type>value</type>
      <value>expense</value>
    </criteria>
    <criteria>
      <name>fiscal_year</name>
      <type>value</type>
      <value>{fiscal_year}</value>
    </criteria>
  </search_criteria>
  <response_columns>
{columns_xml}
  </response_columns>
</request>"""
    for attempt in range(5):
        try:
            response = requests.post(
                API_URL, data=request_xml,
                headers={"Content-Type": "application/xml"}, timeout=120,
            )
            if response.status_code == 200:
                # The API occasionally returns truncated XML with HTTP 200;
                # verify it parses before accepting it
                try:
                    return parse_contracts(response.text)
                except ET.ParseError as e:
                    print(f"    ⚠ Truncated/malformed XML ({e}), attempt {attempt + 1}/5")
            else:
                print(f"    ⚠ HTTP {response.status_code}, attempt {attempt + 1}/5")
        except requests.RequestException as e:
            print(f"    ⚠ {e}, attempt {attempt + 1}/5")
        time.sleep(10)
    return None, 0


def parse_contracts(xml_text):
    root = ET.fromstring(xml_text)
    status = root.find(".//status/result")
    if status is not None and status.text != "success":
        for msg in root.findall(".//messages/message"):
            desc = msg.find("description")
            print(f"    API Error: {desc.text if desc is not None else 'Unknown'}")
        return None, 0
    count_elem = root.find(".//record_count")
    total = int(count_elem.text) if count_elem is not None else 0
    records = []
    for trans in root.findall(".//contract_transactions/transaction"):
        records.append({field.tag: (field.text or "") for field in trans})
    return records, total


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"completed_years": []}


def clean_partial_years(completed_years):
    """Drop rows from any year that wasn't marked complete (crash leftovers)."""
    if not os.path.exists(OUTPUT_FILE):
        return
    keep = set(completed_years)
    with open(OUTPUT_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    kept = [r for r in rows if r.get("year") in keep]
    if len(kept) != len(rows):
        print(f"Removing {len(rows) - len(kept):,} rows from incomplete years")
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(kept)


def main():
    progress = load_progress()
    clean_partial_years(progress["completed_years"])

    write_header = not os.path.exists(OUTPUT_FILE)
    out = open(OUTPUT_FILE, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(out, fieldnames=COLUMNS, extrasaction="ignore")
    if write_header:
        writer.writeheader()

    for year in YEARS:
        if year in progress["completed_years"]:
            continue
        print(f"FY{year}...", flush=True)

        records_from = 1
        total = None
        year_rows = []
        while total is None or records_from <= total:
            records, total = make_api_request(year, records_from, RECORDS_PER_API_CALL)
            if records is None:
                print("    ✗ Giving up; progress saved. Re-run to resume.")
                out.close()
                sys.exit(1)
            if total == 0:
                break
            if not records:
                print(f"    ✗ Empty batch at record {records_from:,}/{total:,}; re-run to retry.")
                out.close()
                sys.exit(1)
            year_rows.extend(records)
            records_from += len(records)
            time.sleep(1)

        # Only write once the whole year is in hand, so a crash can't
        # leave partial years in the output
        writer.writerows(year_rows)
        out.flush()
        progress["completed_years"].append(year)
        with open(PROGRESS_FILE, "w") as f:
            json.dump(progress, f, indent=2)
        print(f"    ✓ {len(year_rows):,} contracts")

    out.close()
    print("\nDONE. Output:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
