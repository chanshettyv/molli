"""Static option vocabularies for the IT issue intake dialog.

Single source of truth for the selection lists used by the dialog builder
in app/cards/dialog.py. Keeping these here (rather than inline in the
builder) means the vocabularies can be maintained in one place when the
Freshservice admin (Adam) confirms the canonical values.

NOTE on selection pre-fill: when Molli pre-fills a selection field, the
value it supplies must match one of these strings EXACTLY (character for
character) or nothing gets selected and it fails silently. If/when an LLM
infers these from chat, constrain it to pick from these lists or fuzzy-match
its guess back onto an exact value before building the dialog.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Affected Location (MULTI_SELECT)
# Source: Freshservice location field, June 2026.
# ---------------------------------------------------------------------------
LOCATIONS: list[str] = [
    "1820 at Centennial",
    "21 Pearl",
    "24 Longview",
    "2909 Oliver",
    "61 Vandy",
    "Auraria Lofts",
    "Axis West Campus",
    "Blue Hill",
    "Cabana Beach Gainesville",
    "Cabana Beach San Marcos",
    "Campus Edge",
    "Colonial Village",
    "Corporate: Accounting",
    "Corporate: Construction Mgmt",
    "Corporate: Executive Team",
    "Corporate: HR",
    "Corporate: IT",
    "Corporate: Management Specialists",
    "Corporate: Marketing",
    "Corporate: New Business",
    "Corporate: Operations",
    "Corporate: PM",
    "Courtyard Lofts",
    "Crossing Place",
    "Eastern on 10th",
    "Flats at Carrs Hill",
    "Gamecock Village",
    "Garnet Crossing",
    "Gateway at Huntsville",
    "Gorman Row",
    "Greene Crossing",
    "Greene Crossing - Commercial",
    "High View",
    "Hoffler Place",
    "Hoffler Place - Commercial",
    "Holleman Crossing",
    "IRIS",
    "Logan Square",
    "Madera",
    "Method Townhomes",
    "Midtown Auburn",
    "Midtown Auburn - Commercial",
    "Mustang Village",
    "Nova Knoxville",
    "Nova Knoxville - Commercial",
    "Orion on Orpington",
    "Platos Lofts at Randall",
    "Preiss Residential Living",
    "Proximity at 10th",
    "Quantum on West Call",
    "Raleigh Condos",
    "Redfield Villages",
    "Red Wolf Crossing",
    "River Club Apartments",
    "Riverfront Village",
    "Signature 1505",
    "Signature 1909",
    "Signature at Varsity",
    "Signature Hartwell Village",
    "Signature Music Row",
    "Signature Music Row - Commercial",
    "Signature on Grand",
    "Social Block",
    "Tenzing Portfolio",
    "The Avenue at Norman",
    "The Boundary at West End",
    "The Bridges Dinkytown",
    "The Collective at Auburn",
    "The Collective at Clemson",
    "The Collective at Kennesaw",
    "The Collective at Lawrence",
    "The Collective at Lubbock",
    "The Collective at Norman",
    "The Edition on Oberlin",
    "The Edition on Rosemary",
    "The Forum at Sam Houston",
    "The Gathering at UC",
    "The Greens at Tryon",
    "The Knoll Dinkytown",
    "The Lookout",
    "The Mill",
    "The Nest at 4955",
    "The Nest at University Center",
    "The One Clemson",
    "The Outpost",
    "The Park on Morton",
    "The Park on Morton - Commercial",
    "The Province Greensboro",
    "The Row (Columbia, MO)",
    "The Row at the Stadium",
    "The Townhomes at River Club",
    "The Union",
    "The Vine at Bermuda Run",
    "The Warehouse",
    "The Wynwood",
    "University Trails",
    "University Village at Clemson (UV)",
    "University Woods",
    "Valentine Commons",
    "Valentine Commons - Commercial",
    "Venue on Guadalupe",
    "Venue on Guadalupe - Commercial",
    "View at Legacy Oaks",
    "Villas on Guadalupe",
    "Villas on Guadalupe - Commercial",
    "Vintages at Clemson",
]

# ---------------------------------------------------------------------------
# System Item (DROPDOWN)
# Source: Freshservice system item field, June 2026.
# Placeholder entry "..." and "Other - do not use" intentionally omitted.
# ---------------------------------------------------------------------------
SYSTEM_ITEMS: list[str] = [
    "Computer/Laptop",
    "Daily Number (DN) Spreadsheet",
    "Entrata",
    "Google Apps (Gmail/email / Drive / Calendar / Docs)",
    "IRIS Technologies: Project Request",
    "Realpage - Knock",
    "Realpage - On-Site Online Leasing",
    "Realpage - Onesite, Financial Suite, Unified",
    "Preiss IQ / Domo",
    "Printer/Copier",
    "Turn - Workbook, Spreadsheets, Jotforms, Documents, etc",
    "Windows",
    "Adobe Products",
    "Amazon Business Account",
    "Amber",
    "Amex/Reconciliation (American Express)",
    "Appfolio",
    "Atmosphere TV",
    "Bloomberg",
    "Bonus Portal",
    "Canva",
    "CollegeHouse",
    "Community Rewards",
    "Corporate Server (TPCO CITRIX + Remanage)",
    "Courtesy Connection",
    "Email Distribution Lists",
    "Flex",
    "Document or Tutorial Request",
    "Entrata - Utilities (Edition on Oberlin)",
    "Epitiro",
    "EZ Turn",
    "GeoKey (Smart Locks)",
    "Google Chrome",
    "Google Sheets/Excel - RO, Electric, Bonus Form, Budget, Master Dashboard, etc.",
    "Grace Hill PerformanceHQ",
    "Grata (Smart Locks)",
    "HelloSign/DocuSign/Adobe Sign",
    "Homebase (Smart Locks)",
    "Hyly - Email Blasts & Drip Campaigns",
    "ILS - Apartments.com, Rent.com, etc",
    "Insurance - DPPSCIC / Stern / ePremium",
    "Leap",
    "Loaner Request/Checkout (laptops, hotspots, etc)",
    "Lock Systems",
    "Maintenance Supply Companies (HD, Lowes, Ferguson, Chadwell)",
    "MailChimp/iContact",
    "Microsoft Office",
    "Mood Media - Music",
    "National Credit Systems (NCS) - Collections",
    "Nationwide Eviction",
    "Network/Internet",
    "Notifii Packages",
    "Staples (Office Supplies)",
    "Package Lockers - Luxer One, Parcel Pending, Amazon Hub",
    "Paylease/Zego",
    "PayReady Collections",
    "Phone",
    "Property Website",
    "QR Codes",
    "Quickbooks",
    "Quote Request - Hardware/Devices or Software",
    "RentPlus/Homebody Rent Reporting",
    "Reviews/Reputation/Surveys - Opiniion, J Turner, Yelp, Google Business",
    "SmartRent (Smart Locks)",
    "Social Media - Facebook, Instagram, Google Business",
    "Stratis (Smart Locks)",
    "Student.com",
    "Tawk.to",
    "Tour24",
    "Travtus",
    "UHomes",
    "Update Office Hours",
    "Utilities - SimpleBills, Conservice, AUM",
    "Yet Another Mail Merge (YAMM)",
    "Zoom Conferencing",
]

# ---------------------------------------------------------------------------
# Group (DROPDOWN) — maps to Freshservice group_id on ticket creation.
# Source: Freshservice groups, June 2026.
#
# Unlike the other lists, group has distinct display text and submitted
# value: `name` is shown to the user, `id` is the Freshservice group_id
# sent on ticket creation. Build selection items as:
#   [{"text": g["name"], "value": str(g["id"])} for g in GROUPS]
# (value stringified — selectionInput values are strings; cast back to int
# when building the Freshservice payload.)
#
# Note: "IRIS " has a trailing space in the source data, preserved exactly.
# Flag to Adam if unintended.
# ---------------------------------------------------------------------------
GROUPS: list[dict[str, object]] = [
    {"id": 5000337271, "name": "IRIS "},
    {"id": 5000233136, "name": "IT"},
    {"id": 5000334601, "name": "IT + Marketing"},
    {"id": 5000263627, "name": "IT + Ops"},
    {"id": 5000340456, "name": "Kasey"},
    {"id": 5000333962, "name": "Marketing"},
    {"id": 5000333963, "name": "Mktg + Ops"},
    {"id": 5000233137, "name": "Operations"},
    {"id": 5000338615, "name": "Operations (Access)"},
    {"id": 5000338084, "name": "Ops + Mktg + IT"},
    {"id": 5000340154, "name": "Ops + Mktg + IT + BI"},
    {"id": 5000339761, "name": "OPS + Preiss IQ"},
    {"id": 5000339544, "name": "Preiss IQ"},
]

STATUSES: list[dict[str, object]] = [
    {"value": 2, "name": "Open"},
    {"value": 3, "name": "Pending"},
    {"value": 4, "name": "Resolved"},
    {"value": 5, "name": "Closed"},
]

# ---------------------------------------------------------------------------
# Priority — maps to Freshservice ticket `priority` on creation.
# Source: Freshservice standard priority enum.
# Display text shown to user; integer `value` sent to the API.
# ---------------------------------------------------------------------------
PRIORITIES: list[dict[str, object]] = [
    {"value": 1, "name": "Low"},
    {"value": 2, "name": "Medium"},
    {"value": 3, "name": "High"},
    {"value": 4, "name": "Urgent"},
]
