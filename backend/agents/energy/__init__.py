"""
FacilityOps — Energy Agent Package
Submodules:
- features: Raw telemetry feature engineering and lag transforms
- anomaly: Isolation Forest anomaly detector
- forecasting: Gradient Boosting 24h electricity forecaster
- recommendations: HVAC efficiency rules, alerts integration, intelligence payload
- agent: Singleton accessors and model training orchestration
"""

from .features import extract_features, extract_forecast_features
from .anomaly import AnomalyDetector
from .forecasting import EnergyForecaster
from .recommendations import (
    analyze_hvac_efficiency,
    generate_recommendations,
    export_energy_intelligence_payload,
)
from .agent import (
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
