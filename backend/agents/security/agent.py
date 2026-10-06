from typing import List, Dict, Tuple, Optional
from .constants import SEVERITY_WEIGHTS, EVENT_BASE_RISKS
from .validation import validate_event
from .events import (
    generate_recommendation,
    process_security_event,
    get_security_events,
    get_event_detail,
)
from .alerts import (
    trigger_security_alert,
    acknowledge_alert,
    resolve_alert,
)
from .analytics import (
    get_security_overview,
    get_security_analytics,
)
from .qa import answer_security_query
from .intelligence import export_facility_intelligence_payload


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
        return validate_event(event)

    # ── 2. Ingestion and Processing ─────────────────────────────────────────
    def process_security_event(self, event_data: Dict) -> Dict:
        return process_security_event(event_data)

    def _generate_recommendation(self, evt_type: str, zone: str, severity: str) -> str:
        return generate_recommendation(evt_type, zone, severity)

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
        return trigger_security_alert(
            event_id=event_id,
            facility_id=facility_id,
            zone=zone,
            event_type=event_type,
            severity=severity,
            description=description,
            recommended_action=recommended_action
        )

    # ── 4. Alert Lifecycle Management ───────────────────────────────────────
    def acknowledge_alert(self, alert_id: int) -> Dict:
        return acknowledge_alert(alert_id)

    def resolve_alert(self, alert_id: int) -> Dict:
        return resolve_alert(alert_id)

    # ── 5. Analytics & Metrics ──────────────────────────────────────────────
    def get_security_overview(self, facility_id: int) -> Dict:
        return get_security_overview(facility_id)

    def get_security_events(self, facility_id: int, limit: int = 50) -> List[Dict]:
        return get_security_events(facility_id, limit=limit)

    def get_event_detail(self, event_id: str) -> Dict:
        return get_event_detail(event_id)

    def get_security_analytics(self, facility_id: int) -> Dict:
        return get_security_analytics(facility_id)

    # ── 6. Natural Language Q&A ─────────────────────────────────────────────
    def answer_security_query(self, query: str, facility_id: int) -> Dict:
        ov = self.get_security_overview(facility_id)
        events = self.get_security_events(facility_id, limit=5)
        return answer_security_query(query, facility_id, ov, events)

    # ── 7. Facility Intelligence Engine Integration ─────────────────────────
    def export_facility_intelligence_payload(self, facility_id: int) -> Dict:
        ov = self.get_security_overview(facility_id)
        events = self.get_security_events(facility_id, limit=5)
        return export_facility_intelligence_payload(facility_id, ov, events)


# Singleton accessor
_security_agent_instance = None


def get_security_agent() -> SecurityAgent:
    global _security_agent_instance
    if _security_agent_instance is None:
        _security_agent_instance = SecurityAgent()
    return _security_agent_instance
