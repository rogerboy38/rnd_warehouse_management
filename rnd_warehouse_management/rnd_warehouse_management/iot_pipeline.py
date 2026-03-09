"""Phase 6.2: IoT Sensor Reading Pipeline Hardening
Data validation, health monitoring, buffering support, drift detection,
and compression for production-grade IoT pipeline reliability."""
import frappe
from frappe import _
from frappe.utils import now_datetime, add_to_date, time_diff_in_seconds
import json
import math
from datetime import datetime, timedelta


# ============================================================================
# SENSOR VALIDATION - Range checks, outlier detection
# ============================================================================

SENSOR_RANGES = {
    "Ford Temperature": {"min": -40, "max": 150, "unit": "C"},
    "DHT11": {"min": 0, "max": 50, "unit": "C"},
    "DHT22": {"min": -40, "max": 80, "unit": "C"},
    "DS18B20": {"min": -55, "max": 125, "unit": "C"},
    "BME280": {"min": -40, "max": 85, "unit": "C"},
    "Generic ADC": {"min": 0, "max": 5, "unit": "V"},
    "HW-080": {"min": 0, "max": 1023, "unit": "raw"},
    "PLC_Temperature": {"min": -20, "max": 200, "unit": "C"},
    "PLC_pH": {"min": 0, "max": 14, "unit": "pH"},
    "PLC_Brix": {"min": 0, "max": 85, "unit": "Brix"},
    "PLC_Color": {"min": 0, "max": 1000, "unit": "idx"},
}


@frappe.whitelist()
def validate_sensor_reading(sensor_type, value, field="temperature"):
    """Validate a sensor reading: range check + outlier detection."""
    try:
        value = float(value)
    except (ValueError, TypeError):
        return {"valid": False, "error": f"Invalid value: {value}", "errors": ["non_numeric"]}

    errors = []
    warnings = []

    # Range check
    if sensor_type in SENSOR_RANGES:
        r = SENSOR_RANGES[sensor_type]
        if value < r["min"] or value > r["max"]:
            errors.append(f"Out of range [{r['min']}, {r['max']}] {r['unit']}")
    else:
        warnings.append(f"Unknown sensor type: {sensor_type}, skipping range check")

    # Outlier detection (3-sigma from recent readings)
    if frappe.db.exists("DocType", "IoT Sensor Reading"):
        try:
            stats = get_sensor_stats(sensor_type, minutes=30)
            if stats and stats.get("count", 0) >= 5:
                mean = stats["mean"]
                std = stats["std"]
                if std > 0 and abs(value - mean) > 3 * std:
                    warnings.append(f"Outlier: value {value} is {abs(value - mean) / std:.1f} sigma from mean {mean:.1f}")
        except Exception:
            pass

    return {
        "valid": len(errors) == 0,
        "value": value,
        "sensor_type": sensor_type,
        "errors": errors,
        "warnings": warnings
    }


def get_sensor_stats(sensor_type, minutes=30):
    """Get statistical summary of recent readings for a sensor type."""
    if not frappe.db.exists("DocType", "IoT Sensor Reading"):
        return None

    cutoff = add_to_date(now_datetime(), minutes=-minutes)
    readings = frappe.db.sql("""
        SELECT temperature FROM `tabIoT Sensor Reading`
        WHERE sensor_type = %s AND creation >= %s AND temperature IS NOT NULL
        ORDER BY creation DESC LIMIT 100
    """, (sensor_type, cutoff), as_dict=True)

    if not readings:
        return {"count": 0}

    values = [r.temperature for r in readings if r.temperature is not None]
    if not values:
        return {"count": 0}

    n = len(values)
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n if n > 1 else 0
    std = math.sqrt(variance)

    return {
        "count": n,
        "mean": mean,
        "std": std,
        "min": min(values),
        "max": max(values),
        "latest": values[0]
    }


# ============================================================================
# SENSOR HEALTH MONITORING
# ============================================================================

@frappe.whitelist()
def check_sensor_health(sensor_type=None):
    """Check health status of sensors. Returns uptime, error rate, last reading."""
    if not frappe.db.exists("DocType", "IoT Sensor Reading"):
        return {"error": "IoT Sensor Reading doctype not found"}

    if sensor_type:
        return _check_single_sensor_health(sensor_type)

    # Check all sensor types
    types = frappe.db.sql("""
        SELECT DISTINCT sensor_type FROM `tabIoT Sensor Reading`
        WHERE sensor_type IS NOT NULL
    """, as_dict=True)

    results = {}
    for t in types:
        results[t.sensor_type] = _check_single_sensor_health(t.sensor_type)
    return results


def _check_single_sensor_health(sensor_type):
    """Health check for a single sensor type."""
    now = now_datetime()
    one_hour_ago = add_to_date(now, hours=-1)
    one_day_ago = add_to_date(now, hours=-24)

    # Recent readings count
    hour_count = frappe.db.count("IoT Sensor Reading", filters={
        "sensor_type": sensor_type,
        "creation": [">=", one_hour_ago]
    })

    day_count = frappe.db.count("IoT Sensor Reading", filters={
        "sensor_type": sensor_type,
        "creation": [">=", one_day_ago]
    })

    # Last reading
    last = frappe.db.sql("""
        SELECT creation, temperature FROM `tabIoT Sensor Reading`
        WHERE sensor_type = %s ORDER BY creation DESC LIMIT 1
    """, (sensor_type,), as_dict=True)

    last_reading_time = last[0].creation if last else None
    seconds_since = time_diff_in_seconds(now, last_reading_time) if last_reading_time else None

    # Determine status
    if seconds_since is None:
        status = "no_data"
    elif seconds_since < 120:
        status = "active"
    elif seconds_since < 600:
        status = "warning"
    else:
        status = "offline"

    # Get stats
    stats = get_sensor_stats(sensor_type, minutes=60)

    return {
        "sensor_type": sensor_type,
        "status": status,
        "readings_last_hour": hour_count,
        "readings_last_24h": day_count,
        "last_reading_time": str(last_reading_time) if last_reading_time else None,
        "seconds_since_last": seconds_since,
        "last_value": last[0].temperature if last else None,
        "stats": stats
    }


# ============================================================================
# DRIFT DETECTION
# ============================================================================

@frappe.whitelist()
def detect_sensor_drift(sensor_type, window_hours=24):
    """Detect if a sensor is drifting from its expected baseline."""
    if not frappe.db.exists("DocType", "IoT Sensor Reading"):
        return {"error": "IoT Sensor Reading doctype not found"}

    now = now_datetime()

    # Get first half and second half averages
    mid = add_to_date(now, hours=-(window_hours // 2))
    start = add_to_date(now, hours=-window_hours)

    first_half = frappe.db.sql("""
        SELECT AVG(temperature) as avg_val, COUNT(*) as cnt
        FROM `tabIoT Sensor Reading`
        WHERE sensor_type = %s AND creation >= %s AND creation < %s
        AND temperature IS NOT NULL
    """, (sensor_type, start, mid), as_dict=True)

    second_half = frappe.db.sql("""
        SELECT AVG(temperature) as avg_val, COUNT(*) as cnt
        FROM `tabIoT Sensor Reading`
        WHERE sensor_type = %s AND creation >= %s
        AND temperature IS NOT NULL
    """, (sensor_type, mid), as_dict=True)

    if not first_half[0].cnt or not second_half[0].cnt:
        return {"drift_detected": False, "reason": "insufficient_data"}

    first_avg = first_half[0].avg_val or 0
    second_avg = second_half[0].avg_val or 0
    drift = second_avg - first_avg
    drift_pct = (drift / first_avg * 100) if first_avg != 0 else 0

    threshold = 5.0  # 5% drift threshold
    return {
        "sensor_type": sensor_type,
        "drift_detected": abs(drift_pct) > threshold,
        "drift_value": round(drift, 3),
        "drift_percent": round(drift_pct, 2),
        "first_half_avg": round(first_avg, 3),
        "second_half_avg": round(second_avg, 3),
        "threshold_pct": threshold,
        "window_hours": window_hours
    }


# ============================================================================
# DATA COMPRESSION / AGGREGATION
# ============================================================================

@frappe.whitelist()
def get_aggregated_readings(sensor_type, interval_minutes=60, hours=24):
    """Get aggregated sensor readings (avg, min, max, count per interval)."""
    if not frappe.db.exists("DocType", "IoT Sensor Reading"):
        return []

    start = add_to_date(now_datetime(), hours=-hours)

    readings = frappe.db.sql("""
        SELECT
            DATE_FORMAT(creation, %s) as time_bucket,
            AVG(temperature) as avg_temp,
            MIN(temperature) as min_temp,
            MAX(temperature) as max_temp,
            COUNT(*) as reading_count
        FROM `tabIoT Sensor Reading`
        WHERE sensor_type = %s AND creation >= %s AND temperature IS NOT NULL
        GROUP BY time_bucket
        ORDER BY time_bucket
    """, (f"%Y-%m-%d %H:{':00' if interval_minutes >= 60 else '%i'}",
          sensor_type, start), as_dict=True)

    return readings


# ============================================================================
# BUFFER SYNC STATUS (for RPi offline resilience monitoring)
# ============================================================================

@frappe.whitelist()
def report_buffer_status(rpi_id, buffered_count=0, last_sync=None):
    """RPi reports its buffer status to ERPNext for monitoring."""
    return {
        "received": True,
        "rpi_id": rpi_id,
        "buffered_count": int(buffered_count),
        "last_sync": last_sync or str(now_datetime()),
        "server_time": str(now_datetime())
    }


@frappe.whitelist()
def get_pipeline_dashboard():
    """Get complete IoT pipeline health dashboard data."""
    if not frappe.db.exists("DocType", "IoT Sensor Reading"):
        return {"error": "IoT Sensor Reading doctype not found"}

    health = check_sensor_health()
    total_readings = frappe.db.count("IoT Sensor Reading")

    active = sum(1 for h in health.values() if h.get("status") == "active")
    warning = sum(1 for h in health.values() if h.get("status") == "warning")
    offline = sum(1 for h in health.values() if h.get("status") == "offline")

    return {
        "total_sensors": len(health),
        "active": active,
        "warning": warning,
        "offline": offline,
        "total_readings": total_readings,
        "sensors": health
    }
