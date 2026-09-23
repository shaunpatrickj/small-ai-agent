#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# FacilityOps AI Platform — One-Command Startup
# Milestones 1–3: Energy, Predictive Maintenance, Occupancy & Security
# ─────────────────────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  🏭 Agentic FacilityOps AI Platform"
echo "  Milestones 1–3: Energy · Maintenance · Occupancy · Security"
echo "════════════════════════════════════════════════════════════"
echo ""

# ── Step 1: Python check ─────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "❌ Python 3 not found. Please install Python 3.9+ and try again."
  exit 1
fi
PYTHON=$(command -v python3)
echo "✅ Python: $("$PYTHON" --version)"

# ── Step 2: Virtual environment ──────────────────────────────────────────────
VENV_DIR="$BACKEND_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "📦 Creating virtual environment…"
  "$PYTHON" -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
echo "✅ Virtual environment active"

# ── Step 3: Install dependencies ─────────────────────────────────────────────
echo ""
echo "📦 Installing Python dependencies…"
pip install -q --upgrade pip
pip install -q -r "$BACKEND_DIR/requirements.txt"
echo "✅ Dependencies installed"

# ── Step 4: Database setup & complete data seeding ───────────────────────────
echo ""
echo "── Step 4: Database & Multi-Agent Telemetry Seeding ───────"
cd "$BACKEND_DIR"
"$PYTHON" seed_data.py

# ── Step 5: AI Engine & Agents Initialization ────────────────────────────────
echo ""
echo "── Step 5: Training AI Models & Agent Setup ───────────────"
"$PYTHON" ai_engine.py

echo ""
echo "── Step 6: Verifying Milestone 3 Occupancy Forecaster ──────"
"$PYTHON" -c "
import sys, os
sys.path.insert(0, '.')
from occupancy_agent import get_occupancy_agent
agent = get_occupancy_agent()
res = agent.train_and_evaluate_forecaster(1)
acc = res.get('accuracy_pct', 0)
print(f'   👥 Occupancy Forecasting Accuracy: {acc}% (Target: >=80.0%) | Status: {\"✅ MET\" if acc >= 80.0 else \"❌ UNMET\"}')
"

echo ""
echo "── Step 7: Verifying Security Agent Threat Engine ──────────"
"$PYTHON" -c "
import sys, os
sys.path.insert(0, '.')
from security_agent import get_security_agent
sec = get_security_agent()
ov = sec.get_security_overview(1)
print(f'   🛡️  Security Risk Grade: {ov.get(\"facility_risk_grade\")} ({ov.get(\"facility_risk_score\")}/100) | Active Alerts: {ov.get(\"active_security_alerts\")}')
"

echo ""
echo "── Step 8: Verifying Cost Optimization & Facility Intelligence Engine ─"
"$PYTHON" -c "
import sys, os
sys.path.insert(0, '.')
from cost_agent import get_cost_agent
from facility_intelligence_engine import get_facility_intelligence_engine
cost = get_cost_agent()
cov = cost.get_cost_overview(1)
engine = get_facility_intelligence_engine()
fintel = engine.get_facility_intelligence_overview(1)
hs = fintel['facility_health']['facility_health_score']
hg = fintel['facility_health']['health_grade']
print(f'   💰 30-Day OpEx: ₹{cov[\"total_operating_cost\"]:,.2f} | Potential Savings: ₹{cov[\"opportunities_summary\"][\"potential_savings\"]:,.2f} ({cov[\"opportunities_summary\"][\"potential_saving_pct\"]}%)')
print(f'   🏛️  Facility Health Score: {hs}/100 ({hg}) | Fleet Agents Active: {len(fintel[\"agent_fleet_status\"])}/5')
"

# ── Step 9: Kill anything on port 8000 ──────────────────────────────────────
if lsof -i :8000 &>/dev/null; then
  echo ""
  echo "⚠️  Port 8000 in use — stopping previous process…"
  lsof -ti :8000 | xargs kill -9 2>/dev/null || true
  sleep 1
fi

# ── Step 10: Start FastAPI server ─────────────────────────────────────────────
echo ""
echo "── Starting API Server & Unified Operations Dashboard ─────"
echo ""
echo "  📡 API Base:   http://localhost:8000/api"
echo "  🏛️  Executive:  http://localhost:8000 (Tab 0)"
echo "  ⚡ Energy:     http://localhost:8000 (Tab 1)"
echo "  🔧 Maint:      http://localhost:8000 (Tab 3)"
echo "  👥 Occupancy:  http://localhost:8000 (Tab 4)"
echo "  🛡️  Security:   http://localhost:8000 (Tab 5)"
echo "  📖 API Docs:   http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop"
echo "════════════════════════════════════════════════════════════"
echo ""

# Open browser after 2s
( sleep 2 && open "http://localhost:8000" ) &

# Start server
cd "$BACKEND_DIR"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

