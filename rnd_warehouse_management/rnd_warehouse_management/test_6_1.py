"""Phase 6.1 Test Plan: Self-Learning Sensor Framework
Tests sensor registry, discovery API, health monitoring, validation."""
import frappe
import json

def run_all_tests():
    results = []
    tests = [
        test_sensor_registry_complete,
        test_registry_has_6_types,
        test_get_sensor_registry_api,
        test_register_new_sensor,
        test_validate_reading_normal,
        test_validate_reading_out_of_range,
        test_validate_unknown_sensor,
        test_get_sensor_health,
        test_get_sensor_config_for_rpi,
        test_iot_sensor_reading_doctype_exists,
    ]
    for test_fn in tests:
        try:
            test_fn()
            results.append({"test": test_fn.__name__, "status": "PASS"})
            print(f"  PASS: {test_fn.__name__}")
        except Exception as e:
            results.append({"test": test_fn.__name__, "status": "FAIL", "error": str(e)})
            print(f"  FAIL: {test_fn.__name__} - {e}")
    passed = sum(1 for r in results if r["status"] == "PASS")
    print(f"\n=== Phase 6.1 Results: {passed}/{len(results)} passed ===")
    return results

def test_sensor_registry_complete():
    from rnd_warehouse_management.rnd_warehouse_management.sensor_discovery import DEFAULT_SENSOR_REGISTRY
    for sensor_type, config in DEFAULT_SENSOR_REGISTRY.items():
        assert "measurement" in config, f"{sensor_type} missing measurement"
        assert "min_value" in config, f"{sensor_type} missing min_value"
        assert "max_value" in config, f"{sensor_type} missing max_value"
        assert "fields" in config, f"{sensor_type} missing fields"

def test_registry_has_6_types():
    from rnd_warehouse_management.rnd_warehouse_management.sensor_discovery import DEFAULT_SENSOR_REGISTRY
    assert len(DEFAULT_SENSOR_REGISTRY) >= 6, f"Expected >= 6 types, got {len(DEFAULT_SENSOR_REGISTRY)}"
    expected = ["Ford Temperature", "DHT11", "DHT22", "DS18B20", "BME280", "Generic ADC"]
    for s in expected:
        assert s in DEFAULT_SENSOR_REGISTRY, f"Missing: {s}"

def test_get_sensor_registry_api():
    from rnd_warehouse_management.rnd_warehouse_management.sensor_discovery import get_sensor_registry
    result = get_sensor_registry()
    assert isinstance(result, dict)
    assert len(result) >= 6

def test_register_new_sensor():
    from rnd_warehouse_management.rnd_warehouse_management.sensor_discovery import register_new_sensor
    result = register_new_sensor(sensor_type="TEST_SENSOR_6_1", rpi_id="RPi-Test", zone="Test Zone")
    assert result["registered"] == True
    assert result["sensor_type"] == "TEST_SENSOR_6_1"

def test_validate_reading_normal():
    from rnd_warehouse_management.rnd_warehouse_management.sensor_discovery import validate_reading
    result = validate_reading("DHT11", 25.0)
    assert result["valid"] == True

def test_validate_reading_out_of_range():
    from rnd_warehouse_management.rnd_warehouse_management.sensor_discovery import validate_reading
    result = validate_reading("DHT11", 999.0)
    assert result["valid"] == False

def test_validate_unknown_sensor():
    from rnd_warehouse_management.rnd_warehouse_management.sensor_discovery import validate_reading
    result = validate_reading("UNKNOWN_TYPE", 42)
    assert result["valid"] == False

def test_get_sensor_health():
    from rnd_warehouse_management.rnd_warehouse_management.sensor_discovery import get_sensor_health
    result = get_sensor_health("Ford Temperature")
    assert isinstance(result, dict)
    assert "status" in result

def test_get_sensor_config_for_rpi():
    from rnd_warehouse_management.rnd_warehouse_management.sensor_discovery import get_sensor_config_for_rpi
    result = get_sensor_config_for_rpi()
    assert isinstance(result, dict)
    assert len(result) >= 6

def test_iot_sensor_reading_doctype_exists():
    assert frappe.db.exists("DocType", "IoT Sensor Reading")
    meta = frappe.get_meta("IoT Sensor Reading")
    assert meta.get_field("sensor_id"), "Missing sensor_id field"
    assert meta.get_field("sensor_type"), "Missing sensor_type field"
    assert meta.get_field("temperature"), "Missing temperature field"

if __name__ == "__main__":
    run_all_tests()
