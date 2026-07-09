#!/usr/bin/env python3
"""
Attribute reseller (pass-through) spending to underlying technology providers.

Reads data/raw/reseller_purposes.csv (from download_reseller_purposes.py),
extracts manufacturer/product names from contract purpose text, and writes
data/outputs/passthrough_attribution.csv plus a console report.

Attribution rules:
  - exactly one maker matched  -> that maker
  - multiple makers matched    -> "Multiple makers"
  - no maker matched           -> "Unattributed"

Usage:
  python3 scripts/analyze_passthrough.py
"""

import re

import pandas as pd

INPUT_FILE = "data/raw/reseller_purposes.csv"
OUTPUT_FILE = "data/outputs/passthrough_attribution.csv"

# canonical maker -> regex (applied to uppercased purpose text)
MAKERS = {
    "VMware": r"VMWARE|VM WARE|VSPHERE|VSAN|VCENTER|WORKSPACE ONE|WORKSPACE 1|\bWS1\b",
    "Microsoft": r"MICROSOFT|M365|MS365|O365|OFFICE 365|AZURE|SHAREPOINT|WINDOWS SERVER|MS SQL|SURFACE HUB|INTUNE|MS ELA|MS-ELA|MS POWERAPPS|DYNAMICS 365",
    "Oracle": r"ORACLE|PEOPLESOFT|NETSUITE|JAVA SE|EXADATA",
    "Adobe": r"ADOBE|ACROBAT",
    "Cisco": r"\bCISCO\b|WEBEX|MERAKI|DUO SECURITY|UMBRELLA|SMARTNET|IRONPORT|APPDYNAMICS|APP DYNAMICS|CISCOPRO",
    "Splunk": r"SPLUNK",
    "Trellix/McAfee": r"TRELLIX|MCAFEE|FIREEYE",
    "IBM": r"\bIBM\b|MAXIMO|COGNOS|\bSPSS\b|WATSON|INFOSPHERE|CLOUDPAK|CLOUD PAK|CURAM|QRADAR",
    "Red Hat": r"RED HAT|REDHAT|ANSIBLE|OPENSHIFT",
    "Nutanix": r"NUTANIX",
    "Citrix": r"CITRIX|XENAPP|NETSCALER",
    "Palo Alto Networks": r"PALO ALTO|PRISMA|CORTEX XDR|XSIAM|XSOAR|DEMISTO",
    "Fortinet": r"FORTINET|FORTIGATE|FORTIANALYZER",
    "Zscaler": r"ZSCALER",
    "CrowdStrike": r"CROWDSTRIKE|FALCON COMPLETE|FALCON HOST|FALCON SENSOR",
    "Okta": r"\bOKTA\b",
    "Proofpoint": r"PROOFPOINT",
    "KnowBe4": r"KNOWBE4|KNOW BE4",
    "Tenable": r"TENABLE|NESSUS",
    "Rapid7": r"RAPID7|RAPID 7",
    "Qualys": r"QUALYS",
    "CyberArk": r"CYBERARK|CYBER ARK",
    "SailPoint": r"SAILPOINT",
    "Varonis": r"VARONIS",
    "F5": r"\bF5\b",
    "Juniper": r"JUNIPER",
    "Arista": r"ARISTA",
    "Extreme Networks": r"EXTREME NETWORK",
    "Rubrik": r"RUBRIK",
    "Cohesity": r"COHESITY",
    "Pure Storage": r"PURE STORAGE",
    "NetApp": r"NETAPP|NET APP",
    "Commvault": r"COMMVAULT",
    "Veritas": r"VERITAS",
    "Veeam": r"VEEAM",
    "Broadcom/Symantec/CA": r"BROADCOM|SYMANTEC|CA MAINFRAME|CA TECHNOLOGIES",
    "Check Point": r"CHECK POINT|CHECKPOINT",
    "SentinelOne": r"SENTINELONE|SENTINEL ONE",
    "Forescout": r"FORESCOUT",
    "Infoblox": r"INFOBLOX",
    "Netscout": r"NETSCOUT",
    "Gigamon": r"GIGAMON",
    "Riverbed": r"RIVERBED",
    "Salesforce": r"SALESFORCE|MULESOFT",
    "Tableau": r"TABLEAU",
    "ServiceNow": r"SERVICENOW|SERVICE NOW",
    "Workday": r"WORKDAY",
    "SAP": r"\bSAP\b|SUCCESSFACTORS",
    "UKG/Kronos": r"KRONOS|\bUKG\b",
    "Atlassian": r"ATLASSIAN|JIRA|CONFLUENCE",
    "GitHub": r"GITHUB",
    "GitLab": r"GITLAB",
    "DocuSign": r"DOCUSIGN",
    "Smartsheet": r"SMARTSHEET",
    "Zoom": r"\bZOOM\b",
    "Slack": r"\bSLACK\b",
    "MongoDB": r"MONGODB|MONGO DB",
    "Snowflake": r"SNOWFLAKE",
    "Databricks": r"DATABRICKS",
    "Elastic": r"ELASTICSEARCH|\bELASTIC\b",
    "OpenAI": r"OPENAI|CHATGPT",
    "Google": r"GOOGLE|\bGCP\b|CHROMEBOOK|CHROME OS|MANDIANT",
    "AWS": r"\bAWS\b|AMAZON WEB",
    "Esri": r"\bESRI\b|ARCGIS",
    "SAS Institute": r"SAS INSTITUTE|SAS VIYA|SAS GRID|SAS ANALYTIC|SAS SOFTWARE",
    "Software AG": r"SOFTWARE AG",
    "Brocade": r"BROCADE",
    "MathWorks": r"MATLAB|MATHWORKS",
    "Qualtrics": r"QUALTRICS",
    "Apple": r"\bAPPLE\b|IPAD|MACBOOK|\bIMAC\b|IPHONE|\bMAC\b",
    "Dell/EMC": r"\bDELL\b|DELLEMC|LATITUDE|OPTIPLEX|POWEREDGE|\bEMC\b|ISILON|ALIENWARE|\bVMAX\b|\bVNX\b|VXRAIL|\bVCE\b|POWERSCALE|POWERSTORE",
    "HP/HPE": r"\bHP\b|\bHPE\b|HEWLETT|PROLIANT|LASERJET|ARUBA",
    "Lenovo": r"LENOVO|THINKPAD|THINKCENTRE",
    "Panasonic": r"PANASONIC|TOUGHBOOK",
    "Getac": r"GETAC",
    "Samsung": r"SAMSUNG",
    "Canon": r"\bCANON\b",
    "Xerox": r"XEROX",
    "Ricoh": r"RICOH",
    "Kyocera": r"KYOCERA",
    "Zebra": r"\bZEBRA\b",
    "Axon": r"\bAXON\b|TASER|FUSUS",
    "Motorola": r"MOTOROLA",
    "Poly/Polycom": r"POLYCOM|\bPOLY\b",
    "Logitech": r"LOGITECH",
    "Crestron": r"CRESTRON",
    "Promethean": r"PROMETHEAN",
    "SMART (boards)": r"SMARTBOARD|SMART BOARD",
    "ViewSonic": r"VIEWSONIC",
    "APC/Schneider": r"\bAPC\b|SCHNEIDER ELECTRIC",
    "Vertiv": r"VERTIV",
    "Autodesk": r"AUTODESK|AUTOCAD|REVIT",
    "Bentley": r"BENTLEY|MICROSTATION",
    "Bluebeam": r"BLUEBEAM",
    "NICE Systems": r"NICE SYSTEMS|NICE INFORM|NICE JUSTICE|NICE CXONE",
    "Genesys": r"GENESYS",
    "Avaya": r"AVAYA",
    "Verint": r"VERINT",
    "SolarWinds": r"SOLARWINDS",
    "Dynatrace": r"DYNATRACE",
    "Datadog": r"DATADOG",
    "Tyler Technologies": r"TYLER TECH|\bMUNIS\b",
    "Granicus": r"GRANICUS",
    "Accela": r"ACCELA",
    "Hyland/OnBase": r"HYLAND|ONBASE",
    "Laserfiche": r"LASERFICHE",
    "Kofax/Tungsten": r"KOFAX|TUNGSTEN AUTOMATION",
    "ABBYY": r"ABBYY",
    "OpenText": r"OPENTEXT|OPEN TEXT",
    "Ivanti": r"IVANTI",
    "BMC": r"\bBMC\b|REMEDY",
    "Pega": r"\bPEGA\b|PEGASYSTEMS",
    "Appian": r"APPIAN",
    "UiPath": r"UIPATH",
    "Alteryx": r"ALTERYX",
    "Informatica": r"INFORMATICA",
    "LexisNexis": r"LEXISNEXIS|LEXIS NEXIS",
    "Securonix": r"SECURONIX",
    "Ciena": r"CIENA",
    "Nuvalence": r"NUVALENCE",
    "Armis": r"\bARMIS\b",
    "Skyhigh Security": r"SKYHIGH",
    "Deloitte": r"DELOITTE",
    "MTX Group": r"\bMTX\b",
    "Live XYZ": r"LIVE XYZ",
    "ScienceLogic": r"SCIENCE LOGIC|SCIENCELOGIC",
    "Veracode": r"VERACODE",
    "Reveald": r"REVEALD",
    "Synack": r"SYNACK",
    "Redis": r"\bREDIS\b",
    "Axis Communications": r"AXIS BODY|AXIS CAMERA|AXIS COMMUNICATIONS",
    "BlueCrest": r"BLUE CREST|BLUECREST",
    "Software House/Tyco": r"SOFTWARE HOUSE|CCURE|C·CURE",
    "Thomson Reuters": r"WESTLAW|THOMSON REUTERS",
}

COMPILED = {name: re.compile(pat) for name, pat in MAKERS.items()}

OVERRIDES_FILE = "data/outputs/passthrough_overrides.csv"


def load_overrides():
    """Manual judgment-pass corrections: exact purpose string -> maker.

    Each row carries an evidence column explaining the attribution (e.g. a
    later year in the same budget-code series naming the maker).
    """
    import os
    if not os.path.exists(OVERRIDES_FILE):
        return {}
    df = pd.read_csv(OVERRIDES_FILE)
    return dict(zip(df["contract_purpose"], df["maker"]))


OVERRIDES = load_overrides()


def attribute(purpose):
    """Return (maker, matched_list) for a purpose string."""
    p = str(purpose)
    if p in OVERRIDES:
        return OVERRIDES[p], [OVERRIDES[p]]
    text = p.upper()
    matches = [name for name, rx in COMPILED.items() if rx.search(text)]
    if len(matches) == 1:
        return matches[0], matches
    if len(matches) > 1:
        return "Multiple makers", matches
    return "Unattributed", matches


def main():
    df = pd.read_csv(INPUT_FILE)
    df["check_amount"] = pd.to_numeric(df["check_amount"], errors="coerce").fillna(0)
    print(f"Loaded {len(df):,} checks, ${df['check_amount'].sum()/1e9:.2f}B total")

    # Attribute each distinct purpose once, then map back
    purposes = df["contract_purpose"].fillna("").unique()
    print(f"{len(purposes):,} distinct purpose strings")
    stale = set(OVERRIDES) - set(purposes)
    if stale:
        print(f"⚠ {len(stale)} override keys match no purpose in the data:")
        for s in sorted(stale):
            print(f"    {s!r}")
    attr_map = {p: attribute(p) for p in purposes}
    df["maker"] = df["contract_purpose"].fillna("").map(lambda p: attr_map[p][0])
    df["makers_matched"] = df["contract_purpose"].fillna("").map(
        lambda p: "; ".join(attr_map[p][1]))

    # Output: reseller x maker x year
    out = (
        df.groupby(["payee_name", "maker", "fiscal_year"])
        .agg(spend=("check_amount", "sum"), checks=("check_amount", "count"))
        .reset_index()
        .sort_values("spend", ascending=False)
    )
    out.to_csv(OUTPUT_FILE, index=False)
    print(f"Wrote {OUTPUT_FILE}\n")

    # ── Console report ───────────────────────────────────────────────────────
    total = df["check_amount"].sum()
    attributed = df[~df["maker"].isin(["Unattributed"])]["check_amount"].sum()
    print("=" * 70)
    print(f"OVERALL: ${attributed/1e9:.2f}B of ${total/1e9:.2f}B attributed "
          f"({attributed/total*100:.0f}%)")
    print("=" * 70)

    print("\nCoverage by reseller (all years):")
    for vendor, g in df.groupby("payee_name"):
        t = g["check_amount"].sum()
        a = g[g["maker"] != "Unattributed"]["check_amount"].sum()
        print(f"  {vendor}: ${t/1e6:,.0f}M total, {a/t*100:.0f}% attributed")

    print("\nTop 25 makers by attributed spend (all years, single-maker only):")
    league = (
        df[~df["maker"].isin(["Unattributed", "Multiple makers"])]
        .groupby("maker")["check_amount"].sum()
        .sort_values(ascending=False).head(25)
    )
    for maker, spend in league.items():
        print(f"  {maker}: ${spend/1e6:,.1f}M")

    print("\n'Multiple makers' bucket: "
          f"${df[df['maker']=='Multiple makers']['check_amount'].sum()/1e6:,.1f}M")

    print("\nTop 20 UNATTRIBUTED purposes by spend (dictionary candidates):")
    unattr = (
        df[df["maker"] == "Unattributed"]
        .groupby("contract_purpose")["check_amount"].sum()
        .sort_values(ascending=False).head(20)
    )
    for purpose, spend in unattr.items():
        print(f"  ${spend/1e6:8,.1f}M  {str(purpose)[:80]}")


if __name__ == "__main__":
    main()
