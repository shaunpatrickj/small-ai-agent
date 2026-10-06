import os
import pickle
from typing import List, Dict

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from database import get_connection
from .features import extract_features

MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models"))
os.makedirs(MODEL_DIR, exist_ok=True)


class AnomalyDetector:
    MODEL_PATH = os.path.join(MODEL_DIR, "isolation_forest.pkl")
    SCALER_PATH = os.path.join(MODEL_DIR, "anomaly_scaler.pkl")

    def __init__(self):
        self.model = None
        self.scaler = None

    def train(self) -> dict:
        """Train Isolation Forest on full historical data. Returns accuracy metrics."""
        conn = get_connection()
        rows = [dict(r) for r in conn.execute("""
            SELECT electricity_usage, hvac_usage, water_usage, lighting_usage,
                   equipment_usage, other_usage, outdoor_temp_c, occupancy_pct,
                   timestamp, is_anomaly
            FROM ENERGY_USAGE ORDER BY timestamp
        """).fetchall()]
        conn.close()

        X = extract_features(rows)
        y = np.array([r["is_anomaly"] for r in rows])

        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # Train on FULL data (Isolation Forest is unsupervised)
        # contamination matches our injected anomaly rate ~4%
        self.model = IsolationForest(
            n_estimators=200,
            contamination=0.04,
            random_state=42,
            max_samples="auto",
            n_jobs=-1
        )
        self.model.fit(X_scaled)

        # Evaluate against ground-truth labels
        # IsolationForest returns -1 for anomaly, 1 for normal
        preds_raw = self.model.predict(X_scaled)
        preds_bin = np.where(preds_raw == -1, 1, 0)   # 1=anomaly

        # Write anomaly scores back to DB
        scores = -self.model.score_samples(X_scaled)    # higher = more anomalous
        self._write_scores_to_db(rows, preds_bin, scores)

        # Metrics
        acc = accuracy_score(y, preds_bin)
        prec = precision_score(y, preds_bin, zero_division=0)
        rec = recall_score(y, preds_bin, zero_division=0)
        f1 = f1_score(y, preds_bin, zero_division=0)

        # Persist
        with open(self.MODEL_PATH, "wb") as f:
            pickle.dump(self.model, f)
        with open(self.SCALER_PATH, "wb") as f:
            pickle.dump(self.scaler, f)

        metrics = {
            "accuracy": round(float(acc), 4),
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "f1_score": round(float(f1), 4),
            "n_samples": len(y),
            "n_anomalies_detected": int(preds_bin.sum()),
            "n_ground_truth_anomalies": int(y.sum()),
        }
        print(f"✅ Anomaly Detector trained — Accuracy: {acc:.1%}  F1: {f1:.3f}")
        return metrics

    def _write_scores_to_db(self, rows, preds_bin, scores):
        conn = get_connection()
        updates = []
        for r, pred, score in zip(rows, preds_bin, scores):
            if pred == 1:
                updates.append((int(pred), round(float(score), 4),
                                r["electricity_usage"], r["hvac_usage"], r["timestamp"]))
        if updates:
            conn.executemany("""
                UPDATE ENERGY_USAGE SET is_anomaly=?, anomaly_score=?
                WHERE electricity_usage=? AND hvac_usage=? AND timestamp=?
            """, updates)
            conn.commit()
        conn.close()

    def load(self):
        if not os.path.exists(self.MODEL_PATH):
            raise FileNotFoundError("Model not trained yet. Run ai_engine.py first.")
        with open(self.MODEL_PATH, "rb") as f:
            self.model = pickle.load(f)
        with open(self.SCALER_PATH, "rb") as f:
            self.scaler = pickle.load(f)

    def predict(self, rows: List[Dict]) -> List[Dict]:
        """Run anomaly detection on a list of rows. Returns annotated list."""
        if self.model is None:
            self.load()
        X = extract_features(rows)
        X_sc = self.scaler.transform(X)
        preds = self.model.predict(X_sc)
        scores = -self.model.score_samples(X_sc)
        results = []
        for row, pred, score in zip(rows, preds, scores):
            results.append({
                **row,
                "is_anomaly": int(pred == -1),
                "anomaly_score": round(float(score), 4)
            })
        return results
