"""Phase 6.4: Real-Time Manufacturing Quality Bridge
Connects IoT sensor data to manufacturing pipeline for real-time quality decisions.
Links Work Orders to zone sensors, quality rules engine, batch quality scoring."""
import frappe
from frappe import _
from frappe.utils import now_datetime, add_to_date, flt
import json


# ============================================================================
# QUALITY RULES ENGINE - Parameter thresholds for production monitoring
# ============================================================================

DEFAULT_QUALITY_RULES = {
    "temperature": {
        "parameter": "temperature",
        "unit": "C",
        "warning_low": 18.0,
        "warning_high": 35.0,
        "critical_low": 10.0,
        "critical_high": 45.0,
        "nominal": 25.0,
        "weight": 0.3
    },
    "ph": {
        "parameter": "ph",
        "unit": "pH",
        "warning_low": 4.5,
        "warning_high": 8.5,
        "critical_low": 3.5,
        "critical_high": 9.5,
        "nominal": 7.0,
        "weight": 0.3
    },
    "brix": {
        "parameter": "brix",
        "unit": "Brix",
        "warning_low": 20.0,
        "warning_high": 65.0,
        "critical_low": 15.0,
        "critical_high": 70.0,
        "nominal": 45.0,
        "weight": 0.2
    },
    "humidity": {
        "parameter": "humidity",
        "unit": "%",
        "warning_low": 30.0,
        "warning_high": 70.0,
        "critical_low": 20.0,
        "critical_high": 80.0,
        "nominal": 50.0,
        "weight": 0.2
    }
}


# ============================================================================
# WORK ORDER - SENSOR ZONE LINKING
# ============================================================================

@frappe.whitelist()
def get_active_work_orders_for_zone(zone=None):
    """Get active Work Orders linked to a warehouse zone."""
    if not frappe.db.exists("DocType", "Work Order"):
        return []

    filters = {"status": ["in", ["Not Started", "In Process"]]}
    if zone:
        filters["fg_warehouse"] = zone

    work_orders = frappe.get_all("Work Order", filters=filters,
        fields=["name", "production_item", "qty", "produced_qty",
                "status", "fg_warehouse", "planned_start_date"],
        order_by="planned_start_date asc",
        limit=20)

    return work_orders


@frappe.whitelist()
def get_zone_sensors_for_work_order(work_order_name):
    """Get sensor readings from the zone where a Work Order is active."""
    if not frappe.db.exists("DocType", "Work Order"):
        return {"error": "Work Order doctype not found"}

    wo = frappe.get_doc("Work Order", work_order_name)
    zone = wo.fg_warehouse

    result = {
        "work_order": work_order_name,
        "zone": zone,
        "production_item": wo.production_item,
        "status": wo.status,
        "sensors": []
    }

    if not frappe.db.exists("DocType", "IoT Sensor Reading"):
        return result

    # Get latest readings from sensors in this zone (last 30 min)
    cutoff = add_to_date(now_datetime(), minutes=-30)
    readings = frappe.db.sql("""
        SELECT sensor_type, sensor_id, temperature, humidity,
               creation as reading_time
        FROM `tabIoT Sensor Reading`
        WHERE creation >= %s
        ORDER BY creation DESC
        LIMIT 50
    """, (cutoff,), as_dict=True)

    result["sensors"] = readings
    result["sensor_count"] = len(readings)
    return result


# ============================================================================
# REAL-TIME QUALITY EVALUATION
# ============================================================================

@frappe.whitelist()
def evaluate_quality_reading(parameter, value, rules=None):
    """Evaluate a single sensor reading against quality rules."""
    value = float(value)
    if rules is None:
        rules = DEFAULT_QUALITY_RULES
    elif isinstance(rules, str):
        rules = json.loads(rules)

    if parameter not in rules:
        return {
            "parameter": parameter,
            "value": value,
            "level": "unknown",
            "message": f"No quality rule for parameter: {parameter}"
        }

    rule = rules[parameter]

    if value <= rule["critical_low"] or value >= rule["critical_high"]:
        level = "critical"
    elif value <= rule["warning_low"] or value >= rule["warning_high"]:
        level = "warning"
    else:
        level = "normal"

    # Calculate deviation from nominal
    nominal = rule["nominal"]
    deviation = abs(value - nominal)
    max_range = max(abs(rule["critical_high"] - nominal), abs(nominal - rule["critical_low"]))
    deviation_pct = (deviation / max_range * 100) if max_range > 0 else 0

    return {
        "parameter": parameter,
        "value": value,
        "level": level,
        "nominal": nominal,
        "deviation": round(deviation, 3),
        "deviation_pct": round(deviation_pct, 2),
        "unit": rule["unit"]
    }


@frappe.whitelist()
def evaluate_production_quality(readings=None):
    """Evaluate overall production quality from multiple sensor readings.
    readings: list of {"parameter": str, "value": float}"""
    if readings is None:
        readings = []
    elif isinstance(readings, str):
        readings = json.loads(readings)

    evaluations = []
    for r in readings:
        ev = evaluate_quality_reading(r["parameter"], r["value"])
        evaluations.append(ev)

    # Calculate overall quality score (0-100)
    if not evaluations:
        return {"score": 0, "level": "no_data", "evaluations": []}

    weighted_score = 0
    total_weight = 0
    worst_level = "normal"
    level_priority = {"normal": 0, "warning": 1, "critical": 2, "unknown": -1}

    for ev in evaluations:
        param = ev["parameter"]
        weight = DEFAULT_QUALITY_RULES.get(param, {}).get("weight", 0.1)
        total_weight += weight

        # Score: 100 at nominal, 0 at critical
        dev_pct = ev.get("deviation_pct", 0)
        param_score = max(0, 100 - dev_pct)
        weighted_score += param_score * weight

        if level_priority.get(ev["level"], -1) > level_priority.get(worst_level, -1):
            worst_level = ev["level"]

    overall_score = round(weighted_score / total_weight, 1) if total_weight > 0 else 0

    return {
        "score": overall_score,
        "level": worst_level,
        "evaluations": evaluations,
        "parameters_checked": len(evaluations)
    }


# ============================================================================
# BATCH QUALITY SCORING
# ============================================================================

@frappe.whitelist()
def calculate_batch_quality_score(batch_id, sensor_readings=None):
    """Calculate quality score for a batch based on sensor data during production."""
    if not batch_id:
        return {"error": "batch_id is required"}

    if sensor_readings is None:
        sensor_readings = []
    elif isinstance(sensor_readings, str):
        sensor_readings = json.loads(sensor_readings)

    if not sensor_readings:
        # Try to get readings from IoT Sensor Reading for this period
        return {
            "batch_id": batch_id,
            "score": None,
            "level": "no_data",
            "message": "No sensor readings provided or found"
        }

    quality = evaluate_production_quality(sensor_readings)

    return {
        "batch_id": batch_id,
        "score": quality["score"],
        "level": quality["level"],
        "parameters_checked": quality["parameters_checked"],
        "evaluations": quality["evaluations"],
        "timestamp": str(now_datetime())
    }


# ============================================================================
# PROCESS DEVIATION TRACKING
# ============================================================================

@frappe.whitelist()
def log_process_deviation(work_order, parameter, value, level, message=None):
    """Log a process deviation for tracking and reporting."""
    value = float(value)
    deviation = {
        "work_order": work_order,
        "parameter": parameter,
        "value": value,
        "level": level,
        "message": message or f"Deviation: {parameter}={value} ({level})",
        "timestamp": str(now_datetime()),
        "logged": True
    }

    if level == "critical":
        frappe.logger().error(
            f"CRITICAL DEVIATION WO:{work_order} {parameter}={value}")
        deviation["recommendation"] = "Production hold recommended"
    elif level == "warning":
        frappe.logger().warning(
            f"WARNING DEVIATION WO:{work_order} {parameter}={value}")
        deviation["recommendation"] = "Monitor closely"

    return deviation


# ============================================================================
# PRODUCTION STATUS API (for Raven @ai integration)
# ============================================================================

@frappe.whitelist()
def get_production_status(work_order_name=None):
    """Get production status with live sensor data for Raven @ai queries."""
    if not frappe.db.exists("DocType", "Work Order"):
        return {"error": "Work Order doctype not found"}

    if work_order_name:
        if not frappe.db.exists("Work Order", work_order_name):
            return {"error": f"Work Order {work_order_name} not found"}

        wo = frappe.get_doc("Work Order", work_order_name)
        progress = (flt(wo.produced_qty) / flt(wo.qty) * 100) if flt(wo.qty) > 0 else 0

        result = {
            "work_order": work_order_name,
            "item": wo.production_item,
            "status": wo.status,
            "qty": wo.qty,
            "produced_qty": wo.produced_qty,
            "progress_pct": round(progress, 1),
            "warehouse": wo.fg_warehouse
        }

        # Add sensor data if available
        sensor_data = get_zone_sensors_for_work_order(work_order_name)
        result["sensor_count"] = sensor_data.get("sensor_count", 0)
        result["sensors"] = sensor_data.get("sensors", [])[:5]

        return result

    # Return all active work orders summary
    active_wos = get_active_work_orders_for_zone()
    return {
        "active_work_orders": len(active_wos),
        "work_orders": active_wos
    }


@frappe.whitelist()
def get_quality_rules():
    """Return quality rules configuration."""
    return DEFAULT_QUALITY_RULES
