from datetime import datetime
from typing import Dict, Optional
from database import get_connection


def trigger_security_alert(
    event_id: str,
    facility_id: int,
    zone: str,
    event_type: str,
    severity: str,
    description: str,
    recommended_action: str
) -> Optional[Dict]:
    """
    Creates an alert in the central ALERTS table with deduplication:
    Checks if an unresolved (resolved=0) alert for this facility and alert_type
    or mentioning this zone was created within the last 2 hours.
    """
    conn = get_connection()
    existing = conn.execute("""
        SELECT alert_id, message, created_at
        FROM ALERTS
        WHERE facility_id=? AND alert_type=? AND resolved=0
          AND created_at >= datetime('now', '-2 hours')
    """, (facility_id, event_type.lower())).fetchone()

    if existing:
        conn.close()
        return None

    cur = conn.cursor()
    msg = f"[{zone}] {description} | Recommended: {recommended_action}"
    cur.execute("""
        INSERT INTO ALERTS
        (facility_id, alert_type, severity, message, metric, value, threshold, resolved, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, datetime('now'))
    """, (
        facility_id,
        event_type.lower(),
        severity.lower(),
        msg,
        "security_incident",
        1.0,
        0.0
    ))
    alert_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {
        "alert_id": alert_id,
        "event_id": event_id,
        "facility_id": facility_id,
        "zone": zone,
        "severity": severity,
        "type": event_type,
        "description": description,
        "recommended_action": recommended_action,
        "status": "NEW",
        "timestamp": datetime.now().isoformat()
    }


def acknowledge_alert(alert_id: int) -> Dict:
    conn = get_connection()
    row = conn.execute("SELECT * FROM ALERTS WHERE alert_id=?", (alert_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Alert {alert_id} not found")
    conn.execute("UPDATE ALERTS SET resolved=0 WHERE alert_id=?", (alert_id,))
    conn.commit()
    conn.close()
    return {"alert_id": alert_id, "status": "ACKNOWLEDGED", "updated_at": datetime.now().isoformat()}


def resolve_alert(alert_id: int) -> Dict:
    conn = get_connection()
    row = conn.execute("SELECT * FROM ALERTS WHERE alert_id=?", (alert_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Alert {alert_id} not found")
    conn.execute("UPDATE ALERTS SET resolved=1 WHERE alert_id=?", (alert_id,))
    conn.commit()
    conn.close()
    return {"alert_id": alert_id, "status": "RESOLVED", "updated_at": datetime.now().isoformat()}
