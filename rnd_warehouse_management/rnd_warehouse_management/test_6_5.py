"""Phase 6.5 Test Plan: Sensor Skill Package Build
Tests DocType existence, field structure, skill package assembly,
validation logic, and default skill library scaffolding."""
import frappe


def run_all_tests():
    results = []
    tests = [
        test_sensor_skill_doctype_exists,
        test_sensor_skill_required_fields,
        test_sensor_skill_code_field_types,
        test_sensor_skill_float_fields,
        test_skill_package_build,
        test_skill_package_min_max_validation,
        test_skill_package_defaults,
        test_multiple_sensor_types,
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
    print(f"\n=== Phase 6.5 Results: {passed}/{len(results)} passed ===")
    return results


# ── DocType meta checks ───────────────────────────────────────────────────────

def test_sensor_skill_doctype_exists():
    """Sensor Skill DocType must be registered in Frappe."""
    meta = frappe.get_meta("Sensor Skill")
    assert meta is not None, "Sensor Skill DocType not found"
    assert meta.name == "Sensor Skill"


def test_sensor_skill_required_fields():
    """Check that all spec-required fieldnames are present."""
    meta = frappe.get_meta("Sensor Skill")
    fieldnames = {f.fieldname for f in meta.fields}
    required = {
        "sensor_type", "arduino_sketch", "python_config",
        "wiring_instructions", "calibration_procedure",
        "min_value", "max_value", "version"
    }
    missing = required - fieldnames
    assert not missing, f"Missing fields: {missing}"


def test_sensor_skill_code_field_types():
    """arduino_sketch and python_config must be Code fields."""
    meta = frappe.get_meta("Sensor Skill")
    field_map = {f.fieldname: f for f in meta.fields}
    assert field_map["arduino_sketch"].fieldtype == "Code", "arduino_sketch must be Code"
    assert field_map["python_config"].fieldtype == "Code", "python_config must be Code"


def test_sensor_skill_float_fields():
    """min_value and max_value must be Float fields."""
    meta = frappe.get_meta("Sensor Skill")
    field_map = {f.fieldname: f for f in meta.fields}
    assert field_map["min_value"].fieldtype == "Float", "min_value must be Float"
    assert field_map["max_value"].fieldtype == "Float", "max_value must be Float"


# ── Document / business logic checks ─────────────────────────────────────────

def _make_skill(sensor_type, **kwargs):
    """Helper: create a transient (unsaved) Sensor Skill doc."""
    data = {
        "doctype": "Sensor Skill",
        "sensor_type": sensor_type,
        "version": kwargs.get("version", "1.0"),
        "min_value": kwargs.get("min_value", 0.0),
        "max_value": kwargs.get("max_value", 100.0),
        "arduino_sketch": kwargs.get("arduino_sketch", "void setup(){} void loop(){}"),
        "python_config": kwargs.get("python_config", "SENSOR_PIN = 4\nINTERVAL = 5"),
        "wiring_instructions": kwargs.get("wiring_instructions", "VCC→3.3V, GND→GND"),
        "calibration_procedure": kwargs.get("calibration_procedure", "Two-point calibration."),
    }
    return frappe.get_doc(data)


def test_skill_package_build():
    """build_skill_package() must return a dict with all 8 keys."""
    doc = _make_skill(
        "_test_dht22",
        arduino_sketch="#include <DHT.h>\nvoid setup(){}\nvoid loop(){}",
        python_config="SENSOR_TYPE = 'DHT22'\nPIN = 4",
        wiring_instructions="DATA to D4, VCC to 3.3V, GND to GND",
        calibration_procedure="Factory-calibrated – no field calibration required.",
        min_value=-40.0,
        max_value=80.0,
        version="2.1",
    )
    pkg = doc.build_skill_package()
    assert isinstance(pkg, dict), "build_skill_package must return a dict"
    expected_keys = {
        "sensor_type", "version", "min_value", "max_value",
        "arduino_sketch", "python_config",
        "wiring_instructions", "calibration_procedure"
    }
    missing = expected_keys - set(pkg.keys())
    assert not missing, f"Skill package missing keys: {missing}"
    assert pkg["sensor_type"] == "_test_dht22"
    assert pkg["version"] == "2.1"
    assert pkg["min_value"] == -40.0
    assert pkg["max_value"] == 80.0
    assert "DHT" in pkg["arduino_sketch"]
    assert "DHT22" in pkg["python_config"]


def test_skill_package_min_max_validation():
    """Validate() should raise when min_value >= max_value."""
    doc = _make_skill("_test_bad_range", min_value=100.0, max_value=10.0)
    try:
        doc.validate()
        assert False, "Expected validation error for min_value >= max_value"
    except Exception as e:
        assert "Min Value" in str(e) or "min" in str(e).lower(), (
            f"Wrong exception: {e}"
        )


def test_skill_package_defaults():
    """build_skill_package() must use '1.0' as default version when blank."""
    doc = _make_skill("_test_defaults", version=None)
    doc.version = None
    pkg = doc.build_skill_package()
    assert pkg["version"] == "1.0", f"Expected '1.0', got {pkg['version']!r}"


def test_multiple_sensor_types():
    """Verify package integrity across several common sensor types."""
    sensor_configs = [
        {"sensor_type": "_test_ds18b20", "min_value": -55.0, "max_value": 125.0},
        {"sensor_type": "_test_hcsr04",  "min_value": 2.0,   "max_value": 400.0},
        {"sensor_type": "_test_mq2",     "min_value": 300.0, "max_value": 10000.0},
    ]
    for cfg in sensor_configs:
        doc = _make_skill(**cfg)
        pkg = doc.build_skill_package()
        assert pkg["sensor_type"] == cfg["sensor_type"]
        assert pkg["min_value"] < pkg["max_value"], (
            f"min/max inverted for {cfg['sensor_type']}"
        )


if __name__ == "__main__":
    run_all_tests()
