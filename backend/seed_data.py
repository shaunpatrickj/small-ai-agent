"""
seed_data.py — FacilityOps Synthetic Dataset Generator
Generates 30 days of realistic hourly energy telemetry for 4 facilities
and seeds the SQLite database. Injected anomalies provide ground truth
for training the Isolation Forest anomaly detector.
"""

import sqlite3
import random
import math
import json
from pathlib import Path
from datetime import datetime, timedelta
from database import get_connection, init_db

# ── Reproducible seed ────────────────────────────────────────────────────────
random.seed(42)

# ── Facility definitions ─────────────────────────────────────────────────────
FACILITIES = [
    {"name": "Campus A — Block 1", "type": "campus",     "location": "Bangalore, KA", "area_sqft": 45000},
    {"name": "Campus A — Block 2", "type": "campus",     "location": "Bangalore, KA", "area_sqft": 38000},
    {"name": "Campus B — Main Hall","type": "office",    "location": "Hyderabad, TS", "area_sqft": 22000},
    {"name": "Data Center — Floor 3","type":"datacenter","location": "Chennai, TN",   "area_sqft": 8000},
]

# ── Base energy profiles (kWh per hour at full load) ─────────────────────────
PROFILES = {
    "campus":     {"electricity": 220, "hvac": 99,  "lighting": 62, "equipment": 40, "water": 45,  "other": 20},
    "office":     {"electricity": 140, "hvac": 63,  "lighting": 39, "equipment": 25, "water": 28,  "other": 13},
    "datacenter": {"electricity": 380, "hvac": 171, "lighting": 11, "equipment": 152,"water": 20,  "other": 46},
}

DAYS = 30
ANOMALY_RATE = 0.04   # ~4% of records will be anomalies


def work_multiplier(hour: int, is_weekend: bool, facility_type: str) -> float:
    """Return a load multiplier based on time of day and day type."""
    if facility_type == "datacenter":
        # Datacenters run near-constant with mild overnight dip
        return 0.85 + 0.15 * math.sin(math.pi * (hour - 2) / 12) if hour >= 6 else 0.80
    if is_weekend:
        return 0.30 if (8 <= hour <= 17) else 0.15
    # Weekday office/campus pattern
    if 7 <= hour <= 9:   return 0.70 + 0.05 * (hour - 7)   # ramp up
    if 10 <= hour <= 17: return 0.95
    if 18 <= hour <= 20: return 0.65
    return 0.20                                              # off-hours


def temperature_c(day_of_year: int, hour: int) -> float:
    """Simulate outdoor temperature (Bangalore-like climate)."""
    seasonal = 27 + 5 * math.sin(2 * math.pi * (day_of_year - 90) / 365)
    diurnal  = 3 * math.sin(math.pi * (hour - 5) / 12)
    return round(seasonal + diurnal + random.gauss(0, 0.8), 1)


def generate_usage(profile: dict, mult: float, temp: float, inject_anomaly: bool) -> dict:
    """Generate a single hourly reading."""
    def jitter(v, frac=0.08):
        return max(0, v * mult * (1 + random.gauss(0, frac)))

    # Temperature drives extra HVAC load
    hvac_temp_factor = 1 + max(0, (temp - 28) * 0.04)

    usage = {
        "electricity": jitter(profile["electricity"]),
        "hvac":        jitter(profile["hvac"]) * hvac_temp_factor,
        "lighting":    jitter(profile["lighting"]),
        "equipment":   jitter(profile["equipment"]),
        "water":       jitter(profile["water"]),
        "other":       jitter(profile["other"]),
    }

    if inject_anomaly:
        # Pick a random subsystem and spike it
        spike_key = random.choice(["electricity", "hvac", "water"])
        usage[spike_key] *= random.uniform(1.8, 3.2)   # 180%–320% spike
        usage["electricity"] = max(usage["electricity"],
                                   usage["hvac"] + usage["lighting"] + usage["equipment"] + usage["other"])

    return usage


def seed():
    init_db()
    conn = get_connection()
    cur  = conn.cursor()

    # ── Clear existing data (for idempotent re-seeding) ──────────────────────
    cur.execute("DELETE FROM FACILITY_INTELLIGENCE_REPORTS")
    cur.execute("DELETE FROM OPTIMIZATION_OPPORTUNITIES")
    cur.execute("DELETE FROM COST_RECORDS")
    cur.execute("DELETE FROM SECURITY_EVENTS")
    cur.execute("DELETE FROM OCCUPANCY_RECORDS")
    cur.execute("DELETE FROM MAINTENANCE_WORK_ORDERS")
    cur.execute("DELETE FROM MAINTENANCE_ALERTS")
    cur.execute("DELETE FROM MAINTENANCE_PREDICTIONS")
    cur.execute("DELETE FROM EQUIPMENT_HEALTH")
    cur.execute("DELETE FROM ASSET_MONITORING_DATA")
    cur.execute("DELETE FROM ASSETS")
    cur.execute("DELETE FROM ALERTS")
    cur.execute("DELETE FROM ENERGY_USAGE")
    cur.execute("DELETE FROM FACILITIES")
    cur.execute("DELETE FROM sqlite_sequence")   # reset auto-increment
    conn.commit()

    # ── Insert facilities ─────────────────────────────────────────────────────
    facility_ids = []
    for f in FACILITIES:
        cur.execute("""
            INSERT INTO FACILITIES (facility_name, facility_type, location, area_sqft)
            VALUES (?, ?, ?, ?)
        """, (f["name"], f["type"], f["location"], f["area_sqft"]))
        facility_ids.append(cur.lastrowid)
    conn.commit()
    print(f"✅ Inserted {len(facility_ids)} facilities")

    # ── Insert Assets ─────────────────────────────────────────────────────────
    assets_def = [
        # Facility 1
        ("HVAC-AHU-001", facility_ids[0], "Primary Air Handling Unit 1", "AHU", "Floor 1-3", "OPERATIONAL", "2023-01-15", "2026-08-01", 14200),
        ("CHILLER-001",  facility_ids[0], "Main Centrifugal Chiller", "Chiller", "Basement Plant", "WARNING", "2022-05-10", "2026-07-15", 18500),
        ("PUMP-001",     facility_ids[0], "Chilled Water Pump 1", "Pump", "Basement Plant", "OPERATIONAL", "2023-03-20", "2026-08-10", 12100),
        ("XFRM-001",     facility_ids[0], "Main Incomer Transformer", "Transformer", "Substation A", "OPERATIONAL", "2021-11-01", "2026-06-01", 24000),
        ("ELEV-001",     facility_ids[0], "Passenger Elevator Bank A", "Elevator", "Main Lobby", "OPERATIONAL", "2022-09-12", "2026-08-05", 9800),

        # Facility 2
        ("HVAC-AHU-002", facility_ids[1], "Secondary AHU Unit 2", "AHU", "Block 2 Wing A", "OPERATIONAL", "2023-02-18", "2026-07-28", 11500),
        ("PUMP-002",     facility_ids[1], "Secondary Water Circulation Pump", "Pump", "Plant Room B", "CRITICAL", "2022-03-14", "2026-05-10", 16800),
        ("GENSET-001",   facility_ids[1], "500kVA Diesel Generator", "Genset", "Power Yard", "OPERATIONAL", "2021-08-05", "2026-08-15", 4200),

        # Facility 3
        ("HVAC-AHU-003", facility_ids[2], "Auditorium AHU Unit 3", "AHU", "Main Hall", "WARNING", "2023-04-01", "2026-06-20", 8900),
        ("PUMP-003",     facility_ids[2], "Condenser Water Pump 3", "Pump", "Mechanical Room", "OPERATIONAL", "2022-10-10", "2026-08-12", 10200),

        # Facility 4
        ("CRAC-001",     facility_ids[3], "Precision Air Conditioner 1", "AHU", "Server Room A", "OPERATIONAL", "2023-06-01", "2026-08-18", 15600),
        ("CRAC-002",     facility_ids[3], "Precision Air Conditioner 2", "AHU", "Server Room B", "WARNING", "2023-06-01", "2026-07-02", 15800),
        ("UPS-001",      facility_ids[3], "250kVA Modular UPS System", "Transformer", "Battery Room", "OPERATIONAL", "2022-01-20", "2026-08-01", 21500),
    ]

    cur.executemany("""
        INSERT INTO ASSETS (asset_id, facility_id, asset_name, asset_type, location_zone, status, installation_date, last_maintenance_date, operating_hours)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, assets_def)
    conn.commit()
    print(f"✅ Inserted {len(assets_def)} assets")

    # ── Generate hourly energy data & asset monitoring data ───────────────────
    start_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=DAYS)
    rows_inserted = 0
    anomaly_count = 0

    batch_energy = []
    batch_telemetry = []

    # Nominal sensor baselines per asset type
    SENSOR_BASELINES = {
        "AHU":         {"temp": 24.0, "vib": 1.2, "current": 25.0, "voltage": 415.0},
        "Chiller":     {"temp": 42.0, "vib": 2.5, "current": 120.0,"voltage": 415.0},
        "Pump":        {"temp": 38.0, "vib": 1.8, "current": 45.0, "voltage": 415.0},
        "Transformer": {"temp": 55.0, "vib": 0.4, "current": 180.0,"voltage": 415.0},
        "Elevator":    {"temp": 30.0, "vib": 0.8, "current": 35.0, "voltage": 415.0},
        "Genset":      {"temp": 75.0, "vib": 3.2, "current": 0.0,  "voltage": 415.0},
    }

    for fac_idx, fac_id in enumerate(facility_ids):
        fac_type = FACILITIES[fac_idx]["type"]
        profile  = PROFILES[fac_type]

        for day_offset in range(DAYS + 1):          # include today
            current_date = start_dt + timedelta(days=day_offset)
            is_weekend   = current_date.weekday() >= 5
            day_of_year  = current_date.timetuple().tm_yday

            for hour in range(24):
                ts   = (current_date + timedelta(hours=hour)).strftime("%Y-%m-%dT%H:%M:%S")
                mult = work_multiplier(hour, is_weekend, fac_type)
                temp = temperature_c(day_of_year, hour)

                inject_anomaly = random.random() < ANOMALY_RATE
                usage = generate_usage(profile, mult, temp, inject_anomaly)
                occupancy = min(100, max(0, mult * 100 + random.gauss(0, 5)))

                batch_energy.append((
                    fac_id,
                    ts,
                    round(usage["electricity"], 2),
                    round(usage["water"],       2),
                    round(usage["hvac"],        2),
                    round(usage["lighting"],    2),
                    round(usage["equipment"],   2),
                    round(usage["other"],       2),
                    temp,
                    round(occupancy, 1),
                    int(inject_anomaly),
                    0.0,
                ))

                if inject_anomaly:
                    anomaly_count += 1

    cur.executemany("""
        INSERT INTO ENERGY_USAGE
        (facility_id, timestamp, electricity_usage, water_usage, hvac_usage,
         lighting_usage, equipment_usage, other_usage,
         outdoor_temp_c, occupancy_pct, is_anomaly, anomaly_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, batch_energy)
    rows_inserted = len(batch_energy)
    conn.commit()

    # Generate telemetry for each asset over last 7 days
    telemetry_start = datetime.now() - timedelta(days=7)
    for asset in assets_def:
        a_id, a_fac_id, a_name, a_type, a_zone, a_status, inst_date, last_maint, base_oph = asset
        base = SENSOR_BASELINES.get(a_type, SENSOR_BASELINES["AHU"])

        # Determine degradation level
        degrad = 0.0
        if a_status == "WARNING":  degrad = 0.35
        elif a_status == "CRITICAL": degrad = 0.75

        curr_oph = base_oph
        for hr_i in range(168): # 7 days * 24 hours
            ts_dt = telemetry_start + timedelta(hours=hr_i)
            ts_str = ts_dt.strftime("%Y-%m-%dT%H:%M:%S")

            # Simulate operational noise + degradation trend
            run_hr = 1.0 if (6 <= ts_dt.hour <= 22 or a_type in ["CRAC", "Transformer", "Chiller"]) else (0.2 if random.random() < 0.3 else 0.0)
            curr_oph += run_hr

            # Abnormal spike injection for warning/critical assets
            is_abn = 1 if (degrad > 0 and random.random() < (0.15 if degrad > 0.5 else 0.05)) else 0

            temp_val = base["temp"] + (degrad * 14) + (8.0 if is_abn else 0) + random.gauss(0, 1.0)
            vib_val  = base["vib"]  + (degrad * 3.5) + (2.5 if is_abn else 0) + random.gauss(0, 0.15)
            curr_val = (base["current"] * (1 + degrad * 0.25 + (0.3 if is_abn else 0))) * run_hr + random.gauss(0, 0.5)
            volt_val = base["voltage"] + random.gauss(0, 2.5) - (degrad * 6.0)

            risk_val = min(1.0, max(0.05, (degrad * 0.7) + (0.25 if is_abn else 0.0) + (curr_oph / 30000.0)))

            batch_telemetry.append((
                a_id,
                ts_str,
                round(temp_val, 1),
                round(max(0.1, vib_val), 2),
                round(max(0.0, curr_val), 1),
                round(volt_val, 1),
                round(curr_oph, 1),
                round(run_hr, 1),
                is_abn,
                round(risk_val, 2)
            ))

    cur.executemany("""
        INSERT INTO ASSET_MONITORING_DATA
        (asset_id, timestamp, temperature_c, vibration_mm_s, current_amps, voltage_v, operating_hours, runtime_hours, is_abnormal, failure_risk)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, batch_telemetry)
    conn.commit()

    print(f"✅ Inserted {len(batch_telemetry):,} asset sensor telemetry records")

    # ── Seed Energy Alerts ───────────────────────────────────────────────────
    alerts = [
        (facility_ids[0], "hvac_inefficiency", "warning",
         "HVAC running at 142% baseline between 14:00–16:00. Likely setpoint misconfiguration.",
         "hvac_usage", 141, 100),
        (facility_ids[0], "peak_demand", "critical",
         "Forecasted demand spike of 38 kW above contracted capacity at 17:30–18:30.",
         "electricity_usage", 338, 300),
        (facility_ids[2], "anomaly", "warning",
         "Water consumption 23% above expected floor-area baseline. Check for leaks.",
         "water_usage", 55, 45),
    ]
    cur.executemany("""
        INSERT INTO ALERTS (facility_id, alert_type, severity, message, metric, value, threshold)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, alerts)
    conn.commit()

    # ── Seed Maintenance Alerts ─────────────────────────────────────────────
    maint_alerts = [
        ("CHILLER-001", facility_ids[0], "warning", "vibration",
         "Elevated vibration (4.8 mm/s) and oil temperature in Compressor Bearing B",
         "Vibration 4.8 mm/s exceeding warning threshold 3.5 mm/s",
         "Inspect bearing lubrication and align shaft coupling", "NEW"),
        ("PUMP-002", facility_ids[1], "critical", "thermal",
         "Critical motor overheating (68.4°C) with elevated current draw on Secondary Pump",
         "Motor winding temp 68.4°C exceeding critical limit 60.0°C",
         "Immediate shutdown required. Inspect impeller for blockages and check motor winding", "NEW"),
        ("HVAC-AHU-003", facility_ids[2], "warning", "electrical", "Abnormal current imbalance (22%) detected across 3-phase blower motor",
         "Current imbalance 22% > 10% threshold",
         "Inspect electrical contractor contacts and verify phase supply voltage", "NEW"),
        ("CRAC-002", facility_ids[3], "warning", "thermal",
         "Refrigerant discharge pressure high (54.2°C condensing temp) in Server Room B",
         "Condensing temp 54.2°C > 48.0°C threshold",
         "Clean outdoor condenser coils and check refrigerant charge level", "NEW"),
    ]

    cur.executemany("""
        INSERT INTO MAINTENANCE_ALERTS
        (asset_id, facility_id, severity, alert_type, description, detected_condition, recommended_action, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, maint_alerts)
    conn.commit()
    print(f"✅ Inserted {len(maint_alerts)} maintenance alerts")

    # ── Seed Maintenance Work Orders ────────────────────────────────────────
    work_orders = [
        ("WO-2026-001", "PUMP-002", facility_ids[1],
         "Critical Motor Overheating & Impeller Jamming", "URGENT",
         "Replace motor bearings, clear impeller debris, and verify thermal overload relay.", "OPEN"),
        ("WO-2026-002", "CHILLER-001", facility_ids[0],
         "Compressor Shaft Vibration & Alignment Inspection", "HIGH",
         "Perform laser alignment of compressor shaft and check oil filter differential pressure.", "IN_PROGRESS"),
    ]

    cur.executemany("""
        INSERT INTO MAINTENANCE_WORK_ORDERS
        (work_order_id, asset_id, facility_id, issue, priority, recommended_action, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, work_orders)
    conn.commit()
    print(f"✅ Inserted {len(work_orders)} maintenance work orders")

    # ═════════════════════════════════════════════════════════════════════════
    # MILESTONE 3 — OCCUPANCY & SECURITY SEEDING
    # ═════════════════════════════════════════════════════════════════════════

    # Define facility zones and capacities
    ZONES_BY_FACILITY = {
        facility_ids[0]: [
            ("Floor 1 Offices", 120, "office"),
            ("Floor 2 Offices", 100, "office"),
            ("Meeting Rooms Wing", 40, "meeting"),
            ("Central Cafeteria", 150, "amenity"),
            ("Executive Boardroom", 25, "executive"),
            ("Visitor Lobby", 50, "lobby"),
        ],
        facility_ids[1]: [
            ("Engineering Bay", 90, "office"),
            ("Research Lab", 35, "lab"),
            ("Training Center", 80, "training"),
            ("Auditorium", 200, "auditorium"),
            ("Parking Deck B", 100, "parking"),
        ],
        facility_ids[2]: [
            ("Open Workspace", 110, "office"),
            ("Conference Suites", 45, "meeting"),
            ("Collaboration Hub", 60, "amenity"),
            ("Dining Hall", 80, "amenity"),
        ],
        facility_ids[3]: [
            ("Server Hall 1", 15, "datacenter"),
            ("Server Hall 2", 15, "datacenter"),
            ("NOC Operations Room", 20, "office"),
            ("Secure Staging Area", 10, "secure"),
        ]
    }

    batch_occupancy = []
    # Generate 30 days of hourly occupancy records
    for fac_id, zones in ZONES_BY_FACILITY.items():
        for zone_name, cap, ztype in zones:
            for day_offset in range(DAYS + 1):
                cur_date = start_dt + timedelta(days=day_offset)
                is_wknd = cur_date.weekday() >= 5
                
                for hr in range(24):
                    ts_str = (cur_date + timedelta(hours=hr)).strftime("%Y-%m-%dT%H:%M:%S")
                    
                    # Compute baseline occupancy factor based on zone type and hour
                    if ztype == "datacenter":
                        occ_factor = random.uniform(0.05, 0.20)
                    elif ztype == "lobby":
                        occ_factor = 0.50 if (8 <= hr <= 10 or 17 <= hr <= 19) and not is_wknd else (0.15 if 10 < hr < 17 and not is_wknd else 0.02)
                    elif ztype == "amenity":
                        occ_factor = 0.85 if (12 <= hr <= 14) and not is_wknd else (0.35 if (8 <= hr <= 11 or 15 <= hr <= 17) and not is_wknd else 0.05)
                    elif ztype == "executive":
                        occ_factor = random.choice([0.0, 0.0, 0.15, 0.40, 0.80]) if (10 <= hr <= 16 and not is_wknd) else 0.0
                    else: # office, lab, training
                        if is_wknd:
                            occ_factor = random.uniform(0.02, 0.12)
                        elif 9 <= hr <= 12 or 14 <= hr <= 17:
                            occ_factor = random.uniform(0.65, 0.88)
                        elif hr in [8, 13, 18]:
                            occ_factor = random.uniform(0.40, 0.60)
                        elif 19 <= hr <= 21:
                            occ_factor = random.uniform(0.10, 0.25)
                        else:
                            occ_factor = random.uniform(0.01, 0.05)

                    # Injected overcrowding scenarios (e.g. Friday all-hands or peak surges)
                    if not is_wknd and hr in [11, 14, 15] and random.random() < 0.035:
                        occ_factor = random.uniform(0.95, 1.15) # Overcrowding!

                    # Injected underutilization scenario (very quiet periods)
                    if not is_wknd and 10 <= hr <= 16 and random.random() < 0.02:
                        occ_factor = random.uniform(0.05, 0.15)

                    raw_count = int(round(cap * occ_factor + random.gauss(0, max(1, cap * 0.02))))
                    count = max(0, raw_count)
                    rate = round(count / max(1, cap), 3)

                    if rate > 0.90:
                        status = "OVERCROWDED"
                    elif rate > 0.75:
                        status = "HIGH"
                    elif rate >= 0.25:
                        status = "OPTIMAL"
                    else:
                        status = "UNDERUTILIZED"

                    batch_occupancy.append((
                        fac_id,
                        zone_name,
                        count,
                        cap,
                        rate,
                        status,
                        ts_str
                    ))

    cur.executemany("""
        INSERT INTO OCCUPANCY_RECORDS
        (facility_id, zone, occupancy_count, capacity, occupancy_rate, occupancy_status, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, batch_occupancy)
    conn.commit()
    print(f"✅ Inserted {len(batch_occupancy):,} zone occupancy records (30-day hourly history)")

    # ── Seed Security Events ────────────────────────────────────────────────
    security_events_def = [
        ("SEC-EVT-001", facility_ids[0], "Floor 1 Offices", "UNAUTHORIZED_ACCESS", "HIGH", "HIGH",
         "Access Control Reader #F1-E", "NEW",
         "Unregistered RFID card badge-scan attempt at East Wing executive turnstile",
         json.dumps({"card_id": "RFID-99482", "badge_holder": "Unknown", "door_id": "TURNSTILE-F1-E", "attempts": 3}),
         (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")),

        ("SEC-EVT-002", facility_ids[0], "Central Cafeteria", "TAILGATING", "WARNING", "MEDIUM",
         "AI Optical Sensor #CCTV-04", "ACKNOWLEDGED",
         "Optical camera detected 2 individuals entering through Cafeteria access gate on single badge swipe",
         json.dumps({"camera_id": "CCTV-CAF-04", "confidence": 0.94, "person_count": 2, "badge_id": "EMP-3841"}),
         (datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%S")),

        ("SEC-EVT-003", facility_ids[3], "Server Hall 1", "DOOR_FORCED", "CRITICAL", "CRITICAL",
         "Door Contact Sensor #DC-SH1", "NEW",
         "Critical door held open alarm breached beyond 45s threshold at Server Room A security portal",
         json.dumps({"door_id": "DOOR-SRV-01", "sensor_type": "magnetic_reed", "duration_sec": 78, "tamper_flag": True}),
         (datetime.now() - timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M:%S")),

        ("SEC-EVT-004", facility_ids[1], "Research Lab", "AFTER_HOURS_ENTRY", "HIGH", "HIGH",
         "Access Control Reader #RL-01", "RESOLVED",
         "After-hours credential entry recorded at 02:41 AM without prior scheduled authorization permit",
         json.dumps({"card_id": "EMP-9102", "badge_holder": "Contractor BioTech", "zone": "Research Lab", "authorized": False}),
         (datetime.now() - timedelta(days=1, hours=6)).strftime("%Y-%m-%dT%H:%M:%S")),

        ("SEC-EVT-005", facility_ids[0], "Visitor Lobby", "BADGE_MISUSE", "WARNING", "MEDIUM",
         "Identity Verification Hub", "RESOLVED",
         "Simultaneous multi-zone badge presentation detected for badge EMP-1092 within 30 seconds",
         json.dumps({"card_id": "EMP-1092", "locations": ["Visitor Lobby", "Floor 2 Offices"], "delta_seconds": 24}),
         (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")),

        ("SEC-EVT-006", facility_ids[3], "Secure Staging Area", "CCTV_ANOMALY", "CRITICAL", "HIGH",
         "AI Vision Analytics #CAM-NOC-02", "NEW",
         "Unidentified person loitering in restricted datacenter server staging perimeter without escort",
         json.dumps({"camera_id": "CAM-NOC-02", "dwell_time_minutes": 7.5, "hi_vis_detected": False}),
         (datetime.now() - timedelta(hours=14)).strftime("%Y-%m-%dT%H:%M:%S")),

        ("SEC-EVT-007", facility_ids[2], "Conference Suites", "UNAUTHORIZED_ACCESS", "HIGH", "HIGH",
         "Smart Lock #SL-CONF-03", "NEW",
         "Repeated PIN brute-force failure lock-out on Conference Room 3 digital lockbox",
         json.dumps({"lock_id": "SL-CONF-03", "failed_attempts": 5, "lockout_duration_min": 15}),
         (datetime.now() - timedelta(hours=18)).strftime("%Y-%m-%dT%H:%M:%S")),

        ("SEC-EVT-008", facility_ids[0], "Executive Boardroom", "AFTER_HOURS_ENTRY", "WARNING", "MEDIUM",
         "Access Control Reader #BR-01", "RESOLVED",
         "Weekend maintenance cleaning crew access registered; verified with facility operations manifest",
         json.dumps({"card_id": "SVC-4412", "crew_lead": "P. Sharma", "cleared_by": "Security Desk"}),
         (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S")),
    ]

    cur.executemany("""
        INSERT INTO SECURITY_EVENTS
        (event_id, facility_id, zone, event_type, severity, risk_level, source, status, description, details, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, security_events_def)
    conn.commit()
    print(f"✅ Inserted {len(security_events_def)} security incident events")

    # ── Also add security alerts to ALERTS table for cross-agent visibility ───
    sec_alerts = [
        (facility_ids[0], "unauthorized_access", "critical",
         "Unregistered RFID card badge-scan attempt at East Wing executive turnstile (Floor 1 Offices)",
         "access_control", 1, 0),
        (facility_ids[3], "door_forced", "critical",
         "Critical door held open alarm breached beyond 45s threshold at Server Hall 1",
         "door_sensor", 78, 45),
        (facility_ids[0], "tailgating", "warning",
         "Optical camera detected 2 individuals entering through Cafeteria access gate on single badge swipe",
         "optical_sensor", 2, 1),
        (facility_ids[3], "cctv_anomaly", "critical",
         "Unidentified person loitering in restricted datacenter server staging perimeter without escort",
         "ai_vision", 7.5, 3.0),
    ]
    cur.executemany("""
        INSERT INTO ALERTS (facility_id, alert_type, severity, message, metric, value, threshold)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, sec_alerts)
    conn.commit()
    print(f"✅ Inserted {len(sec_alerts)} security alerts into central ALERTS table")

    # ── Seed 30-Day Cost Records (Milestone 4) ─────────────────────────────────
    # Generates traceable daily financial records based on operational data:
    # 1. Energy Cost = actual daily electricity usage * ₹9.00/kWh tariff
    # 2. Maintenance Cost = scheduled PM contracts, spare parts, technician hours
    # 3. Security Cost = manned guarding hours, camera system upkeep, monitoring
    # 4. Administrative Cost = facility software licensing, cleaning & waste ops
    batch_costs = []
    
    # Baseline daily allocations per facility type
    BASE_BUDGETS = {
        1: {"ENERGY": 48000.0, "MAINTENANCE": 18000.0, "SECURITY": 12000.0, "ADMINISTRATIVE": 9000.0},
        2: {"ENERGY": 40000.0, "MAINTENANCE": 15000.0, "SECURITY": 11000.0, "ADMINISTRATIVE": 8000.0},
        3: {"ENERGY": 25000.0, "MAINTENANCE": 10000.0, "SECURITY": 8000.0,  "ADMINISTRATIVE": 6000.0},
        4: {"ENERGY": 85000.0, "MAINTENANCE": 22000.0, "SECURITY": 16000.0, "ADMINISTRATIVE": 12000.0},
    }

    for fac_id in facility_ids:
        # Query actual daily energy usage for this facility
        cur.execute("""
            SELECT date(timestamp) as day_date, SUM(electricity_usage) as total_kwh
            FROM ENERGY_USAGE
            WHERE facility_id=?
            GROUP BY date(timestamp)
            ORDER BY day_date
        """, (fac_id,))
        energy_days = cur.fetchall()

        budgets = BASE_BUDGETS.get(fac_id, BASE_BUDGETS[1])

        for row in energy_days:
            day_str = row["day_date"]
            day_kwh = row["total_kwh"] or 1000.0
            p_start = f"{day_str}T00:00:00"
            p_end = f"{day_str}T23:59:59"

            # 1. Energy Cost (Tariff ₹9.00/kWh + demand tariff factor)
            energy_amt = round(day_kwh * 9.0, 2)
            batch_costs.append((
                fac_id, "ENERGY", energy_amt, budgets["ENERGY"], "INR",
                p_start, p_end, f"Grid electricity consumption ({day_kwh:.1f} kWh @ ₹9.00/kWh)"
            ))

            # 2. Maintenance Cost (Routine PM + occasional breakdown parts)
            # Weekend vs weekday slight variation
            dt_obj = datetime.strptime(day_str, "%Y-%m-%d")
            maint_base = budgets["MAINTENANCE"] * random.uniform(0.85, 1.10)
            if dt_obj.weekday() == 2: # Mid-week maintenance run
                maint_base *= 1.35
            maint_amt = round(maint_base, 2)
            batch_costs.append((
                fac_id, "MAINTENANCE", maint_amt, budgets["MAINTENANCE"], "INR",
                p_start, p_end, "HVAC & electrical predictive PM, technician hours & consumables"
            ))

            # 3. Security Cost
            sec_base = budgets["SECURITY"] * random.uniform(0.95, 1.05)
            sec_amt = round(sec_base, 2)
            batch_costs.append((
                fac_id, "SECURITY", sec_amt, budgets["SECURITY"], "INR",
                p_start, p_end, "Access control monitoring, physical patrol & CCTV infrastructure"
            ))

            # 4. Administrative Cost
            admin_base = budgets["ADMINISTRATIVE"] * random.uniform(0.92, 1.08)
            admin_amt = round(admin_base, 2)
            batch_costs.append((
                fac_id, "ADMINISTRATIVE", admin_amt, budgets["ADMINISTRATIVE"], "INR",
                p_start, p_end, "Facility operations administration, janitorial & BMS licensing"
            ))

    cur.executemany("""
        INSERT INTO COST_RECORDS
        (facility_id, category, amount, budget_allocated, currency, period_start, period_end, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, batch_costs)
    conn.commit()
    print(f"✅ Inserted {len(batch_costs):,} cost records (30-day OpEx across 4 categories)")

    # ── Seed Traceable Optimization Opportunities (Milestone 4) ───────────────
    # Valid opportunities derived directly from system baseline data
    opps_def = [
        # Facility 1: Campus A Block 1
        ("OPT-F1-001", facility_ids[0], "ENERGY",
         "HVAC Off-Hours Reset in Low Occupancy Zones",
         "Adjust AHU-1 temperature setpoint by +2.0°C and reduce fan speeds between 20:00 and 06:00 where occupancy drops below 5%.",
         185000.0, 142000.0, 43000.0, 0.92, 14, "APPROVED", "cross_agent"),
        
        ("OPT-F1-002", facility_ids[0], "MAINTENANCE",
         "Centrifugal Chiller Condenser Tube Descaling",
         "Thermal degradation on CHILLER-001 indicates heat transfer fouling. Chemical descaling restores design COP from 3.8 to 5.2.",
         120000.0, 85000.0, 35000.0, 0.88, 30, "IDENTIFIED", "maintenance"),

        ("OPT-F1-003", facility_ids[0], "SPACE_OPERATIONS",
         "Consolidation of Underutilized Wing Workspaces",
         "Floor 3 East Wing operates under 18% occupancy on Mondays and Fridays. Consolidating occupants to Central Wing allows HVAC shutdown.",
         95000.0, 68000.0, 27000.0, 0.85, 21, "IN_REVIEW", "occupancy"),

        ("OPT-F1-004", facility_ids[0], "SECURITY",
         "Automated Optical Badge Access Transition",
         "Replace manual guard checkpoints at secondary turnstiles with AI tailgating detection optical turnstiles.",
         82000.0, 64000.0, 18000.0, 0.89, 45, "IDENTIFIED", "security"),

        # Facility 2: Campus A Block 2
        ("OPT-F2-001", facility_ids[1], "MAINTENANCE",
         "Pump-002 Impeller Alignment & Vibration Damper Refurbishment",
         "Critical vibration of 4.8 mm/s on secondary pump causes excessive current draw and risk of catastrophic seal rupture.",
         110000.0, 72000.0, 38000.0, 0.94, 20, "APPROVED", "maintenance"),

        ("OPT-F2-002", facility_ids[1], "ENERGY",
         "Peak Shaving with Diesel Genset Synchronization during Tariff Spikes",
         "Utilize synchronized genset during peak commercial tariff windows (18:00–21:00) to avoid max demand penalties.",
         140000.0, 112000.0, 28000.0, 0.82, 35, "IDENTIFIED", "energy"),

        # Facility 3: Campus B Main Hall
        ("OPT-F3-001", facility_ids[2], "ENERGY",
         "Auditorium Demand-Controlled Ventilation (DCV) via CO2 Sensors",
         "AHU-003 currently runs on static 100% airflow even when auditorium is empty. Dynamic airflow control reduces energy load by 32%.",
         85000.0, 58000.0, 27000.0, 0.90, 25, "APPROVED", "cross_agent"),

        # Facility 4: Data Center Floor 3
        ("OPT-F4-001", facility_ids[3], "ENERGY",
         "Server Room Cold Aisle Containment & CRAC Setpoint Optimization",
         "CRAC-002 thermal gradient shows hot air recirculation. Implementing containment curtains allows raising server supply temp from 19°C to 23°C.",
         260000.0, 195000.0, 65000.0, 0.95, 18, "APPROVED", "energy"),

        ("OPT-F4-002", facility_ids[3], "SECURITY",
         "Biometric Multi-Factor Gateway for Staging Area",
         "Reduces security supervisor manual escort hours and prevents unauthorized door held alerts.",
         90000.0, 74000.0, 16000.0, 0.86, 60, "IDENTIFIED", "security"),
    ]

    cur.executemany("""
        INSERT INTO OPTIMIZATION_OPPORTUNITIES
        (opportunity_id, facility_id, category, title, description, baseline_cost, estimated_optimized_cost,
         potential_saving, confidence, payback_period_days, status, source_agent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, opps_def)
    conn.commit()
    print(f"✅ Inserted {len(opps_def)} traceable optimization opportunities")

    conn.close()
    print("\n🎉 Database seeding complete!")

    # ── Generate Baseline Health Scores & Predictions for All Assets ────────
    try:
        from maintenance_agent import get_maintenance_agent
        agent = get_maintenance_agent()
        for a in assets_def:
            agent.evaluate_asset_health(a[0])
            agent.predict_maintenance(a[0])
        print("✅ Computed baseline health evaluations & predictions for all 13 assets")
    except Exception as e:
        print(f"⚠️ Could not compute initial health scores: {e}")

    # ── Export All Tables to CSV in dataset/ ─────────────────────────────────
    export_datasets_to_csv()


def export_datasets_to_csv():
    """Exports all database tables to standalone CSV files in dataset/ for review and ML training."""
    import pandas as pd
    out_dir = Path(__file__).resolve().parent.parent / "dataset"
    out_dir.mkdir(parents=True, exist_ok=True)
    conn = get_connection()

    tables = [
        ("FACILITIES", "facilityops_facilities.csv"),
        ("ENERGY_USAGE", "facilityops_energy_usage.csv"),
        ("ALERTS", "facilityops_alerts.csv"),
        ("ASSETS", "facilityops_assets.csv"),
        ("ASSET_MONITORING_DATA", "facilityops_asset_monitoring_data.csv"),
        ("MAINTENANCE_ALERTS", "facilityops_maintenance_alerts.csv"),
        ("MAINTENANCE_WORK_ORDERS", "facilityops_maintenance_work_orders.csv"),
        ("EQUIPMENT_HEALTH", "facilityops_equipment_health.csv"),
        ("MAINTENANCE_PREDICTIONS", "facilityops_maintenance_predictions.csv"),
        ("OCCUPANCY_RECORDS", "facilityops_occupancy_records.csv"),
        ("SECURITY_EVENTS", "facilityops_security_events.csv"),
        ("COST_RECORDS", "facilityops_cost_records.csv"),
        ("OPTIMIZATION_OPPORTUNITIES", "facilityops_optimization_opportunities.csv"),
    ]

    print("\n📂 Exporting datasets to dataset/ directory:")
    for tbl, fname in tables:
        try:
            df = pd.read_sql_query(f"SELECT * FROM {tbl}", conn)
            target = out_dir / fname
            df.to_csv(target, index=False)
            print(f"   📄 {fname:<44} ({len(df):>4} rows, {target.stat().st_size:>8,} bytes)")
        except Exception as e:
            print(f"   ⚠️ Could not export {tbl}: {e}")

    conn.close()
    print("✅ All agent datasets successfully exported to dataset/\n")


if __name__ == "__main__":
    seed()


