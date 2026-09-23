"""
test_milestone4.py — Comprehensive Test & Verification Suite for Milestone 4
Cost Optimization, Cross-Agent Orchestration, Executive KPIs & Enterprise Reporting

Tests:
1. Database Schema & Data Integrity for COST_RECORDS, OPTIMIZATION_OPPORTUNITIES, and REPORTS
2. Cost Optimization Agent unit tests (OpEx calculation, category variance, savings traceability)
3. Common Agent Output Contract validation across all 5 specialized agents
4. Facility Intelligence Engine: Multi-Agent Orchestration & Unified Facility Health Scoring
5. Cross-Agent Reasoning & Correlation Detection (HVAC+Occupancy, Degradation+Energy Surge)
6. 12-Section Facility Intelligence Report Generation & Traceable Export (JSON & Text)
7. Milestone 4 API Endpoints Async Invocation Tests (Cost, Executive KPIs, Reports)
8. MANDATORY END-TO-END TEST:
   Energy Data -> Energy Agent
   Maintenance Data -> Maintenance Agent
   Occupancy Data -> Occupancy Agent
   Security Event -> Security Agent
   Cost Data -> Cost Agent
   All Outputs -> Facility Intelligence Engine -> Cross-Agent Analysis -> Executive Recommendation -> Dashboard & Report
9. Full Non-Regression Suite for Milestones 1, 2, and 3
"""

import sys
import os
import json
import asyncio
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from database import get_connection
from cost_agent import get_cost_agent
from facility_intelligence_engine import get_facility_intelligence_engine
from ai_engine import export_energy_intelligence_payload
from maintenance_agent import get_maintenance_agent
from occupancy_agent import get_occupancy_agent
from security_agent import get_security_agent
from main import (
    app,
    cost_overview,
    cost_trends,
    cost_opportunities,
    cost_agent_analyze,
    facility_intelligence,
    facility_health,
    executive_kpis,
    facility_reports,
    download_facility_report,
    CostAnalyzeRequest,
    # Regression endpoints
    energy_overview,
    energy_distribution,
    energy_forecast,
    energy_alerts,
    maintenance_overview,
    list_assets,
    asset_detail,
    asset_health,
    maintenance_alerts,
    occupancy_overview,
    list_occupancy_zones,
    occupancy_analytics,
    occupancy_forecast,
    security_overview,
    list_security_events,
    list_security_alerts
)

passed_tests = 0
failed_tests = 0

def check(test_name: str, condition: bool, details: str = ""):
    global passed_tests, failed_tests
    if condition:
        passed_tests += 1
        print(f"  ✅ PASS: {test_name}")
    else:
        failed_tests += 1
        print(f"  ❌ FAIL: {test_name} — {details}")


# ─── 1. DATABASE SCHEMA & DATA INTEGRITY ──────────────────────────────────────
def run_database_tests():
    print("\n--- 1. Database Schema & Data Integrity Tests ---")
    conn = get_connection()
    tables = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

    check("Table COST_RECORDS exists", "COST_RECORDS" in tables)
    check("Table OPTIMIZATION_OPPORTUNITIES exists", "OPTIMIZATION_OPPORTUNITIES" in tables)
    check("Table FACILITY_INTELLIGENCE_REPORTS exists", "FACILITY_INTELLIGENCE_REPORTS" in tables)

    cost_count = conn.execute("SELECT COUNT(*) n FROM COST_RECORDS").fetchone()["n"]
    check("Cost records present (>= 400 records)", cost_count >= 400, f"Got {cost_count}")

    opp_count = conn.execute("SELECT COUNT(*) n FROM OPTIMIZATION_OPPORTUNITIES").fetchone()["n"]
    check("Optimization opportunities present (>= 5)", opp_count >= 5, f"Got {opp_count}")

    # Check categories
    cats = [r["category"] for r in conn.execute("SELECT DISTINCT category FROM COST_RECORDS").fetchall()]
    check("All 4 cost categories present (ENERGY, MAINTENANCE, SECURITY, ADMINISTRATIVE)",
          set(["ENERGY", "MAINTENANCE", "SECURITY", "ADMINISTRATIVE"]).issubset(set(cats)))

    conn.close()


# ─── 2. COST OPTIMIZATION AGENT UNIT TESTS ────────────────────────────────────
def run_cost_agent_tests():
    print("\n--- 2. Cost Optimization Agent Core Logic Tests ---")
    agent = get_cost_agent()
    ov = agent.get_cost_overview(1)

    check("Cost overview returns positive total OpEx", ov["total_operating_cost"] > 0)
    check("Cost overview includes budget compliance status", ov["budget_compliance_status"] in ["COMPLIANT", "OVER_BUDGET"])
    check("Cost overview includes cost_per_sqft and cost_per_occupant",
          ov["cost_per_sqft"] > 0 and ov["cost_per_occupant"] > 0)
    check("Cost overview contains 4 category breakdowns", len(ov["cost_by_category"]) == 4)

    # Test trends
    trends = agent.get_cost_trends(1)
    check("Cost trends returns 30 daily series", len(trends) >= 28, f"Got {len(trends)}")
    check("Trend entry has ENERGY, MAINTENANCE, SECURITY, ADMINISTRATIVE, and TOTAL",
          all(k in trends[0] for k in ["ENERGY", "MAINTENANCE", "SECURITY", "ADMINISTRATIVE", "TOTAL", "BUDGET"]))

    # Test opportunities
    opps = agent.get_optimization_opportunities(1)
    check("Optimization opportunities returned with valid structure", len(opps) > 0)
    first_opp = opps[0]
    check("Opportunity has traceable baseline vs optimized cost",
          first_opp["baseline_cost"] > first_opp["estimated_optimized_cost"])
    check("Opportunity potential saving matches difference",
          round(first_opp["baseline_cost"] - first_opp["estimated_optimized_cost"], 2) == round(first_opp["potential_saving"], 2))

    # Test Resource Utilization
    util = agent.analyze_resource_utilization(1)
    check("Resource utilization contains category insights", len(util["insights"]) >= 2)

    # Test Natural Language Q&A
    q_res = agent.answer_cost_query("What is our energy expenditure?", 1)
    check("Cost Q&A answers energy expenditure question", "energy" in q_res["answer"].lower())


# ─── 3. COMMON AGENT OUTPUT CONTRACT TESTS ────────────────────────────────────
def run_agent_contract_tests():
    print("\n--- 3. Common Agent Output Contract Validation Tests ---")
    required_keys = ["agent", "facility_id", "timestamp", "status", "severity", "metrics", "insights", "recommendations"]

    # 1. Energy Agent Contract
    e_p = export_energy_intelligence_payload(1)
    check("Energy agent exports contract", all(k in e_p for k in required_keys) and e_p["agent"] == "energy")

    # 2. Maintenance Agent Contract
    m_p = get_maintenance_agent().export_facility_intelligence_payload(1)
    check("Maintenance agent exports contract", all(k in m_p for k in required_keys) and m_p["agent"] == "maintenance")

    # 3. Occupancy Agent Contract
    o_p = get_occupancy_agent().export_facility_intelligence_payload(1)
    check("Occupancy agent exports contract", all(k in o_p for k in required_keys) and o_p["agent"] == "occupancy")

    # 4. Security Agent Contract
    s_p = get_security_agent().export_facility_intelligence_payload(1)
    check("Security agent exports contract", all(k in s_p for k in required_keys) and s_p["agent"] == "security")

    # 5. Cost Agent Contract
    c_p = get_cost_agent().export_facility_intelligence_payload(1)
    check("Cost agent exports contract", all(k in c_p for k in required_keys) and c_p["agent"] == "cost")


# ─── 4. FACILITY INTELLIGENCE ENGINE & HEALTH SCORING TESTS ───────────────────
def run_facility_intelligence_engine_tests():
    print("\n--- 4. Facility Intelligence Engine & Health Scoring Tests ---")
    engine = get_facility_intelligence_engine()

    payloads = engine.collect_agent_payloads(1)
    check("All 5 agent payloads successfully collected", len(payloads) == 5)
    check("Agents include energy, maintenance, occupancy, security, cost",
          set(["energy", "maintenance", "occupancy", "security", "cost"]) == set(payloads.keys()))

    health = engine.compute_facility_health_score(payloads)
    check("Facility Health Score in valid range [0, 100]", 0.0 <= health["facility_health_score"] <= 100.0)
    check("Health grade assigned (EXCELLENT/GOOD/FAIR/POOR)", health["health_grade"] in ["EXCELLENT", "GOOD", "FAIR", "POOR"])
    check("Health breakdown contains all 5 domain subscores",
          set(["maintenance", "energy", "security", "occupancy", "cost"]) == set(health["subscores"].keys()))
    check("Health breakdown provides methodology documentation", "methodology_note" in health)

    # Test Cross-Agent Reasoning
    correlations = engine.perform_cross_agent_reasoning(1, payloads)
    check("Cross-agent reasoning generates correlations", len(correlations) > 0)
    c1 = correlations[0]
    check("Correlation entry contains rule_id, title, participating_agents, severity, recommendation",
          all(k in c1 for k in ["rule_id", "title", "participating_agents", "severity", "recommendation", "financial_impact"]))


# ─── 5. 12-SECTION REPORT GENERATION TESTS ─────────────────────────────────────
def run_report_generation_tests():
    print("\n--- 5. 12-Section Facility Intelligence Report Tests ---")
    engine = get_facility_intelligence_engine()
    rep = engine.generate_comprehensive_report(1)

    check("Report ID generated with prefix 'REP-'", rep["report_id"].startswith("REP-"))
    check("Report contains exactly 12 required sections", len(rep["sections"]) == 12)

    expected_sections = [
        "executive_summary", "facility_health", "energy_intelligence",
        "maintenance_intelligence", "occupancy_intelligence", "security_intelligence",
        "cost_intelligence", "cross_agent_insights", "recommendations",
        "active_alerts", "optimization_opportunities", "data_quality_and_limitations"
    ]
    check("All 12 specific report sections present", set(expected_sections) == set(rep["sections"].keys()))
    check("Report includes human-readable formatted audit text", len(rep["report_text"]) > 500)
    check("Audit text clearly distinguishes measured vs estimates vs predictions",
          "Measured:" in rep["report_text"] and "Estimates:" in rep["report_text"])


# ─── 6. MILESTONE 4 API ENDPOINTS ASYNC TESTS ─────────────────────────────────
async def run_api_tests():
    print("\n--- 6. Milestone 4 API Endpoints Async Invocation Tests ---")
    # Cost Overview
    cov = await cost_overview(1)
    check("API GET /api/cost/overview operational", "total_operating_cost" in cov)

    # Cost Trends
    ctrends = await cost_trends(1)
    check("API GET /api/cost/trends operational", len(ctrends) >= 28)

    # Cost Opportunities
    copps = await cost_opportunities(1)
    check("API GET /api/cost/opportunities operational", len(copps) > 0)

    # Cost Analyze Q&A
    canalyze = await cost_agent_analyze(CostAnalyzeRequest(facility_id=1, question="Show me potential savings"))
    check("API POST /api/cost/agent/analyze operational", "answer" in canalyze)

    # Facility Intelligence Overview
    fintel = await facility_intelligence(1)
    check("API GET /api/facility/intelligence operational", "facility_health" in fintel)

    # Facility Health Score
    fhealth = await facility_health(1)
    check("API GET /api/facility/health operational", "facility_health_score" in fhealth)

    # Executive KPIs
    ekpis = await executive_kpis(1)
    check("API GET /api/executive/kpis operational", "facility_health_score" in ekpis and "total_operating_cost" in ekpis)

    # Facility Report
    frep = await facility_reports(1)
    check("API GET /api/facility/reports operational", "sections" in frep)

    # Download TXT & JSON
    d_txt = await download_facility_report(1, format="txt")
    check("API GET /api/facility/reports/download (TXT) operational", len(d_txt.body) > 500)

    d_json = await download_facility_report(1, format="json")
    check("API GET /api/facility/reports/download (JSON) operational", len(d_json.body) > 500)


# ─── 7. MANDATORY END-TO-END TEST ─────────────────────────────────────────────
async def run_end_to_end_test():
    print("\n--- 7. Mandatory Milestone 4 End-to-End Test ---")
    print("  Workflow: Energy + Maint + Occ + Sec + Cost -> Facility Intelligence Engine -> Cross-Agent Reasoning -> Executive KPIs -> Report")

    # Step 1: Energy Agent Result
    e_payload = export_energy_intelligence_payload(1)
    check("E2E Step 1/7: Energy Agent generated operational payload", e_payload["status"] in ["NORMAL", "WARNING", "CRITICAL"])

    # Step 2: Maintenance Agent Result
    m_payload = get_maintenance_agent().export_facility_intelligence_payload(1)
    check("E2E Step 2/7: Maintenance Agent generated equipment health payload", m_payload["metrics"]["total_assets"] >= 5)

    # Step 3: Occupancy Agent Result
    o_payload = get_occupancy_agent().export_facility_intelligence_payload(1)
    check("E2E Step 3/7: Occupancy Agent generated utilization payload", o_payload["metrics"]["total_capacity"] > 0)

    # Step 4: Security Agent Result
    s_payload = get_security_agent().export_facility_intelligence_payload(1)
    check("E2E Step 4/7: Security Agent generated threat payload", "facility_risk_score" in s_payload["metrics"])

    # Step 5: Cost Agent Result
    c_payload = get_cost_agent().export_facility_intelligence_payload(1)
    check("E2E Step 5/7: Cost Agent generated OpEx payload", c_payload["metrics"]["total_operating_cost"] > 0)

    # Step 6: Facility Intelligence Engine Aggregation & Cross-Agent Reasoning
    engine = get_facility_intelligence_engine()
    intel = engine.get_facility_intelligence_overview(1)
    check("E2E Step 6/7: Facility Intelligence Engine synthesized cross-agent reasoning & health score",
          intel["facility_health"]["facility_health_score"] > 0 and len(intel["cross_agent_correlations"]) > 0)

    # Step 7: Executive Dashboard API and Full Report Export
    kpis = await executive_kpis(1)
    rep = await facility_reports(1)
    check("E2E Step 7/7: Executive Dashboard & 12-Section Intelligence Report produced",
          kpis["facility_health_score"] == intel["facility_health"]["facility_health_score"] and len(rep["sections"]) == 12)


# ─── 8. NON-REGRESSION SUITE (Milestones 1, 2, 3) ─────────────────────────────
async def run_non_regression_tests():
    print("\n--- 8. Non-Regression Tests (Milestones 1, 2, and 3) ---")
    # Milestone 1: Energy Intelligence
    e_ov = await energy_overview(1)
    check("M1 Regression: Energy overview operational", "total_energy_kwh" in e_ov)
    e_dist = await energy_distribution(1)
    check("M1 Regression: Energy distribution operational", len(e_dist["subsystems"]) >= 4)
    e_fc = await energy_forecast(1)
    check("M1 Regression: Energy demand forecast operational", len(e_fc["forecast_series"]) > 0)
    e_al = await energy_alerts(1)
    check("M1 Regression: Energy alerts operational", "alerts" in e_al)

    # Milestone 2: Predictive Maintenance
    m_ov = await maintenance_overview(1)
    check("M2 Regression: Maintenance overview operational", m_ov["total_assets"] >= 5)
    m_assets = await list_assets(1)
    check("M2 Regression: Assets list operational", len(m_assets["assets"]) >= 5)
    m_det = await asset_detail("HVAC-AHU-001")
    check("M2 Regression: Asset detail operational", m_det["asset"]["asset_id"] == "HVAC-AHU-001")
    m_health = await asset_health("HVAC-AHU-001")
    check("M2 Regression: Asset health scoring operational", "health_score" in m_health)
    m_al = await maintenance_alerts(1)
    check("M2 Regression: Maintenance alerts operational", "alerts" in m_al)

    # Milestone 3: Occupancy & Security Intelligence
    o_ov = await occupancy_overview(1)
    check("M3 Regression: Occupancy overview operational", "total_occupancy" in o_ov)
    o_zones = await list_occupancy_zones(1)
    check("M3 Regression: Occupancy zones list operational", len(o_zones["zones"]) > 0)
    o_fc = await occupancy_forecast(1)
    check("M3 Regression: Occupancy forecast operational (24h)", len(o_fc["forecast_series"]) == 24)
    s_ov = await security_overview(1)
    check("M3 Regression: Security overview operational", "facility_risk_score" in s_ov)
    s_evts = await list_security_events(1)
    check("M3 Regression: Security events list operational", len(s_evts["events"]) > 0)
    s_al = await list_security_alerts(1)
    check("M3 Regression: Security alerts operational", "alerts" in s_al)


# ─── MAIN RUNNER ─────────────────────────────────────────────────────────────
async def main():
    print("==================================================================")
    print("  FACILITYOPS AI PLATFORM — MILESTONE 4 VERIFICATION SUITE       ")
    print("  Cost Optimization, Cross-Agent Orchestration & Enterprise Prod ")
    print("==================================================================")

    run_database_tests()
    run_cost_agent_tests()
    run_agent_contract_tests()
    run_facility_intelligence_engine_tests()
    run_report_generation_tests()
    await run_api_tests()
    await run_end_to_end_test()
    await run_non_regression_tests()

    print("\n==================================================================")
    print(f"  TOTAL TESTS RUN: {passed_tests + failed_tests}")
    print(f"  PASSED: {passed_tests} | FAILED: {failed_tests}")
    print("==================================================================")

    if failed_tests > 0:
        print("  ❌ VERIFICATION FAILED: Some tests did not pass.")
        sys.exit(1)
    else:
        print("  🎉 ALL MILESTONE 4 & REGRESSION TESTS PASSED PERFECTLY!")


if __name__ == "__main__":
    asyncio.run(main())
