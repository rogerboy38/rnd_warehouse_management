"""Phase 5.3: Warehouse Zone & Temperature Monitoring
Zone management, temperature alerts, IoT sensor bridge"""
import frappe
from frappe.utils import now_datetime, nowdate, get_datetime, time_diff_in_seconds
from frappe import _

# Zone type definitions with temperature specs
ZONE_DEFAULTS = {
    "Raw Material": {"temp_min": 15.0, "temp_max": 30.0, "alert_offset": 2.0, "critical_offset": 5.0},
    "Work In Progress": {"temp_min": 18.0, "temp_max": 28.0, "alert_offset": 2.0, "critical_offset": 5.0},
    "Finished Goods": {"temp_min": 15.0, "temp_max": 25.0, "alert_offset": 2.0, "critical_offset": 5.0},
    "Cold Storage": {"temp_min": 2.0, "temp_max": 8.0, "alert_offset": 1.0, "critical_offset": 2.0},
    "Quarantine": {"temp_min": 15.0, "temp_max": 30.0, "alert_offset": 3.0, "critical_offset": 5.0},
    "Transit": {"temp_min": 10.0, "temp_max": 35.0, "alert_offset": 3.0, "critical_offset": 5.0},
}


def get_zone_warehouses(zone_type=None):
    """Get all warehouses with zone configuration"""
    filters = {"custom_is_zone_warehouse": 1, "disabled": 0}
    if zone_type:
        filters["custom_zone_type"] = zone_type
    return frappe.get_all("Warehouse", filters=filters, fields=[
        "name", "warehouse_name", "custom_zone_type", "custom_temperature_controlled",
        "custom_min_temperature", "custom_max_temperature", "custom_target_temperature",
        "custom_current_temperature", "custom_temperature_status",
        "custom_last_temperature_check", "custom_requires_monitoring"
    ])


@frappe.whitelist()
def get_zone_status_summary():
    """Get summary of all warehouse zones with current status"""
    zones = get_zone_warehouses()
    summary = {}
    for wh in zones:
        zone = wh.custom_zone_type or "Unclassified"
        if zone not in summary:
            summary[zone] = {"total": 0, "monitored": 0, "alerts": 0, "critical": 0, "warehouses": []}
        summary[zone]["total"] += 1
        if wh.custom_requires_monitoring:
            summary[zone]["monitored"] += 1
        if wh.custom_temperature_status in ["Above Maximum", "Below Minimum"]:
            summary[zone]["alerts"] += 1
        summary[zone]["warehouses"].append({
            "name": wh.name,
            "warehouse_name": wh.warehouse_name,
            "current_temp": wh.custom_current_temperature,
            "status": wh.custom_temperature_status,
            "last_check": wh.custom_last_temperature_check
        })
    return summary


def calculate_temperature_spec_display(doc):
    """Build human-readable temperature spec string for a warehouse"""
    if not doc.get("custom_temperature_controlled"):
        return "Not Temperature Controlled"
    min_t = doc.get("custom_min_temperature")
    max_t = doc.get("custom_max_temperature")
    target = doc.get("custom_target_temperature")
    uom = doc.get("custom_temperature_uom") or "°C (Celsius)"
    unit = "°C" if "Celsius" in uom else "°F" if "Fahrenheit" in uom else "K"
    parts = []
    if target:
        parts.append(f"Target: {target}{unit}")
    if min_t is not None and max_t is not None:
        parts.append(f"Range: {min_t}{unit} - {max_t}{unit}")
    elif min_t is not None:
        parts.append(f"Min: {min_t}{unit}")
    elif max_t is not None:
        parts.append(f"Max: {max_t}{unit}")
    return " | ".join(parts) if parts else "Temperature Controlled (no spec set)"


def update_temperature_settings(doc):
    """Auto-set temperature defaults based on zone type"""
    zone = doc.get("custom_zone_type")
    if not zone or zone not in ZONE_DEFAULTS:
        return
    defaults = ZONE_DEFAULTS[zone]
    if not doc.get("custom_min_temperature"):
        doc.custom_min_temperature = defaults["temp_min"]
    if not doc.get("custom_max_temperature"):
        doc.custom_max_temperature = defaults["temp_max"]
    if not doc.get("custom_target_temperature"):
        doc.custom_target_temperature = (defaults["temp_min"] + defaults["temp_max"]) / 2
    if zone == "Cold Storage":
        doc.custom_temperature_controlled = 1
        doc.custom_requires_monitoring = 1


def evaluate_temperature_status(current_temp, min_temp, max_temp):
    """Evaluate temperature status given current and limits"""
    if current_temp is None:
        return "Not Monitored"
    if min_temp is not None and current_temp < min_temp:
        return "Below Minimum"
    if max_temp is not None and current_temp > max_temp:
        return "Above Maximum"
    return "Within Range"


def get_latest_iot_reading(warehouse_name):
    """Bridge to IoT Sensor Reading doctype (Phase 6)
    Returns the latest temperature reading for a warehouse sensor"""
    if not frappe.db.exists("DocType", "IoT Sensor Reading"):
        return None
    reading = frappe.get_all("IoT Sensor Reading", filters={
        "sensor_location": warehouse_name,
        "reading_type": "Temperature"
    }, fields=["reading_value", "timestamp", "sensor_id"],
       order_by="timestamp desc", limit=1)
    return reading[0] if reading else None


def update_warehouse_from_iot(warehouse_name):
    """Update warehouse temperature from latest IoT reading"""
    reading = get_latest_iot_reading(warehouse_name)
    if not reading:
        return None
    wh = frappe.get_doc("Warehouse", warehouse_name)
    wh.custom_current_temperature = reading.reading_value
    wh.custom_last_temperature_check = reading.timestamp
    wh.custom_temperature_status = evaluate_temperature_status(
        reading.reading_value, wh.custom_min_temperature, wh.custom_max_temperature
    )
    wh.custom_temperature_spec_display = calculate_temperature_spec_display(wh)
    wh.save(ignore_permissions=True)
    return {
        "warehouse": warehouse_name,
        "temperature": reading.reading_value,
        "status": wh.custom_temperature_status,
        "sensor_id": reading.sensor_id
    }


def check_temperature_alerts():
    """Scheduler job: check all monitored warehouses for temperature alerts
    Runs every 5 minutes via hooks.scheduler_events"""
    warehouses = get_zone_warehouses()
    alerts = []
    for wh in warehouses:
        if not wh.custom_requires_monitoring or not wh.custom_temperature_controlled:
            continue
        # Try to get latest IoT reading first
        iot_result = update_warehouse_from_iot(wh.name)
        current_temp = iot_result["temperature"] if iot_result else wh.custom_current_temperature
        if current_temp is None:
            continue
        min_t = wh.custom_min_temperature
        max_t = wh.custom_max_temperature
        zone = wh.custom_zone_type or "Unknown"
        defaults = ZONE_DEFAULTS.get(zone, {"alert_offset": 2.0, "critical_offset": 5.0})
        status = evaluate_temperature_status(current_temp, min_t, max_t)
        if status == "Within Range":
            continue
        # Determine severity
        severity = "Warning"
        if status == "Above Maximum" and max_t:
            deviation = current_temp - max_t
            if deviation >= defaults["critical_offset"]:
                severity = "Critical"
            elif deviation >= defaults["alert_offset"]:
                severity = "Alert"
        elif status == "Below Minimum" and min_t:
            deviation = min_t - current_temp
            if deviation >= defaults["critical_offset"]:
                severity = "Critical"
            elif deviation >= defaults["alert_offset"]:
                severity = "Alert"
        # Cold storage escalation: >2 degrees over max is always critical
        if zone == "Cold Storage" and max_t and current_temp > (max_t + 2):
            severity = "Critical"
        alert_data = {
            "warehouse": wh.name,
            "zone": zone,
            "current_temp": current_temp,
            "min_temp": min_t,
            "max_temp": max_t,
            "status": status,
            "severity": severity
        }
        alerts.append(alert_data)
        # Log the alert
        frappe.log_error(
            f"Temperature {severity}: {wh.name} ({zone}) at {current_temp}°C "
            f"(Range: {min_t}-{max_t}°C)",
            f"Temperature {severity} - {wh.name}"
        )
    if alerts:
        frappe.publish_realtime("temperature_alerts", {"alerts": alerts})
    return alerts


@frappe.whitelist()
def configure_zone(warehouse, zone_type):
    """Quick configure a warehouse as a zone with defaults"""
    if zone_type not in ZONE_DEFAULTS:
        frappe.throw(_(f"Invalid zone type: {zone_type}. Valid: {list(ZONE_DEFAULTS.keys())}"))
    wh = frappe.get_doc("Warehouse", warehouse)
    wh.custom_zone_type = zone_type
    wh.custom_is_zone_warehouse = 1
    update_temperature_settings(wh)
    wh.custom_temperature_spec_display = calculate_temperature_spec_display(wh)
    wh.save(ignore_permissions=True)
    return {"warehouse": warehouse, "zone_type": zone_type, "configured": True}

# =============================================================================
# Function aliases and scheduler entry points (Phase 5.3 compatibility)
# =============================================================================

def evaluate_temperature(current_temp=None, min_temp=None, max_temp=None, target_temp=None):
    """Evaluate temperature and return status dict. Wrapper around evaluate_temperature_status."""
    if current_temp is None:
        return {"status": "Unknown", "in_range": False, "deviation": 0}
    
    from frappe.utils import flt
    current = flt(current_temp)
    t_min = flt(min_temp) if min_temp else 0
    t_max = flt(max_temp) if max_temp else 100
    t_target = flt(target_temp) if target_temp else (t_min + t_max) / 2
    
    deviation = 0
    if current < t_min:
        deviation = t_min - current
    elif current > t_max:
        deviation = current - t_max
    
    alert_offset = 2.0
    critical_offset = 5.0
    
    if t_min <= current <= t_max:
        status = "Normal"
        in_range = True
    elif deviation <= alert_offset:
        status = "Warning"
        in_range = False
    else:
        status = "Critical"
        in_range = False
    
    return {
        "status": status,
        "in_range": in_range,
        "deviation": round(deviation, 2),
        "current_temp": current,
        "target_temp": t_target,
        "min_temp": t_min,
        "max_temp": t_max
    }


def run_temperature_monitoring():
    """Scheduler entry point - runs every 5 minutes via hooks.py cron."""
    try:
        check_temperature_alerts()
    except Exception as e:
        frappe.log_error(f"Temperature monitoring error: {str(e)}", "Temperature Monitor")


def process_iot_reading(reading_data):
    """Process an IoT sensor reading and update warehouse temperature."""
    warehouse = reading_data.get("warehouse")
    temperature = reading_data.get("temperature")
    if not warehouse or temperature is None:
        return {"status": "error", "message": "Missing warehouse or temperature"}
    
    try:
        frappe.db.set_value("Warehouse", warehouse, {
            "custom_current_temperature": float(temperature),
            "custom_last_temperature_check": frappe.utils.now_datetime()
        })
        frappe.db.commit()
        
        result = evaluate_temperature(
            current_temp=float(temperature),
            min_temp=frappe.db.get_value("Warehouse", warehouse, "custom_min_temperature"),
            max_temp=frappe.db.get_value("Warehouse", warehouse, "custom_max_temperature"),
            target_temp=frappe.db.get_value("Warehouse", warehouse, "custom_target_temperature")
        )
        result["status"] = "success"
        result["warehouse"] = warehouse
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


def check_and_alert(warehouse_name):
    """Check temperature for a specific warehouse and create alert if needed."""
    doc = frappe.db.get_value(
        "Warehouse", warehouse_name,
        ["custom_current_temperature", "custom_min_temperature",
         "custom_max_temperature", "custom_target_temperature"],
        as_dict=True
    )
    if not doc:
        return None
    
    result = evaluate_temperature(
        current_temp=doc.custom_current_temperature,
        min_temp=doc.custom_min_temperature,
        max_temp=doc.custom_max_temperature,
        target_temp=doc.custom_target_temperature
    )
    
    if result["status"] in ("Warning", "Critical"):
        frappe.log_error(
            f"Temperature alert for {warehouse_name}: {result["status"]} - "
            f"Current: {doc.custom_current_temperature}, Range: {doc.custom_min_temperature}-{doc.custom_max_temperature}",
            f"Temperature {result["status"]}: {warehouse_name}"
        )
    
    return result
