import json
from datetime import datetime
from typing import Dict, List, Tuple
from database import get_connection


def score_asset(latest: Dict, limits: Dict, db_status: str) -> Tuple[float, List[str]]:
    """Multi-factor health scoring. Returns (score, contributing_factors)."""
    score, factors = 100.0, []

    temp = latest["temperature_c"]
    if temp > limits["temp_max"]:
        deduct = min(35.0, 15.0 + (temp - limits["temp_max"]) * 2.0)
        score -= deduct
        factors.append(f"Elevated operating temperature ({temp:.1f}°C vs max {limits['temp_max']}°C)")
    elif temp > limits["temp_max"] - 4.0:
        score -= 8.0
        factors.append(f"Temperature approaching threshold ({temp:.1f}°C)")

    vib = latest["vibration_mm_s"]
    if vib > limits["vib_max"]:
        deduct = min(40.0, 18.0 + (vib - limits["vib_max"]) * 8.0)
        score -= deduct
        factors.append(f"Abnormal vibration ({vib:.2f} mm/s vs max {limits['vib_max']} mm/s)")
    elif vib > limits["vib_max"] * 0.8:
        score -= 10.0
        factors.append(f"Vibration approaching warning threshold ({vib:.2f} mm/s)")

    curr = latest["current_amps"]
    if curr > limits["curr_max"]:
        deduct = min(25.0, 10.0 + (curr - limits["curr_max"]) * 0.5)
        score -= deduct
        factors.append(f"Overcurrent draw ({curr:.1f}A vs rated {limits['curr_max']}A)")

    v_diff = abs(latest["voltage_v"] - limits["volt_nominal"])
    if v_diff > 15.0:
        score -= 12.0
        factors.append(f"Voltage instability ({latest['voltage_v']:.1f}V vs nominal {limits['volt_nominal']}V)")

    oph = latest["operating_hours"]
    if oph > 20000:
        score -= 15.0
        factors.append(f"High cumulative operating hours ({oph:,.0f} hrs — approaching overhaul interval)")
    elif oph > 15000:
        score -= 8.0
        factors.append(f"Moderate cumulative wear ({oph:,.0f} hrs)")

    if db_status == "CRITICAL":
        score = min(score, 45.0)
        if not any("critical" in f.lower() for f in factors):
            factors.append("Equipment manually flagged as CRITICAL status")
    elif db_status == "WARNING":
        score = min(score, 72.0)
        if not any("warning" in f.lower() for f in factors):
            factors.append("Equipment status set to WARNING")

    return max(5.0, min(100.0, score)), factors


def classify_score(score: float, asset_type: str) -> Tuple[str, str, str]:
    """Classifies numerical score into (health_status, risk_level, recommended_action)."""
    if score >= 90:
        return "EXCELLENT", "LOW", "Routine inspection on schedule — no action required"
    elif score >= 75:
        return "GOOD", "LOW", "Monitor standard operating parameters at next PM cycle"
    elif score >= 50:
        return "WARNING", "MEDIUM", f"Inspect {asset_type} mechanical assembly, vibration dampers and thermal setpoints"
    else:
        return ("CRITICAL",
                ("CRITICAL" if score < 30 else "HIGH"),
                "Urgent maintenance required — inspect motor windings, bearings, and clear load restrictions")


def save_health_to_db(asset_id: str, score: float, status: str, risk: str, factors: List[str]):
    conn = get_connection()
    conn.execute("""
        INSERT INTO EQUIPMENT_HEALTH (asset_id, health_score, health_status, risk_level, contributing_factors)
        VALUES (?, ?, ?, ?, ?)
    """, (asset_id, score, status, risk, json.dumps(factors)))
    conn.execute("UPDATE ASSETS SET status=? WHERE asset_id=?", (status, asset_id))
    conn.commit()
    conn.close()


def save_prediction_to_db(asset_id: str, risk: str, priority: str, text: str, rec: str, conf: float):
    conn = get_connection()
    conn.execute("""
        INSERT INTO MAINTENANCE_PREDICTIONS (asset_id, risk_level, priority, prediction_text, recommended_action, confidence)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (asset_id, risk, priority, text, rec, conf))
    conn.commit()
    conn.close()


def format_health_output(asset_id: str, asset_name: str, asset_type: str, facility_id: int,
                         health_score: float, health_status: str, risk_level: str,
                         contributing_factors: List[str], latest_telemetry: Dict,
                         recommended_action: str) -> Dict:
    return {
        "asset_id": asset_id, "asset_name": asset_name,
        "asset_type": asset_type, "facility_id": facility_id,
        "health_score": health_score, "health_status": health_status,
        "risk_level": risk_level,
        "anomaly_detected": health_status in ["WARNING", "CRITICAL"],
        "maintenance_required": health_status in ["WARNING", "CRITICAL"],
        "contributing_factors": contributing_factors,
        "recommended_action": recommended_action,
        "latest_telemetry": latest_telemetry,
        "confidence": 0.88, "timestamp": datetime.now().isoformat()
    }
