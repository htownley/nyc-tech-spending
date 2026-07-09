#!/usr/bin/env python3
"""
Download all checks paid to major IT resellers WITH contract purpose text.

The Checkbook Spending API exposes a contract_purpose column that the main
bulk download does not include. Reseller contract purposes usually name the
underlying product/manufacturer (e.g. "VMWARE - ELA RENEWAL"), which lets us
attribute pass-through spending to the actual technology providers.

Resume-safe: tracks completed (vendor, year) pairs in a progress file.

Usage:
  python3 scripts/download_reseller_purposes.py
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

RESELLERS = [
    "CDW GOVERNMENT LLC",
    "SHI INTERNATIONAL CORP",
    "PRESIDIO NETWORKED SOLUTIONS GROUP LLC",
    "PRESIDIO NETWORKED SOLUTIONS LLC",
    "DELL MARKETING LP",
    "WORLD WIDE TECHNOLOGY LLC",
    "GOVCONNECTION INC",
    "CARAHSOFT TECHNOLOGY CORP",
    "INSIGHT PUBLIC SECTOR INC",
]

COLUMNS = [
    "agency", "payee_name", "check_amount", "issue_date", "fiscal_year",
    "contract_id", "contract_purpose", "expense_category",
    "spending_category", "budget_code", "document_id",
]

OUTPUT_FILE = "data/raw/reseller_purposes.csv"
PROGRESS_FILE = "data/raw/reseller_purposes_progress.json"


def make_api_request(payee_name, fiscal_year, records_from, max_records):
    columns_xml = "\n".join(f"    <column>{c}</column>" for c in COLUMNS)
    request_xml = f"""<request>
  <type_of_data>Spending</type_of_data>
  <records_from>{records_from}</records_from>
  <max_records>{max_records}</max_records>
  <search_criteria>
    <criteria>
      <name>payee_name</name>
      <type>value</type>
      <value>{payee_name}</value>
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
    for attempt in range(3):
        try:
            response = requests.post(
                API_URL, data=request_xml,
                headers={"Content-Type": "application/xml"}, timeout=120,
            )
            if response.status_code == 200:
                return response.text
            print(f"    ⚠ HTTP {response.status_code}, attempt {attempt + 1}/3")
        except requests.RequestException as e:
            print(f"    ⚠ {e}, attempt {attempt + 1}/3")
        time.sleep(5)
    return None


def parse_transactions(xml_text):
    root = ET.fromstring(xml_text)
    status = root.find(".//status/result")
    if status is not None and status.text != "success":
        for msg in root.findall(".//messages/message"):
            desc = msg.find("description")
            print(f"    API Error: {desc.text if desc is not None else 'Unknown'}")
        return None, 0
    count_elem = root.find(".//record_count")
    total = int(count_elem.text) if count_elem is not None else 0
    transactions = []
    for trans in root.findall(".//spending_transactions/transaction"):
        record = {field.tag: (field.text or "") for field in trans}
        transactions.append(record)
    return transactions, total


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"completed": []}


def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def main():
    progress = load_progress()
    completed = set(tuple(p) for p in progress["completed"])

    write_header = not os.path.exists(OUTPUT_FILE)
    out = open(OUTPUT_FILE, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(out, fieldnames=COLUMNS, extrasaction="ignore")
    if write_header:
        writer.writeheader()

    for vendor in RESELLERS:
        for year in YEARS:
            if (vendor, year) in completed:
                continue
            print(f"{vendor} FY{year}...", flush=True)

            rows = []
            records_from = 1
            total = None
            while total is None or records_from <= total:
                xml_text = make_api_request(
                    vendor, year, records_from, RECORDS_PER_API_CALL)
                if xml_text is None:
                    print("    ✗ Giving up on this batch; progress saved. Re-run to resume.")
                    out.close()
                    sys.exit(1)
                transactions, total = parse_transactions(xml_text)
                if transactions is None:
                    out.close()
                    sys.exit(1)
                if total == 0:
                    break
                if not transactions:
                    print(f"    ✗ Empty batch at record {records_from:,}/{total:,}; re-run to retry.")
                    out.close()
                    sys.exit(1)
                # API name matching can be fuzzy — keep exact payee matches only
                rows.extend(t for t in transactions
                            if t.get("payee_name", "").strip() == vendor)
                records_from += len(transactions)
                time.sleep(1)

            writer.writerows(rows)
            out.flush()
            completed.add((vendor, year))
            progress["completed"] = sorted(list(c) for c in completed)
            save_progress(progress)
            print(f"    ✓ {len(rows):,} checks")

    out.close()
    print("\nDONE. Output:", OUTPUT_FILE)


if __name__ == "__main__":
    main()
