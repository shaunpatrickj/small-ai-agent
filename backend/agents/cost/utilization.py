from datetime import datetime
from typing import Dict, Optional
from database import get_connection
from .overview import get_cost_overview


def analyze_resource_utilization(facility_id: int = 1, ov: Optional[Dict] = None) -> Dict:
    """
    Evaluate cost efficiency by correlating expenditure with occupancy rate and equipment operations.
    """
    if ov is None:
        ov = get_cost_overview(facility_id)
    conn = get_connection()

    # Check peak energy vs base energy cost
    energy_stats = conn.execute("""
        SELECT AVG(electricity_usage) as avg_elec, MAX(electricity_usage) as peak_elec
        FROM ENERGY_USAGE WHERE facility_id=?
    """, (facility_id,)).fetchone()

    # Check open work orders and critical assets
    asset_stats = conn.execute("""
        SELECT COUNT(*) as total_assets,
               SUM(CASE WHEN status='CRITICAL' THEN 1 ELSE 0 END) as critical_assets,
               SUM(CASE WHEN status='WARNING' THEN 1 ELSE 0 END) as warning_assets
        FROM ASSETS WHERE facility_id=?
    """, (facility_id,)).fetchone()

    conn.close()

    insights = []

    # Energy insight
    energy_cat = ov["cost_by_category"].get("ENERGY", {})
    if energy_cat.get("variance", 0) > 0:
        insights.append({
            "category": "ENERGY",
            "severity": "WARNING",
            "finding": f"Energy expenditure exceeds budget allocation by ₹{energy_cat['variance']:,.2f} ({energy_cat['variance_pct']}%).",
            "driver": "Continuous HVAC baseline and peak demand tariff window surges.",
            "action": "Implement demand-limiting setpoint resets and off-hours night setbacks."
        })
    else:
        insights.append({
            "category": "ENERGY",
            "severity": "NORMAL",
            "finding": f"Energy consumption is currently within budgeted threshold (₹{energy_cat.get('amount', 0):,.2f}).",
            "driver": "Stable baselines without unmanaged demand spikes.",
            "action": "Maintain automated schedule setbacks."
        })

    # Maintenance insight
    maint_cat = ov["cost_by_category"].get("MAINTENANCE", {})
    crit_assets = asset_stats["critical_assets"] or 0
    warn_assets = asset_stats["warning_assets"] or 0
    if crit_assets > 0 or warn_assets > 0:
        insights.append({
            "category": "MAINTENANCE",
            "severity": "HIGH" if crit_assets > 0 else "MEDIUM",
            "finding": f"Maintenance risk identified: {crit_assets} critical and {warn_assets} warning assets actively monitored.",
            "driver": "Vibration and thermal degradation on mechanical equipment accelerating wear.",
            "action": "Prioritize work orders for degrading assets to avert unplanned downtime replacement costs."
        })

    # Space/Occupancy cost insight
    insights.append({
        "category": "SPACE_OPERATIONS",
        "severity": "INFO",
        "finding": f"Operational intensity stands at ₹{ov['cost_per_sqft']} per sq.ft. (₹{ov['cost_per_occupant']} per occupant).",
        "driver": "Dynamic building occupancy across zoned wings.",
        "action": "Consolidate low-density zones during late shifts to shrink conditioned area OpEx."
    })

    return {
        "facility_id": facility_id,
        "cost_per_sqft": ov["cost_per_sqft"],
        "cost_per_occupant": ov["cost_per_occupant"],
        "insights": insights,
        "timestamp": datetime.now().isoformat()
    }
