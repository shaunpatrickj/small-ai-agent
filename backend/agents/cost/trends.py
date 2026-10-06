from typing import List, Dict
from database import get_connection


def get_cost_trends(facility_id: int = 1) -> List[Dict]:
    """
    Retrieve daily time-series operational cost trends partitioned by category.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT date(period_start) as date, category, SUM(amount) as amount, SUM(budget_allocated) as budget
        FROM COST_RECORDS
        WHERE facility_id=?
        GROUP BY date(period_start), category
        ORDER BY date(period_start) ASC
    """, (facility_id,)).fetchall()
    conn.close()

    by_date = {}
    for r in rows:
        d = r["date"]
        if d not in by_date:
            by_date[d] = {
                "date": d,
                "ENERGY": 0.0,
                "MAINTENANCE": 0.0,
                "SECURITY": 0.0,
                "ADMINISTRATIVE": 0.0,
                "TOTAL": 0.0,
                "BUDGET": 0.0
            }
        amt = round(r["amount"] or 0.0, 2)
        bgt = round(r["budget"] or 0.0, 2)
        by_date[d][r["category"]] = amt
        by_date[d]["TOTAL"] = round(by_date[d]["TOTAL"] + amt, 2)
        by_date[d]["BUDGET"] = round(by_date[d]["BUDGET"] + bgt, 2)

    return list(by_date.values())
