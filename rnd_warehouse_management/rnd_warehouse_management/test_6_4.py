"""Phase 6.4 Test Plan: Real-Time Manufacturing Quality Bridge
Tests quality rules, evaluation, batch scoring, deviation logging, production status."""
import frappe
import json

def run_all_tests():
    results = []
    tests = [
        test_quality_rules_complete,
        test_evaluate_normal_temperature,
        test_evaluate_warning_ph,
        test_evaluate_critical_temperature,
        test_evaluate_unknown_parameter,
        test_production_quality_scoring,
        test_production_quality_all_nominal,
        test_production_quality_empty,
        test_batch_quality_score,
        test_batch_quality_no_readings,
        test_log_deviation_critical,
        test_log_deviation_warning,
        test_get_quality_rules_api,
        test_get_active_work_orders,
        test_get_production_status,
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
    print(f"\n=== Phase 6.4 Results: {passed}/{len(results)} passed ===")
    return results

def test_quality_rules_complete():
    from rnd_warehouse_management.rnd_warehouse_management.manufacturing_quality_bridge import DEFAULT_QUALITY_RULES
    assert len(DEFAULT_QUALITY_RULES) == 4
    for name in ["temperature", "ph", "brix", "humidity"]:
        assert name in DEFAULT_QUALITY_RULES, f"Missing {name}"
        rule = DEFAULT_QUALITY_RULES[name]
        for key in ["warning_low", "warning_high", "critical_low", "critical_high", "nominal", "weight"]:
            assert key in rule, f"{name} missing {key}"

def test_evaluate_normal_temperature():
    from rnd_warehouse_management.rnd_warehouse_management.manufacturing_quality_bridge import evaluate_quality_reading
    result = evaluate_quality_reading("temperature", 25.0)
    assert result["level"] == "normal"
    assert result["deviation"] == 0.0

def test_evaluate_warning_ph():
    from rnd_warehouse_management.rnd_warehouse_management.manufacturing_quality_bridge import evaluate_quality_reading
    result = evaluate_quality_reading("ph", 4.0)
    assert result["level"] == "warning", f"Expected warning, got {result['level']}"

def test_evaluate_critical_temperature():
    from rnd_warehouse_management.rnd_warehouse_management.manufacturing_quality_bridge import evaluate_quality_reading
    result = evaluate_quality_reading("temperature", 50.0)
    assert result["level"] == "critical"

def test_evaluate_unknown_parameter():
    from rnd_warehouse_management.rnd_warehouse_management.manufacturing_quality_bridge import evaluate_quality_reading
    result = evaluate_quality_reading("unknown_param", 42)
    assert result["level"] == "unknown"

def test_production_quality_scoring():
    from rnd_warehouse_management.rnd_warehouse_management.manufacturing_quality_bridge import evaluate_production_quality
    readings = [
        {"parameter": "temperature", "value": 25.0},
        {"parameter": "ph", "value": 7.0}
    ]
    result = evaluate_production_quality(readings)
    assert result["score"] == 100.0
    assert result["level"] == "normal"
    assert result["parameters_checked"] == 2

def test_production_quality_all_nominal():
    from rnd_warehouse_management.rnd_warehouse_management.manufacturing_quality_bridge import evaluate_production_quality
    readings = [
        {"parameter": "temperature", "value": 25.0},
        {"parameter": "ph", "value": 7.0},
        {"parameter": "brix", "value": 45.0},
        {"parameter": "humidity", "value": 50.0}
    ]
    result = evaluate_production_quality(readings)
    assert result["score"] == 100.0
    assert result["level"] == "normal"

def test_production_quality_empty():
    from rnd_warehouse_management.rnd_warehouse_management.manufacturing_quality_bridge import evaluate_production_quality
    result = evaluate_production_quality([])
    assert result["level"] == "no_data"

def test_batch_quality_score():
    from rnd_warehouse_management.rnd_warehouse_management.manufacturing_quality_bridge import calculate_batch_quality_score
    readings = [
        {"parameter": "temperature", "value": 26.0},
        {"parameter": "ph", "value": 6.8}
    ]
    result = calculate_batch_quality_score("BATCH-001", json.dumps(readings))
    assert result["batch_id"] == "BATCH-001"
    assert result["score"] is not None
    assert result["score"] > 90

def test_batch_quality_no_readings():
    from rnd_warehouse_management.rnd_warehouse_management.manufacturing_quality_bridge import calculate_batch_quality_score
    result = calculate_batch_quality_score("BATCH-002")
    assert result["level"] == "no_data"

def test_log_deviation_critical():
    from rnd_warehouse_management.rnd_warehouse_management.manufacturing_quality_bridge import log_process_deviation
    result = log_process_deviation("WO-001", "temperature", 50.0, "critical")
    assert result["logged"] == True
    assert result["recommendation"] == "Production hold recommended"

def test_log_deviation_warning():
    from rnd_warehouse_management.rnd_warehouse_management.manufacturing_quality_bridge import log_process_deviation
    result = log_process_deviation("WO-001", "ph", 4.2, "warning")
    assert result["logged"] == True
    assert result["recommendation"] == "Monitor closely"

def test_get_quality_rules_api():
    from rnd_warehouse_management.rnd_warehouse_management.manufacturing_quality_bridge import get_quality_rules
    rules = get_quality_rules()
    assert isinstance(rules, dict)
    assert len(rules) == 4

def test_get_active_work_orders():
    from rnd_warehouse_management.rnd_warehouse_management.manufacturing_quality_bridge import get_active_work_orders_for_zone
    result = get_active_work_orders_for_zone()
    assert isinstance(result, list)

def test_get_production_status():
    from rnd_warehouse_management.rnd_warehouse_management.manufacturing_quality_bridge import get_production_status
    result = get_production_status()
    assert isinstance(result, dict)
    assert "active_work_orders" in result or "error" in result

if __name__ == "__main__":
    run_all_tests()
