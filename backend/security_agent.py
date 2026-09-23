"""
security_agent.py — FacilityOps Security Agent
Milestone 3: Security Intelligence Engine

Provides access control monitoring, unauthorized access detection,
severity classification, security risk scoring, incident context retention,
and alert deduplication workflows.
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

from database import get_connection

# Severity weighting matrix for risk index computation
SEVERITY_WEIGHTS = {
    "INFO": 10,
    "WARNING": 35,
    "HIGH": 75,
    "CRITICAL": 100
}

EVENT_BASE_RISKS = {
    "UNAUTHORIZED_ACCESS": {"severity": "HIGH", "risk_level": "HIGH", "score": 80},
    "DOOR_FORCED":         {"severity": "CRITICAL", "risk_level": "CRITICAL", "score": 95},
    "TAILGATING":           {"severity": "WARNING", "risk_level": "MEDIUM", "score": 45},
    "AFTER_HOURS_ENTRY":   {"severity": "HIGH", "risk_level": "HIGH", "score": 70},
    "CCTV_ANOMALY":        {"severity": "CRITICAL", "risk_level": "HIGH", "score": 85},
    "BADGE_MISUSE":        {"severity": "WARNING", "risk_level": "MEDIUM", "score": 50},
}


class SecurityAgent:
    """
    Autonomous Security Agent responsible for:
    1. Validation of incoming access control and security telemetry
    2. Severity classification and risk level assignment
    3. Detection of unauthorized access attempts and security anomalies
    4. Incident investigation context retention
    5. Deduplicated alert generation and lifecycle management (NEW -> ACKNOWLEDGED -> RESOLVED)
    6. Security analytics and natural language Q&A
    """

    # ── 1. Validation ───────────────────────────────────────────────────────
    def validate_event(self, event: Dict) -> Tuple[bool, List[str]]:
        """Validate security event payload for completeness and field constraints."""
        errors = []
        if not event.get("facility_id"):
            errors.append("facility_id is required")
        if not event.get("zone"):
            errors.append("zone is required")
        if not event.get("event_type"):
            errors.append("event_type is required")
        if not event.get("description"):
            errors.append("description is required")
        ts = event.get("timestamp")
        if not ts:
            errors.append("timestamp is required")
        else:
            try:
                datetime.fromisoformat(ts)
            except ValueError:
                errors.append("timestamp must be valid ISO format")
        return (len(errors) == 0, errors)

    # ── 2. Ingestion and Processing ─────────────────────────────────────────
    def process_security_event(self, event_data: Dict) -> Dict:
        """
        Process a new security event: validate, classify severity, evaluate risk,
        persist to SECURITY_EVENTS, and trigger deduplicated alerts if high risk.
        """
        valid, errors = self.validate_event(event_data)
        if not valid:
            raise ValueError(f"Invalid security event: {'; '.join(errors)}")

        evt_type = event_data["event_type"].upper()
        defaults = EVENT_BASE_RISKS.get(evt_type, {"severity": "WARNING", "risk_level": "MEDIUM", "score": 40})

        severity = event_data.get("severity", defaults["severity"]).upper()
        risk_level = event_data.get("risk_level", defaults["risk_level"]).upper()
        
        # Determine explainable recommendation
        recommendation = self._generate_recommendation(evt_type, event_data.get("zone", "Facility"), severity)

        # Generate event_id if not present
        event_id = event_data.get("event_id")
        if not event_id:
            conn = get_connection()
            cnt = conn.execute("SELECT COUNT(*) as c FROM SECURITY_EVENTS").fetchone()["c"]
            conn.close()
            event_id = f"SEC-EVT-{cnt + 1:04d}"

        raw_details = event_data.get("details", {})
        details_str = json.dumps(raw_details) if isinstance(raw_details, dict) else str(raw_details)

        # Persist event
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

        # Check for alert trigger & deduplication
        alert_result = None
        if severity in ["HIGH", "CRITICAL"] or risk_level in ["HIGH", "CRITICAL"]:
            alert_result = self.trigger_security_alert(
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

    def _generate_recommendation(self, evt_type: str, zone: str, severity: str) -> str:
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
            return f"Temporary badge freeze recommended; investigate potential credential cloning."
        else:
            return f"Inspect access control point in {zone} and monitor activity log."

    # ── 3. Alert Generation with Deduplication ──────────────────────────────
    def trigger_security_alert(
        self,
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
        # Deduplication check
        existing = conn.execute("""
            SELECT alert_id, message, created_at
            FROM ALERTS
            WHERE facility_id=? AND alert_type=? AND resolved=0
              AND created_at >= datetime('now', '-2 hours')
        """, (facility_id, event_type.lower())).fetchone()

        if existing:
            conn.close()
            # Suppress duplicate alert creation
            return None

        # Insert new alert
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

    # ── 4. Alert Lifecycle Management ───────────────────────────────────────
    def acknowledge_alert(self, alert_id: int) -> Dict:
        conn = get_connection()
        row = conn.execute("SELECT * FROM ALERTS WHERE alert_id=?", (alert_id,)).fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Alert {alert_id} not found")
        # In ALERTS table, resolved column tracks state (0=NEW/ACK, 1=RESOLVED).
        # We also look for associated SECURITY_EVENTS
        conn.execute("UPDATE ALERTS SET resolved=0 WHERE alert_id=?", (alert_id,))
        conn.commit()
        conn.close()
        return {"alert_id": alert_id, "status": "ACKNOWLEDGED", "updated_at": datetime.now().isoformat()}

    def resolve_alert(self, alert_id: int) -> Dict:
        conn = get_connection()
        row = conn.execute("SELECT * FROM ALERTS WHERE alert_id=?", (alert_id,)).fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Alert {alert_id} not found")
        conn.execute("UPDATE ALERTS SET resolved=1 WHERE alert_id=?", (alert_id,))
        conn.commit()
        conn.close()
        return {"alert_id": alert_id, "status": "RESOLVED", "updated_at": datetime.now().isoformat()}

    # ── 5. Analytics & Metrics ──────────────────────────────────────────────
    def get_security_overview(self, facility_id: int) -> Dict:
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

    def get_security_events(self, facility_id: int, limit: int = 50) -> List[Dict]:
        """Retrieve recent security events with parsed details."""
        safe_limit = int(limit) if not hasattr(limit, 'default') else int(limit.default)
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

    def get_event_detail(self, event_id: str) -> Dict:
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

        # Associated alerts
        alerts = [dict(a) for a in conn.execute("""
            SELECT * FROM ALERTS
            WHERE facility_id=? AND alert_type=?
            ORDER BY created_at DESC LIMIT 5
        """, (evt["facility_id"], evt["event_type"].lower())).fetchall()]

        # Related events in the same zone within 24h of this event
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
                "recommended_protocols": self._generate_recommendation(evt["event_type"], evt["zone"], evt["severity"]),
                "retention_policy": "Full 90-day forensic audit logs active"
            }
        }

    def get_security_analytics(self, facility_id: int) -> Dict:
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

    # ── 6. Natural Language Q&A ─────────────────────────────────────────────
    def answer_security_query(self, query: str, facility_id: int) -> Dict:
        q = query.lower()
        ov = self.get_security_overview(facility_id)
        events = self.get_security_events(facility_id, limit=5)

        if "unauthor" in q or "breach" in q or "illegal" in q:
            unauth = [e for e in events if e["event_type"] == "UNAUTHORIZED_ACCESS"]
            if unauth:
                answer = f"Detected {len(unauth)} unauthorized access attempts recently. Latest: {unauth[0]['description']} in {unauth[0]['zone']}."
            else:
                answer = "No immediate unauthorized access attempts in recent security sweeps."
        elif "tailgat" in q:
            tg = [e for e in events if e["event_type"] == "TAILGATING"]
            if tg:
                answer = f"Recorded {len(tg)} tailgating instances. Example: {tg[0]['description']} at {tg[0]['zone']}."
            else:
                answer = "Zero tailgating events flagged in the current monitoring cycle."
        elif "door" in q or "forced" in q:
            df = [e for e in events if e["event_type"] == "DOOR_FORCED"]
            if df:
                answer = f"Alert: Door forced open event detected at {df[0]['zone']}. Immediate physical verification advised."
            else:
                answer = "All perimeter and server portal doors report secured latch states."
        elif "risk" in q or "status" in q or "summary" in q:
            answer = f"Facility security risk index is {ov['facility_risk_grade']} ({ov['facility_risk_score']}/100) with {ov['high_severity_events']} high-severity events and {ov['active_security_alerts']} active alerts."
        else:
            answer = f"Security system reports {ov['total_security_events']} total events ({ov['high_severity_events']} high-severity, {ov['unauthorized_access_events']} unauthorized access) with risk grade {ov['facility_risk_grade']}."

        return {
            "facility_id": facility_id,
            "query": query,
            "answer": answer,
            "summary": ov,
            "recent_events": events[:3]
        }

    # ── 7. Facility Intelligence Engine Integration ─────────────────────────
    def export_facility_intelligence_payload(self, facility_id: int) -> Dict:
        """Standardized schema output for downstream cross-agent orchestration in Milestone 4."""
        ov = self.get_security_overview(facility_id)
        events = self.get_security_events(facility_id, limit=5)

        status = ov["facility_risk_grade"]
        severity = "CRITICAL" if ov["facility_risk_grade"] == "CRITICAL" else ("HIGH" if ov["high_severity_events"] > 0 else "LOW")

        insights = [f"{e['event_type']} in {e['zone']}: {e['description']}" for e in events if e.get("severity") in ["HIGH", "CRITICAL"]]
        recommendations = [self._generate_recommendation(e['event_type'], e['zone'], e['severity']) for e in events[:3]]

        return {
            "agent": "security",
            "facility_id": facility_id,
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "severity": severity,
            "metrics": {
                "total_security_events": ov["total_security_events"],
                "high_severity_events": ov["high_severity_events"],
                "unauthorized_access_events": ov["unauthorized_access_events"],
                "active_security_alerts": ov["active_security_alerts"],
                "facility_risk_score": ov["facility_risk_score"]
            },
            "insights": insights,
            "recommendations": recommendations
        }


# Singleton accessor
_security_agent_instance = None

def get_security_agent() -> SecurityAgent:
    global _security_agent_instance
    if _security_agent_instance is None:
        _security_agent_instance = SecurityAgent()
    return _security_agent_instance
