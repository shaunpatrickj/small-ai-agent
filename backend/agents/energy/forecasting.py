import os
import pickle
from datetime import datetime, timedelta
from typing import List, Dict

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split

from database import get_connection
from .features import extract_forecast_features

MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models"))
os.makedirs(MODEL_DIR, exist_ok=True)


class EnergyForecaster:
    MODEL_PATH = os.path.join(MODEL_DIR, "forecaster.pkl")

    def __init__(self):
        self.model = None

    def train(self, facility_id: int = 1) -> dict:
        """Train GradientBoosting forecaster for a given facility."""
        conn = get_connection()
        rows = [dict(r) for r in conn.execute("""
            SELECT timestamp, electricity_usage, hvac_usage, outdoor_temp_c, occupancy_pct
            FROM ENERGY_USAGE WHERE facility_id=? ORDER BY timestamp
        """, (facility_id,)).fetchall()]
        conn.close()

        X, y = extract_forecast_features(rows)
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.15, shuffle=False)

        self.model = GradientBoostingRegressor(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=4,
            subsample=0.8,
            random_state=42
        )
        self.model.fit(X_tr, y_tr)

        y_pred = self.model.predict(X_te)
        mape = float(np.mean(np.abs((y_te - y_pred) / np.maximum(y_te, 1))) * 100)
        rmse = float(np.sqrt(np.mean((y_te - y_pred) ** 2)))

        with open(self.MODEL_PATH, "wb") as f:
            pickle.dump(self.model, f)

        metrics = {
            "mape_pct": round(mape, 2),
            "rmse_kwh": round(rmse, 2),
            "n_train": len(y_tr),
            "n_test": len(y_te)
        }
        print(f"✅ Forecaster trained — MAPE: {mape:.1f}%  RMSE: {rmse:.1f} kWh")
        return metrics

    def load(self):
        if not os.path.exists(self.MODEL_PATH):
            raise FileNotFoundError("Forecaster not trained. Run ai_engine.py first.")
        with open(self.MODEL_PATH, "rb") as f:
            self.model = pickle.load(f)

    def forecast_24h(self, facility_id: int = 1) -> List[Dict]:
        """Return 24-hour forecast for today, using latest DB data as context."""
        if self.model is None:
            self.load()

        conn = get_connection()
        rows = [dict(r) for r in conn.execute("""
            SELECT timestamp, electricity_usage, hvac_usage, outdoor_temp_c, occupancy_pct
            FROM ENERGY_USAGE WHERE facility_id=? ORDER BY timestamp DESC LIMIT 72
        """, (facility_id,)).fetchall()]
        conn.close()
        rows = list(reversed(rows))   # chronological

        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        result = []

        # Historical last 24 hours
        conn = get_connection()
        hist_rows = [dict(r) for r in conn.execute("""
            SELECT timestamp, electricity_usage, hvac_usage, outdoor_temp_c, occupancy_pct
            FROM ENERGY_USAGE WHERE facility_id=?
              AND timestamp >= datetime('now','-1 day')
            ORDER BY timestamp
        """, (facility_id,)).fetchall()]
        conn.close()

        for r in hist_rows:
            ts = datetime.fromisoformat(r["timestamp"])
            result.append({
                "hour": ts.strftime("%H:00"),
                "timestamp": r["timestamp"],
                "actual": round(r["electricity_usage"], 1),
                "forecast": None,
                "is_forecast": False
            })

        # Forecast next 8 hours
        lags = [r["electricity_usage"] for r in rows[-3:]]
        temp = rows[-1]["outdoor_temp_c"] if rows else 27.0
        hvac = rows[-1]["hvac_usage"] if rows else 99.0

        for i in range(8):
            fh = now + timedelta(hours=i + 1)
            hour = fh.hour
            dow = fh.weekday()
            occ = 80 if (8 <= hour <= 18 and dow < 5) else 20
            feat = np.array([[
                hour, dow, temp + i * 0.1,
                lags[-1], lags[-2], lags[-3],
                sum(lags[-3:]) / 3,
                hvac, occ,
                int(dow >= 5), int(8 <= hour <= 20)
            ]])
            pred = float(self.model.predict(feat)[0])
            result.append({
                "hour": fh.strftime("%H:00"),
                "timestamp": fh.isoformat(),
                "actual": None,
                "forecast": round(max(0, pred), 1),
                "is_forecast": True
            })
            lags = lags[1:] + [pred]

        return result
