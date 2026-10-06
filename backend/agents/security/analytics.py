from datetime import datetime
from typing import Dict
from database import get_connection


def get_security_overview(facility_id: int) -> Dict:
    """Overview KPIs for the Security Dashboard."""
    conn = get_connection()
    tot_events = conn.execute(
        "SELECT COUNT(*) c FROM SECURITY_EVENTS WHERE facility_id=?", (facility_id,)
    ).fetchone()["c"]

    high_sev = conn.execute("""
        SELECT COUNT(*) c FROM SECURITY_EVENTS
        WHERE facility_id=? AND severity IN ('HIGH', 'CRITICAL')
    """, (facility_id,)).fetchone()["c"]

    unauth_count = conn.execute("""
        SELECT COUNT(*) c FROM SECURITY_EVENTS
        WHERE facility_id=? AND event_type='UNAUTHORIZED_ACCESS'
    """, (facility_id,)).fetchone()["c"]

    active_alerts = conn.execute("""
        SELECT COUNT(*) c FROM ALERTS
        WHERE facility_id=? AND resolved=0 AND alert_type IN (
            'unauthorized_access', 'door_forced', 'tailgating', 'after_hours_entry', 'cctv_anomaly', 'badge_misuse'
        )
    """, (facility_id,)).fetchone()["c"]

    # Calculate dynamic security risk index (0 to 100)
    risk_score = min(100, int((high_sev * 20) + (active_alerts * 15) + (unauth_count * 10)))
    risk_grade = "LOW" if risk_score < 30 else ("MEDIUM" if risk_score < 60 else ("HIGH" if risk_score < 80 else "CRITICAL"))

    conn.close()

    return {
        "facility_id": facility_id,
        "total_security_events": tot_events,
        "high_severity_events": high_sev,
        "unauthorized_access_events": unauth_count,
        "active_security_alerts": active_alerts,
        "facility_risk_score": risk_score,
        "facility_risk_grade": risk_grade,
        "timestamp": datetime.now().isoformat()
    }


def get_security_analytics(facility_id: int) -> Dict:
    """Distribution metrics for charts: severity, type, zone activity, and trend over time."""
    conn = get_connection()

    # Severity breakdown
    sev_counts = {r["severity"]: r["cnt"] for r in conn.execute("""
        SELECT severity, COUNT(*) as cnt FROM SECURITY_EVENTS
        WHERE facility_id=? GROUP BY severity
    """, (facility_id,)).fetchall()}

    # Event type breakdown
    type_counts = {r["event_type"]: r["cnt"] for r in conn.execute("""
        SELECT event_type, COUNT(*) as cnt FROM SECURITY_EVENTS
        WHERE facility_id=? GROUP BY event_type
    """, (facility_id,)).fetchall()}

    # Zone-wise activity
    zone_counts = {r["zone"]: r["cnt"] for r in conn.execute("""
        SELECT zone, COUNT(*) as cnt FROM SECURITY_EVENTS
        WHERE facility_id=? GROUP BY zone ORDER BY cnt DESC
    """, (facility_id,)).fetchall()}

    # Daily trend (last 7 days)
    trend = [dict(r) for r in conn.execute("""
        SELECT date(timestamp) as event_date, COUNT(*) as cnt
        FROM SECURITY_EVENTS
        WHERE facility_id=? AND timestamp >= datetime('now', '-7 days')
        GROUP BY event_date
        ORDER BY event_date ASC
    """, (facility_id,)).fetchall()]
    conn.close()

    return {
        "facility_id": facility_id,
        "severity_distribution": [
            {"label": "Critical", "count": sev_counts.get("CRITICAL", 0), "color": "#EF4444"},
            {"label": "High", "count": sev_counts.get("HIGH", 0), "color": "#F97316"},
            {"label": "Warning", "count": sev_counts.get("WARNING", 0), "color": "#F59E0B"},
            {"label": "Info", "count": sev_counts.get("INFO", 0), "color": "#3B82F6"}
        ],
        "type_distribution": [{"type": k, "count": v} for k, v in type_counts.items()],
        "zone_distribution": [{"zone": k, "count": v} for k, v in zone_counts.items()],
        "daily_trend": trend
    }
