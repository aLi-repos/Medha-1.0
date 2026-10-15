"""Synthetic Pump P-204 demonstration documents for P4 local RAG.

Clearly labeled demonstration material. Not real MRPL operational data.
Safe for evaluator demo scenarios and tests.
"""

from __future__ import annotations

DEMO_DOCUMENTS: list[dict] = [
    {
        "source_name": "Pump_P204_Inspection_Report",
        "classification": "internal",
        "text": (
            "PUMP P-204 INSPECTION REPORT — DEMONSTRATION MATERIAL\n"
            "Centrifugal Pump P-204, Refinery Unit 3 Crude Distillation.\n"
            "Inspection date: 2026-01-15. Overall vibration 4.8 mm/s RMS, "
            "within ISO 10816 band B for this pump class.\n"
            "Bearing housing temperature 62°C. No active seal leak observed.\n"
            "Impeller shows minor cavitation erosion on leading edge.\n"
            "Recommendation: monitor vibration trend and schedule seal "
            "inspection within next maintenance window.\n"
            "This document is synthetic demonstration content for SIH26117."
        ),
    },
    {
        "source_name": "Pump_P204_Maintenance_SOP",
        "classification": "internal",
        "text": (
            "PUMP P-204 MAINTENANCE SOP — DEMONSTRATION MATERIAL\n"
            "Standard procedure for centrifugal pump P-204 maintenance.\n"
            "1. Isolate pump and lock out motor starter.\n"
            "2. Verify zero energy at coupling.\n"
            "3. Inspect mechanical seal faces for wear or crystallization.\n"
            "4. Check bearing grease condition and re-greas if required.\n"
            "5. Record vibration baseline after reassembly.\n"
            "Max allowable vibration before shutdown: 7.1 mm/s RMS.\n"
            "This SOP is synthetic demonstration content for SIH26117."
        ),
    },
    {
        "source_name": "Pump_P204_Equipment_Reference",
        "classification": "internal",
        "text": (
            "PUMP P-204 EQUIPMENT REFERENCE — DEMONSTRATION MATERIAL\n"
            "Equipment: Centrifugal Pump P-204.\n"
            "Rated flow: 120 m3/h. Rated head: 55 m. Motor rating: 45 kW.\n"
            "Seal type: single mechanical seal, carbon vs silicon carbide.\n"
            "Bearing: 6309 drive end, 6308 non-drive end.\n"
            "Design vibration limit: 4.5 mm/s normal, 7.1 mm/s alarm.\n"
            "This reference is synthetic demonstration content for SIH26117."
        ),
    },
]


def get_demo_documents() -> list[dict]:
    """Return copies of the frozen-style demo document set."""
    return [dict(d) for d in DEMO_DOCUMENTS]
