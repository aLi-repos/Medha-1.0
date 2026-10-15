"""Synthetic Pump P-204 Industrial Dataset.

Illustrative industrial scenario inspired by publicly documented refinery
and enterprise security requirements. This demonstration does not represent
MRPL's internal architecture.

All data is synthetic and labeled for demonstration purposes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import random
import hashlib


@dataclass
class FailureRecord:
    timestamp: datetime
    failure_type: str
    severity: str
    component: str
    downtime_hours: float
    cost_usd: float
    root_cause: str
    resolved: bool


@dataclass
class MaintenanceRecord:
    timestamp: datetime
    action: str
    technician: str
    parts_replaced: list[str]
    notes: str


@dataclass
class SensorReading:
    timestamp: datetime
    vibration_mm_s: float
    temperature_c: float
    pressure_bar: float
    flow_rate_m3h: float
    current_amps: float


FAILURE_TYPES = [
    ("Mechanical Seal Failure", "critical", "seal", "Seal face wear exceeds tolerance"),
    ("Bearing Overheat", "high", "bearing", "Lubrication degradation detected"),
    ("Impeller Erosion", "medium", "impeller", "Cavitation-induced material loss"),
    ("Motor Overload", "high", "motor", "Current draw exceeds rated capacity"),
    ("Coupling Misalignment", "medium", "coupling", "Vibration signature anomaly"),
    ("Cavitation Damage", "critical", "impeller", "NPSH insufficient at operating point"),
    ("Gasket Leak", "low", "gasket", "Compression set loss"),
    ("Vibration Exceedance", "medium", "bearing", "ISO 10816 Zone C threshold breach"),
]

MAINTENANCE_ACTIONS = [
    "Seal replacement",
    "Bearing inspection and replacement",
    "Impeller inspection",
    "Motor rewinding",
    "Coupling realignment",
    "Gasket replacement",
    "Vibration analysis",
    "Oil analysis and change",
    "Alignment check",
    "Thermographic inspection",
]

TECHNICIANS = [
    "Technician A-101",
    "Technician B-204",
    "Technician C-307",
    "Technician D-112",
]

PARTS = [
    "Mechanical seal",
    "Bearing assembly",
    "Impeller",
    "Motor coupling",
    "Gasket set",
    "Lubricant",
    "Vibration sensor",
    "Temperature probe",
]


def _hash_seed(data: str) -> int:
    return int(hashlib.sha256(data.encode()).hexdigest()[:8], 16)


def generate_synthetic_dataset() -> dict:
    """Generate 24 months of synthetic Pump P-204 data."""
    rng = random.Random(_hash_seed("P204-MEDHA-DEMO"))

    start = datetime(2024, 1, 1)
    failures: list[FailureRecord] = []
    maintenance: list[MaintenanceRecord] = []
    sensors: list[SensorReading] = []

    # Generate failures — more frequent in last 6 months
    for month_offset in range(24):
        dt = start + timedelta(days=30 * month_offset)
        # Failure rate increases after month 12
        num_failures = rng.randint(0, 2) if month_offset < 12 else rng.randint(1, 4)
        for _ in range(num_failures):
            ftype, severity, component, cause = rng.choice(FAILURE_TYPES)
            day = rng.randint(1, 28)
            hour = rng.randint(0, 23)
            ts = dt.replace(day=day, hour=hour)
            downtime = round(rng.uniform(2, 72) if severity != "low" else rng.uniform(0.5, 8), 1)
            cost = round(downtime * rng.uniform(150, 800) + rng.uniform(200, 5000), 2)
            failures.append(FailureRecord(
                timestamp=ts,
                failure_type=ftype,
                severity=severity,
                component=component,
                downtime_hours=downtime,
                cost_usd=cost,
                root_cause=cause,
                resolved=rng.random() > 0.05,
            ))

    failures.sort(key=lambda f: f.timestamp)

    # Generate maintenance records
    for f in failures:
        maint_ts = f.timestamp + timedelta(hours=rng.randint(1, 12))
        action = rng.choice(MAINTENANCE_ACTIONS)
        tech = rng.choice(TECHNICIANS)
        parts = rng.sample(PARTS, k=rng.randint(0, 3))
        maintenance.append(MaintenanceRecord(
            timestamp=maint_ts,
            action=action,
            technician=tech,
            parts_replaced=parts,
            notes=f"Post-failure maintenance: {f.failure_type}",
        ))

    # Generate sensor readings — every 4 hours for 24 months
    current = start
    end = start + timedelta(days=730)
    while current < end:
        base_vib = 2.5 + (1.0 if current > start + timedelta(days=365) else 0)
        base_temp = 65 + (5 if current > start + timedelta(days=365) else 0)
        sensors.append(SensorReading(
            timestamp=current,
            vibration_mm_s=round(rng.gauss(base_vib, 0.8), 2),
            temperature_c=round(rng.gauss(base_temp, 3.5), 1),
            pressure_bar=round(rng.gauss(4.2, 0.3), 2),
            flow_rate_m3h=round(rng.gauss(85, 5), 1),
            current_amps=round(rng.gauss(12.5, 0.6), 2),
        ))
        current += timedelta(hours=4)

    # Analysis summary
    total_downtime = sum(f.downtime_hours for f in failures)
    total_cost = sum(f.cost_usd for f in failures)
    critical_count = sum(1 for f in failures if f.severity == "critical")
    high_count = sum(1 for f in failures if f.severity == "high")

    # Component failure frequency
    component_freq: dict[str, int] = {}
    for f in failures:
        component_freq[f.component] = component_freq.get(f.component, 0) + 1

    # Monthly downtime trend
    monthly_downtime: dict[str, float] = {}
    monthly_cost: dict[str, float] = {}
    for f in failures:
        key = f.timestamp.strftime("%Y-%m")
        monthly_downtime[key] = monthly_downtime.get(key, 0) + f.downtime_hours
        monthly_cost[key] = monthly_cost.get(key, 0) + f.cost_usd

    # MTBF calculation
    if len(failures) > 1:
        time_span_hours = (failures[-1].timestamp - failures[0].timestamp).total_seconds() / 3600
        mtbf_hours = round(time_span_hours / (len(failures) - 1), 1)
    else:
        mtbf_hours = 0

    return {
        "equipment": {
            "id": "P-204",
            "name": "Centrifugal Pump P-204",
            "location": "Refinery Unit 3 — Crude Distillation",
            "manufacturer": "Sulzer",
            "model": "CPT 2-31",
            "rated_flow_m3h": 95,
            "rated_head_m": 45,
            "motor_power_kw": 22,
            "installation_date": "2019-06-15",
        },
        "failures": [
            {
                "timestamp": f.timestamp.isoformat(),
                "failure_type": f.failure_type,
                "severity": f.severity,
                "component": f.component,
                "downtime_hours": f.downtime_hours,
                "cost_usd": f.cost_usd,
                "root_cause": f.root_cause,
                "resolved": f.resolved,
            }
            for f in failures
        ],
        "maintenance": [
            {
                "timestamp": m.timestamp.isoformat(),
                "action": m.action,
                "technician": m.technician,
                "parts_replaced": m.parts_replaced,
                "notes": m.notes,
            }
            for m in maintenance
        ],
        "sensors": [
            {
                "timestamp": s.timestamp.isoformat(),
                "vibration_mm_s": s.vibration_mm_s,
                "temperature_c": s.temperature_c,
                "pressure_bar": s.pressure_bar,
                "flow_rate_m3h": s.flow_rate_m3h,
                "current_amps": s.current_amps,
            }
            for s in sensors
        ],
        "analysis_summary": {
            "period": "2024-01-01 to 2025-12-31",
            "total_failures": len(failures),
            "critical_failures": critical_count,
            "high_failures": high_count,
            "total_downtime_hours": round(total_downtime, 1),
            "total_cost_usd": round(total_cost, 2),
            "mtbf_hours": mtbf_hours,
            "component_failure_frequency": dict(sorted(component_freq.items(), key=lambda x: -x[1])),
            "monthly_downtime": dict(sorted(monthly_downtime.items())),
            "monthly_cost": dict(sorted(monthly_cost.items())),
            "resolution_rate": round(sum(1 for f in failures if f.resolved) / len(failures) * 100, 1) if failures else 0,
        },
    }
