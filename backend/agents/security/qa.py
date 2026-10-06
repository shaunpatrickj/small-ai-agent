from typing import Dict, List


def answer_security_query(query: str, facility_id: int, ov: Dict, events: List[Dict]) -> Dict:
    q = query.lower()

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
