"""
FacilityOps — Occupancy Agent Package
Submodules:
- validation: Record ingestion schema and integrity checks
- analytics: Zone metrics, facility aggregates, heatmaps, and trends
- diagnostics: Overcrowding surges and underutilization detection
- forecasting: Gradient Boosting 24h occupancy forecaster and holdout evaluation
- qa: Natural language space utilization Q&A
- intelligence: Standardized facility intelligence payload export
- agent: OccupancyAgent orchestrator and singleton accessor
"""

from .validation import validate_record
from .analytics import (
    generate_zone_recommendation,
    get_latest_zone_occupancy,
    analyze_facility_occupancy,
    get_occupancy_heatmap,
    get_occupancy_trends,
)
from .diagnostics import (
    detect_overcrowding_events,
    detect_underutilization_zones,
    generate_occupancy_insights,
)
from .forecasting import OccupancyForecaster, extract_ml_features
from .qa import answer_occupancy_query
from .intelligence import export_facility_intelligence_payload
from .agent import OccupancyAgent, get_occupancy_agent

__all__ = [
    "validate_record",
    "generate_zone_recommendation",
    "get_latest_zone_occupancy",
    "analyze_facility_occupancy",
    "get_occupancy_heatmap",
    "get_occupancy_trends",
    "detect_overcrowding_events",
    "detect_underutilization_zones",
    "generate_occupancy_insights",
    "OccupancyForecaster",
    "extract_ml_features",
    "answer_occupancy_query",
    "export_facility_intelligence_payload",
    "OccupancyAgent",
    "get_occupancy_agent",
]
