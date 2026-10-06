import json
from typing import Dict, List
from database import get_connection
from .constants import EVENT_BASE_RISKS
from .validation import validate_event
from .alerts import trigger_security_alert


def generate_recommendation(evt_type: str, zone: str, severity: str) -> str:
    if evt_type == "UNAUTHORIZED_ACCESS":
        return f"Review access event logs for {zone}; verify credential revocation list and dispatch on-duty patrol officer."
    elif evt_type == "DOOR_FORCED":
        return f"Emergency: Physical breach alert at {zone}. Inspect door sensor latch integrity and verify security seal."
    elif evt_type == "TAILGATING":
        return f"Review optical surveillance footage at {zone} gate. Remind employees of single-badge anti-passback protocols."
    elif evt_type == "AFTER_HOURS_ENTRY":
        return f"Verify after-hours authorized work permit and cross-check contractor schedule for {zone}."
    elif evt_type == "CCTV_ANOMALY":
        return f"Acknowledge CCTV alert and zoom fixed PTZ camera to track subject dwell in {zone}."
    elif evt_type == "BADGE_MISUSE":
        return "Temporary badge freeze recommended; investigate potential credential cloning."
    else:
        return f"Inspect access control point in {zone} and monitor activity log."


def process_security_event(event_data: Dict) -> Dict:
    """
    Process a new security event: validate, classify severity, evaluate risk,
    persist to SECURITY_EVENTS, and trigger deduplicated alerts if high risk.
    """
    valid, errors = validate_event(event_data)
    if not valid:
        raise ValueError(f"Invalid security event: {'; '.join(errors)}")

    evt_type = event_data["event_type"].upper()
    defaults = EVENT_BASE_RISKS.get(evt_type, {"severity": "WARNING", "risk_level": "MEDIUM", "score": 40})

    severity = event_data.get("severity", defaults["severity"]).upper()
    risk_level = event_data.get("risk_level", defaults["risk_level"]).upper()

    recommendation = generate_recommendation(evt_type, event_data.get("zone", "Facility"), severity)

    event_id = event_data.get("event_id")
    if not event_id:
        conn = get_connection()
        cnt = conn.execute("SELECT COUNT(*) as c FROM SECURITY_EVENTS").fetchone()["c"]
        conn.close()
        event_id = f"SEC-EVT-{cnt + 1:04d}"

    raw_details = event_data.get("details", {})
    details_str = json.dumps(raw_details) if isinstance(raw_details, dict) else str(raw_details)

    conn = get_connection()
    conn.execute("""
        INSERT INTO SECURITY_EVENTS
        (event_id, facility_id, zone, event_type, severity, risk_level, source, status, description, details, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        event_id,
        event_data["facility_id"],
        event_data["zone"],
        evt_type,
        severity,
        risk_level,
        event_data.get("source", "Access Control System"),
        event_data.get("status", "NEW"),
        event_data["description"],
        details_str,
        event_data["timestamp"]
    ))
    conn.commit()
    conn.close()

    alert_result = None
    if severity in ["HIGH", "CRITICAL"] or risk_level in ["HIGH", "CRITICAL"]:
        alert_result = trigger_security_alert(
            event_id=event_id,
            facility_id=event_data["facility_id"],
            zone=event_data["zone"],
            event_type=evt_type,
            severity=severity.lower(),
            description=event_data["description"],
            recommended_action=recommendation
        )

    return {
        "event_id": event_id,
        "facility_id": event_data["facility_id"],
        "zone": event_data["zone"],
        "event_type": evt_type,
        "severity": severity,
        "risk_level": risk_level,
        "detected": True,
        "recommendation": recommendation,
        "alert_created": alert_result is not None,
        "alert_id": alert_result.get("alert_id") if alert_result else None,
        "timestamp": event_data["timestamp"]
    }


def get_security_events(facility_id: int, limit: int = 50) -> List[Dict]:
    """Retrieve recent security events with parsed details."""
    safe_limit = int(limit) if not hasattr(limit, "default") else int(limit.default)
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM SECURITY_EVENTS
        WHERE facility_id=?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (facility_id, safe_limit)).fetchall()
    conn.close()

    results = []
    for r in rows:
        rec = dict(r)
        if rec.get("details"):
            try:
                rec["details"] = json.loads(rec["details"])
            except Exception:
                pass
        results.append(rec)
    return results


def get_event_detail(event_id: str) -> Dict:
    """Fetch complete contextual data for an incident investigation."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM SECURITY_EVENTS WHERE event_id=?", (event_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Security event {event_id} not found")
    evt = dict(row)
    if evt.get("details"):
        try:
            evt["details"] = json.loads(evt["details"])
        except Exception:
            pass

    alerts = [dict(a) for a in conn.execute("""
        SELECT * FROM ALERTS
        WHERE facility_id=? AND alert_type=?
        ORDER BY created_at DESC LIMIT 5
    """, (evt["facility_id"], evt["event_type"].lower())).fetchall()]

    related = [dict(re) for re in conn.execute("""
        SELECT event_id, event_type, severity, timestamp, description
        FROM SECURITY_EVENTS
        WHERE facility_id=? AND zone=? AND event_id != ?
        ORDER BY timestamp DESC LIMIT 5
    """, (evt["facility_id"], evt["zone"], event_id)).fetchall()]
    conn.close()

    return {
        "event": evt,
        "investigation_context": {
            "associated_alerts": alerts,
            "zone_related_events": related,
            "recommended_protocols": generate_recommendation(evt["event_type"], evt["zone"], evt["severity"]),
            "retention_policy": "Full 90-day forensic audit logs active"
        }
    }
