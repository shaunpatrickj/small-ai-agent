from datetime import datetime
from typing import List, Dict, Tuple
import numpy as np


def extract_features(rows: List[Dict]) -> np.ndarray:
    """Convert DB rows into ML feature matrix for anomaly detection."""
    features = []
    for r in rows:
        ts = datetime.fromisoformat(r["timestamp"])
        hour = ts.hour
        dow = ts.weekday()   # 0=Mon, 6=Sun
        is_weekend = int(dow >= 5)
        is_workhour = int(8 <= hour <= 20 and not is_weekend)

        features.append([
            r["electricity_usage"],
            r["hvac_usage"],
            r["water_usage"],
            r["lighting_usage"],
            r["equipment_usage"],
            r["other_usage"],
            r["outdoor_temp_c"],
            r["occupancy_pct"],
            hour,
            dow,
            is_weekend,
            is_workhour,
            # Derived ratios
            r["hvac_usage"] / max(r["electricity_usage"], 1),
            r["lighting_usage"] / max(r["electricity_usage"], 1),
        ])
    return np.array(features, dtype=np.float32)


def extract_forecast_features(rows: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
    """Feature matrix for next-step electricity forecasting."""
    X, y = [], []
    for i, r in enumerate(rows):
        if i < 3:
            continue
        ts = datetime.fromisoformat(r["timestamp"])
        hour = ts.hour
        dow = ts.weekday()
        temp = r["outdoor_temp_c"]

        # Lag features
        lag1 = rows[i - 1]["electricity_usage"]
        lag2 = rows[i - 2]["electricity_usage"]
        lag3 = rows[i - 3]["electricity_usage"]
        roll3 = (lag1 + lag2 + lag3) / 3
        hvac = r["hvac_usage"]
        occ = r["occupancy_pct"]

        X.append([
            hour, dow, temp, lag1, lag2, lag3, roll3, hvac, occ,
            int(dow >= 5), int(8 <= hour <= 20)
        ])
        y.append(r["electricity_usage"])

    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)
