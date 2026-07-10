#!/usr/bin/env python3
"""Generate force-directed graph + Sankey visualization of NYC tech spending."""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from analyze_passthrough import attribute

PROJECT_ROOT = Path(__file__).parent.parent
CSV_PATH     = PROJECT_ROOT / "data" / "outputs" / "digital_services_vendors.csv"
OTI_CSV_PATH = PROJECT_ROOT / "data" / "outputs" / "oti_vendors_for_classification.csv"
RAW_DIR      = PROJECT_ROOT / "data" / "raw"
RESELLER_CSV = PROJECT_ROOT / "data" / "raw" / "reseller_purposes.csv"
OUTPUT_PATH  = PROJECT_ROOT / "graph.html"

PRIVACY_PLACEHOLDER = "N/A (PRIVACY/SECURITY)"
OTI_AGENCY = "Department of Information Technology and Telecommunications"


def parse_spending(val):
    try:
        return float(val.replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def discover_raw_files():
    """Find all fy*_full.csv files and return sorted list of (year, path)."""
    files = sorted(RAW_DIR.glob("fy*_full.csv"))
    results = []
    for f in files:
        year = int(f.stem.replace("fy", "").replace("_full", ""))
        results.append((year, f))
    return results


def build_graph_data():
    """Build per-period graph data for all available fiscal years."""

    # ── Step 1: vendor metadata from both CSVs ───────────────────────────────
    vendor_meta = {}

    main_df = pd.read_csv(CSV_PATH)
    for _, row in main_df.iterrows():
        vendor_name = str(row["vendor"]).strip()
        fy2025 = parse_spending(str(row["fy2025_spending"]))
        if fy2025 <= 0:
            continue
        vendor_meta[vendor_name] = {
            "classification": str(row["is_digital"]).strip(),
            "description": str(row.get("description", "")).strip(),
        }

    oti_vendor_names = set()
    oti_df = pd.read_csv(OTI_CSV_PATH)
    for _, row in oti_df.iterrows():
        vendor_name = str(row["vendor"]).strip()
        if vendor_name in vendor_meta:
            continue
        fy2025 = parse_spending(str(row["fy2025_spending"]))
        if fy2025 <= 0:
            continue
        vendor_meta[vendor_name] = {
            "classification": str(row["category"]).strip(),
            "description": str(row.get("rationale", "")).strip(),
        }
        oti_vendor_names.add(vendor_name)

    vendor_names = set(vendor_meta.keys())
    print(f"Tracking {len(vendor_names)} vendors")

    # ── Step 2: read all raw files and aggregate per-year ────────────────────
    raw_files = discover_raw_files()
    years = [y for y, _ in raw_files]
    print(f"Found fiscal years: {years}")

    # per_year_agg[year] = DataFrame with columns [payee_name, agency, spend]
    per_year_agg = {}
    for year, path in raw_files:
        print(f"  Reading FY{year} ({path.stat().st_size // 1_000_000} MB)...")
        df = pd.read_csv(path, usecols=["payee_name", "agency", "check_amount"])
        df = df[df["payee_name"].isin(vendor_names)]
        df["check_amount"] = pd.to_numeric(df["check_amount"], errors="coerce").fillna(0)
        agg = (
            df.groupby(["payee_name", "agency"])["check_amount"]
            .sum()
            .reset_index()
            .rename(columns={"check_amount": "spend"})
        )
        per_year_agg[year] = agg[agg["spend"] > 0]
        print(f"    → {len(per_year_agg[year])} vendor-agency pairs")

    # ── Step 2b: pass-through maker attribution (reseller → maker) ──────────
    # Reseller checks carry purpose text naming the underlying product;
    # attribute() maps purposes to makers (keyword pass + judgment overrides).
    # Unattributed rows are dropped here: each reseller's unidentified remainder
    # is computed per period against its viz total, so every column conserves $.
    maker_by_year = None
    maker_by_year_oti = None
    reseller_names = set()
    if RESELLER_CSV.exists():
        rp = pd.read_csv(RESELLER_CSV)
        rp["check_amount"] = pd.to_numeric(rp["check_amount"], errors="coerce").fillna(0)
        attr_map = {p: attribute(p)[0] for p in rp["contract_purpose"].fillna("").unique()}
        rp["maker"] = rp["contract_purpose"].fillna("").map(attr_map)
        reseller_names = set(rp["payee_name"].unique())
        att = rp[rp["maker"] != "Unattributed"]
        maker_by_year = (
            att.groupby(["payee_name", "maker", "fiscal_year"])["check_amount"]
            .sum().reset_index()
        )
        att_oti = att[att["agency"] == OTI_AGENCY]
        maker_by_year_oti = (
            att_oti.groupby(["payee_name", "maker", "fiscal_year"])["check_amount"]
            .sum().reset_index()
        )
        print(f"Pass-through makers: {len(reseller_names)} resellers → "
              f"{maker_by_year['maker'].nunique()} makers")
    else:
        print("No reseller_purposes.csv — skipping maker layer")

    # Maker classifications (human-reasoned, reviewable): column 3 uses the
    # same taxonomy and palette as column 2. Any attributed maker missing
    # from the CSV renders gray — the warning below flags it for review.
    maker_class = {}
    mc_path = PROJECT_ROOT / "data" / "outputs" / "maker_classifications.csv"
    if mc_path.exists():
        mc = pd.read_csv(mc_path)
        maker_class = {
            row["maker"]: {"c": row["classification"], "r": row["rationale"]}
            for _, row in mc.iterrows()
        }
    if maker_by_year is not None:
        known = set(maker_class) | {"Multiple makers"}
        missing = sorted(set(maker_by_year["maker"].unique()) - known)
        if missing:
            print(f"⚠ {len(missing)} attributed makers missing from "
                  f"maker_classifications.csv (will render gray): {missing}")

    # Vendors that are themselves the maker, under the maker dictionary's
    # canonical name — their direct spend merges into the same column-3 node
    # as their pass-through spend. Everything else that isn't a reseller flows
    # through to a maker named after itself.
    VENDOR_MAKER_IDENTITY = {
        "MICROSOFT CORPORATION": "Microsoft",
        "INTERNATIONAL BUSINESS MACHINES CORP": "IBM",
        "Motorola Solutions, Inc": "Motorola",
        "MOTOROLA SOLUTIONS CONNECTIVITY INC": "Motorola",
        "MTX GROUP INC": "MTX Group",
        "MTX B2B SOLUTIONS LLC": "MTX Group",
        "NICE SYSTEMS INCORPORATED": "NICE Systems",
        "SAS INSTITUTE INC.": "SAS Institute",
        "WORKDAY INC": "Workday",
        "DELOITTE CONSULTING LLP": "Deloitte",
        # Deliberately NOT mapped: GENESYS CONSULTING SERVICES INC (an Albany
        # IT staffing firm, unrelated to Genesys the CX platform company)
    }

    # ── Step 3: define periods ───────────────────────────────────────────────
    periods = {}
    for year in years:
        periods[f"FY{year}"] = [year]

    if len(years) >= 5:
        periods["Last 5 yrs"] = years[-5:]
    if len(years) >= 10:
        periods["Last 10 yrs"] = years[-10:]

    # ── Step 4: build nodes + links for each period ──────────────────────────
    all_period_data = {}

    for period_name, period_years in periods.items():
        # Combine aggregations for the period's years
        combined = pd.concat(
            [per_year_agg[y] for y in period_years if y in per_year_agg],
            ignore_index=True,
        )
        agg = (
            combined.groupby(["payee_name", "agency"])["spend"]
            .sum()
            .reset_index()
        )
        agg = agg[agg["spend"] > 0]

        citywide = agg.groupby("payee_name")["spend"].sum()
        oti_spend_by_vendor = (
            agg[agg["agency"] == OTI_AGENCY]
            .set_index("payee_name")["spend"]
        )

        nodes = []
        links = []
        agency_seen = set()

        for vendor_name, meta in vendor_meta.items():
            total_spend = float(citywide.get(vendor_name, 0))
            if total_spend <= 0:
                continue
            oti_s = float(oti_spend_by_vendor.get(vendor_name, 0))
            nodes.append({
                "id": vendor_name,
                "type": "vendor",
                "classification": meta["classification"],
                "spending": round(total_spend, 2),
                "oti_spending": round(oti_s, 2),
                "description": meta["description"],
            })

        active_vendors = {n["id"] for n in nodes}

        for _, row in agg.iterrows():
            vendor_name = row["payee_name"]
            agency = row["agency"]
            spend = round(float(row["spend"]), 2)

            if vendor_name not in active_vendors:
                continue

            if agency not in agency_seen:
                agency_seen.add(agency)
                nodes.append({
                    "id": agency,
                    "type": "agency",
                    "classification": "agency",
                    "spending": 0,
                    "oti_spending": 0,
                    "radius": 9,
                    "description": "",
                })

            links.append({"source": vendor_name, "target": agency, "spend": spend})

        # Counts for tooltips
        agency_vendor_counts = {}
        vendor_agency_counts = {}
        for link in links:
            agency_vendor_counts[link["target"]] = agency_vendor_counts.get(link["target"], 0) + 1
            vendor_agency_counts[link["source"]] = vendor_agency_counts.get(link["source"], 0) + 1

        vendor_count = 0
        agency_count = 0
        for node in nodes:
            if node["type"] == "agency":
                node["vendor_count"] = agency_vendor_counts.get(node["id"], 0)
                agency_count += 1
            else:
                node["agency_count"] = vendor_agency_counts.get(node["id"], 0)
                vendor_count += 1

        # Maker links: every vendor's full spend flows to column 3 so all three
        # columns total identically. Resellers decompose into attributed makers
        # plus an "Unidentified purchases" remainder; everyone else flows
        # through to a maker named after itself (or its canonical maker name).
        def build_maker_links(table, spend_key):
            reseller_period = {}
            if table is not None:
                mk = table[table["fiscal_year"].isin(period_years)]
                grouped = mk.groupby(["payee_name", "maker"])["check_amount"].sum()
                for (payee, maker), amt in grouped.items():
                    reseller_period.setdefault(payee, []).append([maker, float(amt)])

            out = []
            for node in nodes:
                if node["type"] != "vendor":
                    continue
                total = node[spend_key]
                if total <= 0.01:
                    continue
                vname = node["id"]
                if vname in reseller_names:
                    flows = reseller_period.get(vname, [])
                    attributed = sum(a for _, a in flows)
                    if attributed > total and attributed > 0:
                        # Small drift between the raw download and the reseller
                        # pull (late records) — scale down to conserve totals
                        flows = [[m, a * total / attributed] for m, a in flows]
                        attributed = total
                    for maker, amt in flows:
                        if amt > 0.01:
                            out.append({"source": vname, "target": maker,
                                        "spend": round(amt, 2), "self": False})
                    remainder = total - attributed
                    if remainder > 0.01:
                        out.append({"source": vname, "target": "Unidentified purchases",
                                    "spend": round(remainder, 2), "self": False})
                else:
                    maker = VENDOR_MAKER_IDENTITY.get(vname, vname)
                    out.append({"source": vname, "target": maker,
                                "spend": round(total, 2), "self": True})

            # Conservation invariant: per vendor, outflow == column-2 total
            outflow = {}
            for l in out:
                outflow[l["source"]] = outflow.get(l["source"], 0) + l["spend"]
            for node in nodes:
                if node["type"] == "vendor" and node[spend_key] > 0.01:
                    diff = abs(outflow.get(node["id"], 0) - node[spend_key])
                    assert diff <= 1.0, (
                        f"{period_name} {node['id']}: maker outflow off by ${diff:,.2f}")
            return out

        maker_links = build_maker_links(maker_by_year, "spending")
        maker_links_oti = build_maker_links(maker_by_year_oti, "oti_spending")

        all_period_data[period_name] = {
            "nodes": nodes, "links": links,
            "maker_links": maker_links, "maker_links_oti": maker_links_oti,
        }
        print(f"  {period_name}: {vendor_count} vendors, {agency_count} agencies, "
              f"{len(links)} links, {len(maker_links)} maker links "
              f"({len(maker_links_oti)} OTI)")

    # ── Step 5: build timeseries data (vendor → year → spend) ────────────────
    timeseries = {}
    for vendor_name, meta in vendor_meta.items():
        yearly = {}
        oti_yearly = {}
        for year in years:
            agg = per_year_agg[year]
            vendor_rows = agg[agg["payee_name"] == vendor_name]
            total = float(vendor_rows["spend"].sum())
            oti = float(
                vendor_rows[vendor_rows["agency"] == OTI_AGENCY]["spend"].sum()
            )
            if total > 0:
                yearly[year] = round(total, 2)
            if oti > 0:
                oti_yearly[year] = round(oti, 2)
        if yearly:
            timeseries[vendor_name] = {
                "classification": meta["classification"],
                "description": meta["description"],
                "yearly": yearly,
                "oti_yearly": oti_yearly,
            }

    print(f"Timeseries: {len(timeseries)} vendors across {len(years)} years")

    # ── Step 5b: maker total series (direct + purpose-verified pass-through) ─
    # One extra Trends line per attributed maker: direct vendor payments plus
    # reseller checks whose purpose text names the maker. Unidentified reseller
    # spend and multi-maker bundles are excluded — verified dollars only.
    if maker_by_year is not None:
        mk_y = maker_by_year[maker_by_year["maker"] != "Multiple makers"]
        attr_yearly = mk_y.groupby(["maker", "fiscal_year"])["check_amount"].sum()
        attr_yearly_oti = maker_by_year_oti[
            maker_by_year_oti["maker"] != "Multiple makers"
        ].groupby(["maker", "fiscal_year"])["check_amount"].sum()

        identity_by_maker = {}
        for vend, mk in VENDOR_MAKER_IDENTITY.items():
            identity_by_maker.setdefault(mk, []).append(vend)

        n_totals = 0
        for m in sorted({m for m, _ in attr_yearly.index}):
            direct_vendors = [v for v in identity_by_maker.get(m, []) if v in timeseries]
            yearly, oti_yearly = {}, {}
            for yr in years:
                tot = float(attr_yearly.get((m, yr), 0.0))
                tot += sum(timeseries[v]["yearly"].get(yr, 0) for v in direct_vendors)
                if tot > 0:
                    yearly[yr] = round(tot, 2)
                oti = float(attr_yearly_oti.get((m, yr), 0.0))
                oti += sum(timeseries[v]["oti_yearly"].get(yr, 0) for v in direct_vendors)
                if oti > 0:
                    oti_yearly[yr] = round(oti, 2)
            if not yearly:
                continue
            name = f"{m} (incl. pass-through)"
            timeseries[name] = {
                "classification": maker_class.get(m, {}).get("c", "Mixed"),
                "description": "Direct vendor payments plus purpose-verified reseller "
                               "pass-through. Unidentified reseller spend excluded.",
                "yearly": yearly,
                "oti_yearly": oti_yearly,
                "maker_total": True,
                "paired": direct_vendors,
            }
            for v in direct_vendors:
                timeseries[v]["paired"] = [name]
            n_totals += 1
        print(f"Maker total series: {n_totals} added to Trends")

    return all_period_data, list(periods.keys()), timeseries, years, maker_class


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NYC Tech Spending — Vendor-Agency Network</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@300;400&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: #080c14;
    color: #c8d4e8;
    font-family: 'DM Mono', monospace;
    overflow: hidden;
    height: 100vh;
    width: 100vw;
  }

  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image: radial-gradient(circle, rgba(90,159,212,0.12) 1px, transparent 1px);
    background-size: 28px 28px;
    pointer-events: none;
    z-index: 0;
  }

  #canvas, #sankey-canvas {
    position: fixed;
    inset: 0;
    z-index: 1;
  }

  #ui {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 10;
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 14px 22px;
    background: linear-gradient(180deg, rgba(8,12,20,0.98) 0%, rgba(8,12,20,0.0) 100%);
    pointer-events: none;
  }

  #title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 26px;
    letter-spacing: 2px;
    color: #e8a030;
    text-shadow: 0 0 20px rgba(232,160,48,0.4);
    white-space: nowrap;
    pointer-events: none;
  }

  #view-toggle {
    display: flex;
    gap: 2px;
    pointer-events: all;
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 4px;
    overflow: hidden;
    flex-shrink: 0;
  }

  .view-btn {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.5px;
    padding: 5px 14px;
    border: none;
    background: rgba(8,12,20,0.8);
    color: #5a6a80;
    cursor: pointer;
    transition: all 0.15s;
    text-transform: uppercase;
  }

  .view-btn:hover:not(.active) {
    color: #8a9ab5;
    background: rgba(255,255,255,0.04);
  }

  .view-btn.active {
    background: rgba(232,160,48,0.15);
    color: #e8a030;
  }

  #ui-sep {
    width: 1px;
    height: 18px;
    background: rgba(255,255,255,0.1);
    pointer-events: none;
    flex-shrink: 0;
  }

  #controls {
    display: flex;
    align-items: center;
    gap: 10px;
    pointer-events: all;
    flex-wrap: wrap;
  }

  #period-select, #filter-select {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.5px;
    padding: 5px 10px;
    border: 1px solid rgba(255,255,255,0.15);
    background: rgba(8,12,20,0.8);
    color: #c8d4e8;
    cursor: pointer;
    border-radius: 3px;
    outline: none;
    transition: border-color 0.15s;
  }
  #period-select:hover, #filter-select:hover { border-color: rgba(232,160,48,0.5); }
  #period-select option, #filter-select option { background: #0f1822; color: #c8d4e8; }

  #slider-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    color: #6a7a95;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  #oti-toggle, #maker-toggle {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.15);
    color: #7a8a9f;
    padding: 4px 10px;
    border-radius: 3px;
    cursor: pointer;
    letter-spacing: 0.5px;
    margin-left: 8px;
    transition: all 0.15s;
  }
  #oti-toggle:hover { border-color: rgba(90,159,212,0.5); color: #5a9fd4; }
  #oti-toggle.active {
    background: rgba(90,159,212,0.15);
    border-color: #5a9fd4;
    color: #5a9fd4;
  }
  #maker-toggle { display: none; }
  #maker-toggle:hover { border-color: rgba(90,159,212,0.5); color: #5a9fd4; }
  #maker-toggle.active {
    background: rgba(90,159,212,0.15);
    border-color: #5a9fd4;
    color: #5a9fd4;
  }

  #threshold-slider {
    -webkit-appearance: none;
    width: 160px;
    height: 3px;
    background: rgba(255,255,255,0.1);
    border-radius: 2px;
    outline: none;
    cursor: pointer;
  }

  #threshold-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #e8a030;
    cursor: pointer;
    box-shadow: 0 0 6px rgba(232,160,48,0.6);
  }

  #threshold-label { color: #e8a030; min-width: 52px; font-size: 11px; }

  #search-wrap {
    position: relative;
    display: inline-flex;
    align-items: center;
  }
  #search-input {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.15);
    color: #c8d4e8;
    padding: 4px 10px;
    border-radius: 3px;
    width: 160px;
    outline: none;
    transition: border-color 0.15s;
  }
  #search-input::placeholder { color: #4a5a6a; }
  #search-input:focus { border-color: rgba(90,159,212,0.5); }
  #search-dropdown {
    display: none;
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    width: 260px;
    background: #0f1822;
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 3px;
    z-index: 100;
    max-height: 240px;
    overflow-y: auto;
  }
  .search-result {
    padding: 6px 10px;
    font-size: 11px;
    color: #c8d4e8;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }
  .search-result:hover { background: rgba(255,255,255,0.06); }
  .search-result-type {
    font-size: 9px;
    color: #4a5a6a;
    flex-shrink: 0;
  }

  /* Bottom chrome bar: legend + notes left, stats right. Own background so
     the full-height chart never collides with it. */
  #legend {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    min-height: 42px;
    z-index: 10;
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    align-items: center;
    align-content: center;
    gap: 4px 14px;
    padding: 4px 280px 4px 22px;
    background: rgba(8,12,20,0.94);
    border-top: 1px solid rgba(255,255,255,0.07);
    font-size: 10px;
    color: #6a7a95;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .legend-item { display: flex; align-items: center; gap: 7px; white-space: nowrap; }
  .legend-dot { border-radius: 50%; flex-shrink: 0; }
  #legend-maker-group { display: contents; }

  #stats {
    position: fixed;
    bottom: 0;
    right: 22px;
    height: 42px;
    z-index: 11;
    display: flex;
    align-items: center;
    gap: 16px;
    font-size: 10px;
    color: #3a4a5f;
    letter-spacing: 0.3px;
  }

  #stats span { color: #5a6a80; }

  #tooltip {
    position: fixed;
    z-index: 20;
    background: rgba(10,15,26,0.96);
    border: 1px solid rgba(90,159,212,0.25);
    border-radius: 5px;
    padding: 10px 14px;
    font-size: 12px;
    line-height: 1.6;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.12s;
    max-width: 280px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.6);
  }

  #tooltip.visible { opacity: 1; }

  .tt-name {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 16px;
    letter-spacing: 1px;
    color: #e8d4a8;
    margin-bottom: 4px;
    line-height: 1.2;
  }

  .tt-type-vendor       { color: #e8a030; }
  .tt-type-mixed        { color: #d4624a; }
  .tt-type-hardware     { color: #7c6af0; }
  .tt-type-nontechnical { color: #4a9a72; }
  .tt-type-internal     { color: #5a7a8a; }
  .tt-type-agency       { color: #5a9fd4; }
  .tt-row { color: #7a8a9f; }
  .tt-row span { color: #aabdd0; }

  #trends-canvas { position: fixed; inset: 0; z-index: 1; }

  .trends-axis text {
    font-family: 'DM Mono', monospace;
    font-size: 12px;
    fill: #8a9ab5;
  }
  .trends-axis line, .trends-axis path { stroke: rgba(255,255,255,0.12); }
  .trends-grid line { stroke: rgba(255,255,255,0.04); }
  .trends-grid path { stroke: none; }
  .trend-line { fill: none; stroke-width: 1.5; stroke-opacity: 0.25; transition: stroke-opacity 0.15s, stroke-width 0.15s; }
  .trend-line.highlighted { stroke-opacity: 1; stroke-width: 2.5; filter: url(#trends-glow); }
  .trend-line.dimmed { stroke-opacity: 0.05; stroke-width: 1; }
  .trend-dot { stroke: #080c14; stroke-width: 1.5; }

  #trends-vendor-list {
    position: fixed;
    top: 56px;
    right: 16px;
    bottom: 16px;
    width: 240px;
    z-index: 10;
    overflow-y: auto;
    display: none;
  }
  .tv-item {
    font-family: 'DM Mono', monospace;
    font-size: 10px;
    padding: 4px 8px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    color: #5a6a80;
    border-radius: 2px;
    transition: background 0.1s;
  }
  .tv-item:hover { background: rgba(255,255,255,0.04); }
  .tv-item.active { color: #c8d4e8; }
  .tv-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }

  /* Sankey-specific */
  .sk-label {
    paint-order: stroke;
    stroke: #080c14;
    stroke-width: 2.5px;
    stroke-linejoin: round;
  }

  .sk-label { pointer-events: none; }
</style>
</head>
<body>

<div id="ui">
  <div id="title">NYC TECH SPENDING</div>

  <div id="view-toggle">
    <button class="view-btn active" data-view="network">Network</button>
    <button class="view-btn" data-view="sankey">Sankey</button>
    <button class="view-btn" data-view="trends">Trends</button>
  </div>

  <div id="ui-sep"></div>

  <div id="controls">
    <select id="period-select"></select>
    <select id="filter-select">
      <option value="all">All</option>
      <option value="digital">Digital</option>
      <option value="mixed">Mixed</option>
      <option value="hardware">Hardware</option>
      <option value="nontechnical">Nontechnical</option>
      <option value="internal">Internal</option>
    </select>
    <div id="search-wrap">
      <input type="text" id="search-input" placeholder="Search vendors &amp; agencies&hellip;" autocomplete="off">
      <div id="search-dropdown"></div>
    </div>
    <button id="oti-toggle">OTI only</button>
    <button id="maker-toggle" class="active">Makers: on</button>
    <div id="slider-wrap">
      Min spend:
      <input type="range" id="threshold-slider" min="0" max="100" value="0" step="1">
      <span id="threshold-label">$0M</span>
    </div>
  </div>
</div>

<svg id="canvas"></svg>
<svg id="sankey-canvas" style="display:none"></svg>
<svg id="trends-canvas" style="display:none"></svg>

<div id="tooltip">
  <div class="tt-name" id="tt-name"></div>
  <div id="tt-body"></div>
</div>

<div id="legend">
  <div class="legend-item">
    <div class="legend-dot" style="width:12px;height:12px;background:#e8a030;box-shadow:0 0 6px rgba(232,160,48,0.5)"></div>
    Vendor (Digital)
  </div>
  <div class="legend-item">
    <div class="legend-dot" style="width:12px;height:12px;background:#d4624a;box-shadow:0 0 6px rgba(212,98,74,0.5)"></div>
    Vendor (Mixed)
  </div>
  <div class="legend-item">
    <div class="legend-dot" style="width:12px;height:12px;background:#7c6af0;box-shadow:0 0 6px rgba(124,106,240,0.5)"></div>
    Vendor (Hardware)
  </div>
  <div class="legend-item">
    <div class="legend-dot" style="width:12px;height:12px;background:#4a9a72;box-shadow:0 0 6px rgba(74,154,114,0.4)"></div>
    Vendor (Nontechnical)
  </div>
  <div class="legend-item">
    <div class="legend-dot" style="width:12px;height:12px;background:#5a7a8a;box-shadow:0 0 6px rgba(90,122,138,0.4)"></div>
    Vendor (Internal)
  </div>
  <div class="legend-item">
    <div class="legend-dot" style="width:12px;height:12px;background:rgba(90,159,212,0.06);border:1.5px solid #5a9fd4;box-shadow:0 0 6px rgba(90,159,212,0.4)"></div>
    Agency
  </div>
  <div id="legend-maker-group" style="display:none">
    <div class="legend-item">
      <div class="legend-dot" style="width:12px;height:12px;background:#5a6472;box-shadow:0 0 6px rgba(90,100,114,0.4)"></div>
      Unidentified
    </div>
  </div>
  <div class="legend-item" id="legend-size-note" style="border-left:1px solid rgba(255,255,255,0.12);padding-left:16px;color:#4a5a72">
    Node size &#8733; period spending
  </div>
  <div class="legend-item" id="legend-sankey-note" style="border-left:1px solid rgba(255,255,255,0.12);padding-left:16px;color:#4a5a72;display:none">
    Bar height &amp; band width &#8733; period spend &nbsp;&middot;&nbsp; scroll to zoom
  </div>
</div>

<div id="stats">
  <div>Vendors: <span id="stat-vendors">&#8212;</span></div>
  <div>Agencies: <span id="stat-agencies">&#8212;</span></div>
  <div>Connections: <span id="stat-links">&#8212;</span></div>
</div>


<div id="trends-vendor-list"></div>

<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/d3-sankey@0.12.3/dist/d3-sankey.min.js"></script>
<script>
const PERIOD_DATA = __PERIOD_DATA__;
const PERIOD_KEYS = __PERIOD_KEYS__;
const TIMESERIES = __TIMESERIES_DATA__;
const ALL_YEARS = __ALL_YEARS__;
// Maker → vendor-taxonomy classification (from data/outputs/maker_classifications.csv)
const MAKER_CLASS = __MAKER_CLASS__;

let currentPeriod = PERIOD_KEYS[PERIOD_KEYS.length - 1]; // default to latest single year
// Pick latest single FY as default (last key before multi-year entries)
for (let i = PERIOD_KEYS.length - 1; i >= 0; i--) {
  if (PERIOD_KEYS[i].startsWith('FY')) { currentPeriod = PERIOD_KEYS[i]; break; }
}
let RAW_NODES = PERIOD_DATA[currentPeriod].nodes;
let RAW_LINKS = PERIOD_DATA[currentPeriod].links;

// Populate period picker
const periodSelect = document.getElementById('period-select');
PERIOD_KEYS.forEach(k => {
  const opt = document.createElement('option');
  opt.value = k; opt.textContent = k;
  if (k === currentPeriod) opt.selected = true;
  periodSelect.appendChild(opt);
});

// ─── Color helpers ────────────────────────────────────────────────────────────
const VENDOR_COLORS = {
  Digital:      '#e8a030',
  Mixed:        '#d4624a',
  Hardware:     '#7c6af0',
  Nontechnical: '#4a9a72',
  Internal:     '#5a7a8a',
};
const VENDOR_STROKES = {
  Digital:      'rgba(232,160,48,0.3)',
  Mixed:        'rgba(212,98,74,0.3)',
  Hardware:     'rgba(124,106,240,0.3)',
  Nontechnical: 'rgba(74,154,114,0.3)',
  Internal:     'rgba(90,122,138,0.3)',
};
// Dollar formatter: billions get $X.XXB, millions $X.XM, small values $XK
function fmtUSD(v) {
  if (v >= 1e9) return '$' + (v / 1e9).toFixed(2) + 'B';
  if (v >= 1e6) return '$' + (v / 1e6).toFixed(1) + 'M';
  if (v > 0)    return '$' + Math.round(v / 1e3) + 'K';
  return '$0';
}

// Makers use the same taxonomy palette as vendors. Gray is reserved for
// "we can't say": unidentified purchases, multi-maker bundles, slider rollup.
const MAKER_GRAY = '#5a6472';
function nodeColor(d)  {
  if (d.type === 'agency') return '#5a9fd4';
  if (d.type === 'maker') {
    return VENDOR_COLORS[d.classification] || MAKER_GRAY;
  }
  return VENDOR_COLORS[d.classification] || '#d4624a';
}
function nodeStroke(d) { return d.type === 'agency' ? '#5a9fd4' : (VENDOR_STROKES[d.classification] || 'rgba(212,98,74,0.3)'); }

// ─── State ────────────────────────────────────────────────────────────────────
let activeFilter = 'all';
let thresholdM = 0;
let currentView = 'network';
let isOtiMode = false;
let showMakers = true;   // third sankey layer: reseller → underlying maker
let pinnedNodes = new Set();
let lockedHighlight = null;  // node id currently click-locked, or null
let netNodes = [];           // live simulation node objects (have .x/.y after tick)

const OTI_AGENCY = 'Department of Information Technology and Telecommunications';

function activeSpend(node) {
  return isOtiMode ? (node.oti_spending || 0) : node.spending;
}
function nodeRadius(spendingDollars) {
  const m = spendingDollars / 1e6;
  return 3 + Math.sqrt(m) * 3;
}
function maxVendorSpendM() {
  return Math.max(...RAW_NODES.filter(n => n.type === 'vendor').map(n => activeSpend(n) / 1e6));
}
let simulation = null;

const W = window.innerWidth, H = window.innerHeight;
// MAX_M is computed dynamically — see maxVendorSpendM()

// ─── Shared: filter logic ─────────────────────────────────────────────────────
function vendorVisible(node) {
  if (node.type === 'agency') return true;
  if (isOtiMode && !node.oti_spending) return false;
  const filterMap = { digital: 'Digital', mixed: 'Mixed', hardware: 'Hardware', nontechnical: 'Nontechnical', internal: 'Internal' };
  if (filterMap[activeFilter] && node.classification !== filterMap[activeFilter]) return false;
  if (activeSpend(node) < thresholdM * 1e6) return false;
  return true;
}
function activeLinks() {
  return isOtiMode ? RAW_LINKS.filter(l => (l.target.id ?? l.target) === OTI_AGENCY) : RAW_LINKS;
}

function getFilteredData() {
  const visibleVendorIds = new Set(
    RAW_NODES.filter(n => n.type === 'vendor' && vendorVisible(n)).map(n => n.id)
  );
  const filteredLinks = activeLinks().filter(l => visibleVendorIds.has(l.source.id ?? l.source));
  const connectedAgencies = new Set(filteredLinks.map(l => l.target.id ?? l.target));
  const nodes = RAW_NODES
    .filter(n => n.type === 'vendor' ? visibleVendorIds.has(n.id) : connectedAgencies.has(n.id))
    .map(n => ({ ...n }));
  const links = filteredLinks.map(l => ({
    source: l.source.id ?? l.source,
    target: l.target.id ?? l.target,
  }));
  return { nodes, links, visibleVendorIds, connectedAgencies };
}

function updateStats(nodes, links) {
  document.getElementById('stat-vendors').textContent   = nodes.filter(n => n.type === 'vendor').length;
  document.getElementById('stat-agencies').textContent  = nodes.filter(n => n.type === 'agency').length;
  document.getElementById('stat-links').textContent     = links.length;
}

// ─── Tooltip ──────────────────────────────────────────────────────────────────
const tooltip = document.getElementById('tooltip');
const ttName  = document.getElementById('tt-name');
const ttBody  = document.getElementById('tt-body');

function showTooltip(d, event) {
  ttName.textContent = d.label || d.id;
  if (d.type === 'maker') {
    ttName.className = 'tt-name';
    ttName.style.color = nodeColor(d);
    const fm = fmtUSD;
    const rows = [`<div class="tt-row">${currentPeriod} total: <span>${fm(d.spending)}</span></div>`];
    if (d.direct_spend > 0) {
      rows.push(`<div class="tt-row">Paid directly as vendor: <span>${fm(d.direct_spend)}</span></div>`);
    }
    if (d.via_spend > 0) {
      rows.push(`<div class="tt-row">Via ${d.via_count} reseller${d.via_count > 1 ? 's' : ''}: <span>${fm(d.via_spend)}</span></div>`);
    }
    let note;
    if (d.classification === 'unidentified') {
      note = 'Reseller checks whose purpose text names no product/maker (mostly task orders & POs).';
    } else if (d.classification === 'other') {
      note = 'Makers whose total falls below the min-spend slider, rolled up so every dollar stays visible.';
    } else if (d.via_spend > 0) {
      note = 'Reseller-routed dollars are attributed from check purpose text; for that portion the maker is not the payee.';
    } else {
      note = 'This vendor is its own maker — spend flows through unchanged.';
    }
    ttBody.innerHTML = rows.join('')
      + (d.description ? `<div class="tt-row" style="margin-top:5px;color:#8a9ab5;font-size:11px">${String(d.description).substring(0, 120)}</div>` : '')
      + `<div class="tt-row" style="margin-top:5px;color:#5a6a80;font-size:11px">${note}</div>`;
    positionTooltip(event);
    tooltip.classList.add('visible');
    return;
  }
  ttName.style.color = '';
  if (d.type === 'vendor') {
    const ttClass = { Digital: 'tt-type-vendor', Mixed: 'tt-type-mixed', Hardware: 'tt-type-hardware', Nontechnical: 'tt-type-nontechnical', Internal: 'tt-type-internal' };
    ttName.className = `tt-name ${ttClass[d.classification] || 'tt-type-mixed'}`;
    const spend = activeSpend(d);
    const spendLabel = isOtiMode ? 'OTI Spend' : currentPeriod + ' Spend';
    ttBody.innerHTML = `
      <div class="tt-row">Type: <span>${d.classification}</span></div>
      <div class="tt-row">${spendLabel}: <span>${fmtUSD(spend)}</span></div>
      <div class="tt-row">Agencies served: <span>${d.agency_count}</span></div>
      ${d.description ? `<div class="tt-row" style="margin-top:5px;color:#5a6a80;font-size:11px">${d.description.substring(0,120)}${d.description.length>120?'&hellip;':''}</div>` : ''}
    `;
  } else {
    ttName.className = 'tt-name tt-type-agency';
    ttBody.innerHTML = `
      <div class="tt-row">Agency</div>
      <div class="tt-row">Active vendors: <span>${d.vendor_count}</span></div>
      ${d._estSpend ? `<div class="tt-row">${currentPeriod} tech spend: <span>${fmtUSD(d._estSpend)}</span></div>` : ''}
    `;
  }
  positionTooltip(event);
  tooltip.classList.add('visible');
}

function positionTooltip(event) {
  const x = event.clientX + 16, y = event.clientY - 10;
  tooltip.style.left = (x + 280 > W ? x - 280 - 24 : x) + 'px';
  tooltip.style.top  = (y + 120 > window.innerHeight ? y - 120 : y) + 'px';
}

function hideTooltip() { tooltip.classList.remove('visible'); }

// ═══════════════════════════════════════════════════════════════════════════════
// NETWORK VIEW
// ═══════════════════════════════════════════════════════════════════════════════
const svg = d3.select('#canvas').attr('width', W).attr('height', H)
  .on('click', () => {
    if (lockedHighlight) {
      lockedHighlight = null;
      hideTooltip();
      // nodeGroup/linkSel may not exist yet on first render; guard against that
      if (typeof nodeGroup !== 'undefined') resetNet(nodeGroup, linkSel);
    }
  });

const defs = svg.append('defs');
const glowFilter = defs.append('filter').attr('id', 'glow')
  .attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%');
glowFilter.append('feGaussianBlur').attr('stdDeviation', '4').attr('result', 'blur');
const feMerge = glowFilter.append('feMerge');
feMerge.append('feMergeNode').attr('in', 'blur');
feMerge.append('feMergeNode').attr('in', 'SourceGraphic');

const zoomGroup = svg.append('g').attr('id', 'zoom-group');
const zoom = d3.zoom().scaleExtent([0.1, 8]).on('zoom', e => {
  zoomGroup.attr('transform', e.transform);
  zoomGroup.selectAll('.node-label').attr('opacity', e.transform.k > 2.5 ? 1 : 0);
});
svg.call(zoom);

let linkSel, nodeSel, nodeGroup;

function buildGraph() {
  if (simulation) simulation.stop();
  zoomGroup.selectAll('*').remove();

  const { nodes, links } = getFilteredData();
  updateStats(nodes, links);

  simulation = d3.forceSimulation(nodes)
    .alphaDecay(0.02)
    .force('link',      d3.forceLink(links).id(d => d.id).distance(65))
    .force('charge',    d3.forceManyBody().strength(-150))
    .force('collision', d3.forceCollide(d => (d.type === 'vendor' ? nodeRadius(activeSpend(d)) : d.radius) + 4))
    .force('center',    d3.forceCenter(W / 2, H / 2));

  netNodes = nodes;
  nodes.forEach(n => { if (pinnedNodes.has(n.id)) { n.fx = n.x; n.fy = n.y; } });

  linkSel = zoomGroup.append('g').attr('class', 'links')
    .selectAll('line').data(links).join('line')
    .attr('stroke', 'rgba(255,255,255,0.06)')
    .attr('stroke-width', 1);

  nodeGroup = zoomGroup.append('g').attr('class', 'nodes')
    .selectAll('g').data(nodes).join('g')
    .attr('class', 'node-group')
    .call(d3.drag()
      .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag',  (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on('end',   (e, d) => { if (!e.active) simulation.alphaTarget(0); if (!pinnedNodes.has(d.id)) { d.fx = null; d.fy = null; } })
    )
    .on('mouseover', (event, d) => {
      showTooltip(d, event);
      if (!lockedHighlight) highlightNet(d, nodeGroup, linkSel);
    })
    .on('mousemove', (event) => positionTooltip(event))
    .on('mouseout',  () => {
      hideTooltip();
      if (!lockedHighlight) resetNet(nodeGroup, linkSel);
    })
    .on('click', (event, d) => {
      event.stopPropagation();
      if (lockedHighlight === d.id) {
        lockedHighlight = null;
        hideTooltip(); resetNet(nodeGroup, linkSel);
      } else {
        lockedHighlight = d.id;
        showTooltip(d, event); highlightNet(d, nodeGroup, linkSel);
      }
    });

  nodeSel = nodeGroup;

  nodeGroup.append('circle')
    .attr('r', d => d.type === 'vendor' ? nodeRadius(activeSpend(d)) : d.radius)
    .attr('fill', d => d.type === 'agency' ? 'rgba(90,159,212,0.06)' : nodeColor(d))
    .attr('fill-opacity', d => d.type === 'agency' ? 1 : 0.85)
    .attr('stroke', d => nodeStroke(d))
    .attr('stroke-width', d => d.type === 'agency' ? 1.5 : 1);

  nodeGroup.append('text')
    .attr('class', 'node-label')
    .text(d => d.id.length > 24 ? d.id.substring(0, 22) + '\u2026' : d.id)
    .attr('font-family', 'DM Mono, monospace').attr('font-size', '8px')
    .attr('fill', '#8a9ab5').attr('text-anchor', 'middle')
    .attr('dy', d => (d.type === 'vendor' ? nodeRadius(activeSpend(d)) : d.radius) + 10).attr('opacity', 0).attr('pointer-events', 'none');

  simulation.on('tick', () => {
    linkSel.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
           .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    nodeGroup.attr('transform', d => `translate(${d.x},${d.y})`);
  });
}

function highlightNet(d, nodeGroup, linkSel) {
  const ids = new Set([d.id]);
  linkSel.each(l => {
    const s = l.source.id ?? l.source, t = l.target.id ?? l.target;
    if (s === d.id || t === d.id) { ids.add(s); ids.add(t); }
  });
  linkSel
    .attr('stroke', l => {
      const s = l.source.id ?? l.source, t = l.target.id ?? l.target;
      return (s === d.id || t === d.id) ? 'rgba(255,255,255,0.5)' : 'rgba(255,255,255,0.02)';
    })
    .attr('stroke-width', l => {
      const s = l.source.id ?? l.source, t = l.target.id ?? l.target;
      return (s === d.id || t === d.id) ? 1.5 : 0.5;
    });
  nodeGroup.selectAll('circle')
    .attr('fill-opacity', nd => {
      if (!ids.has(nd.id)) return nd.type === 'agency' ? 0.03 : 0.08;
      return 1;
    })
    .attr('stroke-opacity', nd => ids.has(nd.id) ? 1 : 0.15)
    .attr('filter', nd => ids.has(nd.id) ? 'url(#glow)' : null);
}

function resetNet(nodeGroup, linkSel) {
  linkSel.attr('stroke', 'rgba(255,255,255,0.06)').attr('stroke-width', 1);
  nodeGroup.selectAll('circle')
    .attr('fill-opacity', nd => nd.type === 'agency' ? 1 : 0.85)
    .attr('stroke-opacity', 1).attr('filter', null);
}

// ═══════════════════════════════════════════════════════════════════════════════
// SANKEY VIEW
// ═══════════════════════════════════════════════════════════════════════════════
const skSvg = d3.select('#sankey-canvas').attr('width', W).attr('height', H);

// Glow filter for sankey
const skDefs = skSvg.append('defs');
const skGlow = skDefs.append('filter').attr('id', 'sk-glow')
  .attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%');
skGlow.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'blur');
const skMerge = skGlow.append('feMerge');
skMerge.append('feMergeNode').attr('in', 'blur');
skMerge.append('feMergeNode').attr('in', 'SourceGraphic');

const skGlowStrong = skDefs.append('filter').attr('id', 'sk-glow-strong')
  .attr('x', '-100%').attr('y', '-100%').attr('width', '300%').attr('height', '300%');
skGlowStrong.append('feGaussianBlur').attr('stdDeviation', '5').attr('result', 'blur');
const skMergeStrong = skGlowStrong.append('feMerge');
skMergeStrong.append('feMergeNode').attr('in', 'blur');
skMergeStrong.append('feMergeNode').attr('in', 'SourceGraphic');
skMerge.append('feMergeNode').attr('in', 'SourceGraphic');

// Zoom/pan (same pattern as the network view) — lets small slices be
// inspected and clicked. Label visibility relaxes as you zoom in.
const skZoomGroup = skSvg.append('g').attr('id', 'sk-zoom-group');
let skZoomK = 1;
// Zoom floor at 100%; translateExtent keeps the chart from being dragged
// offscreen (and makes panning a no-op until you're zoomed in).
const skZoom = d3.zoom().scaleExtent([1, 8]).translateExtent([[0, 0], [W, H]]).on('zoom', e => {
  skZoomGroup.attr('transform', e.transform);
  skZoomK = e.transform.k;
  if (!lockedHighlight) {
    skSvg.selectAll('.sk-label')
      .attr('opacity', d => (d.y1 - d.y0) * skZoomK >= 9 ? 1 : 0);
  }
});
skSvg.call(skZoom);

function buildSankey() {
  skZoomGroup.selectAll('.sk-layer').remove();

  const { visibleVendorIds } = getFilteredData();

  // Raw filtered links (vendor → agency), respecting OTI mode
  const rawLinks = activeLinks().filter(l => visibleVendorIds.has(l.source.id ?? l.source));

  // Count agencies per vendor for equal-split spending
  const vendorAgencyCount = {};
  rawLinks.forEach(l => {
    const v = l.source.id ?? l.source;
    vendorAgencyCount[v] = (vendorAgencyCount[v] || 0) + 1;
  });

  const connectedAgencyIds = new Set(rawLinks.map(l => l.target.id ?? l.target));

  // Build node list (agencies first so they appear on left as sources)
  const agencyNodes = RAW_NODES
    .filter(n => n.type === 'agency' && connectedAgencyIds.has(n.id))
    .map(n => ({ ...n }));

  const vendorNodes = RAW_NODES
    .filter(n => n.type === 'vendor' && visibleVendorIds.has(n.id))
    .map(n => ({ ...n }));

  const allNodes = [...agencyNodes, ...vendorNodes];

  // Compute actual agency spend for tooltip from real per-pair spend
  const agencyActualSpend = {};
  rawLinks.forEach(l => {
    const ag = l.target.id ?? l.target;
    agencyActualSpend[ag] = (agencyActualSpend[ag] || 0) + (l.spend || 0);
  });
  agencyNodes.forEach(n => { n._estSpend = agencyActualSpend[n.id] || 0; });

  // Sankey links: source = agency, target = vendor (flow left → right)
  // Value = actual per-agency spend in millions from raw transaction data.
  const sankeyLinks = rawLinks.map(l => {
    const v = l.source.id ?? l.source, ag = l.target.id ?? l.target;
    return {
      source: ag,
      target: v,
      value: (l.spend || 1) / 1e6,
    };
  });

  // ── Third layer: vendor → maker. Every visible vendor's full spend flows
  // on, so columns 2 and 3 total identically (and column 1 already equals 2).
  if (showMakers) {
    const mlKey = isOtiMode ? 'maker_links_oti' : 'maker_links';
    const rawMakerLinks = (PERIOD_DATA[currentPeriod][mlKey] || [])
      .filter(l => visibleVendorIds.has(l.source));

    const vendorClassById = {};
    vendorNodes.forEach(v => { vendorClassById[v.id] = v.classification; });

    const vendorDescById = {};
    vendorNodes.forEach(v => { vendorDescById[v.id] = v.description; });

    // First pass: per-maker totals (to decide slider rollup) + self classes
    const preTotals = {}, selfClass = {}, selfDesc = {};
    rawMakerLinks.forEach(l => {
      preTotals[l.target] = (preTotals[l.target] || 0) + l.spend;
      if (l.self && !(l.target in selfClass)) {
        selfClass[l.target] = vendorClassById[l.source];
        selfDesc[l.target]  = vendorDescById[l.source];
      }
    });

    // Makers below the min-spend slider roll up into one node instead of
    // being dropped, so every dollar still lands in column 3.
    const ROLLUP = 'Other makers (below slider)';
    const merged = {};
    rawMakerLinks.forEach(l => {
      const tgt = preTotals[l.target] < thresholdM * 1e6 ? ROLLUP : l.target;
      const key = l.source + '||' + tgt + '||' + (l.self ? 1 : 0);
      if (!merged[key]) merged[key] = { source: l.source, target: tgt, spend: 0, self: l.self };
      merged[key].spend += l.spend;
    });

    const makerAgg = {};
    Object.values(merged).forEach(l => {
      const a = makerAgg[l.target] || (makerAgg[l.target] = { total: 0, via: 0, direct: 0, sources: new Set() });
      a.total += l.spend;
      if (l.self) a.direct += l.spend;
      else { a.via += l.spend; a.sources.add(l.source); }
      sankeyLinks.push({ source: l.source, target: 'maker::' + l.target, value: l.spend / 1e6 });
    });

    Object.keys(makerAgg).forEach(name => {
      const a = makerAgg[name];
      let cls;
      if (name === 'Unidentified purchases') cls = 'unidentified';
      else if (name === 'Multiple makers')   cls = 'multi';
      else if (name === ROLLUP)              cls = 'other';
      else cls = (MAKER_CLASS[name] && MAKER_CLASS[name].c) || selfClass[name] || 'multi';
      // Self-mirrors inherit their vendor's research description; attributed
      // makers use the rationale from maker_classifications.csv
      const desc = selfDesc[name] || (MAKER_CLASS[name] && MAKER_CLASS[name].r) || '';
      allNodes.push({
        id: 'maker::' + name,
        label: name,
        type: 'maker',
        classification: cls,
        spending: a.total,
        direct_spend: a.direct,
        via_spend: a.via,
        via_count: a.sources.size,
        description: desc,
      });
    });
  }

  updateStats(allNodes, rawLinks);

  const ML = 230, MR = 240, MT = 52, MB = 62;

  const sankey = d3.sankey()
    .nodeId(d => d.id)
    .nodeWidth(14)
    // Zero layout padding: column height is purely Σspend, so all columns are
    // exactly equal. Node separation comes from a hairline stroke instead.
    .nodePadding(0)
    .extent([[ML, MT], [W - MR, H - MB]]);

  let graph;
  try {
    graph = sankey({ nodes: allNodes, links: sankeyLinks });
  } catch(e) {
    console.error('Sankey layout error:', e);
    return;
  }

  // ── Gradient defs for bands ──
  // Each band fades source-node color → target-node color across the actual
  // gap it spans, so colors hand off cleanly at every column. Gradients are
  // cached per (column gap, color pair) — all links in a gap share x-extent.
  skDefs.selectAll('.sk-grad').remove();
  const gradCache = new Set();
  function linkGradId(l) {
    const sc = nodeColor(l.source), tc = nodeColor(l.target);
    const id = 'skg' + l.source.depth + '-' + sc.slice(1) + '-' + tc.slice(1);
    if (!gradCache.has(id)) {
      gradCache.add(id);
      const g = skDefs.append('linearGradient').attr('class', 'sk-grad').attr('id', id)
        .attr('gradientUnits', 'userSpaceOnUse')
        .attr('x1', l.source.x1).attr('y1', 0).attr('x2', l.target.x0).attr('y2', 0);
      g.append('stop').attr('offset', '0%').attr('stop-color', sc).attr('stop-opacity', 0.55);
      g.append('stop').attr('offset', '100%').attr('stop-color', tc).attr('stop-opacity', 0.55);
    }
    return id;
  }

  // ── Draw bands ──
  const linkLayer = skZoomGroup.append('g').attr('class', 'sk-layer sk-links');
  const linkPaths = linkLayer.selectAll('path')
    .data(graph.links)
    .join('path')
    .attr('d', d3.sankeyLinkHorizontal())
    .attr('stroke', d => `url(#${linkGradId(d)})`)
    .attr('stroke-width', d => Math.max(0.5, d.width))
    .attr('stroke-opacity', 1)
    .attr('fill', 'none');

  // ── Draw node rects ──
  const nodeLayer = skZoomGroup.append('g').attr('class', 'sk-layer sk-nodes');
  const nodeRects = nodeLayer.selectAll('rect')
    .data(graph.nodes)
    .join('rect')
    .attr('x',      d => d.x0)
    .attr('y',      d => d.y0)
    .attr('width',  d => d.x1 - d.x0)
    .attr('height', d => Math.max(1, d.y1 - d.y0))
    .attr('fill',   d => d.type === 'agency' ? '#5a9fd4' : nodeColor(d))
    .attr('fill-opacity', 0.82)
    .attr('stroke', '#080c14')
    .attr('stroke-width', 0.5)
    .attr('rx', 1);

  // ── Draw labels ──
  const labelLayer = skZoomGroup.append('g').attr('class', 'sk-layer sk-labels');
  labelLayer.selectAll('text')
    .data(graph.nodes)
    .join('text')
    .attr('class', 'sk-label')
    .attr('x', d => d.type === 'agency' ? d.x0 - 7 : d.x1 + 7)
    .attr('y', d => (d.y0 + d.y1) / 2)
    .attr('text-anchor', d => d.type === 'agency' ? 'end' : 'start')
    .attr('dominant-baseline', 'middle')
    .attr('font-family', 'DM Mono, monospace')
    .attr('font-size', '9px')
    .attr('fill', d => d.type === 'agency' ? '#5a9fd4' : nodeColor(d))
    .attr('opacity', d => (d.y1 - d.y0) * skZoomK >= 9 ? 1 : 0)
    .text(d => {
      const name = d.label || d.id;
      const maxLen = d.type === 'agency' ? 32 : 26;
      return name.length > maxLen ? name.substring(0, maxLen - 2) + '\u2026' : name;
    });

  const skLabels = skSvg.selectAll('.sk-label');

  let lockedConnIds = null;  // set of connected node ids when highlight is locked

  function applySkHighlight(d) {
    const connIds = new Set([d.id]);
    linkPaths.each(function(l) {
      if (l.source.id === d.id || l.target.id === d.id) {
        connIds.add(l.source.id); connIds.add(l.target.id);
      }
    });
    lockedConnIds = lockedHighlight ? connIds : null;
    linkPaths
      .attr('stroke-opacity', l =>
        (l.source.id === d.id || l.target.id === d.id) ? 1 : 0.04)
      .attr('stroke', l =>
        (l.source.id === d.id || l.target.id === d.id)
          ? `url(#${linkGradId(l)})`
          : 'rgba(255,255,255,0.15)');
    nodeRects
      .attr('fill-opacity', nd => connIds.has(nd.id) ? 1.0 : 0.12)
      .attr('filter', nd => connIds.has(nd.id) ? 'url(#sk-glow-strong)' : null);
    skLabels
      .attr('opacity', nd => connIds.has(nd.id) ? ((nd.y1 - nd.y0) * skZoomK >= 9 ? 1 : 0) : 0.06);
  }
  function resetSkHighlight() {
    lockedConnIds = null;
    linkPaths
      .attr('stroke-opacity', 1)
      .attr('stroke', d => `url(#${linkGradId(d)})`);
    nodeRects.attr('fill-opacity', 0.82).attr('filter', null)
      .attr('stroke', '#080c14').attr('stroke-width', 0.5).attr('stroke-opacity', 1);
    skLabels.attr('opacity', nd => (nd.y1 - nd.y0) * skZoomK >= 9 ? 1 : 0);
  }

  // ── Hover & click ──
  nodeRects
    .on('mouseover', (event, d) => {
      if (!lockedHighlight || (lockedConnIds && lockedConnIds.has(d.id))) {
        showTooltip(d, event);
      }
      if (!lockedHighlight) {
        applySkHighlight(d);
      } else if (lockedConnIds && lockedConnIds.has(d.id)) {
        nodeRects.filter(nd => nd.id === d.id)
          .attr('stroke', '#fff')
          .attr('stroke-width', 1.5)
          .attr('stroke-opacity', 0.6);
      }
    })
    .on('mousemove', event => positionTooltip(event))
    .on('mouseout', (event, d) => {
      hideTooltip();
      if (!lockedHighlight) {
        resetSkHighlight();
      } else {
        nodeRects.filter(nd => nd.id === d.id)
          .attr('stroke', '#080c14')
          .attr('stroke-width', 0.5)
          .attr('stroke-opacity', 1);
      }
    })
    .on('click', (event, d) => {
      event.stopPropagation();
      if (lockedHighlight === d.id) {
        lockedHighlight = null;
        hideTooltip(); resetSkHighlight();
      } else {
        lockedHighlight = d.id;
        showTooltip(d, event); applySkHighlight(d);
      }
    });

  skSvg.on('click', () => {
    if (lockedHighlight) {
      lockedHighlight = null;
      hideTooltip(); resetSkHighlight();
    }
  });

  // Apply lock if search selected a node before this build
  if (lockedHighlight) {
    const locked = graph.nodes.find(n => n.id === lockedHighlight);
    if (locked) { showTooltip(locked, { clientX: W / 2, clientY: 80 }); applySkHighlight(locked); }
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// TRENDS VIEW
// ═══════════════════════════════════════════════════════════════════════════════
const trSvg = d3.select('#trends-canvas').attr('width', W).attr('height', H);
const trDefs = trSvg.append('defs');
const trGlow = trDefs.append('filter').attr('id', 'trends-glow')
  .attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%');
trGlow.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'blur');
const trMerge = trGlow.append('feMerge');
trMerge.append('feMergeNode').attr('in', 'blur');
trMerge.append('feMergeNode').attr('in', 'SourceGraphic');

const trendsVendorList = document.getElementById('trends-vendor-list');
let trendsHighlighted = new Set(); // vendor ids currently highlighted
let trendsHovered = null;

function buildTrends() {
  trSvg.selectAll('.tr-layer').remove();

  // Sort vendors by max yearly spend descending
  const vendorEntries = Object.entries(TIMESERIES)
    .map(([name, d]) => ({
      name,
      classification: d.classification,
      yearly: d.yearly,
      oti_yearly: d.oti_yearly,
      makerTotal: !!d.maker_total,
      maxSpend: Math.max(...Object.values(isOtiMode ? d.oti_yearly : d.yearly).map(v => v || 0)),
      totalSpend: Object.values(isOtiMode ? d.oti_yearly : d.yearly).reduce((a, b) => a + b, 0),
    }))
    .filter(v => v.maxSpend > 0)
    .sort((a, b) => b.totalSpend - a.totalSpend);

  // Apply classification filter
  const filterMap = { digital: 'Digital', mixed: 'Mixed', hardware: 'Hardware', nontechnical: 'Nontechnical', internal: 'Internal' };
  const filtered = activeFilter === 'all'
    ? vendorEntries
    : vendorEntries.filter(v => v.classification === filterMap[activeFilter]);

  // Auto-highlight top 5 if nothing selected
  if (trendsHighlighted.size === 0) {
    filtered.slice(0, 5).forEach(v => trendsHighlighted.add(v.name));
  }

  // Chart margins
  const ML = 80, MR = 260, MT = 70, MB = 50;
  const cw = W - ML - MR, ch = H - MT - MB;

  const x = d3.scaleLinear().domain([ALL_YEARS[0], ALL_YEARS[ALL_YEARS.length - 1]]).range([0, cw]);
  // Scale y-axis to highlighted vendors only (or all if none highlighted)
  const scaleVendors = trendsHighlighted.size > 0
    ? filtered.filter(v => trendsHighlighted.has(v.name))
    : filtered;
  const maxY = Math.max(...scaleVendors.map(v => {
    const vals = isOtiMode ? v.oti_yearly : v.yearly;
    return Math.max(...ALL_YEARS.map(y => (vals[y] || 0) / 1e6));
  }));
  const y = d3.scaleLinear().domain([0, maxY * 1.1]).range([ch, 0]).nice();

  const chartG = trSvg.append('g').attr('class', 'tr-layer').attr('transform', `translate(${ML},${MT})`);

  // Grid
  chartG.append('g').attr('class', 'trends-grid')
    .call(d3.axisLeft(y).ticks(6).tickSize(-cw).tickFormat(''));

  // Axes
  chartG.append('g').attr('class', 'trends-axis')
    .attr('transform', `translate(0,${ch})`)
    .call(d3.axisBottom(x)
      .tickValues(ALL_YEARS)
      .tickFormat(d => String(d))
      .tickSizeOuter(0));

  chartG.append('g').attr('class', 'trends-axis')
    .call(d3.axisLeft(y).ticks(6).tickFormat(d => {
      if (d >= 1000) return '$' + (d / 1000).toFixed(1) + 'B';
      if (d >= 1) return '$' + Math.round(d) + 'M';
      if (d > 0) return '$' + Math.round(d * 1000) + 'K';
      return '$0';
    }).tickSizeOuter(0));

  // Line generator
  const line = d3.line()
    .defined(d => d[1] != null)
    .x(d => x(d[0]))
    .y(d => y(d[1]))
    .curve(d3.curveMonotoneX);

  // Draw lines
  const linesG = chartG.append('g');

  filtered.forEach(v => {
    const vals = isOtiMode ? v.oti_yearly : v.yearly;
    const points = ALL_YEARS.map(yr => [yr, vals[yr] ? vals[yr] / 1e6 : null]);
    const defined = points.filter(p => p[1] != null);
    if (defined.length === 0) return;

    const color = VENDOR_COLORS[v.classification] || '#d4624a';
    const isActive = trendsHighlighted.has(v.name);

    const path = linesG.append('path')
      .datum(points)
      .attr('class', 'trend-line' + (isActive ? ' highlighted' : (trendsHighlighted.size > 0 ? ' dimmed' : '')))
      .attr('d', line)
      .attr('stroke', color)
      .attr('data-vendor', v.name);
    // Maker totals (direct + verified pass-through) render dashed
    if (v.makerTotal) path.attr('stroke-dasharray', '7,4');

    // Dots and value labels for highlighted lines
    if (isActive) {
      defined.forEach(([yr, val]) => {
        linesG.append('circle')
          .attr('class', 'trend-dot')
          .attr('cx', x(yr)).attr('cy', y(val))
          .attr('r', 3.5).attr('fill', color)
          .attr('data-vendor', v.name);
        const label = val >= 1000 ? '$' + (val / 1000).toFixed(1) + 'B'
          : val >= 1 ? '$' + val.toFixed(1) + 'M'
          : '$' + Math.round(val * 1000) + 'K';
        linesG.append('text')
          .attr('x', x(yr)).attr('y', y(val) - 10)
          .attr('text-anchor', 'middle')
          .attr('font-family', 'DM Mono, monospace')
          .attr('font-size', '10px')
          .attr('fill', color)
          .attr('pointer-events', 'none')
          .text(label);
      });
    }

    // Hover target (wider invisible stroke)
    linesG.append('path')
      .datum(points)
      .attr('d', line)
      .attr('stroke', 'transparent')
      .attr('stroke-width', 12)
      .attr('fill', 'none')
      .style('cursor', 'pointer')
      .on('mouseover', (event) => {
        trendsHovered = v.name;
        const vals2 = isOtiMode ? v.oti_yearly : v.yearly;
        const latest = ALL_YEARS.slice().reverse().find(yr => vals2[yr]);
        const latestVal = latest ? vals2[latest] : 0;
        ttName.textContent = v.name;
        const ttClass = { Digital: 'tt-type-vendor', Mixed: 'tt-type-mixed', Hardware: 'tt-type-hardware', Nontechnical: 'tt-type-nontechnical', Internal: 'tt-type-internal' };
        ttName.className = 'tt-name ' + (ttClass[v.classification] || 'tt-type-mixed');
        const yearsActive = ALL_YEARS.filter(yr => vals2[yr]).length;
        ttBody.innerHTML = '<div class="tt-row">Type: <span>' + v.classification + '</span></div>'
          + '<div class="tt-row">Total: <span>' + fmtUSD(v.totalSpend) + '</span></div>'
          + (latest ? '<div class="tt-row">FY' + latest + ': <span>' + fmtUSD(latestVal) + '</span></div>' : '')
          + '<div class="tt-row">Active years: <span>' + yearsActive + '/' + ALL_YEARS.length + '</span></div>'
          + (v.makerTotal ? '<div class="tt-row" style="margin-top:5px;color:#5a6a80;font-size:11px">Direct payments + purpose-verified reseller pass-through. Unidentified reseller spend excluded, so this is a floor.</div>' : '');
        positionTooltip(event);
        tooltip.classList.add('visible');
        applyTrendsHover(v.name);
      })
      .on('mousemove', event => positionTooltip(event))
      .on('mouseout', () => {
        trendsHovered = null;
        hideTooltip();
        applyTrendsHighlight();
      })
      .on('click', (event) => {
        event.stopPropagation();
        if (trendsHighlighted.has(v.name) && trendsHighlighted.size === 1) {
          trendsHighlighted.clear();
        } else {
          trendsHighlighted.clear();
          trendsHighlighted.add(v.name);
        }
        buildTrends();
      });
  });

  // Build vendor list panel
  trendsVendorList.innerHTML = '';
  filtered.forEach(v => {
    const color = VENDOR_COLORS[v.classification] || '#d4624a';
    const isActive = trendsHighlighted.has(v.name);
    const el = document.createElement('div');
    el.className = 'tv-item' + (isActive ? ' active' : '');
    const dotStyle = v.makerTotal
      ? 'background:transparent;border:2px solid ' + color + (isActive ? '' : ';opacity:0.3')
      : 'background:' + color + (isActive ? '' : ';opacity:0.3');
    el.innerHTML = '<div class="tv-dot" style="' + dotStyle + '"></div>'
      + '<span>' + (v.name.length > 28 ? v.name.substring(0, 26) + '\u2026' : v.name) + '</span>';
    el.addEventListener('click', () => {
      if (trendsHighlighted.has(v.name) && trendsHighlighted.size === 1) {
        trendsHighlighted.clear();
      } else {
        trendsHighlighted.clear();
        trendsHighlighted.add(v.name);
      }
      buildTrends();
    });
    el.addEventListener('mouseover', () => { trendsHovered = v.name; applyTrendsHover(v.name); });
    el.addEventListener('mouseout', () => { trendsHovered = null; applyTrendsHighlight(); });
    trendsVendorList.appendChild(el);
  });

  updateStats(
    filtered.map(v => ({ type: 'vendor' })),
    [] // no links in trends view
  );
  document.getElementById('stat-agencies').textContent = ALL_YEARS.length + ' yrs';
  document.getElementById('stat-links').textContent = '\u2014';
}

function applyTrendsHighlight() {
  trSvg.selectAll('.trend-line').each(function() {
    const el = d3.select(this);
    const vendor = el.attr('data-vendor');
    if (trendsHighlighted.size === 0) {
      el.attr('class', 'trend-line');
    } else if (trendsHighlighted.has(vendor)) {
      el.attr('class', 'trend-line highlighted');
    } else {
      el.attr('class', 'trend-line dimmed');
    }
  });
}

function applyTrendsHover(vendorName) {
  trSvg.selectAll('.trend-line').each(function() {
    const el = d3.select(this);
    const vendor = el.attr('data-vendor');
    if (vendor === vendorName) {
      el.attr('class', 'trend-line highlighted');
    } else if (trendsHighlighted.has(vendor)) {
      el.attr('class', 'trend-line highlighted');
    } else {
      el.attr('class', 'trend-line dimmed');
    }
  });
}

// ═══════════════════════════════════════════════════════════════════════════════
// VIEW TOGGLE
// ═══════════════════════════════════════════════════════════════════════════════
function switchView(view) {
  currentView = view;
  lockedHighlight = null;
  hideTooltip();
  document.getElementById('canvas').style.display         = view === 'network' ? '' : 'none';
  document.getElementById('sankey-canvas').style.display  = view === 'sankey'  ? '' : 'none';
  document.getElementById('trends-canvas').style.display  = view === 'trends'  ? '' : 'none';
  document.getElementById('legend').style.display         = view === 'trends'  ? 'none' : '';
  document.getElementById('trends-vendor-list').style.display = view === 'trends' ? 'block' : 'none';
  // Stats reflect network/sankey builds and would sit on top of the trends list
  document.getElementById('stats').style.display = view === 'trends' ? 'none' : '';
  document.getElementById('legend-size-note').style.display   = view === 'network' ? '' : 'none';
  document.getElementById('legend-sankey-note').style.display = view === 'sankey'  ? '' : 'none';
  document.getElementById('maker-toggle').style.display       = view === 'sankey'  ? '' : 'none';
  document.getElementById('legend-maker-group').style.display = view === 'sankey' && showMakers ? '' : 'none';
  // Hide period picker and slider in trends (it shows all years)
  periodSelect.style.display = view === 'trends' ? 'none' : '';
  document.getElementById('slider-wrap').style.display = view === 'trends' ? 'none' : '';

  document.querySelectorAll('.view-btn').forEach(b => b.classList.toggle('active', b.dataset.view === view));

  if (view === 'network') {
    if (simulation) simulation.alphaTarget(0);
    buildGraph();
  } else if (view === 'sankey') {
    if (simulation) simulation.stop();
    buildSankey();
  } else {
    if (simulation) simulation.stop();
    buildTrends();
  }
}

document.querySelectorAll('.view-btn').forEach(btn => {
  btn.addEventListener('click', () => switchView(btn.dataset.view));
});

// ─── Filter / slider controls ─────────────────────────────────────────────────
periodSelect.addEventListener('change', function() {
  currentPeriod = this.value;
  RAW_NODES = PERIOD_DATA[currentPeriod].nodes;
  RAW_LINKS = PERIOD_DATA[currentPeriod].links;
  pinnedNodes.clear();
  lockedHighlight = null;
  document.getElementById('legend-size-note').innerHTML = 'Node size &#8733; ' + currentPeriod + ' spending';
  document.getElementById('legend-sankey-note').innerHTML = 'Bar height &amp; band width &#8733; ' + currentPeriod + ' spend &nbsp;&middot;&nbsp; scroll to zoom';
  if (currentView === 'network') buildGraph();
  else if (currentView === 'sankey') buildSankey();
});

function rebuildCurrentView() {
  if (currentView === 'network') buildGraph();
  else if (currentView === 'sankey') buildSankey();
  else buildTrends();
}

document.getElementById('filter-select').addEventListener('change', function() {
  activeFilter = this.value;
  pinnedNodes.clear();
  lockedHighlight = null;
  trendsHighlighted.clear();
  rebuildCurrentView();
});

const slider = document.getElementById('threshold-slider');
const sliderLabel = document.getElementById('threshold-label');
function sliderToM(v) {
  if (v === 0) return 0;
  const maxM = maxVendorSpendM();
  return Math.round(Math.pow(10, (v / 100) * Math.log10(maxM + 1)));
}
function updateSliderLabel() {
  const m = sliderToM(parseInt(slider.value));
  sliderLabel.textContent = m < 1 ? `$${(m * 1000).toFixed(0)}k` : `$${m}M`;
}
slider.addEventListener('input', () => {
  thresholdM = sliderToM(parseInt(slider.value));
  updateSliderLabel();
  rebuildCurrentView();
});

document.getElementById('maker-toggle').addEventListener('click', function() {
  showMakers = !showMakers;
  this.classList.toggle('active', showMakers);
  this.textContent = 'Makers: ' + (showMakers ? 'on' : 'off');
  document.getElementById('legend-maker-group').style.display = currentView === 'sankey' && showMakers ? '' : 'none';
  lockedHighlight = null;
  if (currentView === 'sankey') buildSankey();
});

document.getElementById('oti-toggle').addEventListener('click', function() {
  isOtiMode = !isOtiMode;
  this.classList.toggle('active', isOtiMode);
  slider.value = 0;
  thresholdM = 0;
  updateSliderLabel();
  pinnedNodes.clear();
  trendsHighlighted.clear();
  rebuildCurrentView();
});

// ─── Search ───────────────────────────────────────────────────────────────────
const searchInput    = document.getElementById('search-input');
const searchDropdown = document.getElementById('search-dropdown');

function selectSearchResult(nodeId) {
  searchInput.value = nodeId;
  searchDropdown.style.display = 'none';

  if (currentView === 'trends') {
    // In trends, highlight the selection plus its paired series
    // (direct vendor ↔ maker total), so e.g. "microsoft" shows both lines
    if (TIMESERIES[nodeId]) {
      trendsHighlighted.clear();
      trendsHighlighted.add(nodeId);
      (TIMESERIES[nodeId].paired || []).forEach(p => trendsHighlighted.add(p));
      buildTrends();
    }
    return;
  }

  const d = RAW_NODES.find(n => n.id === nodeId);
  if (!d) return;

  lockedHighlight = nodeId;

  if (currentView === 'network') {
    if (nodeGroup) {
      showTooltip(d, { clientX: W / 2, clientY: 80 });
      highlightNet(d, nodeGroup, linkSel);
    }
  } else {
    // Rebuild Sankey — lockedHighlight is already set, buildSankey will apply highlight
    buildSankey();
  }
}

searchInput.addEventListener('input', () => {
  const q = searchInput.value.trim().toLowerCase();
  if (!q) { searchDropdown.style.display = 'none'; return; }

  const searchSource = currentView === 'trends'
    ? Object.entries(TIMESERIES).map(([name, d]) => ({
        id: name, type: 'vendor', classification: d.classification,
        spending: Object.values(d.yearly).reduce((a, b) => a + b, 0),
      }))
    : RAW_NODES;
  const matches = searchSource
    .filter(n => n.id.toLowerCase().includes(q))
    .sort((a, b) => {
      const aStarts = a.id.toLowerCase().startsWith(q) ? 0 : 1;
      const bStarts = b.id.toLowerCase().startsWith(q) ? 0 : 1;
      return aStarts - bStarts || (b.spending - a.spending);
    })
    .slice(0, 10);

  if (!matches.length) { searchDropdown.style.display = 'none'; return; }

  searchDropdown.innerHTML = matches.map(n => {
    const typeLabel = n.type === 'agency' ? 'agency' : n.classification.toLowerCase();
    const spendM = n.type === 'vendor' ? ` \u00b7 ${fmtUSD(n.spending)}` : '';
    return `<div class="search-result" data-id="${n.id.replace(/"/g, '&quot;')}">
      <span>${n.id}</span>
      <span class="search-result-type">${typeLabel}${spendM}</span>
    </div>`;
  }).join('');
  searchDropdown.style.display = 'block';

  searchDropdown.querySelectorAll('.search-result').forEach(el => {
    el.addEventListener('click', () => selectSearchResult(el.dataset.id));
  });
});

searchInput.addEventListener('keydown', e => {
  if (e.key === 'Escape') { searchInput.value = ''; searchDropdown.style.display = 'none'; }
  if (e.key === 'Enter') {
    const first = searchDropdown.querySelector('.search-result');
    if (first) selectSearchResult(first.dataset.id);
  }
});

document.addEventListener('click', e => {
  if (!document.getElementById('search-wrap').contains(e.target)) {
    searchDropdown.style.display = 'none';
  }
});

// ─── Init ─────────────────────────────────────────────────────────────────────
switchView('sankey');
</script>
</body>
</html>
"""


def generate_html(all_period_data, period_keys, timeseries, all_years, maker_class):
    period_json = json.dumps(all_period_data)
    period_keys_json = json.dumps(period_keys)
    timeseries_json = json.dumps(timeseries)
    years_json = json.dumps(all_years)
    maker_class_json = json.dumps(maker_class)
    return (
        HTML_TEMPLATE
        .replace("__PERIOD_DATA__", period_json)
        .replace("__PERIOD_KEYS__", period_keys_json)
        .replace("__TIMESERIES_DATA__", timeseries_json)
        .replace("__ALL_YEARS__", years_json)
        .replace("__MAKER_CLASS__", maker_class_json)
    )


def main():
    print(f"Reading {CSV_PATH}")
    all_period_data, period_keys, timeseries, all_years, maker_class = build_graph_data()
    html = generate_html(all_period_data, period_keys, timeseries, all_years, maker_class)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Written: {OUTPUT_PATH}")
    print(f"File size: {OUTPUT_PATH.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
