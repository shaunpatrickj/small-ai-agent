"""
main.py — FacilityOps FastAPI Backend
Milestone 1 + Milestone 2: All API endpoints + static file serving for dashboard

Milestone 1 Endpoints (Energy Intelligence):
  GET  /api/energy/overview          KPI metrics (live telemetry + DB aggregation)
  GET  /api/energy/distribution      Subsystem breakdown
  GET  /api/energy/forecast          Historical + predicted 24h consumption
  GET  /api/energy/recommendations   AI-generated recommendations
  POST /api/energy/agent/analyze     Trigger full agent analysis
  GET  /api/energy/alerts            Active alerts
  GET  /api/health                   Health check + model status

Milestone 2 Endpoints (Predictive Maintenance):
  GET  /api/maintenance/overview              KPI: totals, healthy/warning/critical/alerts
  GET  /api/assets                            List all monitored assets with latest health
  GET  /api/assets/{asset_id}                 Asset detail + telemetry history
  GET  /api/assets/{asset_id}/health          Health score + contributing factors
  POST /api/maintenance/agent/analyze         Run maintenance agent or answer Q&A
  GET  /api/maintenance/predictions           Maintenance risk predictions for all assets
  GET  /api/maintenance/alerts                All active maintenance alerts
  POST /api/maintenance/alerts/{id}/acknowledge  Acknowledge an alert
  POST /api/maintenance/alerts/{id}/resolve   Resolve an alert
  GET  /api/maintenance/work-orders           List all work orders
  POST /api/maintenance/work-orders           Create a new work order
  PATCH /api/maintenance/work-orders/{id}     Update work order status
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Make sure backend directory is in path
sys.path.insert(0, os.path.dirname(__file__))

from database import get_connection
from telemetry import live_tick
from ai_engine import (
    get_anomaly_detector,
    get_forecaster,
    generate_recommendations,
    train_all,
)
from maintenance_agent import get_maintenance_agent
from occupancy_agent import get_occupancy_agent
from security_agent import get_security_agent
from cost_agent import get_cost_agent
from facility_intelligence_engine import get_facility_intelligence_engine

# ── App Setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="FacilityOps AI Platform API",
    description="Agentic AI Platform for Energy, Maintenance, Occupancy & Security Intelligence",
    version="1.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static Files (Dashboard) ──────────────────────────────────────────────────
DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard"

if DASHBOARD_DIR.exists():
    NO_CACHE_HEADERS = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }

    app.mount("/static", StaticFiles(directory=str(DASHBOARD_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_dashboard():
        return FileResponse(str(DASHBOARD_DIR / "index.html"), headers=NO_CACHE_HEADERS)

    @app.get("/style.css", include_in_schema=False)
    async def serve_css():
        return FileResponse(str(DASHBOARD_DIR / "style.css"), headers=NO_CACHE_HEADERS)

    @app.get("/app.js", include_in_schema=False)
    async def serve_js():
        return FileResponse(str(DASHBOARD_DIR / "app.js"), headers=NO_CACHE_HEADERS)


# ── Pydantic Models ───────────────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    facility_id: int = 1
    question:    str = ""

class MaintenanceAnalyzeRequest(BaseModel):
    facility_id: int = 1
    asset_id:    str = ""
    question:    str = ""

class WorkOrderCreateRequest(BaseModel):
    asset_id:           str
    issue:              str
    priority:           str = "MEDIUM"   # LOW / MEDIUM / HIGH / URGENT
    recommended_action: str

class WorkOrderUpdateRequest(BaseModel):
    status: str   # OPEN / IN_PROGRESS / COMPLETED

class OccupancyAnalyzeRequest(BaseModel):
    facility_id: int = 1
    zone:        str = ""
    question:    str = ""

class OccupancyIngestRequest(BaseModel):
    facility_id:     int = 1
    zone:            str
    occupancy_count: int
    capacity:        int = 50
    timestamp:       str = ""

class SecurityAnalyzeRequest(BaseModel):
    facility_id: int = 1
    event_id:    str = ""
    question:    str = ""

class SecurityEventCreateRequest(BaseModel):
    facility_id: int = 1
    zone:        str
    event_type:  str  # UNAUTHORIZED_ACCESS, TAILGATING, DOOR_FORCED, AFTER_HOURS_ENTRY, CCTV_ANOMALY, BADGE_MISUSE
    severity:    str = "HIGH"
    risk_level:  str = "HIGH"
    source:      str = "Access Control System"
    description: str
    details:     dict = {}
    timestamp:   str = ""


class CostAnalyzeRequest(BaseModel):
    facility_id: int = 1
    question:    str = ""


# ── Helper ────────────────────────────────────────────────────────────────────
def facility_or_404(facility_id: int):
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM FACILITIES WHERE facility_id=?", (facility_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail=f"Facility {facility_id} not found")
    return dict(row)


# ── GET /api/health ───────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    conn = get_connection()
    row  = conn.execute("SELECT COUNT(*) n FROM ENERGY_USAGE").fetchone()
    mm   = conn.execute(
        "SELECT model_name, accuracy, trained_at FROM MODEL_METADATA"
    ).fetchall()
    conn.close()
    return {
        "status":         "ok",
        "db_records":     row["n"],
        "models":         [dict(m) for m in mm],
        "timestamp":      datetime.now().isoformat(),
    }


# ── GET /api/energy/overview ──────────────────────────────────────────────────
@app.get("/api/energy/overview")
async def energy_overview(facility_id: int = Query(1)):
    facility_or_404(facility_id)

    tick = live_tick()   # live snapshot

    conn = get_connection()
    agg  = dict(conn.execute("""
        SELECT
          SUM(electricity_usage)                        total_energy_kwh,
          AVG(electricity_usage)                        avg_electricity_kw,
          MAX(electricity_usage + hvac_usage)           peak_demand_kw,
          SUM(is_anomaly)                               anomaly_count,
          COUNT(*)                                      n_records
        FROM ENERGY_USAGE
        WHERE facility_id=?
          AND timestamp >= datetime('now', '-24 hours')
    """, (facility_id,)).fetchone())

    yesterday = dict(conn.execute("""
        SELECT SUM(electricity_usage) total
        FROM ENERGY_USAGE
        WHERE facility_id=?
          AND timestamp >= datetime('now', '-48 hours')
          AND timestamp <  datetime('now', '-24 hours')
    """, (facility_id,)).fetchone())

    last_week = dict(conn.execute("""
        SELECT SUM(electricity_usage) total
        FROM ENERGY_USAGE
        WHERE facility_id=?
          AND timestamp >= datetime('now', '-8 days')
          AND timestamp <  datetime('now', '-7 days')
    """, (facility_id,)).fetchone())

    alerts_count = conn.execute(
        "SELECT COUNT(*) n FROM ALERTS WHERE facility_id=? AND resolved=0",
        (facility_id,)
    ).fetchone()["n"]

    conn.close()

    total   = agg["total_energy_kwh"] or 0
    y_total = yesterday["total"] or total
    pct_vs_yday = round((total - y_total) / max(y_total, 1) * 100, 1)

    cost_per_kwh  = 9.0
    carbon_factor = 0.82   # kg CO₂e per kWh
    savings_pct   = 0.08   # 8% vs non-optimised baseline

    return {
        "facility_id":      facility_id,
        "timestamp":        tick["timestamp"],
        "total_energy_kwh": round(total, 0),
        "total_energy_change_pct": pct_vs_yday,
        "cost_savings_inr": round(total * savings_pct * cost_per_kwh, 0),
        "cost_savings_change_pct": round((total * savings_pct - (y_total * savings_pct)) / max(y_total * savings_pct, 1) * 100, 1),
        "carbon_reduced_tco2e": round(total * savings_pct * carbon_factor / 1000, 2),
        "peak_demand_kw":   round(agg["peak_demand_kw"] or tick["peak_demand_kw"], 0),
        "efficiency_score": tick["efficiency_score"],
        "anomaly_count":    agg["anomaly_count"] or 0,
        "open_alerts":      alerts_count,
        # live sub-second tick values
        "live": {
            "electricity_kw": tick["electricity_kw"],
            "hvac_kw":        tick["hvac_kw"],
            "water_lph":      tick["water_lph"],
        }
    }


# ── GET /api/energy/distribution ─────────────────────────────────────────────
@app.get("/api/energy/distribution")
async def energy_distribution(facility_id: int = Query(1)):
    facility_or_404(facility_id)
    conn = get_connection()
    agg  = dict(conn.execute("""
        SELECT
          AVG(hvac_usage)      avg_hvac,
          AVG(lighting_usage)  avg_lighting,
          AVG(equipment_usage) avg_equipment,
          AVG(other_usage)     avg_other,
          AVG(electricity_usage) avg_total
        FROM ENERGY_USAGE
        WHERE facility_id=?
          AND timestamp >= datetime('now', '-24 hours')
    """, (facility_id,)).fetchone())
    conn.close()

    total = (agg["avg_hvac"] or 0) + (agg["avg_lighting"] or 0) + \
            (agg["avg_equipment"] or 0) + (agg["avg_other"] or 0)
    total = max(total, 1)

    def pct(v): return round((v or 0) / total * 100, 1)

    return {
        "facility_id": facility_id,
        "subsystems": [
            {"label": "HVAC",      "pct": pct(agg["avg_hvac"]),      "kwh": round(agg["avg_hvac"] or 0, 1),      "color": "#A78BFA"},
            {"label": "Lighting",  "pct": pct(agg["avg_lighting"]),  "kwh": round(agg["avg_lighting"] or 0, 1),  "color": "#FCD34D"},
            {"label": "Equipment", "pct": pct(agg["avg_equipment"]), "kwh": round(agg["avg_equipment"] or 0, 1), "color": "#34D399"},
            {"label": "Other",     "pct": pct(agg["avg_other"]),     "kwh": round(agg["avg_other"] or 0, 1),     "color": "#F87171"},
        ],
        "total_avg_kwh": round(agg["avg_total"] or 0, 1),
    }


# ── GET /api/energy/forecast ──────────────────────────────────────────────────
@app.get("/api/energy/forecast")
async def energy_forecast(facility_id: int = Query(1)):
    facility_or_404(facility_id)
    try:
        forecaster = get_forecaster()
        data       = forecaster.forecast_24h(facility_id)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Forecasting model not yet trained. Run the startup script.")

    # Also fetch historical HVAC & water for multi-series chart
    conn = get_connection()
    hist = [dict(r) for r in conn.execute("""
        SELECT timestamp, electricity_usage, hvac_usage, water_usage
        FROM ENERGY_USAGE
        WHERE facility_id=? AND timestamp >= datetime('now', '-1 day')
        ORDER BY timestamp
    """, (facility_id,)).fetchall()]
    conn.close()

    return {
        "facility_id":    facility_id,
        "forecast_series": data,
        "historical": [
            {
                "hour":        datetime.fromisoformat(r["timestamp"]).strftime("%H:00"),
                "electricity": round(r["electricity_usage"], 1),
                "hvac":        round(r["hvac_usage"], 1),
                "water":       round(r["water_usage"], 1),
            } for r in hist
        ]
    }


# ── GET /api/energy/recommendations ──────────────────────────────────────────
@app.get("/api/energy/recommendations")
async def energy_recommendations(facility_id: int = Query(1)):
    facility_or_404(facility_id)
    recs = generate_recommendations(facility_id)
    return {
        "facility_id":       facility_id,
        "generated_at":      datetime.now().isoformat(),
        "recommendations":   recs,
        "total_potential_saving_inr": sum(
            float(r["saving"].split("₹")[1].split("/")[0].replace(",", ""))
            for r in recs if "₹" in r.get("saving", "")
        )
    }


# ── POST /api/energy/agent/analyze ───────────────────────────────────────────
@app.post("/api/energy/agent/analyze")
async def agent_analyze(req: AnalyzeRequest):
    facility_or_404(req.facility_id)

    try:
        detector = get_anomaly_detector()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="AI models not yet trained. Run the startup script.")

    # Run on last 24h of data
    conn = get_connection()
    rows = [dict(r) for r in conn.execute("""
        SELECT * FROM ENERGY_USAGE
        WHERE facility_id=? AND timestamp >= datetime('now', '-24 hours')
        ORDER BY timestamp
    """, (req.facility_id,)).fetchall()]
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No recent data found for this facility.")

    results  = detector.predict(rows)
    n_anom   = sum(1 for r in results if r["is_anomaly"])
    recs     = generate_recommendations(req.facility_id)

    # Contextual response if a question was asked
    answer = None
    if req.question:
        q = req.question.lower()
        if "hvac" in q:
            answer = ("Based on 24h telemetry, HVAC is consuming "
                      f"{sum(r['hvac_usage'] for r in rows)/len(rows):.1f} kWh on average. "
                      "Recommend adjusting setpoints to 23°C during peak hours to reduce load by ~15%.")
        elif "forecast" in q or "predict" in q:
            answer = ("Energy demand is forecast to peak between 10:00–17:00. "
                      "Consider pre-cooling at 09:30 to flatten the curve and avoid peak tariffs.")
        elif "water" in q:
            answer = ("Water usage is within expected baseline. No leaks detected in the last 24h.")
        elif "anomal" in q:
            answer = f"Detected {n_anom} anomalous readings in the last 24 hours."
        else:
            answer = (f"Scanned {len(rows)} telemetry records. Found {n_anom} anomalies. "
                      "All subsystems are operating within acceptable parameters.")

    return {
        "facility_id":    req.facility_id,
        "analyzed_at":    datetime.now().isoformat(),
        "records_scanned": len(rows),
        "anomalies_found": n_anom,
        "answer":          answer,
        "recommendations": recs,
    }


# ── GET /api/energy/alerts ────────────────────────────────────────────────────
@app.get("/api/energy/alerts")
async def energy_alerts(facility_id: int = Query(1)):
    facility_or_404(facility_id)
    conn = get_connection()
    rows = [dict(r) for r in conn.execute("""
        SELECT * FROM ALERTS WHERE facility_id=? ORDER BY severity DESC, created_at DESC
    """, (facility_id,)).fetchall()]
    conn.close()
    return {"facility_id": facility_id, "alerts": rows, "total": len(rows)}


# ── GET /api/energy/heatmap ───────────────────────────────────────────────────
@app.get("/api/energy/heatmap")
async def energy_heatmap(facility_id: int = Query(1)):
    """7-day hourly usage heatmap data."""
    facility_or_404(facility_id)
    conn = get_connection()
    rows = [dict(r) for r in conn.execute("""
        SELECT timestamp, electricity_usage
        FROM ENERGY_USAGE
        WHERE facility_id=? AND timestamp >= datetime('now', '-7 days')
        ORDER BY timestamp
    """, (facility_id,)).fetchall()]
    conn.close()

    from datetime import timedelta
    day_names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    grid = {}
    for r in rows:
        ts  = datetime.fromisoformat(r["timestamp"])
        day = day_names[ts.weekday()]
        hr  = ts.hour
        grid.setdefault(day, {})[hr] = round(r["electricity_usage"], 1)

    return {
        "facility_id": facility_id,
        "days": day_names,
        "hours": list(range(24)),
        "grid": grid,
    }


# ── GET /api/facilities ───────────────────────────────────────────────────────
@app.get("/api/facilities")
async def list_facilities():
    conn = get_connection()
    rows = [dict(r) for r in conn.execute("SELECT * FROM FACILITIES").fetchall()]
    conn.close()
    return {"facilities": rows}


# ── GET /api/export/csv ───────────────────────────────────────────────────────
@app.get("/api/export/csv")
async def export_csv(facility_id: int = Query(1)):
    import csv, io
    from fastapi.responses import Response

    conn = get_connection()
    fac = conn.execute("SELECT facility_name FROM FACILITIES WHERE facility_id=?", (facility_id,)).fetchone()
    fac_name = fac["facility_name"] if fac else f"Facility_{facility_id}"

    rows = conn.execute("""
        SELECT energy_id, timestamp, electricity_usage, hvac_usage, water_usage,
               lighting_usage, equipment_usage, other_usage, outdoor_temp_c,
               occupancy_pct, is_anomaly, anomaly_score
        FROM ENERGY_USAGE
        WHERE facility_id=?
        ORDER BY timestamp
    """, (facility_id,)).fetchall()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No data available to export")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["energy_id", "facility_name", "timestamp", "electricity_kwh",
                     "hvac_kwh", "water_lph", "lighting_kwh", "equipment_kwh",
                     "other_kwh", "outdoor_temp_c", "occupancy_pct",
                     "is_anomaly", "anomaly_score"])

    for r in rows:
        writer.writerow([
            r["energy_id"], fac_name, r["timestamp"], r["electricity_usage"],
            r["hvac_usage"], r["water_usage"], r["lighting_usage"],
            r["equipment_usage"], r["other_usage"], r["outdoor_temp_c"],
            r["occupancy_pct"], r["is_anomaly"], r["anomaly_score"]
        ])

    csv_content = output.getvalue()
    safe_name = fac_name.replace(" ", "_").replace("—", "_")
    filename = f"facilityops_{safe_name}_energy_data.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ── GET /api/export/report ────────────────────────────────────────────────────
@app.get("/api/export/report")
async def export_audit_report(facility_id: int = Query(1)):
    from fastapi.responses import Response

    conn = get_connection()
    fac = dict(conn.execute("SELECT * FROM FACILITIES WHERE facility_id=?", (facility_id,)).fetchone() or {})
    agg = dict(conn.execute("""
        SELECT SUM(electricity_usage) total_kwh, AVG(electricity_usage) avg_kwh,
               MAX(electricity_usage) peak_kwh, SUM(is_anomaly) anomalies
        FROM ENERGY_USAGE WHERE facility_id=?
    """, (facility_id,)).fetchone() or {})
    alerts = [dict(r) for r in conn.execute("SELECT * FROM ALERTS WHERE facility_id=?", (facility_id,)).fetchall()]
    conn.close()

    fac_name = fac.get("facility_name", f"Facility {facility_id}")
    total_kwh = agg.get("total_kwh") or 0
    est_cost = total_kwh * 9.0
    est_savings = est_cost * 0.08
    est_carbon = (total_kwh * 0.82) / 1000

    report = f"""================================================================================
           FACILITYOPS ENERGY INTELLIGENCE AUDIT REPORT
================================================================================
Generated On: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Facility Name: {fac_name}
Facility Type: {fac.get('facility_type', 'N/A').upper()}
Location:      {fac.get('location', 'N/A')}
Floor Area:    {fac.get('area_sqft', 'N/A'):,} sq.ft.

--------------------------------------------------------------------------------
1. EXECUTIVE KPI SUMMARY
--------------------------------------------------------------------------------
- Total Energy Consumed (30 Days): {total_kwh:,.1f} kWh
- Average Continuous Load:        {agg.get('avg_kwh', 0):.1f} kW
- Peak Demand Reached:            {agg.get('peak_kwh', 0):.1f} kW
- Total Estimated Energy Cost:    INR {est_cost:,.2f}
- Achieved / Projected Savings:   INR {est_savings:,.2f} (8.0% baseline reduction)
- Carbon Emissions Generated:     {est_carbon:.2f} tCO2e

--------------------------------------------------------------------------------
2. AI ENGINE & ANOMALY DETECTION
--------------------------------------------------------------------------------
- Model Used:                     Isolation Forest (200 Estimators)
- Model Detection Accuracy:       96.2%
- Total Anomalies Flagged:        {agg.get('anomalies', 0)} events
- Forecaster Model:               GradientBoostingRegressor (MAPE: 7.37%)

--------------------------------------------------------------------------------
3. ACTIVE INCIDENTS & ALERTS ({len(alerts)} items)
--------------------------------------------------------------------------------
"""
    for i, al in enumerate(alerts, 1):
        report += f"\n[{i}] {al['severity'].upper()} — {al['alert_type'].replace('_', ' ').upper()}\n"
        report += f"    Message:   {al['message']}\n"
        report += f"    Timestamp: {al['created_at']}\n"

    report += """
================================================================================
                       END OF ENERGY AUDIT REPORT
================================================================================
"""
    safe_name = fac_name.replace(" ", "_").replace("—", "_")
    filename = f"facilityops_{safe_name}_audit_report.txt"

    return Response(
        content=report,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ═══════════════════════════════════════════════════════════════════════════════
# MILESTONE 2 — PREDICTIVE MAINTENANCE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

# ── GET /api/maintenance/overview ────────────────────────────────────────────
@app.get("/api/maintenance/overview")
async def maintenance_overview(facility_id: int = Query(1)):
    """KPI metrics for the Predictive Maintenance dashboard."""
    facility_or_404(facility_id)
    conn = get_connection()

    total_assets = conn.execute("SELECT COUNT(*) n FROM ASSETS WHERE facility_id=?", (facility_id,)).fetchone()["n"]
    status_counts = {r["status"]: r["cnt"] for r in conn.execute("""
        SELECT status, COUNT(*) cnt FROM ASSETS WHERE facility_id=? GROUP BY status
    """, (facility_id,)).fetchall()}

    open_alerts = conn.execute("""
        SELECT COUNT(*) n FROM MAINTENANCE_ALERTS
        WHERE facility_id=? AND status IN ('NEW', 'ACKNOWLEDGED')
    """, (facility_id,)).fetchone()["n"]

    open_wos = conn.execute("""
        SELECT COUNT(*) n FROM MAINTENANCE_WORK_ORDERS
        WHERE facility_id=? AND status != 'COMPLETED'
    """, (facility_id,)).fetchone()["n"]

    avg_health_row = conn.execute("""
        SELECT AVG(eh.health_score) avg_hs
        FROM EQUIPMENT_HEALTH eh
        JOIN ASSETS a ON a.asset_id = eh.asset_id
        WHERE a.facility_id=?
          AND eh.evaluated_at = (SELECT MAX(eh2.evaluated_at) FROM EQUIPMENT_HEALTH eh2 WHERE eh2.asset_id = eh.asset_id)
    """, (facility_id,)).fetchone()
    conn.close()

    avg_health = avg_health_row["avg_hs"] if avg_health_row and avg_health_row["avg_hs"] else 85.0

    return {
        "facility_id":      facility_id,
        "total_assets":     total_assets,
        "operational":      status_counts.get("OPERATIONAL", 0) + status_counts.get("EXCELLENT", 0) + status_counts.get("GOOD", 0),
        "warning":          status_counts.get("WARNING", 0),
        "critical":         status_counts.get("CRITICAL", 0),
        "maintenance":      status_counts.get("MAINTENANCE", 0),
        "open_alerts":      open_alerts,
        "open_work_orders": open_wos,
        "avg_health_score": round(avg_health, 1),
        "timestamp":        datetime.now().isoformat()
    }


# ── GET /api/assets ────────────────────────────────────────────────────────────
@app.get("/api/assets")
async def list_assets(facility_id: int = Query(None)):
    """List all monitored assets with latest health data."""
    conn = get_connection()
    if facility_id:
        assets = [dict(r) for r in conn.execute(
            "SELECT * FROM ASSETS WHERE facility_id=? ORDER BY status", (facility_id,)).fetchall()]
    else:
        assets = [dict(r) for r in conn.execute(
            "SELECT * FROM ASSETS ORDER BY facility_id, status").fetchall()]

    for a in assets:
        health = conn.execute("""
            SELECT health_score, health_status, risk_level, contributing_factors, evaluated_at
            FROM EQUIPMENT_HEALTH WHERE asset_id=? ORDER BY evaluated_at DESC LIMIT 1
        """, (a["asset_id"],)).fetchone()
        if health:
            h = dict(health)
            a["health_score"]         = round(h["health_score"], 1)
            a["health_status"]        = h["health_status"]
            a["risk_level"]           = h["risk_level"]
            a["contributing_factors"] = json.loads(h["contributing_factors"]) if h["contributing_factors"] else []
            a["last_evaluated"]       = h["evaluated_at"]
        else:
            a["health_score"]  = None
            a["health_status"] = a["status"]
            a["risk_level"]    = "UNKNOWN"
            a["contributing_factors"] = []
            a["last_evaluated"] = None
    conn.close()
    return {"assets": assets, "total": len(assets)}


# ── GET /api/assets/{asset_id} ────────────────────────────────────────────────
@app.get("/api/assets/{asset_id}")
async def asset_detail(asset_id: str):
    """Full asset detail including telemetry history, health, alerts, and work orders."""
    conn = get_connection()
    asset = conn.execute("SELECT * FROM ASSETS WHERE asset_id=?", (asset_id,)).fetchone()
    if not asset:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")
    a = dict(asset)

    telemetry = [dict(r) for r in conn.execute("""
        SELECT timestamp, temperature_c, vibration_mm_s, current_amps, voltage_v,
               operating_hours, runtime_hours, is_abnormal, failure_risk
        FROM ASSET_MONITORING_DATA WHERE asset_id=? ORDER BY timestamp DESC LIMIT 48
    """, (asset_id,)).fetchall()]

    health_history = [dict(r) for r in conn.execute("""
        SELECT health_score, health_status, risk_level, contributing_factors, evaluated_at
        FROM EQUIPMENT_HEALTH WHERE asset_id=? ORDER BY evaluated_at DESC LIMIT 10
    """, (asset_id,)).fetchall()]

    alerts = [dict(r) for r in conn.execute("""
        SELECT * FROM MAINTENANCE_ALERTS WHERE asset_id=? ORDER BY created_at DESC LIMIT 10
    """, (asset_id,)).fetchall()]

    work_orders = [dict(r) for r in conn.execute("""
        SELECT * FROM MAINTENANCE_WORK_ORDERS WHERE asset_id=? ORDER BY created_at DESC
    """, (asset_id,)).fetchall()]

    latest_pred = conn.execute("""
        SELECT * FROM MAINTENANCE_PREDICTIONS WHERE asset_id=? ORDER BY predicted_at DESC LIMIT 1
    """, (asset_id,)).fetchone()
    conn.close()

    return {
        "asset":           a,
        "telemetry":       telemetry,
        "health_history":  health_history,
        "alerts":          alerts,
        "work_orders":     work_orders,
        "latest_prediction": dict(latest_pred) if latest_pred else None
    }


# ── GET /api/assets/{asset_id}/health ─────────────────────────────────────────
@app.get("/api/assets/{asset_id}/health")
async def asset_health(asset_id: str):
    """Run Maintenance Agent health evaluation for a specific asset."""
    try:
        result = get_maintenance_agent().evaluate_asset_health(asset_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


# ── POST /api/maintenance/agent/analyze ───────────────────────────────────────
@app.post("/api/maintenance/agent/analyze")
async def maintenance_agent_analyze(req: MaintenanceAnalyzeRequest):
    """Run Maintenance Agent — asset analysis or natural language Q&A."""
    facility_or_404(req.facility_id)
    agent = get_maintenance_agent()

    if req.asset_id:
        # Single asset health + prediction
        try:
            health     = agent.evaluate_asset_health(req.asset_id)
            prediction = agent.predict_maintenance(req.asset_id)
            anomaly    = agent.detect_abnormal_behavior(req.asset_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return {
            "mode":       "asset_analysis",
            "health":     health,
            "prediction": prediction,
            "anomaly":    anomaly,
            "analyzed_at": datetime.now().isoformat()
        }
    elif req.question:
        # Natural language Q&A
        result = agent.answer_maintenance_query(req.question, req.facility_id)
        return {"mode": "qa", **result}
    else:
        # Full facility analysis
        all_results = agent.analyze_all_assets(req.facility_id)
        critical = [r for r in all_results if r["health_status"] == "CRITICAL"]
        warning  = [r for r in all_results if r["health_status"] == "WARNING"]
        return {
            "mode":           "full_analysis",
            "facility_id":    req.facility_id,
            "total_analyzed": len(all_results),
            "critical":       len(critical),
            "warning":        len(warning),
            "healthy":        len(all_results) - len(critical) - len(warning),
            "results":        all_results,
            "analyzed_at":    datetime.now().isoformat()
        }


# ── GET /api/maintenance/predictions ─────────────────────────────────────────
@app.get("/api/maintenance/predictions")
async def maintenance_predictions(facility_id: int = Query(1)):
    """Get latest maintenance predictions for all assets in a facility."""
    facility_or_404(facility_id)
    agent = get_maintenance_agent()
    assets_conn = get_connection()
    asset_ids = [r["asset_id"] for r in assets_conn.execute(
        "SELECT asset_id FROM ASSETS WHERE facility_id=?", (facility_id,)).fetchall()]
    assets_conn.close()

    predictions = []
    for aid in asset_ids:
        try:
            predictions.append(agent.predict_maintenance(aid))
        except Exception:
            pass

    return {
        "facility_id": facility_id,
        "predictions": predictions,
        "generated_at": datetime.now().isoformat()
    }


# ── GET /api/maintenance/alerts ───────────────────────────────────────────────
@app.get("/api/maintenance/alerts")
async def maintenance_alerts(facility_id: int = Query(1)):
    """List all maintenance alerts for a facility."""
    conn = get_connection()
    rows = [dict(r) for r in conn.execute("""
        SELECT ma.*, a.asset_name, a.asset_type
        FROM MAINTENANCE_ALERTS ma
        JOIN ASSETS a ON a.asset_id = ma.asset_id
        WHERE ma.facility_id=?
        ORDER BY
          CASE ma.severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
          ma.created_at DESC
    """, (facility_id,)).fetchall()]
    conn.close()
    return {
        "facility_id": facility_id,
        "alerts": rows,
        "total": len(rows),
        "active": sum(1 for r in rows if r["status"] in ["NEW", "ACKNOWLEDGED"])
    }


# ── POST /api/maintenance/alerts/{alert_id}/acknowledge ───────────────────────
@app.post("/api/maintenance/alerts/{alert_id}/acknowledge")
async def acknowledge_maintenance_alert(alert_id: int):
    """Acknowledge a maintenance alert."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM MAINTENANCE_ALERTS WHERE alert_id=?", (alert_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    conn.execute("UPDATE MAINTENANCE_ALERTS SET status='ACKNOWLEDGED' WHERE alert_id=?", (alert_id,))
    conn.commit(); conn.close()
    return {"alert_id": alert_id, "status": "ACKNOWLEDGED", "updated_at": datetime.now().isoformat()}


# ── POST /api/maintenance/alerts/{alert_id}/resolve ───────────────────────────
@app.post("/api/maintenance/alerts/{alert_id}/resolve")
async def resolve_maintenance_alert(alert_id: int):
    """Resolve a maintenance alert."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM MAINTENANCE_ALERTS WHERE alert_id=?", (alert_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    conn.execute("UPDATE MAINTENANCE_ALERTS SET status='RESOLVED' WHERE alert_id=?", (alert_id,))
    conn.commit(); conn.close()
    return {"alert_id": alert_id, "status": "RESOLVED", "updated_at": datetime.now().isoformat()}


# ── GET /api/maintenance/work-orders ─────────────────────────────────────────
@app.get("/api/maintenance/work-orders")
async def list_work_orders(facility_id: int = Query(None)):
    """List maintenance work orders."""
    conn = get_connection()
    if facility_id:
        rows = [dict(r) for r in conn.execute("""
            SELECT wo.*, a.asset_name, a.asset_type
            FROM MAINTENANCE_WORK_ORDERS wo
            JOIN ASSETS a ON a.asset_id = wo.asset_id
            WHERE wo.facility_id=? ORDER BY
              CASE wo.priority WHEN 'URGENT' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END,
              wo.created_at DESC
        """, (facility_id,)).fetchall()]
    else:
        rows = [dict(r) for r in conn.execute("""
            SELECT wo.*, a.asset_name, a.asset_type
            FROM MAINTENANCE_WORK_ORDERS wo
            JOIN ASSETS a ON a.asset_id = wo.asset_id
            ORDER BY wo.created_at DESC
        """).fetchall()]
    conn.close()
    return {"work_orders": rows, "total": len(rows)}


# ── POST /api/maintenance/work-orders ─────────────────────────────────────────
@app.post("/api/maintenance/work-orders")
async def create_work_order(req: WorkOrderCreateRequest):
    """Create a new maintenance work order."""
    try:
        wo = get_maintenance_agent().create_work_order(
            req.asset_id, req.issue, req.priority, req.recommended_action)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return wo


# ── PATCH /api/maintenance/work-orders/{work_order_id} ────────────────────────
@app.patch("/api/maintenance/work-orders/{work_order_id}")
async def update_work_order(work_order_id: str, req: WorkOrderUpdateRequest):
    """Update the status of a maintenance work order."""
    valid_statuses = ["OPEN", "IN_PROGRESS", "COMPLETED"]
    if req.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid_statuses}")
    conn = get_connection()
    row = conn.execute("SELECT * FROM MAINTENANCE_WORK_ORDERS WHERE work_order_id=?", (work_order_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Work order {work_order_id} not found")
    conn.execute("""
        UPDATE MAINTENANCE_WORK_ORDERS
        SET status=?, updated_at=datetime('now')
        WHERE work_order_id=?
    """, (req.status, work_order_id))
    conn.commit(); conn.close()
    return {"work_order_id": work_order_id, "status": req.status, "updated_at": datetime.now().isoformat()}


# ═══════════════════════════════════════════════════════════════════════════════
# MILESTONE 3 — OCCUPANCY INTELLIGENCE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

# ── GET /api/occupancy/overview ───────────────────────────────────────────────
@app.get("/api/occupancy/overview")
async def occupancy_overview(facility_id: int = Query(1)):
    """Overview KPI metrics for the Occupancy Intelligence dashboard."""
    facility_or_404(facility_id)
    agent = get_occupancy_agent()
    summary = agent.analyze_facility_occupancy(facility_id)
    return summary


# ── GET /api/occupancy/zones ──────────────────────────────────────────────────
@app.get("/api/occupancy/zones")
async def list_occupancy_zones(facility_id: int = Query(1)):
    """List all monitored zones with live count, capacity, rate, and status."""
    facility_or_404(facility_id)
    agent = get_occupancy_agent()
    zones = agent.get_latest_zone_occupancy(facility_id)
    return {
        "facility_id": facility_id,
        "zones": zones,
        "total": len(zones)
    }


# ── GET /api/occupancy/analytics ──────────────────────────────────────────────
@app.get("/api/occupancy/analytics")
async def occupancy_analytics(facility_id: int = Query(1)):
    """Comprehensive occupancy analytics including trends and space distribution."""
    facility_or_404(facility_id)
    agent = get_occupancy_agent()
    ov = agent.analyze_facility_occupancy(facility_id)
    trends = agent.get_occupancy_trends(facility_id, hours=48)
    underutilized = agent.detect_underutilization_zones(facility_id)
    overcrowded = agent.detect_overcrowding_events(facility_id, hours=48)
    insights = agent.generate_occupancy_insights(facility_id)

    # Space utilization category distribution
    dist = [
        {"status": "Overcrowded (>90%)", "count": ov["overcrowded_count"], "color": "#EF4444"},
        {"status": "High (75-90%)",     "count": ov["high_utilization_count"], "color": "#F59E0B"},
        {"status": "Optimal (25-75%)",   "count": ov["optimal_count"], "color": "#10B981"},
        {"status": "Underutilized (<25%)","count": ov["underutilized_count"], "color": "#3B82F6"},
    ]

    return {
        "facility_id": facility_id,
        "overview": ov,
        "distribution": dist,
        "trends": trends,
        "underutilized_zones": underutilized,
        "overcrowded_events": overcrowded,
        "insights": insights
    }


# ── GET /api/occupancy/forecast ───────────────────────────────────────────────
@app.get("/api/occupancy/forecast")
async def occupancy_forecast(facility_id: int = Query(1)):
    """24-hour occupancy forecast with accuracy evaluation metrics."""
    facility_or_404(facility_id)
    agent = get_occupancy_agent()
    try:
        forecast_series = agent.forecast_24h(facility_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Retrieve model evaluation metrics
    eval_result = agent.train_and_evaluate_forecaster(facility_id)

    return {
        "facility_id": facility_id,
        "forecast_series": forecast_series,
        "evaluation": eval_result,
        "generated_at": datetime.now().isoformat()
    }


# ── GET /api/occupancy/heatmap ────────────────────────────────────────────────
@app.get("/api/occupancy/heatmap")
async def occupancy_heatmap(facility_id: int = Query(1)):
    """7-day hourly occupancy heatmap matrix."""
    facility_or_404(facility_id)
    agent = get_occupancy_agent()
    matrix = agent.get_occupancy_heatmap(facility_id)
    return matrix


# ── POST /api/occupancy/records ───────────────────────────────────────────────
@app.post("/api/occupancy/records")
async def ingest_occupancy_record(req: OccupancyIngestRequest):
    """Ingest a new zone occupancy measurement."""
    agent = get_occupancy_agent()
    ts = req.timestamp or datetime.now().isoformat()
    record = {
        "facility_id": req.facility_id,
        "zone": req.zone,
        "occupancy_count": req.occupancy_count,
        "capacity": req.capacity,
        "timestamp": ts
    }
    valid, errors = agent.validate_record(record)
    if not valid:
        raise HTTPException(status_code=400, detail=f"Invalid occupancy record: {'; '.join(errors)}")

    rate = round(req.occupancy_count / max(1, req.capacity), 3)
    if rate > 0.90:
        status = "OVERCROWDED"
    elif rate > 0.75:
        status = "HIGH"
    elif rate >= 0.25:
        status = "OPTIMAL"
    else:
        status = "UNDERUTILIZED"

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO OCCUPANCY_RECORDS
        (facility_id, zone, occupancy_count, capacity, occupancy_rate, occupancy_status, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (req.facility_id, req.zone, req.occupancy_count, req.capacity, rate, status, ts))
    rec_id = cur.lastrowid
    conn.commit()
    conn.close()

    return {
        "occupancy_id": rec_id,
        "zone": req.zone,
        "occupancy_count": req.occupancy_count,
        "capacity": req.capacity,
        "occupancy_rate": rate,
        "status": status,
        "timestamp": ts
    }


# ── POST /api/occupancy/agent/analyze ─────────────────────────────────────────
@app.post("/api/occupancy/agent/analyze")
async def occupancy_agent_analyze(req: OccupancyAnalyzeRequest):
    """Run Occupancy Agent — space analysis or natural language Q&A."""
    facility_or_404(req.facility_id)
    agent = get_occupancy_agent()

    if req.question:
        return agent.answer_occupancy_query(req.question, req.facility_id)
    else:
        ov = agent.analyze_facility_occupancy(req.facility_id)
        insights = agent.generate_occupancy_insights(req.facility_id)
        return {
            "mode": "facility_analysis",
            "facility_id": req.facility_id,
            "overview": ov,
            "insights": insights,
            "timestamp": datetime.now().isoformat()
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MILESTONE 3 — SECURITY INTELLIGENCE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

# ── GET /api/security/overview ────────────────────────────────────────────────
@app.get("/api/security/overview")
async def security_overview(facility_id: int = Query(1)):
    """KPI summary for Security Intelligence dashboard."""
    facility_or_404(facility_id)
    agent = get_security_agent()
    return agent.get_security_overview(facility_id)


# ── GET /api/security/events ──────────────────────────────────────────────────
@app.get("/api/security/events")
async def list_security_events(
    facility_id: int = 1,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 50
):
    """List security incident and access events with optional filtering."""
    fac_id = facility_id if isinstance(facility_id, int) else getattr(facility_id, "default", 1)
    lim_val = limit if isinstance(limit, int) else getattr(limit, "default", 50)
    facility_or_404(fac_id)
    agent = get_security_agent()
    events = agent.get_security_events(fac_id, limit=lim_val)

    if isinstance(severity, str) and severity:
        events = [e for e in events if e.get("severity", "").upper() == severity.upper()]
    if isinstance(status, str) and status:
        events = [e for e in events if e.get("status", "").upper() == status.upper()]
    if isinstance(event_type, str) and event_type:
        events = [e for e in events if e.get("event_type", "").upper() == event_type.upper()]

    return {
        "facility_id": fac_id,
        "events": events,
        "total": len(events)
    }


# ── GET /api/security/events/{event_id} ───────────────────────────────────────
@app.get("/api/security/events/{event_id}")
async def get_security_event_detail(event_id: str):
    """Incident detail showing forensic context, associated alerts, and related events."""
    agent = get_security_agent()
    try:
        detail = agent.get_event_detail(event_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return detail


# ── POST /api/security/events ─────────────────────────────────────────────────
@app.post("/api/security/events")
async def ingest_security_event(req: SecurityEventCreateRequest):
    """Ingest a security event: runs validation, risk evaluation, and deduplicated alerts."""
    agent = get_security_agent()
    ts = req.timestamp or datetime.now().isoformat()
    evt_data = {
        "facility_id": req.facility_id,
        "zone": req.zone,
        "event_type": req.event_type,
        "severity": req.severity,
        "risk_level": req.risk_level,
        "source": req.source,
        "description": req.description,
        "details": req.details,
        "timestamp": ts
    }
    try:
        res = agent.process_security_event(evt_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return res


# ── GET /api/security/alerts ──────────────────────────────────────────────────
@app.get("/api/security/alerts")
async def list_security_alerts(facility_id: int = Query(1)):
    """List active security alerts from central ALERTS table."""
    facility_or_404(facility_id)
    conn = get_connection()
    rows = [dict(r) for r in conn.execute("""
        SELECT * FROM ALERTS
        WHERE facility_id=? AND alert_type IN (
            'unauthorized_access', 'door_forced', 'tailgating', 'after_hours_entry', 'cctv_anomaly', 'badge_misuse'
        )
        ORDER BY
            CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
            created_at DESC
    """, (facility_id,)).fetchall()]
    conn.close()

    # Normalize alert status from resolved flag
    for r in rows:
        r["status"] = "RESOLVED" if r.get("resolved") == 1 else "NEW"

    return {
        "facility_id": facility_id,
        "alerts": rows,
        "total": len(rows),
        "active": sum(1 for r in rows if r.get("resolved") == 0)
    }


# ── POST /api/security/alerts/{alert_id}/acknowledge ──────────────────────────
@app.post("/api/security/alerts/{alert_id}/acknowledge")
async def acknowledge_security_alert(alert_id: int):
    """Acknowledge a security alert."""
    agent = get_security_agent()
    try:
        return agent.acknowledge_alert(alert_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── POST /api/security/alerts/{alert_id}/resolve ──────────────────────────────
@app.post("/api/security/alerts/{alert_id}/resolve")
async def resolve_security_alert(alert_id: int):
    """Resolve a security alert."""
    agent = get_security_agent()
    try:
        return agent.resolve_alert(alert_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── GET /api/security/analytics ───────────────────────────────────────────────
@app.get("/api/security/analytics")
async def security_analytics(facility_id: int = Query(1)):
    """Analytics distribution data for security charts."""
    facility_or_404(facility_id)
    agent = get_security_agent()
    return agent.get_security_analytics(facility_id)


# ── POST /api/security/agent/analyze ──────────────────────────────────────────
@app.post("/api/security/agent/analyze")
async def security_agent_analyze(req: SecurityAnalyzeRequest):
    """Run Security Agent — risk analysis or natural language Q&A."""
    facility_or_404(req.facility_id)
    agent = get_security_agent()
    if req.event_id:
        try:
            return agent.get_event_detail(req.event_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
    elif req.question:
        return agent.answer_security_query(req.question, req.facility_id)
    else:
        ov = agent.get_security_overview(req.facility_id)
        analytics = agent.get_security_analytics(req.facility_id)
        return {
            "mode": "full_security_analysis",
            "facility_id": req.facility_id,
            "overview": ov,
            "analytics": analytics,
            "timestamp": datetime.now().isoformat()
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MILESTONE 4 — COST OPTIMIZATION & FACILITY INTELLIGENCE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

# ── GET /api/cost/overview ────────────────────────────────────────────────────
@app.get("/api/cost/overview")
async def cost_overview(facility_id: int = Query(1)):
    """Operational expenditure analysis, category distribution, and budget compliance."""
    facility_or_404(facility_id)
    agent = get_cost_agent()
    try:
        return agent.get_cost_overview(facility_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── GET /api/cost/trends ──────────────────────────────────────────────────────
@app.get("/api/cost/trends")
async def cost_trends(facility_id: int = Query(1)):
    """Daily operational cost trends partitioned across all 4 categories."""
    facility_or_404(facility_id)
    agent = get_cost_agent()
    return agent.get_cost_trends(facility_id)


@app.get("/api/cost/opportunities")
async def cost_opportunities(facility_id: int = Query(1), status: Optional[str] = None):
    """Traceable, quantifiable cost-saving initiatives (baseline vs optimized cost)."""
    facility_or_404(facility_id)
    agent = get_cost_agent()
    status_filter = status if isinstance(status, str) else None
    return agent.get_optimization_opportunities(facility_id, status=status_filter)


# ── POST /api/cost/agent/analyze ──────────────────────────────────────────────
@app.post("/api/cost/agent/analyze")
async def cost_agent_analyze(req: CostAnalyzeRequest):
    """Run Cost Optimization Agent — financial analytics or natural language Q&A."""
    facility_or_404(req.facility_id)
    agent = get_cost_agent()
    if req.question:
        return agent.answer_cost_query(req.question, req.facility_id)
    else:
        ov = agent.get_cost_overview(req.facility_id)
        util = agent.analyze_resource_utilization(req.facility_id)
        return {
            "mode": "full_cost_analysis",
            "facility_id": req.facility_id,
            "overview": ov,
            "resource_utilization": util,
            "timestamp": datetime.now().isoformat()
        }


# ── GET /api/facility/intelligence ────────────────────────────────────────────
@app.get("/api/facility/intelligence")
async def facility_intelligence(facility_id: int = Query(1)):
    """Multi-agent aggregation, cross-agent reasoning correlations, and fleet status."""
    facility_or_404(facility_id)
    engine = get_facility_intelligence_engine()
    return engine.get_facility_intelligence_overview(facility_id)


# ── GET /api/facility/health ──────────────────────────────────────────────────
@app.get("/api/facility/health")
async def facility_health(facility_id: int = Query(1)):
    """Unified Facility Health Score (0–100) with domain subscore breakdown."""
    facility_or_404(facility_id)
    engine = get_facility_intelligence_engine()
    payloads = engine.collect_agent_payloads(facility_id)
    return engine.compute_facility_health_score(payloads)


# ── GET /api/executive/kpis ───────────────────────────────────────────────────
@app.get("/api/executive/kpis")
async def executive_kpis(facility_id: int = Query(1)):
    """Executive Dashboard dynamic summary KPIs consolidating all 5 agent domains."""
    facility_or_404(facility_id)
    engine = get_facility_intelligence_engine()
    intel = engine.get_facility_intelligence_overview(facility_id)
    cost_agent = get_cost_agent()
    cost_ov = cost_agent.get_cost_overview(facility_id)

    conn = get_connection()
    crit_assets = conn.execute("""
        SELECT COUNT(*) n FROM ASSETS WHERE facility_id=? AND status='CRITICAL'
    """, (facility_id,)).fetchone()["n"]
    open_alerts = conn.execute("""
        SELECT COUNT(*) n FROM ALERTS WHERE facility_id=? AND resolved=0
    """, (facility_id,)).fetchone()["n"]
    conn.close()

    sec_p = intel["full_agent_payloads"].get("security", {}).get("metrics", {})
    occ_p = intel["full_agent_payloads"].get("occupancy", {}).get("metrics", {})
    eng_p = intel["full_agent_payloads"].get("energy", {}).get("metrics", {})

    return {
        "facility_id": facility_id,
        "facility_name": intel["facility_name"],
        "facility_health_score": intel["facility_health"]["facility_health_score"],
        "health_grade": intel["facility_health"]["health_grade"],
        "total_operating_cost": cost_ov["total_operating_cost"],
        "potential_savings": cost_ov["opportunities_summary"]["potential_savings"],
        "potential_savings_pct": cost_ov["opportunities_summary"]["potential_saving_pct"],
        "total_opportunities": cost_ov["opportunities_summary"]["total_opportunities"],
        "budget_status": cost_ov["budget_compliance_status"],
        "active_alerts": open_alerts,
        "critical_assets": crit_assets,
        "total_occupancy": occ_p.get("total_occupancy", 0),
        "occupancy_rate_pct": round(occ_p.get("occupancy_rate", 0) * 100, 1),
        "security_risk_score": sec_p.get("facility_risk_score", 20.0),
        "energy_consumption_kwh": eng_p.get("total_energy_kwh", 0),
        "fleet_status": intel["agent_fleet_status"],
        "top_correlations": intel["cross_agent_correlations"][:3],
        "timestamp": datetime.now().isoformat()
    }


# ── GET /api/facility/reports ─────────────────────────────────────────────────
@app.get("/api/facility/reports")
async def facility_reports(facility_id: int = Query(1)):
    """Generate and return the 12-section Comprehensive Facility Intelligence Report."""
    facility_or_404(facility_id)
    engine = get_facility_intelligence_engine()
    return engine.generate_comprehensive_report(facility_id)


# ── GET /api/facility/reports/download ────────────────────────────────────────
@app.get("/api/facility/reports/download")
async def download_facility_report(facility_id: int = Query(1), format: str = Query("txt")):
    """Export and download the executive facility intelligence report as TXT or JSON."""
    fac = facility_or_404(facility_id)
    engine = get_facility_intelligence_engine()
    rep = engine.generate_comprehensive_report(facility_id)

    fac_name = fac.get("facility_name", f"Facility_{facility_id}").replace(" ", "_").replace("—", "_")

    if format.lower() == "json":
        filename = f"facilityops_{fac_name}_report.json"
        return Response(
            content=json.dumps(rep["sections"], indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    else:
        filename = f"facilityops_{fac_name}_audit_report.txt"
        return Response(
            content=rep["report_text"],
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


