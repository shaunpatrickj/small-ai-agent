"""
backend/ai_engine.py — Energy Agent (Compatibility Entry Point)
Re-exports the modular Energy Agent implementation from backend.agents.energy.
"""

import json
from agents.energy import (
    extract_features,
    extract_forecast_features,
    AnomalyDetector,
    EnergyForecaster,
    analyze_hvac_efficiency,
    generate_recommendations,
    export_energy_intelligence_payload,
    get_anomaly_detector,
    get_forecaster,
    train_all,
    check_accuracy,
)

__all__ = [
    "extract_features",
    "extract_forecast_features",
    "AnomalyDetector",
    "EnergyForecaster",
    "analyze_hvac_efficiency",
    "generate_recommendations",
    "export_energy_intelligence_payload",
    "get_anomaly_detector",
    "get_forecaster",
    "train_all",
    "check_accuracy",
]

if __name__ == "__main__":
    metrics = train_all()
    print("\n── Final Metrics ─────────────────────────────────────────────────")
    print(json.dumps(metrics, indent=2))
    print("\n── Accuracy Check ────────────────────────────────────────────────")
    print(check_accuracy())
