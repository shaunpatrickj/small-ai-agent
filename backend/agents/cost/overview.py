from datetime import datetime
from typing import Dict
from database import get_connection


def get_cost_overview(facility_id: int = 1) -> Dict:
    """
    Calculate total operational expenditure, category distribution, budget variance,
    and cost-saving opportunity totals for a given facility.
    """
    conn = get_connection()

    # Get facility details
    fac = conn.execute("""
        SELECT facility_name, facility_type, location, area_sqft
        FROM FACILITIES WHERE facility_id=?
    """, (facility_id,)).fetchone()

    if not fac:
        conn.close()
        raise ValueError(f"Facility {facility_id} does not exist.")

    # Get last 30 days cost records
    costs = conn.execute("""
        SELECT category, SUM(amount) as total_amount, SUM(budget_allocated) as total_budget,
               COUNT(*) as record_count
        FROM COST_RECORDS
        WHERE facility_id=?
        GROUP BY category
    """, (facility_id,)).fetchall()

    category_breakdown = {}
    total_opex = 0.0
    total_budget = 0.0

    for r in costs:
        cat = r["category"]
        amt = round(r["total_amount"] or 0.0, 2)
        bgt = round(r["total_budget"] or 0.0, 2)
        variance = round(amt - bgt, 2)
        variance_pct = round((variance / max(bgt, 1.0)) * 100, 1)

        category_breakdown[cat] = {
            "amount": amt,
            "budget": bgt,
            "variance": variance,
            "variance_pct": variance_pct,
            "status": "OVER_BUDGET" if variance > 0 else "UNDER_BUDGET"
        }
        total_opex += amt
        total_budget += bgt

    total_opex = round(total_opex, 2)
    total_budget = round(total_budget, 2)
    net_variance = round(total_opex - total_budget, 2)
    net_variance_pct = round((net_variance / max(total_budget, 1.0)) * 100, 1)

    # Optimization opportunities summary
    opps = conn.execute("""
        SELECT COUNT(*) as total_opps,
               SUM(potential_saving) as total_potential_savings,
               SUM(baseline_cost) as total_baseline,
               SUM(estimated_optimized_cost) as total_optimized
        FROM OPTIMIZATION_OPPORTUNITIES
        WHERE facility_id=?
    """, (facility_id,)).fetchone()

    total_opps = opps["total_opps"] or 0
    potential_savings = round(opps["total_potential_savings"] or 0.0, 2)
    baseline_cost = round(opps["total_baseline"] or 0.0, 2)
    potential_saving_pct = round((potential_savings / max(baseline_cost, 1.0)) * 100, 1) if baseline_cost > 0 else 0.0

    # Efficiency metrics (Cost per sq.ft.)
    area_sqft = fac["area_sqft"] or 1.0
    cost_per_sqft = round(total_opex / max(area_sqft, 1.0), 2)

    # Average occupant headcount over last 30 days
    occ_row = conn.execute("""
        SELECT AVG(occupancy_count) as avg_occ
        FROM OCCUPANCY_RECORDS
        WHERE facility_id=?
    """, (facility_id,)).fetchone()
    avg_occ = round(occ_row["avg_occ"] or 1.0, 1)
    cost_per_occupant = round(total_opex / max(avg_occ, 1.0), 2)

    conn.close()

    return {
        "facility_id": facility_id,
        "facility_name": fac["facility_name"],
        "currency": "INR",
        "period": "Last 30 Days",
        "total_operating_cost": total_opex,
        "total_budget_allocated": total_budget,
        "net_budget_variance": net_variance,
        "net_budget_variance_pct": net_variance_pct,
        "budget_compliance_status": "COMPLIANT" if net_variance <= 0 else "OVER_BUDGET",
        "cost_by_category": category_breakdown,
        "cost_per_sqft": cost_per_sqft,
        "cost_per_occupant": cost_per_occupant,
        "opportunities_summary": {
            "total_opportunities": total_opps,
            "potential_savings": potential_savings,
            "potential_saving_pct": potential_saving_pct,
            "savings_nature": "ESTIMATED_POTENTIAL (Non-Realized)"
        },
        "timestamp": datetime.now().isoformat()
    }
