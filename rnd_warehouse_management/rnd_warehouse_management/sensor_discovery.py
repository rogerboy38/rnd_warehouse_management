# sensor_discovery.py - Phase 6.1: Self-Learning Sensor Framework (ERPNext side)
"""Phase 6.1: Self-Learning Sensor Framework
ERPNext API endpoints for RPi sensor auto-discovery and auto-integration.
The RPi-side scripts call these APIs to register new sensors, update configs,
and manage the sensor skill registry."""
import frappe
from frappe import _
from frappe.utils import now_datetime
import json


# ============================================================================
# SENSOR REGISTRY - Known sensor types and their configurations
# ============================================================================

DEFAULT_SENSOR_REGISTRY = {
    "Ford Temperature": {
        "sensor_type": "Ford Temperature",
        "measurement": "temperature",
        "unit": "C",
        "min_value": -40.0,
        "max_value": 150.0,
        "calibration_method": "steinhart_hart",
        "fields": ["temperature", "resistance", "raw_adc", "millivolts"],
        "arduino_sketch": "ford_ntc_reader",
        "description": "Ford NTC thermistor (216+1S7Z6G004AA) with 10K pull-up"
    },
    "DHT11": {
        "sensor_type": "DHT11",
        "measurement": "temperature_humidity",
        "unit": "C/%",
        "min_value": 0.0,
        "max_value": 50.0,
        "calibration_method": "linear",
        "fields": ["temperature", "humidity"],
        "gpio_pin": 4,
        "description": "DHT11 digital temperature and humidity sensor"
    },
    "DHT22": {
        "sensor_type": "DHT22",
        "measurement": "temperature_humidity",
        "unit": "C/%",
        "min_value": -40.0,
        "max_value": 80.0,
        "calibration_method": "linear",
        "fields": ["temperature", "humidity"],
        "gpio_pin": 4,
        "description": "DHT22/AM2302 precision temperature and humidity sensor"
    },
    "DS18B20": {
        "sensor_type": "DS18B20",
        "measurement": "temperature",
        "unit": "C",
        "min_value": -55.0,
        "max_value": 125.0,
        "calibration_method": "factory",
        "fields": ["temperature"],
        "protocol": "1-wire",
        "description": "DS18B20 waterproof 1-Wire digital temperature sensor"
    },
    "BME280": {
        "sensor_type": "BME280",
        "measurement": "environment",
        "unit": "C/%/hPa",
        "min_value": -40.0,
        "max_value": 85.0,
        "calibration_method": "factory",
        "fields": ["temperature", "humidity", "pressure"],
        "protocol": "i2c",
        "i2c_address": "0x76",
        "description": "BME280 environmental sensor (temp, humidity, pressure)"
    },
    "Generic ADC": {
        "sensor_type": "Generic ADC",
        "measurement": "voltage",
        "unit": "V",
        "min_value": 0.0,
        "max_value": 5.0,
        "calibration_method": "linear",
        "fields": ["raw_adc", "voltage"],
        "description": "Generic analog sensor via ADC"
    }
}


# ============================================================================
# API ENDPOINTS
# ============================================================================

@frappe.whitelist()
def get_sensor_registry():
    """Return the complete sensor registry for RPi auto-discovery."""
    return DEFAULT_SENSOR_REGISTRY


@frappe.whitelist()
def register_new_sensor(sensor_type, rpi_id=None, zone=None, config=None):
    """Register a newly discovered sensor from RPi.
    Adds the sensor type to IoT Sensor Reading options if not present."""
    if not sensor_type:
        frappe.throw(_("sensor_type is required"))

    # Check if sensor type already exists in IoT Sensor Reading options
    meta = frappe.get_meta("IoT Sensor Reading")
    sensor_type_field = meta.get_field("sensor_type")
    existing_options = (sensor_type_field.options or "").split("\n") if sensor_type_field else []

    result = {
        "sensor_type": sensor_type,
        "registered": True,
        "rpi_id": rpi_id,
        "zone": zone,
        "timestamp": str(now_datetime())
    }

    if sensor_type not in existing_options:
        new_options = "\n".join(existing_options + [sensor_type])
        frappe.db.sql("""
            UPDATE `tabCustom Field`
            SET options = %s
            WHERE dt = 'IoT Sensor Reading' AND fieldname = 'sensor_type'
        """, (new_options,))
        frappe.db.commit()
        result["new_type_added"] = True
    else:
        result["new_type_added"] = False

    if config:
        result["config_received"] = True

    return result


@frappe.whitelist()
def validate_reading(sensor_type, value, field="temperature"):
    """Validate a sensor reading against the registry bounds."""
    registry = DEFAULT_SENSOR_REGISTRY
    value = float(value)

    if sensor_type not in registry:
        return {
            "valid": False,
            "error": f"Unknown sensor type: {sensor_type}",
            "sensor_type": sensor_type
        }

    config = registry[sensor_type]
    min_val = config.get("min_value", -999)
    max_val = config.get("max_value", 999)

    if value < min_val or value > max_val:
        return {
            "valid": False,
            "error": f"Value {value} out of range [{min_val}, {max_val}]",
            "sensor_type": sensor_type,
            "value": value,
            "min": min_val,
            "max": max_val
        }

    return {
        "valid": True,
        "sensor_type": sensor_type,
        "value": value,
        "unit": config.get("unit", "")
    }


@frappe.whitelist()
def get_sensor_health(sensor_type):
    """Get health/status info for a sensor type."""
    registry = DEFAULT_SENSOR_REGISTRY

    if sensor_type not in registry:
        return {"status": "unknown", "sensor_type": sensor_type}

    config = registry[sensor_type]
    # Count recent readings
    count = frappe.db.count("IoT Sensor Reading", filters={
        "sensor_type": sensor_type
    }) if frappe.db.exists("DocType", "IoT Sensor Reading") else 0

    return {
        "status": "active" if count > 0 else "idle",
        "sensor_type": sensor_type,
        "reading_count": count,
        "calibration_method": config.get("calibration_method", "unknown"),
        "unit": config.get("unit", "")
    }


@frappe.whitelist()
def get_sensor_config_for_rpi(sensor_type=None):
    """Get sensor configuration optimized for RPi consumption."""
    registry = DEFAULT_SENSOR_REGISTRY

    if sensor_type:
        if sensor_type in registry:
            return {sensor_type: registry[sensor_type]}
        return {}

    # Return simplified config for all sensors
    rpi_config = {}
    for name, config in registry.items():
        rpi_config[name] = {
            "type": config["sensor_type"],
            "measurement": config["measurement"],
            "unit": config["unit"],
            "fields": config["fields"],
            "min": config["min_value"],
            "max": config["max_value"]
        }
    return rpi_config
