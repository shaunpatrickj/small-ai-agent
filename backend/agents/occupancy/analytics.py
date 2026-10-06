from datetime import datetime
from typing import List, Dict
from database import get_connection


def generate_zone_recommendation(zone: str, count: int, cap: int, rate: float, status: str) -> str:
    pct = round(rate * 100, 1)
    if rate > 0.90:
        return f"Immediate alert: {zone} is at {pct}% capacity ({count}/{cap}). Divert incoming personnel to adjacent underutilized zones."
    elif rate > 0.75:
        return f"Monitor approaching peak capacity at {pct}% ({count}/{cap}). Restrict further bookings."
    elif rate < 0.25:
        return f"Low utilization at {pct}% ({count}/{cap}). Set HVAC to eco-mode and turn off peripheral lighting to conserve power."
    else:
        return f"Space utilization is optimal ({pct}%). Maintain standard ventilation and operations."


def get_latest_zone_occupancy(facility_id: int) -> List[Dict]:
    """Fetch latest occupancy reading and utilization metrics for all zones in a facility."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT o.*
        FROM OCCUPANCY_RECORDS o
        INNER JOIN (
            SELECT zone, MAX(timestamp) as max_ts
            FROM OCCUPANCY_RECORDS
            WHERE facility_id=?
            GROUP BY zone
        ) latest ON o.zone = latest.zone AND o.timestamp = latest.max_ts
        WHERE o.facility_id=?
        ORDER BY o.occupancy_rate DESC
    """, (facility_id, facility_id)).fetchall()
    conn.close()

    results = []
    for r in rows:
        rec = dict(r)
        rate = rec["occupancy_rate"]
        status = rec["occupancy_status"]
        count = rec["occupancy_count"]
        cap = rec["capacity"]

        rec["overcrowding"] = bool(count > cap or rate > 0.90)
        rec["underutilized"] = bool(rate < 0.25)
        rec["recommendation"] = generate_zone_recommendation(rec["zone"], count, cap, rate, status)
        results.append(rec)
    return results


def analyze_facility_occupancy(facility_id: int) -> Dict:
    """Aggregate facility-wide occupancy metrics, trends, and health indicators."""
    zones = get_latest_zone_occupancy(facility_id)
    if not zones:
        return {
            "facility_id": facility_id,
            "total_occupancy": 0,
            "total_capacity": 0,
            "occupancy_rate": 0.0,
            "occupied_zones_count": 0,
            "overcrowded_count": 0,
            "underutilized_count": 0,
            "zones": [],
            "timestamp": datetime.now().isoformat()
        }

    tot_occ = sum(z["occupancy_count"] for z in zones)
    tot_cap = sum(z["capacity"] for z in zones)
    avg_rate = round(tot_occ / max(1, tot_cap), 3)

    overcrowded = [z for z in zones if z["overcrowding"]]
    high_util = [z for z in zones if 0.75 < z["occupancy_rate"] <= 0.90]
    underutilized = [z for z in zones if z["underutilized"]]
    optimal = [z for z in zones if 0.25 <= z["occupancy_rate"] <= 0.75]

    return {
        "facility_id": facility_id,
        "total_occupancy": tot_occ,
        "total_capacity": tot_cap,
        "occupancy_rate": avg_rate,
        "occupancy_pct": round(avg_rate * 100, 1),
        "total_zones": len(zones),
        "occupied_zones_count": sum(1 for z in zones if z["occupancy_count"] > 0),
        "overcrowded_count": len(overcrowded),
        "high_utilization_count": len(high_util),
        "optimal_count": len(optimal),
        "underutilized_count": len(underutilized),
        "zones": zones,
        "timestamp": datetime.now().isoformat()
    }


def get_occupancy_heatmap(facility_id: int) -> Dict:
    """7-day hourly occupancy heatmap matrix and zone comparison."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT timestamp, AVG(occupancy_rate) as avg_rate, SUM(occupancy_count) as total_occ
        FROM OCCUPANCY_RECORDS
        WHERE facility_id=? AND timestamp >= datetime('now', '-7 days')
        GROUP BY timestamp
        ORDER BY timestamp
    """, (facility_id,)).fetchall()

    zone_rows = conn.execute("""
        SELECT zone, strftime('%H', timestamp) as hr, AVG(occupancy_rate) as avg_rate
        FROM OCCUPANCY_RECORDS
        WHERE facility_id=? AND timestamp >= datetime('now', '-7 days')
        GROUP BY zone, hr
        ORDER BY zone, hr
    """, (facility_id,)).fetchall()
    conn.close()

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    day_grid = {d: {h: 0.0 for h in range(24)} for d in day_names}

    for r in rows:
        try:
            dt = datetime.fromisoformat(r["timestamp"])
            day_str = day_names[dt.weekday()]
            day_grid[day_str][dt.hour] = round(float(r["avg_rate"] or 0) * 100, 1)
        except Exception:
            pass

    zone_matrix = {}
    for zr in zone_rows:
        zname = zr["zone"]
        hr = int(zr["hr"])
        zone_matrix.setdefault(zname, {})[hr] = round(float(zr["avg_rate"] or 0) * 100, 1)

    return {
        "facility_id": facility_id,
        "days": day_names,
        "hours": list(range(24)),
        "day_grid": day_grid,
        "zone_matrix": zone_matrix
    }


def get_occupancy_trends(facility_id: int, hours: int = 48) -> List[Dict]:
    """Time-series occupancy history for trend visualization."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT timestamp, SUM(occupancy_count) as total_occupancy, SUM(capacity) as total_capacity,
               AVG(occupancy_rate) as avg_rate
        FROM OCCUPANCY_RECORDS
        WHERE facility_id=? AND timestamp >= datetime('now', ?)
        GROUP BY timestamp
        ORDER BY timestamp ASC
    """, (facility_id, f"-{hours} hours")).fetchall()
    conn.close()

    results = []
    for r in rows:
        rec = dict(r)
        rec["occupancy_pct"] = round(float(rec["avg_rate"] or 0) * 100, 1)
        results.append(rec)
    return results
