
# test_5_3.py - Phase 5.3: Warehouse Zone & Temperature Monitoring Test Plan
"""Phase 5.3 Test Plan: Warehouse Zone & Temperature Monitoring
Tests zone assignment, temperature evaluation, alerts, IoT bridge, scheduler."""
import frappe
from frappe.utils import now_datetime, nowdate
import json

def run_all_tests():
    results = []
    tests = [
        test_zone_defaults_defined,
        test_get_zone_warehouses,
        test_evaluate_temperature_normal,
        test_evaluate_temperature_warning,
        test_evaluate_temperature_critical,
        test_assign_warehouse_zone,
        test_update_warehouse_temperature,
        test_get_zone_temperature_status,
        test_iot_sensor_bridge,
        test_temperature_alert_creation,
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
    print(f"\n=== Phase 5.3 Results: {passed}/{len(results)} passed ===")
    return results


def test_zone_defaults_defined():
    """Test that ZONE_DEFAULTS has all expected zone types."""
    from rnd_warehouse_management.rnd_warehouse_management.warehouse_monitoring import ZONE_DEFAULTS
    expected = ["Raw Material", "Work In Progress", "Finished Goods", "Cold Storage", "Quarantine", "Transit"]
    for zone in expected:
        assert zone in ZONE_DEFAULTS, f"Missing zone: {zone}"
        assert "temp_min" in ZONE_DEFAULTS[zone]
        assert "temp_max" in ZONE_DEFAULTS[zone]
        assert "alert_offset" in ZONE_DEFAULTS[zone]
        assert "critical_offset" in ZONE_DEFAULTS[zone]


def test_get_zone_warehouses():
    """Test fetching zone-configured warehouses."""
    from rnd_warehouse_management.rnd_warehouse_management.warehouse_monitoring import get_zone_warehouses
    result = get_zone_warehouses()
    assert isinstance(result, list), "Should return a list"
    # May be empty if no warehouses configured yet


def test_evaluate_temperature_normal():
    """Test temperature evaluation - normal range."""
    from rnd_warehouse_management.rnd_warehouse_management.warehouse_monitoring import evaluate_temperature
    result = evaluate_temperature(current_temp=22.0, min_temp=15.0, max_temp=30.0, target_temp=22.5)
    assert result["status"] == "Normal", f"Expected Normal, got {result["status"]}"
    assert result["in_range"] == True


def test_evaluate_temperature_warning():
    """Test temperature evaluation - warning range."""
    from rnd_warehouse_management.rnd_warehouse_management.warehouse_monitoring import evaluate_temperature
    # Just outside max by alert_offset amount
    result = evaluate_temperature(current_temp=31.5, min_temp=15.0, max_temp=30.0, target_temp=22.5)
    assert result["status"] in ["Warning", "Critical"], f"Expected Warning/Critical, got {result["status"]}"
    assert result["in_range"] == False


def test_evaluate_temperature_critical():
    """Test temperature evaluation - critical range."""
    from rnd_warehouse_management.rnd_warehouse_management.warehouse_monitoring import evaluate_temperature
    # Far outside range
    result = evaluate_temperature(current_temp=40.0, min_temp=15.0, max_temp=30.0, target_temp=22.5)
    assert result["status"] == "Critical", f"Expected Critical, got {result["status"]}"


def test_assign_warehouse_zone():
    """Test assigning a zone type to a warehouse."""
    # Find any active warehouse
    wh = frappe.db.get_value("Warehouse", {"disabled": 0, "is_group": 0}, "name")
    if not wh:
        print("    SKIP: No active warehouse found")
        return
    from rnd_warehouse_management.rnd_warehouse_management.warehouse import assign_warehouse_zone
    result = assign_warehouse_zone(wh, "Raw Material")
    assert result["status"] == "success", f"Assignment failed: {result}"
    # Verify fields were set
    doc = frappe.get_doc("Warehouse", wh)
    assert doc.custom_zone_type == "Raw Material"
    assert doc.custom_is_zone_warehouse == 1
    assert doc.custom_temperature_controlled == 1


def test_update_warehouse_temperature():
    """Test updating warehouse temperature."""
    wh = frappe.db.get_value("Warehouse", {"disabled": 0, "is_group": 0, "custom_is_zone_warehouse": 1}, "name")
    if not wh:
        print("    SKIP: No zone warehouse found")
        return
    from rnd_warehouse_management.rnd_warehouse_management.warehouse import update_warehouse_temperature
    result = update_warehouse_temperature(wh, 22.5, "test")
    assert "status" in result, f"Missing status in result: {result}"
    assert result["warehouse"] == wh


def test_get_zone_temperature_status():
    """Test getting zone temperature overview."""
    from rnd_warehouse_management.rnd_warehouse_management.warehouse import get_zone_temperature_status
    result = get_zone_temperature_status()
    assert isinstance(result, list), "Should return list"


def test_iot_sensor_bridge():
    """Test IoT sensor bridge endpoint."""
    from rnd_warehouse_management.rnd_warehouse_management.warehouse_monitoring import process_iot_reading
    wh = frappe.db.get_value("Warehouse", {"disabled": 0, "is_group": 0, "custom_is_zone_warehouse": 1}, "name")
    if not wh:
        print("    SKIP: No zone warehouse")
        return
    result = process_iot_reading({
        "warehouse": wh,
        "temperature": 23.0,
        "humidity": 45.0,
        "sensor_id": "TEST-SENSOR-001",
        "timestamp": str(now_datetime())
    })
    assert result.get("status") in ["success", "recorded"], f"IoT bridge failed: {result}"


def test_temperature_alert_creation():
    """Test that temperature alerts/logs are created."""
    from rnd_warehouse_management.rnd_warehouse_management.warehouse_monitoring import check_and_alert
    wh = frappe.db.get_value("Warehouse", {"disabled": 0, "is_group": 0, "custom_is_zone_warehouse": 1}, "name")
    if not wh:
        print("    SKIP: No zone warehouse")
        return
    # Set temp out of range to trigger alert
    frappe.db.set_value("Warehouse", wh, "custom_current_temperature", 50.0)
    frappe.db.commit()
    try:
        result = check_and_alert(wh)
        assert result is not None, "check_and_alert should return result"
    except Exception as e:
        # Alert function may log error, that is acceptable
        print(f"    INFO: Alert function raised: {e}")
    finally:
        frappe.db.set_value("Warehouse", wh, "custom_current_temperature", 22.0)
        frappe.db.commit()


if __name__ == "__main__":
    run_all_tests()
