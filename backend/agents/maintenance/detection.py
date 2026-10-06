from typing import Dict
from database import get_connection
from .thresholds import ASSET_THRESHOLDS


def detect_abnormal_behavior(asset_id: str) -> Dict:
    """Detect abnormal equipment behavior across historical sensor telemetry."""
    conn = get_connection()
    asset = conn.execute("SELECT asset_type FROM ASSETS WHERE asset_id=?", (asset_id,)).fetchone()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM ASSET_MONITORING_DATA WHERE asset_id=? ORDER BY timestamp DESC LIMIT 48",
        (asset_id,)).fetchall()]
    conn.close()

    if not rows:
        return {"asset_id": asset_id, "anomalies_detected": 0, "status": "NOMINAL", "details": []}

    a_type = dict(asset)["asset_type"] if asset else "AHU"
    limits = ASSET_THRESHOLDS.get(a_type, ASSET_THRESHOLDS["AHU"])
    latest = rows[0]
    abnormal_rows = [r for r in rows if r["is_abnormal"] == 1]

    anom_reasons = []
    if latest["vibration_mm_s"] > limits["vib_max"]:
        anom_reasons.append(f"Vibration spike ({latest['vibration_mm_s']:.2f} mm/s > {limits['vib_max']} limit)")
    if latest["temperature_c"] > limits["temp_max"]:
        anom_reasons.append(f"Thermal anomaly ({latest['temperature_c']:.1f}°C > {limits['temp_max']}°C limit)")
    if latest["current_amps"] > limits["curr_max"]:
        anom_reasons.append(f"Current surge ({latest['current_amps']:.1f}A > {limits['curr_max']}A rated)")

    return {
        "asset_id": asset_id,
        "records_scanned": len(rows),
        "anomalies_detected": len(abnormal_rows),
        "latest_is_abnormal": bool(latest["is_abnormal"] or anom_reasons),
        "reasons": anom_reasons if anom_reasons else ["Telemetry within normal statistical bounds"],
        "latest_telemetry": {
            "temperature_c": latest["temperature_c"],
            "vibration_mm_s": latest["vibration_mm_s"],
            "current_amps": latest["current_amps"],
            "voltage_v": latest["voltage_v"]
        }
    }
