"""Phase 6.3: PLC Integration (Allen Bradley)
ERPNext-side integration for Allen Bradley PLC sensors.
Register mapping, calibration, alarm forwarding, combined dashboard."""
import frappe
from frappe import _
from frappe.utils import now_datetime, add_to_date
import json


# ============================================================================
# PLC REGISTER MAP - Maps PLC data registers to named parameters
# ============================================================================

DEFAULT_PLC_REGISTER_MAP = {
    "PLC_Temperature": {
        "register_address": "N7:0",
        "register_type": "INT",
        "parameter": "temperature",
        "unit": "C",
        "scale_factor": 0.1,
        "offset": 0.0,
        "min_raw": 0,
        "max_raw": 2000,
        "min_eng": -20.0,
        "max_eng": 200.0,
        "description": "Production line temperature sensor via PLC"
    },
    "PLC_pH": {
        "register_address": "N7:1",
        "register_type": "INT",
        "parameter": "ph",
        "unit": "pH",
        "scale_factor": 0.01,
        "offset": 0.0,
        "min_raw": 0,
        "max_raw": 1400,
        "min_eng": 0.0,
        "max_eng": 14.0,
        "description": "Process pH sensor via PLC"
    },
    "PLC_Brix": {
        "register_address": "N7:2",
        "register_type": "INT",
        "parameter": "brix",
        "unit": "Brix",
        "scale_factor": 0.1,
        "offset": 0.0,
        "min_raw": 0,
        "max_raw": 850,
        "min_eng": 0.0,
        "max_eng": 85.0,
        "description": "Refractometer Brix reading via PLC"
    },
    "PLC_Color": {
        "register_address": "N7:3",
        "register_type": "INT",
        "parameter": "color_index",
        "unit": "idx",
        "scale_factor": 1.0,
        "offset": 0.0,
        "min_raw": 0,
        "max_raw": 1000,
        "min_eng": 0.0,
        "max_eng": 1000.0,
        "description": "Colorimeter index reading via PLC"
    }
}

# PLC Connection defaults
DEFAULT_PLC_CONFIG = {
    "protocol": "ModbusTCP",
    "fallback_protocol": "EtherNetIP",
    "ip_address": "192.168.1.100",
    "port": 502,
    "timeout": 5,
    "poll_interval_seconds": 10,
    "retry_count": 3,
    "retry_delay": 2
}

# PLC Alarm thresholds
DEFAULT_PLC_ALARMS = {
    "PLC_Temperature": {
        "warning_low": 15.0, "warning_high": 80.0,
        "critical_low": 5.0, "critical_high": 100.0
    },
    "PLC_pH": {
        "warning_low": 4.0, "warning_high": 9.0,
        "critical_low": 3.0, "critical_high": 10.0
    },
    "PLC_Brix": {
        "warning_low": 10.0, "warning_high": 70.0,
        "critical_low": 5.0, "critical_high": 80.0
    },
    "PLC_Color": {
        "warning_low": 50, "warning_high": 800,
        "critical_low": 20, "critical_high": 950
    }
}


# ============================================================================
# API ENDPOINTS
# ============================================================================

@frappe.whitelist()
def get_plc_register_map():
    """Return the PLC register map for RPi plc_reader.py."""
    return DEFAULT_PLC_REGISTER_MAP


@frappe.whitelist()
def get_plc_config():
    """Return PLC connection configuration."""
    return DEFAULT_PLC_CONFIG


@frappe.whitelist()
def get_plc_alarms():
    """Return PLC alarm thresholds."""
    return DEFAULT_PLC_ALARMS


@frappe.whitelist()
def convert_raw_to_engineering(sensor_type, raw_value):
    """Convert raw PLC register value to engineering units."""
    raw_value = float(raw_value)
    if sensor_type not in DEFAULT_PLC_REGISTER_MAP:
        return {"error": f"Unknown PLC sensor type: {sensor_type}"}

    reg = DEFAULT_PLC_REGISTER_MAP[sensor_type]
    eng_value = (raw_value * reg["scale_factor"]) + reg["offset"]

    # Clamp to engineering range
    eng_value = max(reg["min_eng"], min(reg["max_eng"], eng_value))

    return {
        "sensor_type": sensor_type,
        "raw_value": raw_value,
        "eng_value": round(eng_value, 3),
        "unit": reg["unit"],
        "register": reg["register_address"]
    }


@frappe.whitelist()
def check_plc_alarm(sensor_type, value):
    """Check if a PLC reading triggers warning or critical alarm."""
    value = float(value)
    if sensor_type not in DEFAULT_PLC_ALARMS:
        return {"alarm_level": "none", "sensor_type": sensor_type, "value": value}

    alarm = DEFAULT_PLC_ALARMS[sensor_type]

    if value <= alarm["critical_low"] or value >= alarm["critical_high"]:
        level = "critical"
    elif value <= alarm["warning_low"] or value >= alarm["warning_high"]:
        level = "warning"
    else:
        level = "normal"

    return {
        "alarm_level": level,
        "sensor_type": sensor_type,
        "value": value,
        "thresholds": alarm
    }


@frappe.whitelist()
def forward_plc_alarm(sensor_type, value, alarm_level, message=None):
    """Forward a PLC alarm to ERPNext as a log entry.
    In production this would create an ERPNext alert and notify via Raven."""
    value = float(value)
    log_entry = {
        "sensor_type": sensor_type,
        "value": value,
        "alarm_level": alarm_level,
        "message": message or f"PLC alarm: {sensor_type} = {value} ({alarm_level})",
        "timestamp": str(now_datetime()),
        "forwarded": True
    }

    # Log to frappe logger
    if alarm_level == "critical":
        frappe.logger().error(f"PLC CRITICAL ALARM: {sensor_type} = {value}")
    elif alarm_level == "warning":
        frappe.logger().warning(f"PLC WARNING: {sensor_type} = {value}")

    return log_entry


@frappe.whitelist()
def get_plc_sensor_types():
    """Return list of all PLC sensor types for IoT Sensor Reading doctype."""
    return list(DEFAULT_PLC_REGISTER_MAP.keys())


@frappe.whitelist()
def get_combined_dashboard():
    """Get combined dashboard showing both Arduino and PLC sensors."""
    if not frappe.db.exists("DocType", "IoT Sensor Reading"):
        return {"error": "IoT Sensor Reading doctype not found"}

    # Get all sensor types with their counts
    sensor_data = frappe.db.sql("""
        SELECT sensor_type, COUNT(*) as count,
               MAX(creation) as last_reading,
               AVG(temperature) as avg_value
        FROM `tabIoT Sensor Reading`
        WHERE sensor_type IS NOT NULL
        GROUP BY sensor_type
        ORDER BY sensor_type
    """, as_dict=True)

    arduino_sensors = []
    plc_sensors = []

    for s in sensor_data:
        entry = {
            "sensor_type": s.sensor_type,
            "reading_count": s.count,
            "last_reading": str(s.last_reading) if s.last_reading else None,
            "avg_value": round(float(s.avg_value), 2) if s.avg_value else None
        }
        if s.sensor_type and s.sensor_type.startswith("PLC_"):
            plc_sensors.append(entry)
        else:
            arduino_sensors.append(entry)

    total = frappe.db.count("IoT Sensor Reading")

    return {
        "total_readings": total,
        "arduino_sensors": arduino_sensors,
        "plc_sensors": plc_sensors,
        "arduino_count": len(arduino_sensors),
        "plc_count": len(plc_sensors),
        "plc_register_map": DEFAULT_PLC_REGISTER_MAP,
        "plc_config": DEFAULT_PLC_CONFIG
    }


@frappe.whitelist()
def validate_plc_connection_config(ip_address, port=502, protocol="ModbusTCP"):
    """Validate PLC connection parameters (does not actually connect)."""
    errors = []
    port = int(port)

    # Validate IP format
    parts = ip_address.split(".")
    if len(parts) != 4:
        errors.append("Invalid IP address format")
    else:
        for p in parts:
            try:
                n = int(p)
                if n < 0 or n > 255:
                    errors.append(f"IP octet {p} out of range")
            except ValueError:
                errors.append(f"Non-numeric IP octet: {p}")

    if port < 1 or port > 65535:
        errors.append(f"Port {port} out of valid range")

    if protocol not in ["ModbusTCP", "EtherNetIP"]:
        errors.append(f"Unsupported protocol: {protocol}")

    return {
        "valid": len(errors) == 0,
        "ip_address": ip_address,
        "port": port,
        "protocol": protocol,
        "errors": errors
    }
