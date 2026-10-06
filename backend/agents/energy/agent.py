import json
from database import get_connection
from .anomaly import AnomalyDetector
from .forecasting import EnergyForecaster

# ─── Singletons (lazy loaded by API) ─────────────────────────────────────────
_anomaly_detector = None
_forecaster = None


def get_anomaly_detector() -> AnomalyDetector:
    global _anomaly_detector
    if _anomaly_detector is None:
        _anomaly_detector = AnomalyDetector()
        _anomaly_detector.load()
    return _anomaly_detector


def get_forecaster() -> EnergyForecaster:
    global _forecaster
    if _forecaster is None:
        _forecaster = EnergyForecaster()
        _forecaster.load()
    return _forecaster


def train_all() -> dict:
    """Train all energy models and return combined metrics."""
    print("\n── Training Anomaly Detector ─────────────────────────────────────")
    anomaly_det = AnomalyDetector()
    anom_metrics = anomaly_det.train()

    print("\n── Training Energy Forecaster ────────────────────────────────────")
    forecaster = EnergyForecaster()
    fore_metrics = forecaster.train(facility_id=1)

    # Save metrics to DB
    conn = get_connection()
    conn.execute("DELETE FROM MODEL_METADATA")
    conn.execute("""
        INSERT INTO MODEL_METADATA (model_name, accuracy, parameters)
        VALUES (?, ?, ?)
    """, ("IsolationForest_AnomalyDetector",
          anom_metrics["accuracy"],
          json.dumps(anom_metrics)))
    conn.execute("""
        INSERT INTO MODEL_METADATA (model_name, accuracy, parameters)
        VALUES (?, ?, ?)
    """, ("GradientBoosting_EnergyForecaster",
          None,
          json.dumps(fore_metrics)))
    conn.commit()
    conn.close()

    return {"anomaly": anom_metrics, "forecaster": fore_metrics}


def check_accuracy() -> str:
    """Quick accuracy check — reads stored metrics from DB."""
    conn = get_connection()
    row = conn.execute("""
        SELECT accuracy, parameters FROM MODEL_METADATA
        WHERE model_name='IsolationForest_AnomalyDetector'
        ORDER BY trained_at DESC LIMIT 1
    """).fetchone()
    conn.close()
    if row:
        metrics = json.loads(row["parameters"])
        acc = metrics.get("accuracy", 0)
        print(f"Anomaly detection accuracy: {acc:.1%}")
        assert acc >= 0.85, f"Accuracy {acc:.1%} below 85% target!"
        return f"✅ {acc:.1%} accuracy — meets ≥85% target"
    return "⚠️ Model not trained yet"
