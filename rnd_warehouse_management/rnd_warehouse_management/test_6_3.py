"""Phase 6.3 Test Plan: PLC Integration (Allen Bradley)
Tests register mapping, raw-to-eng conversion, alarms, combined dashboard."""
import frappe

def run_all_tests():
    results = []
    tests = [
        test_plc_register_map_complete,
        test_plc_config,
        test_plc_alarms_defined,
        test_convert_raw_temperature,
        test_convert_raw_ph,
        test_convert_raw_brix,
        test_convert_raw_color,
        test_convert_unknown_type,
        test_alarm_normal,
        test_alarm_warning,
        test_alarm_critical,
        test_forward_alarm,
        test_plc_sensor_types,
        test_combined_dashboard,
        test_validate_plc_config_valid,
        test_validate_plc_config_invalid,
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
    print(f"\n=== Phase 6.3 Results: {passed}/{len(results)} passed ===")
    return results

def test_plc_register_map_complete():
    from rnd_warehouse_management.rnd_warehouse_management.plc_integration import DEFAULT_PLC_REGISTER_MAP
    assert len(DEFAULT_PLC_REGISTER_MAP) == 4
    for name in ["PLC_Temperature", "PLC_pH", "PLC_Brix", "PLC_Color"]:
        assert name in DEFAULT_PLC_REGISTER_MAP, f"Missing {name}"
        reg = DEFAULT_PLC_REGISTER_MAP[name]
        for key in ["register_address", "scale_factor", "unit", "min_eng", "max_eng"]:
            assert key in reg, f"{name} missing {key}"

def test_plc_config():
    from rnd_warehouse_management.rnd_warehouse_management.plc_integration import get_plc_config
    config = get_plc_config()
    assert config["protocol"] == "ModbusTCP"
    assert config["port"] == 502
    assert "ip_address" in config

def test_plc_alarms_defined():
    from rnd_warehouse_management.rnd_warehouse_management.plc_integration import DEFAULT_PLC_ALARMS
    assert len(DEFAULT_PLC_ALARMS) == 4
    for name, alarm in DEFAULT_PLC_ALARMS.items():
        assert "warning_low" in alarm, f"{name} missing warning_low"
        assert "critical_high" in alarm, f"{name} missing critical_high"

def test_convert_raw_temperature():
    from rnd_warehouse_management.rnd_warehouse_management.plc_integration import convert_raw_to_engineering
    result = convert_raw_to_engineering("PLC_Temperature", 250)
    assert result["eng_value"] == 25.0
    assert result["unit"] == "C"

def test_convert_raw_ph():
    from rnd_warehouse_management.rnd_warehouse_management.plc_integration import convert_raw_to_engineering
    result = convert_raw_to_engineering("PLC_pH", 700)
    assert result["eng_value"] == 7.0
    assert result["unit"] == "pH"

def test_convert_raw_brix():
    from rnd_warehouse_management.rnd_warehouse_management.plc_integration import convert_raw_to_engineering
    result = convert_raw_to_engineering("PLC_Brix", 450)
    assert result["eng_value"] == 45.0
    assert result["unit"] == "Brix"

def test_convert_raw_color():
    from rnd_warehouse_management.rnd_warehouse_management.plc_integration import convert_raw_to_engineering
    result = convert_raw_to_engineering("PLC_Color", 500)
    assert result["eng_value"] == 500.0
    assert result["unit"] == "idx"

def test_convert_unknown_type():
    from rnd_warehouse_management.rnd_warehouse_management.plc_integration import convert_raw_to_engineering
    result = convert_raw_to_engineering("PLC_Unknown", 100)
    assert "error" in result

def test_alarm_normal():
    from rnd_warehouse_management.rnd_warehouse_management.plc_integration import check_plc_alarm
    result = check_plc_alarm("PLC_pH", 7.0)
    assert result["alarm_level"] == "normal"

def test_alarm_warning():
    from rnd_warehouse_management.rnd_warehouse_management.plc_integration import check_plc_alarm
    result = check_plc_alarm("PLC_pH", 3.5)
    assert result["alarm_level"] == "warning"

def test_alarm_critical():
    from rnd_warehouse_management.rnd_warehouse_management.plc_integration import check_plc_alarm
    result = check_plc_alarm("PLC_pH", 2.0)
    assert result["alarm_level"] == "critical"

def test_forward_alarm():
    from rnd_warehouse_management.rnd_warehouse_management.plc_integration import forward_plc_alarm
    result = forward_plc_alarm("PLC_Temperature", 105.0, "critical")
    assert result["forwarded"] == True
    assert result["alarm_level"] == "critical"

def test_plc_sensor_types():
    from rnd_warehouse_management.rnd_warehouse_management.plc_integration import get_plc_sensor_types
    types = get_plc_sensor_types()
    assert len(types) == 4
    assert "PLC_Temperature" in types
    assert "PLC_pH" in types

def test_combined_dashboard():
    from rnd_warehouse_management.rnd_warehouse_management.plc_integration import get_combined_dashboard
    result = get_combined_dashboard()
    assert isinstance(result, dict)
    assert "arduino_sensors" in result or "error" not in result

def test_validate_plc_config_valid():
    from rnd_warehouse_management.rnd_warehouse_management.plc_integration import validate_plc_connection_config
    result = validate_plc_connection_config("192.168.1.100", 502, "ModbusTCP")
    assert result["valid"] == True

def test_validate_plc_config_invalid():
    from rnd_warehouse_management.rnd_warehouse_management.plc_integration import validate_plc_connection_config
    result = validate_plc_connection_config("999.999.999.999", 502)
    assert result["valid"] == False
    assert len(result["errors"]) > 0

if __name__ == "__main__":
    run_all_tests()
