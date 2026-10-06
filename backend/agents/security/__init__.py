"""
FacilityOps — Security Agent Package
Submodules:
- constants: Severity weights and event baseline risks
- validation: Security telemetry and incident payload validation
- events: Incident ingestion, classification, and investigation context
- alerts: Alert generation with deduplication and lifecycle transitions
- analytics: Overview KPIs, incident distribution, and trend tracking
- qa: Natural language security audit Q&A
- intelligence: Standardized facility intelligence payload export
- agent: SecurityAgent orchestrator and singleton accessor
"""

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
from .agent import SecurityAgent, get_security_agent

__all__ = [
    "SEVERITY_WEIGHTS",
    "EVENT_BASE_RISKS",
    "validate_event",
    "generate_recommendation",
    "process_security_event",
    "get_security_events",
    "get_event_detail",
    "trigger_security_alert",
    "acknowledge_alert",
    "resolve_alert",
    "get_security_overview",
    "get_security_analytics",
    "answer_security_query",
    "export_facility_intelligence_payload",
    "SecurityAgent",
    "get_security_agent",
]
