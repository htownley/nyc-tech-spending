#!/usr/bin/env python3
"""Generate force-directed graph + Sankey visualization of NYC tech spending."""

import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
CSV_PATH     = PROJECT_ROOT / "data" / "outputs" / "digital_services_vendors.csv"
OTI_CSV_PATH = PROJECT_ROOT / "data" / "outputs" / "oti_vendors_for_classification.csv"
RAW_FY2025   = PROJECT_ROOT / "data" / "raw" / "fy2025_full.csv"
OUTPUT_PATH  = PROJECT_ROOT / "graph.html"

PRIVACY_PLACEHOLDER = "N/A (PRIVACY/SECURITY)"


def parse_spending(val):
    try:
        return float(val.replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0



def build_graph_data():
    nodes = []
    links = []
    agency_seen = set()

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
            "fy2025_spending": fy2025,
            "description": str(row.get("description", "")).strip(),
        }

    # OTI vendors not already in main list; fy2025_spending is OTI-only here
    # and will be replaced with city-wide spend after reading the raw data.
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
            "fy2025_spending": fy2025,
            "description": str(row.get("rationale", "")).strip(),
        }
        oti_vendor_names.add(vendor_name)

    # ── Step 2: actual per-agency spend from raw FY2025 transactions ─────────
    OTI_AGENCY = "Department of Information Technology and Telecommunications"
    print(f"Reading {RAW_FY2025} ({RAW_FY2025.stat().st_size // 1_000_000} MB)...")
    df = pd.read_csv(RAW_FY2025, usecols=["payee_name", "agency", "check_amount"])
    df = df[df["payee_name"].isin(vendor_meta.keys())]
    df["check_amount"] = pd.to_numeric(df["check_amount"], errors="coerce").fillna(0)
    agg = (
        df.groupby(["payee_name", "agency"])["check_amount"]
        .sum()
        .reset_index()
        .rename(columns={"check_amount": "spend"})
    )
    agg = agg[agg["spend"] > 0]
    print(f"Vendor-agency pairs with spend: {len(agg)}")

    # City-wide totals (used to update OTI-vendor spend and for oti_spending)
    citywide = agg.groupby("payee_name")["spend"].sum()
    oti_spend_by_vendor = (
        agg[agg["agency"] == OTI_AGENCY]
        .set_index("payee_name")["spend"]
    )

    # Update OTI vendors to use city-wide spend instead of OTI-only
    for vname in oti_vendor_names:
        if vname in citywide:
            vendor_meta[vname]["fy2025_spending"] = float(citywide[vname])

    # ── Step 3: build nodes ───────────────────────────────────────────────────
    for vendor_name, meta in vendor_meta.items():
        oti_s = float(oti_spend_by_vendor.get(vendor_name, 0))
        nodes.append({
            "id": vendor_name,
            "type": "vendor",
            "classification": meta["classification"],
            "fy2025_spending": meta["fy2025_spending"],
            "oti_spending": round(oti_s, 2),
            "description": meta["description"],
        })

    for _, row in agg.iterrows():
        vendor_name = row["payee_name"]
        agency      = row["agency"]
        spend       = round(float(row["spend"]), 2)

        if vendor_name not in vendor_meta:
            continue

        if agency not in agency_seen:
            agency_seen.add(agency)
            nodes.append({
                "id": agency,
                "type": "agency",
                "classification": "agency",
                "fy2025_spending": 0,
                "oti_spending": 0,
                "radius": 9,
                "description": "",
            })

        links.append({"source": vendor_name, "target": agency, "spend": spend})

    # ── Step 4: counts for tooltips ───────────────────────────────────────────
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

    print(f"Vendors: {vendor_count}")
    print(f"Agencies: {agency_count}")
    print(f"Links: {len(links)}")

    return nodes, links


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

  .filter-btn {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.5px;
    padding: 5px 12px;
    border: 1px solid rgba(255,255,255,0.15);
    background: rgba(8,12,20,0.8);
    color: #8a9ab5;
    cursor: pointer;
    border-radius: 3px;
    transition: all 0.15s;
    text-transform: uppercase;
  }

  .filter-btn:hover { border-color: rgba(232,160,48,0.5); color: #e8a030; }

  .filter-btn.active {
    background: rgba(232,160,48,0.15);
    border-color: #e8a030;
    color: #e8a030;
  }

  #slider-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    color: #6a7a95;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  #oti-toggle {
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

  #legend {
    position: fixed;
    bottom: 20px;
    left: 22px;
    z-index: 10;
    display: flex;
    flex-direction: column;
    gap: 7px;
    font-size: 11px;
    color: #6a7a95;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .legend-item { display: flex; align-items: center; gap: 9px; }
  .legend-dot { border-radius: 50%; flex-shrink: 0; }

  #stats {
    position: fixed;
    bottom: 20px;
    right: 22px;
    z-index: 10;
    text-align: right;
    font-size: 11px;
    color: #3a4a5f;
    line-height: 1.8;
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

  /* Sankey-specific */
  .sk-label { pointer-events: none; }
  #sankey-hint {
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 10;
    font-size: 11px;
    color: #3a4a5f;
    letter-spacing: 0.3px;
    display: none;
  }
</style>
</head>
<body>

<div id="ui">
  <div id="title">NYC TECH SPENDING</div>

  <div id="view-toggle">
    <button class="view-btn active" data-view="network">Network</button>
    <button class="view-btn" data-view="sankey">Sankey</button>
  </div>

  <div id="ui-sep"></div>

  <div id="controls">
    <button class="filter-btn active" data-filter="all">All</button>
    <button class="filter-btn" data-filter="digital">Digital</button>
    <button class="filter-btn" data-filter="mixed">Mixed</button>
    <button class="filter-btn" data-filter="hardware">Hardware</button>
    <button class="filter-btn" data-filter="nontechnical">Nontechnical</button>
    <button class="filter-btn" data-filter="internal">Internal</button>
    <button id="oti-toggle">OTI only</button>
    <div id="slider-wrap">
      Min spend:
      <input type="range" id="threshold-slider" min="0" max="100" value="0" step="1">
      <span id="threshold-label">$0M</span>
    </div>
  </div>
</div>

<svg id="canvas"></svg>
<svg id="sankey-canvas" style="display:none"></svg>

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
  <div class="legend-item" id="legend-size-note" style="margin-top:4px;border-top:1px solid rgba(255,255,255,0.06);padding-top:6px">
    Node size &#8733; FY2025 spending
  </div>
  <div class="legend-item" id="legend-sankey-note" style="margin-top:4px;border-top:1px solid rgba(255,255,255,0.06);padding-top:6px;display:none">
    Bar height &amp; band width &#8733; FY2025 spend
  </div>
</div>

<div id="stats">
  <div>Vendors: <span id="stat-vendors">&#8212;</span></div>
  <div>Agencies: <span id="stat-agencies">&#8212;</span></div>
  <div>Connections: <span id="stat-links">&#8212;</span></div>
</div>

<div id="sankey-hint">Band width &#8733; estimated spend flow &nbsp;|&nbsp; Use min-spend slider to reduce density</div>

<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/d3-sankey@0.12.3/dist/d3-sankey.min.js"></script>
<script>
const RAW_NODES = __NODES_DATA__;

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
function nodeColor(d)  { return d.type === 'agency' ? '#5a9fd4' : (VENDOR_COLORS[d.classification]  || '#d4624a'); }
function nodeStroke(d) { return d.type === 'agency' ? '#5a9fd4' : (VENDOR_STROKES[d.classification] || 'rgba(212,98,74,0.3)'); }
function gradId(d)     { return 'sk-grad-' + (d.classification || 'mixed').toLowerCase().replace(/[^a-z]/g, ''); }
const RAW_LINKS = __LINKS_DATA__;

// ─── State ────────────────────────────────────────────────────────────────────
let activeFilter = 'all';
let thresholdM = 0;
let currentView = 'network';
let isOtiMode = false;
let pinnedNodes = new Set();

const OTI_AGENCY = 'Department of Information Technology and Telecommunications';

function activeSpend(node) {
  return isOtiMode ? (node.oti_spending || 0) : node.fy2025_spending;
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
  ttName.textContent = d.id;
  if (d.type === 'vendor') {
    const ttClass = { Digital: 'tt-type-vendor', Mixed: 'tt-type-mixed', Hardware: 'tt-type-hardware', Nontechnical: 'tt-type-nontechnical', Internal: 'tt-type-internal' };
    ttName.className = `tt-name ${ttClass[d.classification] || 'tt-type-mixed'}`;
    const spend = activeSpend(d);
    const m = (spend / 1e6).toFixed(1);
    const spendLabel = isOtiMode ? 'OTI Spend' : 'FY2025 Spend';
    ttBody.innerHTML = `
      <div class="tt-row">Type: <span>${d.classification}</span></div>
      <div class="tt-row">${spendLabel}: <span>$${m}M</span></div>
      <div class="tt-row">Agencies served: <span>${d.agency_count}</span></div>
      ${d.description ? `<div class="tt-row" style="margin-top:5px;color:#5a6a80;font-size:11px">${d.description.substring(0,120)}${d.description.length>120?'&hellip;':''}</div>` : ''}
    `;
  } else {
    ttName.className = 'tt-name tt-type-agency';
    const estM = d._estSpend ? (d._estSpend / 1e6).toFixed(1) : null;
    ttBody.innerHTML = `
      <div class="tt-row">Agency</div>
      <div class="tt-row">Active vendors: <span>${d.vendor_count}</span></div>
      ${estM ? `<div class="tt-row">FY2025 tech spend: <span>$${estM}M</span></div>` : ''}
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
const svg = d3.select('#canvas').attr('width', W).attr('height', H);

const defs = svg.append('defs');
const glowFilter = defs.append('filter').attr('id', 'glow')
  .attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%');
glowFilter.append('feGaussianBlur').attr('stdDeviation', '4').attr('result', 'blur');
const feMerge = glowFilter.append('feMerge');
feMerge.append('feMergeNode').attr('in', 'blur');
feMerge.append('feMergeNode').attr('in', 'SourceGraphic');

const zoomGroup = svg.append('g').attr('id', 'zoom-group');
svg.call(d3.zoom().scaleExtent([0.1, 8]).on('zoom', e => {
  zoomGroup.attr('transform', e.transform);
  zoomGroup.selectAll('.node-label').attr('opacity', e.transform.k > 2.5 ? 1 : 0);
}));

let linkSel, nodeSel;

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

  nodes.forEach(n => { if (pinnedNodes.has(n.id)) { n.fx = n.x; n.fy = n.y; } });

  linkSel = zoomGroup.append('g').attr('class', 'links')
    .selectAll('line').data(links).join('line')
    .attr('stroke', 'rgba(255,255,255,0.06)')
    .attr('stroke-width', 1);

  const nodeGroup = zoomGroup.append('g').attr('class', 'nodes')
    .selectAll('g').data(nodes).join('g')
    .attr('class', 'node-group')
    .call(d3.drag()
      .on('start', (e, d) => { if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
      .on('drag',  (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on('end',   (e, d) => { if (!e.active) simulation.alphaTarget(0); if (!pinnedNodes.has(d.id)) { d.fx = null; d.fy = null; } })
    )
    .on('mouseover', (event, d) => { showTooltip(d, event); highlightNet(d, nodeGroup, linkSel); })
    .on('mousemove', (event)    => positionTooltip(event))
    .on('mouseout',  ()         => { hideTooltip(); resetNet(nodeGroup, linkSel); })
    .on('click', (event, d) => {
      event.stopPropagation();
      if (pinnedNodes.has(d.id)) { pinnedNodes.delete(d.id); d.fx = null; d.fy = null; }
      else { pinnedNodes.add(d.id); d.fx = d.x; d.fy = d.y; }
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

function buildSankey() {
  skSvg.selectAll('.sk-layer').remove();

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

  updateStats(allNodes, rawLinks);

  const ML = 230, MR = 240, MT = 52, MB = 24;

  const sankey = d3.sankey()
    .nodeId(d => d.id)
    .nodeWidth(14)
    .nodePadding(3)
    .extent([[ML, MT], [W - MR, H - MB]]);

  let graph;
  try {
    graph = sankey({ nodes: allNodes, links: sankeyLinks });
  } catch(e) {
    console.error('Sankey layout error:', e);
    return;
  }

  // ── Gradient defs for bands (blue → vendor category color) ──
  skDefs.selectAll('.sk-grad').remove();
  [['sk-grad-digital', '#e8a030'], ['sk-grad-mixed', '#d4624a'],
   ['sk-grad-hardware', '#7c6af0'], ['sk-grad-nontechnical', '#4a9a72'],
   ['sk-grad-internal', '#5a7a8a']].forEach(([id, endColor]) => {
    const g = skDefs.append('linearGradient').attr('class', 'sk-grad').attr('id', id)
      .attr('gradientUnits', 'userSpaceOnUse')
      .attr('x1', ML).attr('y1', 0).attr('x2', W - MR).attr('y2', 0);
    g.append('stop').attr('offset', '0%').attr('stop-color', '#5a9fd4').attr('stop-opacity', 0.55);
    g.append('stop').attr('offset', '100%').attr('stop-color', endColor).attr('stop-opacity', 0.55);
  });

  // ── Draw bands ──
  const linkLayer = skSvg.append('g').attr('class', 'sk-layer sk-links');
  const linkPaths = linkLayer.selectAll('path')
    .data(graph.links)
    .join('path')
    .attr('d', d3.sankeyLinkHorizontal())
    .attr('stroke', d => `url(#${gradId(d.target)})`)
    .attr('stroke-width', d => Math.max(0.5, d.width))
    .attr('stroke-opacity', 1)
    .attr('fill', 'none');

  // ── Draw node rects ──
  const nodeLayer = skSvg.append('g').attr('class', 'sk-layer sk-nodes');
  const nodeRects = nodeLayer.selectAll('rect')
    .data(graph.nodes)
    .join('rect')
    .attr('x',      d => d.x0)
    .attr('y',      d => d.y0)
    .attr('width',  d => d.x1 - d.x0)
    .attr('height', d => Math.max(1, d.y1 - d.y0))
    .attr('fill',   d => d.type === 'agency' ? '#5a9fd4' : nodeColor(d))
    .attr('fill-opacity', 0.82)
    .attr('rx', 1);

  // ── Draw labels ──
  const labelLayer = skSvg.append('g').attr('class', 'sk-layer sk-labels');
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
    .attr('opacity', d => (d.y1 - d.y0) >= 9 ? 1 : 0)
    .text(d => {
      const maxLen = d.type === 'agency' ? 32 : 26;
      return d.id.length > maxLen ? d.id.substring(0, maxLen - 2) + '\u2026' : d.id;
    });

  // ── Hover ──
  nodeRects
    .on('mouseover', (event, d) => {
      showTooltip(d, event);
      const connIds = new Set([d.id]);
      linkPaths.each(function(l) {
        if (l.source.id === d.id || l.target.id === d.id) {
          connIds.add(l.source.id); connIds.add(l.target.id);
        }
      });
      linkPaths
        .attr('stroke-opacity', l =>
          (l.source.id === d.id || l.target.id === d.id) ? 1 : 0.04)
        .attr('stroke', l =>
          (l.source.id === d.id || l.target.id === d.id)
            ? `url(#${gradId(l.target)})`
            : 'rgba(255,255,255,0.15)');
      nodeRects
        .attr('fill-opacity', nd => connIds.has(nd.id) ? 0.95 : 0.12)
        .attr('filter', nd => connIds.has(nd.id) ? 'url(#sk-glow)' : null);
    })
    .on('mousemove', event => positionTooltip(event))
    .on('mouseout', () => {
      hideTooltip();
      linkPaths
        .attr('stroke-opacity', 1)
        .attr('stroke', d => `url(#${gradId(d.target)})`);
      nodeRects
        .attr('fill-opacity', 0.82)
        .attr('filter', null);
    });
}

// ═══════════════════════════════════════════════════════════════════════════════
// VIEW TOGGLE
// ═══════════════════════════════════════════════════════════════════════════════
function switchView(view) {
  currentView = view;
  const isNet = view === 'network';
  document.getElementById('canvas').style.display        = isNet ? '' : 'none';
  document.getElementById('sankey-canvas').style.display = isNet ? 'none' : '';
  document.getElementById('legend-size-note').style.display   = isNet ? ''     : 'none';
  document.getElementById('legend-sankey-note').style.display = isNet ? 'none' : '';
  document.getElementById('sankey-hint').style.display        = isNet ? 'none' : 'block';

  document.querySelectorAll('.view-btn').forEach(b => b.classList.toggle('active', b.dataset.view === view));

  if (isNet) {
    if (simulation) simulation.alphaTarget(0);
    buildGraph();
  } else {
    if (simulation) simulation.stop();
    buildSankey();
  }
}

document.querySelectorAll('.view-btn').forEach(btn => {
  btn.addEventListener('click', () => switchView(btn.dataset.view));
});

// ─── Filter / slider controls ─────────────────────────────────────────────────
document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeFilter = btn.dataset.filter;
    pinnedNodes.clear();
    currentView === 'network' ? buildGraph() : buildSankey();
  });
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
  currentView === 'network' ? buildGraph() : buildSankey();
});

document.getElementById('oti-toggle').addEventListener('click', function() {
  isOtiMode = !isOtiMode;
  this.classList.toggle('active', isOtiMode);
  slider.value = 0;
  thresholdM = 0;
  updateSliderLabel();
  pinnedNodes.clear();
  currentView === 'network' ? buildGraph() : buildSankey();
});

// ─── Init ─────────────────────────────────────────────────────────────────────
switchView('network');
</script>
</body>
</html>
"""


def generate_html(nodes, links):
    nodes_json = json.dumps(nodes)
    links_json = json.dumps(links)
    return HTML_TEMPLATE.replace("__NODES_DATA__", nodes_json).replace("__LINKS_DATA__", links_json)


def main():
    print(f"Reading {CSV_PATH}")
    nodes, links = build_graph_data()
    html = generate_html(nodes, links)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Written: {OUTPUT_PATH}")
    print(f"File size: {OUTPUT_PATH.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
