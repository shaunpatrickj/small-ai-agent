from datetime import datetime
from typing import Dict, List
from .events import generate_recommendation


def export_facility_intelligence_payload(facility_id: int, ov: Dict, events: List[Dict]) -> Dict:
    """Standardized schema output for downstream cross-agent orchestration in Milestone 4."""
    status = ov["facility_risk_grade"]
    severity = "CRITICAL" if ov["facility_risk_grade"] == "CRITICAL" else ("HIGH" if ov["high_severity_events"] > 0 else "LOW")

    insights = [f"{e['event_type']} in {e['zone']}: {e['description']}" for e in events if e.get("severity") in ["HIGH", "CRITICAL"]]
    recommendations = [generate_recommendation(e["event_type"], e["zone"], e["severity"]) for e in events[:3]]

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
