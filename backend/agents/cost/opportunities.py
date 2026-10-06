from typing import List, Dict, Optional
from database import get_connection


def get_optimization_opportunities(facility_id: int = 1, status: Optional[str] = None) -> List[Dict]:
    """
    List all quantified optimization opportunities with traceable baseline vs optimized cost.
    """
    conn = get_connection()
    query = """
        SELECT opportunity_id, facility_id, category, title, description,
               baseline_cost, estimated_optimized_cost, potential_saving,
               confidence, payback_period_days, status, source_agent, created_at
        FROM OPTIMIZATION_OPPORTUNITIES
        WHERE facility_id=?
    """
    params = [facility_id]
    if status and isinstance(status, str):
        query += " AND status=?"
        params.append(status.upper())

    query += " ORDER BY potential_saving DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    opps = []
    for r in rows:
        opps.append({
            "opportunity_id": r["opportunity_id"],
            "facility_id": r["facility_id"],
            "category": r["category"],
            "title": r["title"],
            "description": r["description"],
            "baseline_cost": r["baseline_cost"],
            "estimated_optimized_cost": r["estimated_optimized_cost"],
            "potential_saving": r["potential_saving"],
            "saving_pct": round((r["potential_saving"] / max(r["baseline_cost"], 1.0)) * 100, 1),
            "confidence": r["confidence"],
            "payback_period_days": r["payback_period_days"],
            "status": r["status"],
            "source_agent": r["source_agent"],
            "created_at": r["created_at"]
        })
    return opps
