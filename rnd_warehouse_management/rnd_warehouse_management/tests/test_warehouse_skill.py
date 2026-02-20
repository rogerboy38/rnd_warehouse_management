# tests/test_warehouse_skill.py
# Integration tests for Warehouse Intelligence Skill
# Run with: bench --site <site> run-tests --app rnd_warehouse_management --module test_warehouse_skill

from __future__ import unicode_literals

import frappe
from frappe.tests.utils import FrappeTestCase


class TestWarehouseAPI(FrappeTestCase):
    """
    Test the whitelisted server methods in warehouse_api.py
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = frappe.defaults.get_global_default("company")
        cls.test_item = cls._get_or_create_test_item()
        cls.test_warehouse = cls._get_or_create_test_warehouse()
        cls._seed_bin_data()

    @classmethod
    def _get_or_create_test_item(cls):
        item_code = "_TEST-WH-SKILL-001"
        if not frappe.db.exists("Item", item_code):
            item = frappe.get_doc({
                "doctype": "Item",
                "item_code": item_code,
                "item_name": "Test Warehouse Skill Item",
                "item_group": "All Item Groups",
                "stock_uom": "Nos",
                "is_stock_item": 1,
                "lead_time_days": 7,
            })
            item.insert(ignore_permissions=True)
        return item_code

    @classmethod
    def _get_or_create_test_warehouse(cls):
        wh_name = f"_Test WH Skill - {cls.company}"
        if not frappe.db.exists("Warehouse", wh_name):
            wh = frappe.get_doc({
                "doctype": "Warehouse",
                "warehouse_name": "_Test WH Skill",
                "company": cls.company,
                "warehouse_type": "Raw Material",
            })
            wh.insert(ignore_permissions=True)
            wh_name = wh.name
        return wh_name

    @classmethod
    def _seed_bin_data(cls):
        """Ensure a Bin record exists for test item/warehouse."""
        from erpnext.stock.utils import get_bin
        b = get_bin(cls.test_item, cls.test_warehouse)
        b.actual_qty = 100
        b.reserved_qty = 10
        b.projected_qty = 90
        b.db_update()
        frappe.db.commit()

    # ----- get_item_stock_locations -----

    def test_item_stock_locations_returns_data(self):
        from rnd_warehouse_management.api.warehouse import get_item_stock_locations
        result = get_item_stock_locations(self.test_item)
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0, "Should return at least one warehouse")

        row = result[0]
        self.assertIn("warehouse", row)
        self.assertIn("actual_qty", row)
        self.assertIn("available_qty", row)
        self.assertIn("warehouse_type", row)

    def test_item_stock_locations_missing_item_throws(self):
        from rnd_warehouse_management.api.warehouse import get_item_stock_locations
        self.assertRaises(frappe.ValidationError, get_item_stock_locations, "")

    # ----- get_kardex -----

    def test_kardex_returns_list(self):
        from rnd_warehouse_management.api.warehouse import get_kardex
        result = get_kardex(warehouse=self.test_warehouse)
        self.assertIsInstance(result, list)

    def test_kardex_with_item_filter(self):
        from rnd_warehouse_management.api.warehouse import get_kardex
        result = get_kardex(
            warehouse=self.test_warehouse,
            item_code=self.test_item,
        )
        self.assertIsInstance(result, list)
        for row in result:
            self.assertEqual(row["item_code"], self.test_item)

    def test_kardex_with_date_range(self):
        from rnd_warehouse_management.api.warehouse import get_kardex
        result = get_kardex(
            from_date="2020-01-01",
            to_date="2099-12-31",
        )
        self.assertIsInstance(result, list)

    def test_kardex_respects_limit(self):
        from rnd_warehouse_management.api.warehouse import get_kardex
        result = get_kardex(limit=5)
        self.assertTrue(len(result) <= 5)

    # ----- get_oos_risk_list -----

    def test_oos_risk_list_returns_list(self):
        from rnd_warehouse_management.api.warehouse import get_oos_risk_list
        result = get_oos_risk_list(company=self.company)
        self.assertIsInstance(result, list)

    def test_oos_risk_list_with_warehouse(self):
        from rnd_warehouse_management.api.warehouse import get_oos_risk_list
        result = get_oos_risk_list(
            company=self.company,
            warehouse=self.test_warehouse,
        )
        self.assertIsInstance(result, list)

    def test_oos_risk_list_missing_company_throws(self):
        from rnd_warehouse_management.api.warehouse import get_oos_risk_list
        self.assertRaises(frappe.ValidationError, get_oos_risk_list, "")

    def test_oos_risk_list_row_shape(self):
        from rnd_warehouse_management.api.warehouse import get_oos_risk_list
        result = get_oos_risk_list(company=self.company, include_zero_demand=True)
        if result:
            row = result[0]
            expected_keys = [
                "item_code", "item_name", "warehouse",
                "available_qty", "daily_demand", "days_of_supply",
                "lead_time_days", "status",
            ]
            for key in expected_keys:
                self.assertIn(key, row, f"Missing key: {key}")
            self.assertIn(row["status"], ["OOS", "AT_RISK", "BELOW_REORDER"])

    # ----- get_warehouses_by_type -----

    def test_warehouses_by_type_returns_list(self):
        from rnd_warehouse_management.api.warehouse import get_warehouses_by_type
        result = get_warehouses_by_type(company=self.company)
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)

    def test_warehouses_by_type_filtered(self):
        from rnd_warehouse_management.api.warehouse import get_warehouses_by_type
        result = get_warehouses_by_type(
            company=self.company,
            warehouse_type="Raw Material",
        )
        self.assertIsInstance(result, list)
        for wh in result:
            self.assertEqual(wh["warehouse_type"], "Raw Material")


class TestWarehouseSkill(FrappeTestCase):
    """
    Test the WarehouseSkill class (agent-side dispatcher).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = frappe.defaults.get_global_default("company")
        # Reuse the same seeded data from TestWarehouseAPI

    def _get_skill(self):
        # Import from wherever the skill lives in your project
        from raven_ai_agent.skills.warehouse import WarehouseSkill
        return WarehouseSkill()

    def test_skill_has_tools(self):
        skill = self._get_skill()
        tools = skill.get_tools()
        self.assertIsInstance(tools, list)
        self.assertTrue(len(tools) >= 5)
        names = [t["name"] for t in tools]
        self.assertIn("get_item_stock_locations", names)
        self.assertIn("get_kardex", names)
        self.assertIn("get_oos_risk_list", names)
        self.assertIn("get_warehouse_status", names)
        self.assertIn("get_work_order_zone_status", names)

    def test_skill_tool_schema(self):
        skill = self._get_skill()
        for tool in skill.get_tools():
            self.assertIn("name", tool)
            self.assertIn("description", tool)
            self.assertIn("parameters", tool)
            self.assertIn("type", tool["parameters"])
            self.assertEqual(tool["parameters"]["type"], "object")

    def test_skill_dispatch_item_locations(self):
        skill = self._get_skill()
        result = skill.call("get_item_stock_locations", {
            "item_code": "_TEST-WH-SKILL-001",
        })
        self.assertIsInstance(result, list)

    def test_skill_dispatch_unknown_tool(self):
        skill = self._get_skill()
        result = skill.call("nonexistent_tool", {})
        self.assertIn("error", result)

    def test_skill_dispatch_oos_risk(self):
        skill = self._get_skill()
        result = skill.call("get_oos_risk_list", {
            "company": self.company,
        })
        self.assertIsInstance(result, list)

    def test_skill_dispatch_warehouses_by_type(self):
        skill = self._get_skill()
        result = skill.call("get_warehouses_by_type", {
            "company": self.company,
        })
        self.assertIsInstance(result, list)

    def test_skill_register(self):
        from raven_ai_agent.skills.warehouse import register_skill
        registry = {}
        register_skill(registry)
        self.assertIn("warehouse", registry)
        self.assertIsNotNone(registry["warehouse"].get_tools())
