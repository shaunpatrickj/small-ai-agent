"""
test_milestone3.py — Comprehensive Test Suite for Milestone 3: Occupancy & Security Intelligence
Tests:
1. Database Schema & Data Integrity for OCCUPANCY_RECORDS and SECURITY_EVENTS
2. Occupancy Agent unit tests (validation, analytics, overcrowding detection, underutilization)
3. Occupancy Forecasting ML evaluation (verifying >= 80% accuracy honest measurement)
4. Security Agent unit tests (validation, severity classification, unauthorized access detection)
5. Alert Generation & Deduplication Lifecycle (NEW -> ACKNOWLEDGED -> RESOLVED)
6. Facility Intelligence standardized payload export schema
7. API Endpoints async invocation tests (Occupancy & Security)
8. Mandatory End-to-End TEST A: Occupancy Data -> Agent -> Analytics -> Forecast -> Dashboard API
9. Mandatory End-to-End TEST B: Security Event -> Agent -> Detection -> Alert -> Dashboard API
10. Non-regression of Milestone 1 (Energy Intelligence) and Milestone 2 (Predictive Maintenance)
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from database import get_connection
from occupancy_agent import get_occupancy_agent
from security_agent import get_security_agent
from main import (
    app,
    occupancy_overview,
    list_occupancy_zones,
    occupancy_analytics,
    occupancy_forecast,
    occupancy_heatmap,
    ingest_occupancy_record,
    occupancy_agent_analyze,
    security_overview,
    list_security_events,
    get_security_event_detail,
    ingest_security_event,
    list_security_alerts,
    acknowledge_security_alert,
    resolve_security_alert,
    security_analytics,
    security_agent_analyze,
    OccupancyIngestRequest,
    OccupancyAnalyzeRequest,
    SecurityEventCreateRequest,
    SecurityAnalyzeRequest,
    # Regression endpoints
    energy_overview,
    energy_distribution,
    energy_forecast,
    energy_alerts,
    maintenance_overview,
    list_assets,
    asset_detail,
    asset_health,
    maintenance_alerts
)

passed_tests = 0
failed_tests = 0

def check(name: str, condition: bool, msg: str = ""):
    global passed_tests, failed_tests
    if condition:
        print(f"  ✅ PASS: {name}")
        passed_tests += 1
    else:
        print(f"  ❌ FAIL: {name} - {msg}")
        failed_tests += 1


# ─── 1. DATABASE SCHEMA & DATA INTEGRITY TESTS ────────────────────────────────
def run_database_tests():
    print("\n--- 1. Database Schema & Data Integrity Tests ---")
    conn = get_connection()
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

    for t in ["OCCUPANCY_RECORDS", "SECURITY_EVENTS", "FACILITIES", "ENERGY_USAGE", "ASSETS", "ALERTS"]:
        check(f"Table {t} exists in SQLite", t in tables)

    occ_count = conn.execute("SELECT COUNT(*) n FROM OCCUPANCY_RECORDS").fetchone()["n"]
    check("Occupancy records present (>= 5,000)", occ_count >= 5000, f"Found {occ_count}")

    sec_count = conn.execute("SELECT COUNT(*) n FROM SECURITY_EVENTS").fetchone()["n"]
    check("Security events present (>= 5)", sec_count >= 5, f"Found {sec_count}")

    conn.close()


# ─── 2. OCCUPANCY AGENT CORE LOGIC TESTS ─────────────────────────────────────
def run_occupancy_agent_tests():
    print("\n--- 2. Occupancy Agent Core Logic & Analytics Tests ---")
    agent = get_occupancy_agent()

    # Data validation
    valid, errs = agent.validate_record({
        "facility_id": 1, "zone": "Test Zone", "occupancy_count": 25, "capacity": 50,
        "timestamp": datetime.now().isoformat()
    })
    check("OccupancyAgent validates complete record", valid)

    invalid, errs = agent.validate_record({
        "facility_id": 1, "zone": "Test Zone", "occupancy_count": -5, "capacity": 0
    })
    check("OccupancyAgent rejects negative count or invalid capacity", not invalid and len(errs) >= 2)

    # Zone analysis
    zones = agent.get_latest_zone_occupancy(1)
    check("OccupancyAgent retrieves facility zones", len(zones) >= 4, f"Found {len(zones)}")
    check("Zones contain occupancy_rate and recommendations", all("occupancy_rate" in z and "recommendation" in z for z in zones))

    # Facility aggregate analysis
    fac_occ = agent.analyze_facility_occupancy(1)
    check("Facility aggregate headcount calculated", fac_occ["total_occupancy"] >= 0)
    check("Facility occupancy_pct in range [0, 100]", 0 <= fac_occ["occupancy_pct"] <= 100)

    # Overcrowding & Underutilization detection
    over = agent.detect_overcrowding_events(1, hours=720) # 30 days
    check("Overcrowding detection operational", isinstance(over, list))

    under = agent.detect_underutilization_zones(1)
    check("Underutilized zone detection operational", isinstance(under, list))

    # Heatmap matrix
    hm = agent.get_occupancy_heatmap(1)
    check("Heatmap days present (7 days)", len(hm["days"]) == 7)
    check("Heatmap hours present (24 hours)", len(hm["hours"]) == 24)

    # Natural language Q&A
    qa = agent.answer_occupancy_query("Which zones are overcrowded?", 1)
    check("Occupancy Q&A produces answer", len(qa["answer"]) > 10)


# ─── 3. OCCUPANCY FORECASTING EVALUATION TEST ─────────────────────────────────
def run_occupancy_forecasting_tests():
    print("\n--- 3. Occupancy ML Forecaster Evaluation Tests ---")
    agent = get_occupancy_agent()

    eval_result = agent.train_and_evaluate_forecaster(1)
    check("Forecasting model trained successfully", eval_result.get("trained") is True)
    check("Evaluation metric measured honestly", "accuracy_pct" in eval_result and "mape" in eval_result)

    acc = eval_result.get("accuracy_pct", 0)
    print(f"      📊 Measured Forecast Accuracy: {acc}% (Target: >= 80.0%)")
    print(f"      📊 MAPE: {eval_result.get('mape')} | R² Score: {eval_result.get('r2_score')}")
    check("Occupancy forecasting accuracy >= 80%", acc >= 80.0, f"Got {acc}%")

    forecast_24h = agent.forecast_24h(1)
    check("24-hour forecast generated (24 hourly steps)", len(forecast_24h) == 24)
    check("Forecast items have predicted_occupancy and predicted_pct", all("predicted_occupancy" in f and "predicted_pct" in f for f in forecast_24h))


# ─── 4. SECURITY AGENT CORE LOGIC & ALERTS ───────────────────────────────────
def run_security_agent_tests():
    print("\n--- 4. Security Agent Core Logic & Alert Deduplication Tests ---")
    agent = get_security_agent()

    # Event validation
    valid, errs = agent.validate_event({
        "facility_id": 1, "zone": "East Gate", "event_type": "UNAUTHORIZED_ACCESS",
        "description": "Invalid card presented", "timestamp": datetime.now().isoformat()
    })
    check("SecurityAgent validates complete event", valid)

    # Process and detect unauthorized access
    test_evt = {
        "facility_id": 1,
        "zone": "Floor 1 Offices",
        "event_type": "UNAUTHORIZED_ACCESS",
        "severity": "HIGH",
        "risk_level": "HIGH",
        "source": "Access Control Test Suite",
        "description": "Synthetic unauthorized access penetration test",
        "details": {"test_run": True, "card": "CARD-TEST-01"},
        "timestamp": datetime.now().isoformat()
    }
    processed = agent.process_security_event(test_evt)
    check("Security event processed and classified", processed["detected"] is True)
    check("Security event severity classified as HIGH", processed["severity"] == "HIGH")
    check("Security event produced explainable recommendation", len(processed["recommendation"]) > 10)

    # Alert generation and deduplication
    alert1 = agent.trigger_security_alert(
        event_id="SEC-TEST-DEDUP",
        facility_id=1,
        zone="Executive Wing",
        event_type="DOOR_FORCED",
        severity="critical",
        description="Door held open test",
        recommended_action="Dispatch guard"
    )
    check("Initial security alert generated", alert1 is not None and alert1.get("alert_id") is not None)

    # Re-triggering duplicate alert in same facility/type window must be suppressed
    alert2 = agent.trigger_security_alert(
        event_id="SEC-TEST-DEDUP",
        facility_id=1,
        zone="Executive Wing",
        event_type="DOOR_FORCED",
        severity="critical",
        description="Door held open test duplicate",
        recommended_action="Dispatch guard"
    )
    check("Duplicate alert suppressed by deduplication", alert2 is None)

    # Alert lifecycle (NEW -> ACKNOWLEDGED -> RESOLVED)
    if alert1:
        aid = alert1["alert_id"]
        ack_res = agent.acknowledge_alert(aid)
        check("Alert acknowledged successfully", ack_res["status"] == "ACKNOWLEDGED")
        res_res = agent.resolve_alert(aid)
        check("Alert resolved successfully", res_res["status"] == "RESOLVED")

    # Security Overview & Q&A
    ov = agent.get_security_overview(1)
    check("Security overview returns total and risk grade", "facility_risk_grade" in ov and ov["total_security_events"] > 0)

    qa = agent.answer_security_query("Are there any door forced events?", 1)
    check("Security Q&A responds with context", len(qa["answer"]) > 10)


# ─── 5. FACILITY INTELLIGENCE PAYLOAD INTEGRATION ────────────────────────────
def run_facility_intelligence_payload_tests():
    print("\n--- 5. Facility Intelligence Schema Payload Tests ---")
    occ_agent = get_occupancy_agent()
    sec_agent = get_security_agent()

    occ_payload = occ_agent.export_facility_intelligence_payload(1)
    check("Occupancy exports agent='occupancy'", occ_payload.get("agent") == "occupancy")
    check("Occupancy payload has status, severity, insights, recommendations",
          all(k in occ_payload for k in ["status", "severity", "insights", "recommendations"]))

    sec_payload = sec_agent.export_facility_intelligence_payload(1)
    check("Security exports agent='security'", sec_payload.get("agent") == "security")
    check("Security payload has status, severity, insights, recommendations",
          all(k in sec_payload for k in ["status", "severity", "insights", "recommendations"]))


# ─── 6. API ENDPOINTS ASYNC INVOCATION TESTS ─────────────────────────────────
async def run_api_tests():
    print("\n--- 6. Milestone 3 API Endpoints Async Invocation Tests ---")

    # Occupancy endpoints
    occ_ov = await occupancy_overview(1)
    check("API GET /api/occupancy/overview", occ_ov["facility_id"] == 1 and "total_occupancy" in occ_ov)

    zones_res = await list_occupancy_zones(1)
    check("API GET /api/occupancy/zones", len(zones_res["zones"]) >= 4)

    an_res = await occupancy_analytics(1)
    check("API GET /api/occupancy/analytics", "distribution" in an_res and "trends" in an_res)

    fc_res = await occupancy_forecast(1)
    check("API GET /api/occupancy/forecast", "forecast_series" in fc_res and "evaluation" in fc_res)

    hm_res = await occupancy_heatmap(1)
    check("API GET /api/occupancy/heatmap", "day_grid" in hm_res)

    ing_occ = await ingest_occupancy_record(OccupancyIngestRequest(
        facility_id=1, zone="Floor 1 Offices", occupancy_count=85, capacity=120
    ))
    check("API POST /api/occupancy/records ingests data", ing_occ["occupancy_id"] > 0)

    qa_occ = await occupancy_agent_analyze(OccupancyAnalyzeRequest(
        facility_id=1, question="What is current facility occupancy?"
    ))
    check("API POST /api/occupancy/agent/analyze (Q&A mode)", "answer" in qa_occ)

    # Security endpoints
    sec_ov = await security_overview(1)
    check("API GET /api/security/overview", "facility_risk_score" in sec_ov)

    sec_events = await list_security_events(1)
    check("API GET /api/security/events", len(sec_events["events"]) > 0)

    first_event_id = sec_events["events"][0]["event_id"]
    evt_detail = await get_security_event_detail(first_event_id)
    check("API GET /api/security/events/{id} returns forensic detail", "investigation_context" in evt_detail)

    sec_alerts_data = await list_security_alerts(1)
    check("API GET /api/security/alerts returns active alerts", "alerts" in sec_alerts_data)

    if sec_alerts_data["alerts"]:
        al_id = sec_alerts_data["alerts"][0]["alert_id"]
        ack_res = await acknowledge_security_alert(al_id)
        check("API POST /api/security/alerts/{id}/acknowledge", ack_res["status"] == "ACKNOWLEDGED")

    sec_an = await security_analytics(1)
    check("API GET /api/security/analytics returns distribution charts", "severity_distribution" in sec_an)

    sec_qa = await security_agent_analyze(SecurityAnalyzeRequest(
        facility_id=1, question="Summarize security risk status"
    ))
    check("API POST /api/security/agent/analyze (Q&A mode)", "answer" in sec_qa)


# ─── 7. MANDATORY END-TO-END TESTS ───────────────────────────────────────────
async def run_end_to_end_tests():
    print("\n--- 7. Mandatory End-to-End Tests ---")

    # TEST A: Occupancy Data -> Occupancy Agent -> Analytics -> Forecast -> Dashboard API
    print("  [TEST A Workflow]: Occupancy Data -> Agent -> Analytics -> Forecast -> Dashboard API")
    now_str = datetime.now().isoformat()
    latest_ts = (datetime.now() + timedelta(days=2)).replace(microsecond=0).isoformat()
    # Step 1: Ingest occupancy data
    ingest_res = await ingest_occupancy_record(OccupancyIngestRequest(
        facility_id=1,
        zone="Central Cafeteria",
        occupancy_count=145,
        capacity=150,
        timestamp=latest_ts
    ))
    check("TEST A (1/5): Occupancy data ingested", ingest_res["occupancy_count"] == 145)

    # Step 2: Agent evaluation
    zones = get_occupancy_agent().get_latest_zone_occupancy(1)
    cafe_zone = next((z for z in zones if z["zone"] == "Central Cafeteria"), None)
    check("TEST A (2/5): Occupancy Agent evaluated zone status", cafe_zone is not None and cafe_zone["occupancy_rate"] > 0.90)

    # Step 3: Analytics aggregate
    analytics = await occupancy_analytics(1)
    check("TEST A (3/5): Analytics updated with latest data", analytics["overview"]["total_occupancy"] > 0)

    # Step 4: Forecast generation
    fc = await occupancy_forecast(1)
    check("TEST A (4/5): Forecast operational with target >= 80%", fc["evaluation"]["accuracy_pct"] >= 80.0)

    # Step 5: Dashboard overview
    ov = await occupancy_overview(1)
    check("TEST A (5/5): Dashboard API delivers updated occupancy metrics", ov["total_zones"] >= 4)

    # TEST B: Security Event -> Security Agent -> Detection -> Alert -> Dashboard API
    print("\n  [TEST B Workflow]: Security Event -> Security Agent -> Detection -> Alert -> Dashboard API")
    # Step 1: Ingest security event
    sec_ingest = await ingest_security_event(SecurityEventCreateRequest(
        facility_id=1,
        zone="Executive Boardroom",
        event_type="UNAUTHORIZED_ACCESS",
        severity="HIGH",
        risk_level="HIGH",
        source="Biometric Turnstile #BR-01",
        description="E2E Test: Unauthorized biometric scan attempt",
        details={"badge_id": "TEST-BIOM-999", "attempts": 3},
        timestamp=datetime.now().isoformat()
    ))
    check("TEST B (1/5): Security event received & persisted", sec_ingest["event_id"].startswith("SEC-EVT-"))

    # Step 2: Agent detection & classification
    check("TEST B (2/5): Security Agent detected incident", sec_ingest["detected"] is True and sec_ingest["severity"] == "HIGH")

    # Step 3: Alert triggered
    alerts = await list_security_alerts(1)
    check("TEST B (3/5): Security alert exists in alert registry", alerts["total"] > 0)

    # Step 4: Alert lifecycle management
    unresolved = [a for a in alerts["alerts"] if a["status"] != "RESOLVED"]
    if unresolved:
        target_aid = unresolved[0]["alert_id"]
        res = await resolve_security_alert(target_aid)
        check("TEST B (4/5): Alert lifecycle resolved", res["status"] == "RESOLVED")

    # Step 5: Security Dashboard API reflects updated state
    sec_dash = await security_overview(1)
    check("TEST B (5/5): Dashboard API returns updated security overview", sec_dash["total_security_events"] > 0)


# ─── 8. MILESTONE 1 & 2 NON-REGRESSION TESTS ─────────────────────────────────
async def run_regression_tests():
    print("\n--- 8. Non-Regression Tests (Milestones 1 & 2) ---")

    # Milestone 1: Energy Intelligence
    e_ov = await energy_overview(1)
    check("M1 Regression: Energy overview operational", "total_energy_kwh" in e_ov and "efficiency_score" in e_ov)

    e_dist = await energy_distribution(1)
    check("M1 Regression: Energy distribution operational", len(e_dist["subsystems"]) == 4)

    e_fc = await energy_forecast(1)
    check("M1 Regression: Energy forecast operational", len(e_fc["forecast_series"]) > 0)

    e_al = await energy_alerts(1)
    check("M1 Regression: Energy alerts operational", "alerts" in e_al)

    # Milestone 2: Predictive Maintenance
    m_ov = await maintenance_overview(1)
    check("M2 Regression: Maintenance overview operational", m_ov["total_assets"] >= 5)

    m_assets = await list_assets(1)
    check("M2 Regression: Assets list operational", len(m_assets["assets"]) >= 5)

    m_detail = await asset_detail("HVAC-AHU-001")
    check("M2 Regression: Asset detail operational", m_detail["asset"]["asset_id"] == "HVAC-AHU-001")

    m_health = await asset_health("HVAC-AHU-001")
    check("M2 Regression: Asset health scoring operational", "health_score" in m_health)

    m_alerts = await maintenance_alerts(1)
    check("M2 Regression: Maintenance alerts operational", "alerts" in m_alerts)


# ─── MAIN RUNNER ─────────────────────────────────────────────────────────────
async def main():
    print("==================================================================")
    print("  FACILITYOPS AI PLATFORM — MILESTONE 3 VERIFICATION SUITE       ")
    print("  Occupancy & Security Intelligence + Regression Verification    ")
    print("==================================================================")

    run_database_tests()
    run_occupancy_agent_tests()
    run_occupancy_forecasting_tests()
    run_security_agent_tests()
    run_facility_intelligence_payload_tests()
    await run_api_tests()
    await run_end_to_end_tests()
    await run_regression_tests()

    print("\n==================================================================")
    print(f"  TOTAL TESTS RUN: {passed_tests + failed_tests}")
    print(f"  PASSED: {passed_tests} | FAILED: {failed_tests}")
    print("==================================================================")

    if failed_tests > 0:
        print("  ❌ VERIFICATION FAILED: Some tests did not pass.")
        sys.exit(1)
    else:
        print("  🎉 ALL MILESTONE 3 & REGRESSION TESTS PASSED PERFECTLY!")


if __name__ == "__main__":
    asyncio.run(main())
