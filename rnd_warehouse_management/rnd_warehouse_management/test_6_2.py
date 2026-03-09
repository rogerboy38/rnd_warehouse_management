"""Phase 6.2 Test Plan: IoT Sensor Reading Pipeline Hardening
Tests validation, health monitoring, drift detection, aggregation, buffer reporting."""
import frappe
import json

def run_all_tests():
    results = []
    tests = [
        test_validate_normal_reading,
        test_validate_out_of_range,
        test_validate_unknown_sensor,
        test_validate_non_numeric,
        test_sensor_ranges_defined,
        test_check_sensor_health_all,
        test_check_sensor_health_single,
        test_drift_detection,
        test_aggregated_readings,
        test_buffer_status_report,
        test_pipeline_dashboard,
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
    print(f"\n=== Phase 6.2 Results: {passed}/{len(results)} passed ===")
    return results

def test_validate_normal_reading():
    from rnd_warehouse_management.rnd_warehouse_management.iot_pipeline import validate_sensor_reading
    result = validate_sensor_reading("DHT11", 25.0)
    assert result["valid"] == True, f"Expected valid, got {result}"
    assert len(result["errors"]) == 0

def test_validate_out_of_range():
    from rnd_warehouse_management.rnd_warehouse_management.iot_pipeline import validate_sensor_reading
    result = validate_sensor_reading("DHT11", 999.0)
    assert result["valid"] == False
    assert len(result["errors"]) > 0

def test_validate_unknown_sensor():
    from rnd_warehouse_management.rnd_warehouse_management.iot_pipeline import validate_sensor_reading
    result = validate_sensor_reading("UNKNOWN_TYPE", 42)
    assert result["valid"] == True  # Unknown types pass with warning
    assert len(result["warnings"]) > 0

def test_validate_non_numeric():
    from rnd_warehouse_management.rnd_warehouse_management.iot_pipeline import validate_sensor_reading
    result = validate_sensor_reading("DHT11", "not_a_number")
    assert result["valid"] == False
    assert "non_numeric" in result["errors"]

def test_sensor_ranges_defined():
    from rnd_warehouse_management.rnd_warehouse_management.iot_pipeline import SENSOR_RANGES
    assert len(SENSOR_RANGES) >= 7, f"Expected >= 7 ranges, got {len(SENSOR_RANGES)}"
    for name, r in SENSOR_RANGES.items():
        assert "min" in r, f"{name} missing min"
        assert "max" in r, f"{name} missing max"
        assert "unit" in r, f"{name} missing unit"

def test_check_sensor_health_all():
    from rnd_warehouse_management.rnd_warehouse_management.iot_pipeline import check_sensor_health
    result = check_sensor_health()
    assert isinstance(result, dict)

def test_check_sensor_health_single():
    from rnd_warehouse_management.rnd_warehouse_management.iot_pipeline import check_sensor_health
    result = check_sensor_health("Ford Temperature")
    assert isinstance(result, dict)
    assert "status" in result
    assert "readings_last_hour" in result

def test_drift_detection():
    from rnd_warehouse_management.rnd_warehouse_management.iot_pipeline import detect_sensor_drift
    result = detect_sensor_drift("Ford Temperature", window_hours=24)
    assert isinstance(result, dict)
    assert "drift_detected" in result

def test_aggregated_readings():
    from rnd_warehouse_management.rnd_warehouse_management.iot_pipeline import get_aggregated_readings
    result = get_aggregated_readings("Ford Temperature", interval_minutes=60, hours=24)
    assert isinstance(result, (list, tuple))

def test_buffer_status_report():
    from rnd_warehouse_management.rnd_warehouse_management.iot_pipeline import report_buffer_status
    result = report_buffer_status(rpi_id="RPi-IoT-L01", buffered_count=5)
    assert result["received"] == True
    assert result["rpi_id"] == "RPi-IoT-L01"
    assert result["buffered_count"] == 5

def test_pipeline_dashboard():
    from rnd_warehouse_management.rnd_warehouse_management.iot_pipeline import get_pipeline_dashboard
    result = get_pipeline_dashboard()
    assert isinstance(result, dict)
    assert "total_sensors" in result or "error" not in result

if __name__ == "__main__":
    run_all_tests()
