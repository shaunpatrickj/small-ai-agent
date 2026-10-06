from typing import List, Dict
from database import get_connection
from .analytics import analyze_facility_occupancy


def detect_overcrowding_events(facility_id: int, hours: int = 24) -> List[Dict]:
    """Detect recent overcrowding instances in the past N hours."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM OCCUPANCY_RECORDS
        WHERE facility_id=? AND (occupancy_rate > 0.90 OR occupancy_count > capacity)
          AND timestamp >= datetime('now', ?)
        ORDER BY timestamp DESC
    """, (facility_id, f"-{hours} hours")).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def detect_underutilization_zones(facility_id: int) -> List[Dict]:
    """Identify zones consistently underutilized (< 25%) during working hours."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT zone, AVG(occupancy_rate) as avg_rate, AVG(occupancy_count) as avg_count, MAX(capacity) as capacity,
               COUNT(*) as reading_count
        FROM OCCUPANCY_RECORDS
        WHERE facility_id=?
          AND strftime('%H', timestamp) BETWEEN '09' AND '17'
          AND timestamp >= datetime('now', '-7 days')
        GROUP BY zone
        HAVING AVG(occupancy_rate) < 0.25
        ORDER BY avg_rate ASC
    """, (facility_id,)).fetchall()
    conn.close()

    results = []
    for r in rows:
        res = dict(r)
        res["avg_rate"] = round(res["avg_rate"], 3)
        res["avg_occupancy_pct"] = round(res["avg_rate"] * 100, 1)
        res["recommendation"] = f"Consider repurposing or downscaling HVAC capacity in {res['zone']} (averaged {res['avg_occupancy_pct']}% during working hours)."
        results.append(res)
    return results


def generate_occupancy_insights(facility_id: int) -> List[Dict]:
    """Generate explainable tactical & strategic recommendations."""
    ov = analyze_facility_occupancy(facility_id)
    under = detect_underutilization_zones(facility_id)
    over = detect_overcrowding_events(facility_id, hours=48)

    insights = []

    # 1. Overcrowding alerts
    if ov["overcrowded_count"] > 0:
        oc_names = ", ".join(z["zone"] for z in ov["zones"] if z["overcrowding"])
        insights.append({
            "type": "OVERCROWDING_RISK",
            "severity": "HIGH",
            "title": "Severe Overcrowding Detected",
            "detail": f"Zones currently exceeding 90% threshold: {oc_names}. Risk of HVAC load strain and ventilation degradation.",
            "action": "Trigger temporary zone redirect in digital signage and adjust VAV ventilation to 100% fresh air."
        })
    elif over:
        insights.append({
            "type": "RECURRENT_OVERCROWDING",
            "severity": "MEDIUM",
            "title": "Recent Peak Surge Detected",
            "detail": f"Recorded {len(over)} overcrowding surges over the past 48 hours during peak collaborative hours.",
            "action": "Consider setting up flexible desk reservation quotas during peak weekday periods (11:00–15:00)."
        })

    # 2. Underutilized spaces
    if under:
        u_names = ", ".join(u["zone"] for u in under[:2])
        insights.append({
            "type": "ENERGY_CONSERVATION",
            "severity": "LOW",
            "title": "Energy Saving Opportunity via Space Consolidation",
            "detail": f"Consistently underutilized spaces during prime hours: {u_names} (operating below 25% capacity).",
            "action": "Program smart thermostats to increase cooling setpoint by 2°C in these zones and disable unused lighting circuits."
        })

    # 3. Overall facility efficiency score
    rate_pct = ov["occupancy_pct"]
    if 40 <= rate_pct <= 75:
        insights.append({
            "type": "OPTIMAL_UTILIZATION",
            "severity": "INFO",
            "title": "Balanced Space Allocation",
            "detail": f"Facility overall occupancy is sitting at healthy {rate_pct}%. Traffic flow is well distributed.",
            "action": "Maintain active scheduling protocols."
        })
    elif rate_pct > 80:
        insights.append({
            "type": "CAPACITY_CONSTRAINT",
            "severity": "HIGH",
            "title": "Facility Nearing Max Capacity Threshold",
            "detail": f"Aggregate building occupancy is at {rate_pct}% of theoretical max floor limit.",
            "action": "Review lease options or activate secondary conference facilities."
        })

    return insights
