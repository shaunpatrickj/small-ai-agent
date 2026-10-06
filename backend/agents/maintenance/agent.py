from datetime import datetime
from typing import List, Dict, Optional

from database import get_connection
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


class MaintenanceAgent:
    """
    Autonomous Maintenance Agent for condition monitoring, health scoring,
    anomaly detection, failure risk prediction, alert management, and work order creation.
    """

    # ── Internal Delegations (Preserving exact interface) ───────────────────
    def _score_asset(self, latest: Dict, limits: Dict, db_status: str):
        return score_asset(latest, limits, db_status)

    def _classify_score(self, score: float, asset_type: str):
        return classify_score(score, asset_type)

    def _save_health_to_db(self, asset_id, score, status, risk, factors):
        return save_health_to_db(asset_id, score, status, risk, factors)

    def _save_prediction_to_db(self, asset_id, risk, priority, text, rec, conf):
        return save_prediction_to_db(asset_id, risk, priority, text, rec, conf)

    def _format_health_output(self, asset_id, asset_name, asset_type, facility_id,
                              health_score, health_status, risk_level,
                              contributing_factors, latest_telemetry, recommended_action):
        return format_health_output(
            asset_id, asset_name, asset_type, facility_id,
            health_score, health_status, risk_level,
            contributing_factors, latest_telemetry, recommended_action
        )

    # ── Public API ──────────────────────────────────────────────────────────

    def evaluate_asset_health(self, asset_id: str) -> Dict:
        """Evaluate health score (0-100) and risk profile for a specific asset."""
        conn = get_connection()
        asset = conn.execute("SELECT * FROM ASSETS WHERE asset_id=?", (asset_id,)).fetchone()
        if not asset:
            conn.close()
            raise ValueError(f"Asset {asset_id} not found")
        asset = dict(asset)
        telemetry = [dict(t) for t in conn.execute(
            "SELECT * FROM ASSET_MONITORING_DATA WHERE asset_id=? ORDER BY timestamp DESC LIMIT 24",
            (asset_id,)).fetchall()]
        conn.close()

        if not telemetry:
            return self._format_health_output(
                asset_id=asset_id, asset_name=asset["asset_name"],
                asset_type=asset["asset_type"], facility_id=asset["facility_id"],
                health_score=88.0, health_status="GOOD", risk_level="LOW",
                contributing_factors=["Nominal baseline — no recent telemetry recorded"],
                latest_telemetry={}, recommended_action="Continue standard monitoring schedule")

        latest = telemetry[0]
        limits = ASSET_THRESHOLDS.get(asset["asset_type"], ASSET_THRESHOLDS["AHU"])
        score, factors = self._score_asset(latest, limits, asset["status"])

        health_status, risk_level, recommended_action = self._classify_score(score, asset["asset_type"])

        if not factors:
            factors = ["All monitored parameters operating within normal tolerance limits"]

        self._save_health_to_db(asset_id, score, health_status, risk_level, factors)

        if health_status in ["WARNING", "CRITICAL"]:
            self.trigger_maintenance_alert(
                asset_id, asset["facility_id"], score, health_status,
                factors, recommended_action, latest)

        return self._format_health_output(
            asset_id=asset_id, asset_name=asset["asset_name"],
            asset_type=asset["asset_type"], facility_id=asset["facility_id"],
            health_score=round(score, 1), health_status=health_status,
            risk_level=risk_level, contributing_factors=factors,
            latest_telemetry=latest, recommended_action=recommended_action)

    def predict_maintenance(self, asset_id: str) -> Dict:
        """Predict maintenance requirements and priority without fabricating failure dates."""
        health = self.evaluate_asset_health(asset_id)
        score, status = health["health_score"], health["health_status"]

        if status == "CRITICAL":
            priority, confidence = "URGENT", 0.92
            prediction = "High probability of functional breakdown under peak load."
            recommendation = "Urgent maintenance required within 24–48 hours to prevent forced outage."
        elif status == "WARNING":
            priority, confidence = "RECOMMENDED", 0.85
            prediction = "Accelerated component degradation detected; close monitoring advised."
            recommendation = "Schedule preventive maintenance within the next maintenance cycle."
        elif score < 85:
            priority, confidence = "MONITOR", 0.78
            prediction = "Minor parameter drift detected; asset stable under normal load."
            recommendation = "Continue close monitoring during next scheduled facility round."
        else:
            priority, confidence = "NORMAL", 0.95
            prediction = "Equipment operating at peak health index."
            recommendation = "No immediate maintenance required. Maintain standard PM schedule."

        result = {
            "asset_id": asset_id, "asset_name": health["asset_name"],
            "asset_type": health["asset_type"], "facility_id": health["facility_id"],
            "health_score": score, "health_status": status,
            "risk_level": health["risk_level"], "priority": priority,
            "prediction": prediction, "recommended_action": recommendation,
            "contributing_factors": health["contributing_factors"],
            "confidence": confidence, "timestamp": datetime.now().isoformat()
        }
        self._save_prediction_to_db(asset_id, health["risk_level"], priority, prediction, recommendation, confidence)
        return result

    def detect_abnormal_behavior(self, asset_id: str) -> Dict:
        return detect_abnormal_behavior(asset_id)

    def trigger_maintenance_alert(self, asset_id: str, facility_id: int, health_score: float,
                                  health_status: str, factors: List[str], recommended_action: str,
                                  latest_telemetry: Dict) -> Optional[Dict]:
        return trigger_maintenance_alert(
            asset_id, facility_id, health_score, health_status,
            factors, recommended_action, latest_telemetry
        )

    def create_work_order(self, asset_id: str, issue: str, priority: str, recommended_action: str) -> Dict:
        return create_work_order(asset_id, issue, priority, recommended_action)

    def analyze_all_assets(self, facility_id: Optional[int] = None) -> List[Dict]:
        """Run health evaluation across all (or facility-scoped) assets."""
        conn = get_connection()
        if facility_id:
            assets = conn.execute("SELECT asset_id FROM ASSETS WHERE facility_id=?", (facility_id,)).fetchall()
        else:
            assets = conn.execute("SELECT asset_id FROM ASSETS").fetchall()
        conn.close()
        return [self.evaluate_asset_health(a["asset_id"]) for a in assets]

    def answer_maintenance_query(self, question: str, facility_id: int = 1) -> Dict:
        all_evals = self.analyze_all_assets(facility_id)
        return answer_maintenance_query(question, facility_id, all_evals)

    def export_facility_intelligence_payload(self, facility_id: int = 1) -> Dict:
        return export_facility_intelligence_payload(facility_id)


# ── Singleton ──────────────────────────────────────────────────────────────────
_maintenance_agent = None


def get_maintenance_agent() -> MaintenanceAgent:
    global _maintenance_agent
    if _maintenance_agent is None:
        _maintenance_agent = MaintenanceAgent()
    return _maintenance_agent
