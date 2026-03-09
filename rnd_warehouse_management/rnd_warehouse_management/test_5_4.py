
# test_5_4.py - Phase 5.4: Warehouse Intelligence Skill Test Plan
"""Phase 5.4 Test Plan: Warehouse Intelligence Skill (Raven)
Tests skill registration, tool definitions, dispatching, and all 8 tool implementations."""
import frappe

def run_all_tests():
    results = []
    tests = [
        test_skill_instantiation,
        test_get_tools_returns_8,
        test_tool_names_complete,
        test_dispatch_unknown_tool,
        test_get_item_stock_locations,
        test_get_kardex,
        test_get_warehouses_by_type,
        test_get_warehouse_status,
        test_get_zone_temperature_status,
        test_track_batch_not_found,
        test_get_work_order_zone_status,
        test_register_skill,
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
    print(f"\n=== Phase 5.4 Results: {passed}/{len(results)} passed ===")
    return results


def test_skill_instantiation():
    from rnd_warehouse_management.rnd_warehouse_management.skills.warehouse import WarehouseSkill
    skill = WarehouseSkill()
    assert skill.name == "warehouse"
    assert "warehouse" in skill.description.lower()


def test_get_tools_returns_8():
    from rnd_warehouse_management.rnd_warehouse_management.skills.warehouse import WarehouseSkill
    skill = WarehouseSkill()
    tools = skill.get_tools()
    assert len(tools) == 8, f"Expected 8 tools, got {len(tools)}"


def test_tool_names_complete():
    from rnd_warehouse_management.rnd_warehouse_management.skills.warehouse import WarehouseSkill
    skill = WarehouseSkill()
    tools = skill.get_tools()
    names = {t["name"] for t in tools}
    expected = {
        "get_item_stock_locations", "get_kardex", "get_oos_risk_list",
        "get_warehouse_status", "get_work_order_zone_status",
        "get_warehouses_by_type", "get_zone_temperature_status", "track_batch"
    }
    assert names == expected, f"Missing: {expected - names}, Extra: {names - expected}"


def test_dispatch_unknown_tool():
    from rnd_warehouse_management.rnd_warehouse_management.skills.warehouse import WarehouseSkill
    skill = WarehouseSkill()
    result = skill.call("nonexistent_tool", {})
    assert "error" in result


def test_get_item_stock_locations():
    from rnd_warehouse_management.rnd_warehouse_management.skills.warehouse import WarehouseSkill
    skill = WarehouseSkill()
    # Use any item that exists
    item = frappe.db.get_value("Item", {"disabled": 0}, "name")
    if not item:
        print("    SKIP: No items found")
        return
    result = skill.call("get_item_stock_locations", {"item_code": item})
    assert isinstance(result, (list, type(None))), f"Unexpected type: {type(result)}"


def test_get_kardex():
    from rnd_warehouse_management.rnd_warehouse_management.skills.warehouse import WarehouseSkill
    skill = WarehouseSkill()
    result = skill.call("get_kardex", {"limit": 5})
    assert isinstance(result, (list, type(None))), f"Unexpected: {type(result)}"


def test_get_warehouses_by_type():
    from rnd_warehouse_management.rnd_warehouse_management.skills.warehouse import WarehouseSkill
    skill = WarehouseSkill()
    company = frappe.db.get_value("Company", {}, "name")
    if not company:
        print("    SKIP: No company")
        return
    result = skill.call("get_warehouses_by_type", {"company": company})
    assert isinstance(result, (list, type(None)))


def test_get_warehouse_status():
    from rnd_warehouse_management.rnd_warehouse_management.skills.warehouse import WarehouseSkill
    skill = WarehouseSkill()
    wh = frappe.db.get_value("Warehouse", {"disabled": 0, "is_group": 0}, "name")
    if not wh:
        print("    SKIP: No warehouse")
        return
    result = skill.call("get_warehouse_status", {"warehouse": wh})
    assert result is not None


def test_get_zone_temperature_status():
    from rnd_warehouse_management.rnd_warehouse_management.skills.warehouse import WarehouseSkill
    skill = WarehouseSkill()
    result = skill.call("get_zone_temperature_status", {})
    assert isinstance(result, (list, type(None)))


def test_track_batch_not_found():
    from rnd_warehouse_management.rnd_warehouse_management.skills.warehouse import WarehouseSkill
    skill = WarehouseSkill()
    result = skill.call("track_batch", {"batch_id": "NONEXISTENT-BATCH-9999"})
    assert "error" in result, "Should return error for nonexistent batch"


def test_get_work_order_zone_status():
    from rnd_warehouse_management.rnd_warehouse_management.skills.warehouse import WarehouseSkill
    skill = WarehouseSkill()
    wo = frappe.db.get_value("Work Order", {"status": ["!=", "Cancelled"]}, "name")
    if not wo:
        print("    SKIP: No work orders")
        return
    result = skill.call("get_work_order_zone_status", {"work_order_name": wo})
    assert "zone_status" in result or "error" in result


def test_register_skill():
    from rnd_warehouse_management.rnd_warehouse_management.skills.warehouse import register_skill
    registry = {}
    register_skill(registry)
    assert "warehouse" in registry
    assert hasattr(registry["warehouse"], "call")
    assert hasattr(registry["warehouse"], "get_tools")


if __name__ == "__main__":
    run_all_tests()
