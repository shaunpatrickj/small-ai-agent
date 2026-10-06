"""
FacilityOps — Maintenance Agent Package
Submodules:
- thresholds: Sensor thresholds per asset class
- scoring: Multi-factor health scoring, classification, and persistence
- detection: Abnormal sensor condition detection
- workflow: Alert deduplication and work order lifecycle
- qa: Natural language diagnostic Q&A
- intelligence: Standardized facility intelligence payload export
- agent: MaintenanceAgent orchestrator and singleton accessor
"""

from .thresholds import ASSET_THRESHOLDS
from .scoring import (
    score_asset,
    classify_score,
    save_health_to_db,
    save_prediction_to_db,
    format_health_output,
)
from .detection import detect_abnormal_behavior
from .workflow import trigger_maintenance_alert, create_work_order
from .qa import answer_maintenance_query
from .intelligence import export_facility_intelligence_payload
from .agent import MaintenanceAgent, get_maintenance_agent

__all__ = [
    "ASSET_THRESHOLDS",
    "score_asset",
    "classify_score",
    "save_health_to_db",
    "save_prediction_to_db",
    "format_health_output",
    "detect_abnormal_behavior",
    "trigger_maintenance_alert",
    "create_work_order",
    "answer_maintenance_query",
    "export_facility_intelligence_payload",
    "MaintenanceAgent",
    "get_maintenance_agent",
]
