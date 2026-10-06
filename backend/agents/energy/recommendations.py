from datetime import datetime
from typing import List, Dict

from database import get_connection


def analyze_hvac_efficiency(facility_id: int = 1) -> List[Dict]:
    """Rule-based HVAC & lighting efficiency checks on last 24h data."""
    conn = get_connection()
    rows = [dict(r) for r in conn.execute("""
        SELECT timestamp, electricity_usage, hvac_usage, lighting_usage,
               equipment_usage, occupancy_pct, outdoor_temp_c
        FROM ENERGY_USAGE
        WHERE facility_id=?
          AND timestamp >= datetime('now', '-24 hours')
        ORDER BY timestamp
    """, (facility_id,)).fetchall()]
    conn.close()

    issues = []
    for r in rows:
        ts = datetime.fromisoformat(r["timestamp"])
        occ = r["occupancy_pct"]
        hvac = r["hvac_usage"]
        elec = r["electricity_usage"]
        light = r["lighting_usage"]

        hvac_ratio = hvac / max(elec, 1)
        light_ratio = light / max(elec, 1)

        # HVAC over 50% of total while temp is mild → inefficiency
        if hvac_ratio > 0.50 and r["outdoor_temp_c"] < 30:
            issues.append({
                "type": "hvac_high_ratio",
                "severity": "warning",
                "hour": ts.strftime("%H:00"),
                "message": f"HVAC consuming {hvac_ratio:.0%} of total electricity at {r['outdoor_temp_c']}°C outdoor temp",
                "saving_est_inr": round(hvac * 0.15 * 9, 0)   # ₹9/kWh, save 15%
            })

        # Lighting above 35% while occupancy is low
        if light_ratio > 0.35 and occ < 30:
            issues.append({
                "type": "lighting_waste",
                "severity": "warning",
                "hour": ts.strftime("%H:00"),
                "message": f"Lighting {light_ratio:.0%} of load at {occ:.0f}% occupancy — likely unoccupied zones lit",
                "saving_est_inr": round(light * 0.40 * 9, 0)
            })

    return issues[:10]   # cap at 10 issues


def generate_recommendations(facility_id: int = 1) -> List[Dict]:
    """Combine anomaly scores + efficiency checks into actionable recommendations."""
    conn = get_connection()

    # Recent anomalies
    anomaly_rows = [dict(r) for r in conn.execute("""
        SELECT timestamp, electricity_usage, hvac_usage, water_usage,
               anomaly_score, is_anomaly
        FROM ENERGY_USAGE
        WHERE facility_id=? AND is_anomaly=1
          AND timestamp >= datetime('now', '-48 hours')
        ORDER BY anomaly_score DESC LIMIT 5
    """, (facility_id,)).fetchall()]

    # Open alerts
    alert_rows = [dict(r) for r in conn.execute("""
        SELECT * FROM ALERTS WHERE facility_id=? AND resolved=0
        ORDER BY severity DESC, created_at DESC LIMIT 5
    """, (facility_id,)).fetchall()]

    # Last 24h aggregate
    agg = dict(conn.execute("""
        SELECT AVG(electricity_usage) avg_elec, AVG(hvac_usage) avg_hvac,
               AVG(water_usage) avg_water, AVG(occupancy_pct) avg_occ
        FROM ENERGY_USAGE
        WHERE facility_id=? AND timestamp >= datetime('now', '-24 hours')
    """, (facility_id,)).fetchone())
    conn.close()

    recs = []

    # ── From alerts ──────────────────────────────────────────────────────────
    for al in alert_rows:
        sev_map = {"critical": "danger", "warning": "warn", "info": ""}
        recs.append({
            "type": sev_map.get(al["severity"], ""),
            "icon": "🔴" if al["severity"] == "critical" else "⚡",
            "title": al["message"][:60],
            "desc": al["message"],
            "saving": f"Threshold breached: {al['value']} vs {al['threshold']} limit" if al["value"] else "",
            "source": "alert"
        })

    # ── From anomalies ───────────────────────────────────────────────────────
    for row in anomaly_rows:
        ts = datetime.fromisoformat(row["timestamp"])
        recs.append({
            "type": "warn",
            "icon": "⚡",
            "title": f"Anomaly detected at {ts.strftime('%d %b %H:00')}",
            "desc": (f"Electricity: {row['electricity_usage']:.0f} kWh, "
                     f"HVAC: {row['hvac_usage']:.0f} kWh — anomaly score: {row['anomaly_score']:.3f}. "
                     "Review HVAC setpoints and check for equipment faults."),
            "saving": f"Potential saving: ₹{row['electricity_usage'] * 0.08 * 9:.0f}/event",
            "source": "anomaly_model"
        })

    # ── From efficiency ───────────────────────────────────────────────────────
    eff_issues = analyze_hvac_efficiency(facility_id)
    for issue in eff_issues[:3]:
        recs.append({
            "type": "warn",
            "icon": "🌡️",
            "title": issue["message"][:60],
            "desc": issue["message"],
            "saving": f"Potential saving: ₹{issue['saving_est_inr']:.0f}/hour",
            "source": "efficiency_analyzer"
        })

    # ── General good-practice ─────────────────────────────────────────────────
    if agg.get("avg_occ") and agg["avg_occ"] < 40:
        recs.append({
            "type": "good",
            "icon": "🌙",
            "title": "Off-hours energy within target",
            "desc": (f"Average occupancy {agg['avg_occ']:.0f}% with energy draw "
                     f"{agg['avg_elec']:.0f} kWh/h — automation running effectively."),
            "saving": "",
            "source": "efficiency_analyzer"
        })

    if not recs:
        recs.append({
            "type": "good",
            "icon": "✅",
            "title": "All systems nominal",
            "desc": "No anomalies or inefficiencies detected in the last 48 hours.",
            "saving": "",
            "source": "anomaly_model"
        })

    return recs[:8]


def export_energy_intelligence_payload(facility_id: int = 1) -> Dict:
    """
    Standardized schema output for downstream cross-agent orchestration in Milestone 4.
    """
    conn = get_connection()
    agg = dict(conn.execute("""
        SELECT
            SUM(electricity_usage) total_energy_kwh,
            AVG(electricity_usage) avg_electricity_kw,
            MAX(electricity_usage) peak_electricity_kw,
            SUM(hvac_usage) total_hvac_kwh,
            AVG(hvac_usage) avg_hvac_kw,
            SUM(is_anomaly) anomaly_count,
            COUNT(*) n_records
        FROM ENERGY_USAGE
        WHERE facility_id=?
          AND timestamp >= datetime('now', '-24 hours')
    """, (facility_id,)).fetchone())

    active_alerts = conn.execute("""
        SELECT COUNT(*) n FROM ALERTS
        WHERE facility_id=? AND resolved=0
    """, (facility_id,)).fetchone()["n"]

    conn.close()

    total_kwh = agg.get("total_energy_kwh") or 0.0
    anom_count = agg.get("anomaly_count") or 0
    hvac_ratio = (agg.get("total_hvac_kwh") or 0.0) / max(total_kwh, 1.0)

    # Status classification
    status = "CRITICAL" if anom_count >= 3 else ("WARNING" if anom_count > 0 or hvac_ratio > 0.55 else "NORMAL")
    severity = "HIGH" if anom_count >= 3 else ("MEDIUM" if anom_count > 0 else "LOW")

    recs_list = generate_recommendations(facility_id)
    insights = [r["desc"] for r in recs_list[:4]]
    recommendations = [r["title"] for r in recs_list[:4]]

    return {
        "agent": "energy",
        "facility_id": facility_id,
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "severity": severity,
        "metrics": {
            "total_energy_kwh": round(total_kwh, 1),
            "avg_electricity_kw": round(agg.get("avg_electricity_kw") or 0.0, 1),
            "peak_electricity_kw": round(agg.get("peak_electricity_kw") or 0.0, 1),
            "hvac_share_pct": round(hvac_ratio * 100, 1),
            "anomaly_count_24h": anom_count,
            "active_alerts": active_alerts
        },
        "insights": insights,
        "recommendations": recommendations,
        "confidence": 0.96
    }
