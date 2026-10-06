from datetime import datetime
from typing import List, Dict, Optional
from database import get_connection


def trigger_maintenance_alert(asset_id: str, facility_id: int, health_score: float,
                              health_status: str, factors: List[str], recommended_action: str,
                              latest_telemetry: Dict) -> Optional[Dict]:
    """Generate maintenance alert with deduplication (avoids repeated NEW alerts for same issue)."""
    conn = get_connection()
    alert_type = "health_critical" if health_status == "CRITICAL" else "health_warning"
    severity = "critical" if health_status == "CRITICAL" else "warning"

    # Deduplication: suppress if an unresolved alert of same type already exists
    existing = conn.execute("""
        SELECT alert_id FROM MAINTENANCE_ALERTS
        WHERE asset_id=? AND alert_type=? AND status IN ('NEW', 'ACKNOWLEDGED')
    """, (asset_id, alert_type)).fetchone()
    if existing:
        conn.close()
        return None

    desc = f"Equipment health degraded to {health_score:.0f}/100 ({health_status}). " + "; ".join(factors[:2])
    condition = f"Health Score {health_score:.0f}/100 — Status: {health_status}"

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO MAINTENANCE_ALERTS
        (asset_id, facility_id, severity, alert_type, description, detected_condition, recommended_action, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'NEW')
    """, (asset_id, facility_id, severity, alert_type, desc, condition, recommended_action))
    alert_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {
        "alert_id": alert_id, "asset_id": asset_id, "facility_id": facility_id,
        "severity": severity, "alert_type": alert_type,
        "description": desc, "detected_condition": condition,
        "recommended_action": recommended_action,
        "status": "NEW", "created_at": datetime.now().isoformat()
    }


def create_work_order(asset_id: str, issue: str, priority: str, recommended_action: str) -> Dict:
    """Create a new maintenance work order."""
    conn = get_connection()
    asset = conn.execute("SELECT facility_id FROM ASSETS WHERE asset_id=?", (asset_id,)).fetchone()
    facility_id = dict(asset)["facility_id"] if asset else 1
    wo_count = conn.execute("SELECT COUNT(*) n FROM MAINTENANCE_WORK_ORDERS").fetchone()["n"]
    wo_id = f"WO-{datetime.now().year}-{wo_count + 101:03d}"
    conn.execute("""
        INSERT INTO MAINTENANCE_WORK_ORDERS
        (work_order_id, asset_id, facility_id, issue, priority, recommended_action, status)
        VALUES (?, ?, ?, ?, ?, ?, 'OPEN')
    """, (wo_id, asset_id, facility_id, issue, priority, recommended_action))
    conn.commit()
    conn.close()
    return {
        "work_order_id": wo_id, "asset_id": asset_id, "facility_id": facility_id,
        "issue": issue, "priority": priority,
        "recommended_action": recommended_action,
        "status": "OPEN", "created_at": datetime.now().isoformat()
    }
