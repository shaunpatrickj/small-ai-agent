from datetime import datetime
from typing import List, Dict
from database import get_connection


def answer_maintenance_query(question: str, facility_id: int, all_evals: List[Dict]) -> Dict:
    """Contextual Q&A for natural language maintenance queries."""
    q = question.lower()
    critical = [e for e in all_evals if e["health_status"] == "CRITICAL"]
    warning = [e for e in all_evals if e["health_status"] == "WARNING"]
    healthy = [e for e in all_evals if e["health_status"] in ["EXCELLENT", "GOOD"]]

    conn = get_connection()
    open_wos = [dict(r) for r in conn.execute(
        "SELECT * FROM MAINTENANCE_WORK_ORDERS WHERE facility_id=? AND status != 'COMPLETED'",
        (facility_id,)).fetchall()]
    open_alerts = [dict(r) for r in conn.execute(
        "SELECT * FROM MAINTENANCE_ALERTS WHERE facility_id=? AND status != 'RESOLVED'",
        (facility_id,)).fetchall()]
    conn.close()

    avg_health = sum(e["health_score"] for e in all_evals) / max(len(all_evals), 1)

    if any(k in q for k in ["critical", "urgent", "breakdown", "failure"]):
        if critical:
            c = critical[0]
            answer = (f"Found {len(critical)} CRITICAL asset(s) requiring urgent attention. "
                      f"**{c['asset_name']} ({c['asset_id']})** health score: **{c['health_score']}/100**. "
                      f"Factors: {', '.join(c['contributing_factors'][:2])}. "
                      f"Recommended: {c['recommended_action']}")
        else:
            answer = "No critical asset breakdowns detected. All monitored equipment is operating above critical thresholds."

    elif "vibration" in q:
        vib_flagged = [e for e in all_evals if any("vibration" in f.lower() for f in e["contributing_factors"])]
        if vib_flagged:
            v = vib_flagged[0]
            tele = v["latest_telemetry"]
            answer = (f"Vibration anomaly detected in **{v['asset_name']} ({v['asset_id']})**. "
                      f"Latest: {tele.get('vibration_mm_s', 'N/A')} mm/s. "
                      f"Recommend: shaft alignment check and bearing housing inspection.")
        else:
            answer = "All vibration sensor readings are within nominal limits across all monitored motors and pumps."

    elif any(k in q for k in ["work order", "ticket", "open"]):
        if open_wos:
            wo = open_wos[0]
            answer = (f"{len(open_wos)} open maintenance work orders for this facility. "
                      f"Top priority: **{wo['work_order_id']}** — {wo['issue']} (Status: {wo['status']}). "
                      f"Active maintenance alerts: {len(open_alerts)}.")
        else:
            answer = f"No open work orders. All tasks completed. Active alerts: {len(open_alerts)}."

    elif any(k in q for k in ["summary", "overview", "status", "all assets", "health"]):
        answer = (f"Scanned **{len(all_evals)} assets** for Facility {facility_id}. "
                  f"Healthy: **{len(healthy)}** | Warning: **{len(warning)}** | Critical: **{len(critical)}**. "
                  f"Facility Equipment Health Index: **{avg_health:.1f}/100**. "
                  f"Open alerts: **{len(open_alerts)}** | Open work orders: **{len(open_wos)}**.")

    elif "temperature" in q or "thermal" in q or "overheat" in q:
        temp_flagged = [e for e in all_evals if any("temperature" in f.lower() or "thermal" in f.lower() for f in e["contributing_factors"])]
        if temp_flagged:
            t = temp_flagged[0]
            answer = (f"Thermal anomaly in **{t['asset_name']}**: operating temperature elevated. "
                      f"Health score: {t['health_score']}/100. Recommend cooling system inspection.")
        else:
            answer = "All thermal sensor readings are within normal operating ranges. No overheating detected."

    else:
        answer = (f"Maintenance Agent scanned {len(all_evals)} facility assets. "
                  f"Overall Equipment Health Index: **{avg_health:.1f}/100**. "
                  f"{len(warning) + len(critical)} asset(s) need attention. "
                  f"{len(open_alerts)} maintenance alert(s) active.")

    return {
        "facility_id": facility_id, "question": question, "answer": answer,
        "total_assets": len(all_evals), "critical_count": len(critical),
        "warning_count": len(warning), "healthy_count": len(healthy),
        "open_work_orders": len(open_wos), "open_alerts": len(open_alerts),
        "avg_health_score": round(avg_health, 1),
        "timestamp": datetime.now().isoformat()
    }
