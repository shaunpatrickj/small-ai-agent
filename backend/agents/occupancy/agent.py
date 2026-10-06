from typing import List, Dict, Tuple
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


class OccupancyAgent:
    """
    Autonomous Occupancy Agent responsible for space utilization analytics,
    overcrowding detection, underutilization diagnostics, explainable insights,
    and 24-hour occupancy forecasting.
    """

    def __init__(self):
        self.forecaster = OccupancyForecaster()

    @property
    def model(self):
        return self.forecaster.model

    @model.setter
    def model(self, value):
        self.forecaster.model = value

    # ── 1. Data Validation ──────────────────────────────────────────────────
    def validate_record(self, record: dict) -> Tuple[bool, List[str]]:
        return validate_record(record)

    # ── 2. Zone & Facility Utilization Analysis ─────────────────────────────
    def get_latest_zone_occupancy(self, facility_id: int) -> List[Dict]:
        return get_latest_zone_occupancy(facility_id)

    def _generate_zone_recommendation(self, zone: str, count: int, cap: int, rate: float, status: str) -> str:
        return generate_zone_recommendation(zone, count, cap, rate, status)

    def analyze_facility_occupancy(self, facility_id: int) -> Dict:
        return analyze_facility_occupancy(facility_id)

    # ── 3. Overcrowding and Underutilization Diagnostics ────────────────────
    def detect_overcrowding_events(self, facility_id: int, hours: int = 24) -> List[Dict]:
        return detect_overcrowding_events(facility_id, hours=hours)

    def detect_underutilization_zones(self, facility_id: int) -> List[Dict]:
        return detect_underutilization_zones(facility_id)

    # ── 4. Heatmap & Temporal Analytics ────────────────────────────────────
    def get_occupancy_heatmap(self, facility_id: int) -> Dict:
        return get_occupancy_heatmap(facility_id)

    def get_occupancy_trends(self, facility_id: int, hours: int = 48) -> List[Dict]:
        return get_occupancy_trends(facility_id, hours=hours)

    # ── 5. Explainable Insights Generation ─────────────────────────────────
    def generate_occupancy_insights(self, facility_id: int) -> List[Dict]:
        return generate_occupancy_insights(facility_id)

    # ── 6. ML Occupancy Forecasting & Evaluation ───────────────────────────
    def _extract_ml_features(self, rows: List[Dict]) -> Tuple:
        return extract_ml_features(rows)

    def train_and_evaluate_forecaster(self, facility_id: int = 1, force_retrain: bool = False) -> Dict:
        return self.forecaster.train_and_evaluate_forecaster(facility_id, force_retrain=force_retrain)

    def forecast_24h(self, facility_id: int) -> List[Dict]:
        return self.forecaster.forecast_24h(facility_id)

    # ── 7. Natural Language Q&A ─────────────────────────────────────────────
    def answer_occupancy_query(self, query: str, facility_id: int) -> Dict:
        ov = self.analyze_facility_occupancy(facility_id)
        insights = self.generate_occupancy_insights(facility_id)
        return answer_occupancy_query(query, facility_id, ov, insights, self.forecaster)

    # ── 8. Facility Intelligence Engine Integration ─────────────────────────
    def export_facility_intelligence_payload(self, facility_id: int) -> Dict:
        ov = self.analyze_facility_occupancy(facility_id)
        insights = self.generate_occupancy_insights(facility_id)
        return export_facility_intelligence_payload(facility_id, ov, insights)


# Singleton accessor
_occupancy_agent_instance = None


def get_occupancy_agent() -> OccupancyAgent:
    global _occupancy_agent_instance
    if _occupancy_agent_instance is None:
        _occupancy_agent_instance = OccupancyAgent()
    return _occupancy_agent_instance
