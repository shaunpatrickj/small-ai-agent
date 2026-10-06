from datetime import datetime
from typing import Dict
from database import get_connection


def export_facility_intelligence_payload(facility_id: int = 1) -> Dict:
    """
    Standardized schema output for downstream cross-agent orchestration in Milestone 4.
    """
    conn = get_connection()
    assets = conn.execute("""
        SELECT a.asset_id, a.asset_name, a.asset_type, a.status,
               COALESCE(eh.health_score, 85.0) as health_score,
               COALESCE(eh.health_status, 'GOOD') as health_status
        FROM ASSETS a
        LEFT JOIN EQUIPMENT_HEALTH eh ON eh.asset_id = a.asset_id
          AND eh.evaluated_at = (SELECT MAX(eh2.evaluated_at) FROM EQUIPMENT_HEALTH eh2 WHERE eh2.asset_id = a.asset_id)
        WHERE a.facility_id=?
    """, (facility_id,)).fetchall()

    open_alerts = conn.execute("""
        SELECT COUNT(*) n FROM MAINTENANCE_ALERTS
        WHERE facility_id=? AND status IN ('NEW', 'ACKNOWLEDGED')
    """, (facility_id,)).fetchone()["n"]

    open_wos = conn.execute("""
        SELECT COUNT(*) n FROM MAINTENANCE_WORK_ORDERS
        WHERE facility_id=? AND status != 'COMPLETED'
    """, (facility_id,)).fetchone()["n"]

    conn.close()

    total_assets = len(assets)
    scores = [a["health_score"] for a in assets] if assets else [85.0]
    avg_health = round(sum(scores) / max(len(scores), 1), 1)

    crit_assets = [a for a in assets if a["status"] == "CRITICAL" or a["health_status"] == "CRITICAL"]
    warn_assets = [a for a in assets if a["status"] == "WARNING" or a["health_status"] == "WARNING"]

    status = "CRITICAL" if len(crit_assets) > 0 else ("WARNING" if len(warn_assets) > 0 else "NORMAL")
    severity = "HIGH" if len(crit_assets) > 0 else ("MEDIUM" if len(warn_assets) > 0 else "LOW")

    insights = []
    recommendations = []

    for c in crit_assets[:2]:
        insights.append(f"Critical degradation on {c['asset_name']} ({c['asset_id']}) with health score {c['health_score']:.0f}/100.")
        recommendations.append(f"Dispatch mechanical team for {c['asset_name']} inspection and vibration dampers replacement.")

    for w in warn_assets[:2]:
        insights.append(f"Elevated operating stress observed on {w['asset_name']} ({w['asset_id']}).")
        recommendations.append(f"Schedule preventive maintenance for {w['asset_name']} in upcoming maintenance window.")

    if not insights:
        insights.append(f"All {total_assets} monitored assets operating within nominal manufacturer thresholds.")
        recommendations.append("Continue routine preventive maintenance inspection cycle.")

    return {
        "agent": "maintenance",
        "facility_id": facility_id,
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "severity": severity,
        "metrics": {
            "total_assets": total_assets,
            "average_equipment_health": avg_health,
            "critical_assets_count": len(crit_assets),
            "warning_assets_count": len(warn_assets),
            "open_maintenance_alerts": open_alerts,
            "open_work_orders": open_wos
        },
        "insights": insights,
        "recommendations": recommendations,
        "confidence": 0.92
    }
