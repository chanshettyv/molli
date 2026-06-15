"""Card and dialog builders for the dialogtest flow.

Bare-bones dialog spike: trigger card -> open dialog -> submit -> notify.
Plain-message responses use the chatDataAction envelope (see _chat_reply in
main.py); dialog open/submit responses use the renderActions envelope.
"""

from __future__ import annotations

from typing import Any

SERVICE_URL = "https://molli-chat-service-719635778769.us-central1.run.app/"


def trigger_card() -> dict[str, Any]:
    """Reply to 'dialogtest': a message card with a button that opens the dialog."""
    return {
        "hostAppDataAction": {
            "chatDataAction": {
                "createMessageAction": {
                    "message": {
                        "cardsV2": [
                            {
                                "cardId": "dialogtest-trigger",
                                "card": {
                                    "sections": [
                                        {
                                            "widgets": [
                                                {
                                                    "buttonList": {
                                                        "buttons": [
                                                            {
                                                                "text": "Open dialog",
                                                                "onClick": {
                                                                    "action": {
                                                                        "function": SERVICE_URL,
                                                                        "interaction": "OPEN_DIALOG",
                                                                        "parameters": [
                                                                            {
                                                                                "key": "actionName",
                                                                                "value": "openInitialDialog",
                                                                            }
                                                                        ],
                                                                    }
                                                                },
                                                            }
                                                        ]
                                                    }
                                                }
                                            ]
                                        }
                                    ]
                                },
                            }
                        ]
                    }
                }
            }
        }
    }


def open_dialog() -> dict[str, Any]:
    """Response to the openInitialDialog click: push the IT issue intake dialog."""

    locations = [
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

    system_items = [
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

    location_items = [{"text": loc, "value": loc} for loc in locations]
    system_items = [{"text": item, "value": item} for item in system_items]

    return {
        "action": {
            "navigations": [
                {
                    "pushCard": {
                        "sections": [
                            {
                                "header": "Submit an IT issue",
                                "widgets": [
                                    {
                                        "textInput": {
                                            "label": "Email",
                                            "type": "SINGLE_LINE",
                                            "name": "email",
                                        }
                                    },
                                    {
                                        "selectionInput": {
                                            "name": "affectedLocation",
                                            "label": "Affected Location",
                                            "type": "MULTI_SELECT",
                                            "items": location_items,
                                        }
                                    },
                                    {
                                        "selectionInput": {
                                            "name": "systemItem",
                                            "label": "System Item",
                                            "type": "DROPDOWN",
                                            "items": system_items,
                                        }
                                    },
                                    {
                                        "textInput": {
                                            "label": "Summarize Issue",
                                            "type": "MULTIPLE_LINE",
                                            "name": "summary",
                                        }
                                    },
                                    {
                                        "textInput": {
                                            "label": "Details",
                                            "type": "MULTIPLE_LINE",
                                            "name": "details",
                                        }
                                    },
                                    {
                                        "textInput": {
                                            "label": "Computer Name",
                                            "type": "SINGLE_LINE",
                                            "name": "computerName",
                                        }
                                    },
                                    {
                                        "buttonList": {
                                            "buttons": [
                                                {
                                                    "text": "Submit",
                                                    "onClick": {
                                                        "action": {
                                                            "function": SERVICE_URL,
                                                            "parameters": [
                                                                {
                                                                    "key": "actionName",
                                                                    "value": "submitNameDialog",
                                                                }
                                                            ],
                                                        }
                                                    },
                                                }
                                            ]
                                        }
                                    },
                                ],
                            }
                        ]
                    }
                }
            ]
        }
    }


def submit_notification(name: str) -> dict[str, Any]:
    """Response to submitNameDialog: confirm via notification.

    The notification is the confirmed-correct Add-On submit response
    (per SubmitFormResponse docs). The explicit dialog-close instruction
    (standalone-Chat docs call it EndNavigation -> CLOSE_DIALOG) may differ
    in the Add-On envelope. TODO: verify against a real submit event log
    whether the notification alone dismisses the modal; if not, add the
    Add-On close instruction here.
    """
    return {
        "action": {
            "navigations": [{"endNavigation": {"action": "CLOSE_DIALOG"}}],
            "notification": {"text": f"Got it — name received: {name}"},
        }
    }
