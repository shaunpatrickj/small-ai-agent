# ── Sensor Thresholds per Asset Type ─────────────────────────────────────────
ASSET_THRESHOLDS = {
    "AHU":         {"temp_max": 32.0, "vib_max": 2.5, "curr_max": 35.0,  "volt_nominal": 415.0},
    "Chiller":     {"temp_max": 50.0, "vib_max": 3.8, "curr_max": 150.0, "volt_nominal": 415.0},
    "Pump":        {"temp_max": 45.0, "vib_max": 2.8, "curr_max": 55.0,  "volt_nominal": 415.0},
    "Transformer": {"temp_max": 65.0, "vib_max": 1.0, "curr_max": 220.0, "volt_nominal": 415.0},
    "Elevator":    {"temp_max": 40.0, "vib_max": 1.5, "curr_max": 48.0,  "volt_nominal": 415.0},
    "Genset":      {"temp_max": 85.0, "vib_max": 5.0, "curr_max": 300.0, "volt_nominal": 415.0},
}
