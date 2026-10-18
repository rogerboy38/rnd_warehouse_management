# Tests for the hourly update_zone_status job (v2.1.1): it must not re-save Work Orders.
# Run with: bench --site <site> run-tests --app rnd_warehouse_management
#           --module rnd_warehouse_management.rnd_warehouse_management.tests.test_zone_status_task
#
# Fixtures are _T182-named rows written with db_insert inside each test (no hooks, no submit) and are removed by
# the test runner's rollback. While the job runs, frappe.db.commit is stubbed (the job commits once in scheduler
# context) and frappe.log_error is captured, so nothing the job does on this site can outlive the rollback.

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import get_datetime

from rnd_warehouse_management.rnd_warehouse_management import work_order as wo_module
from rnd_warehouse_management.rnd_warehouse_management.tasks import update_zone_status

PAST = "2026-01-01 00:00:00"
WAREHOUSE = "_T182 Stores"


def _make_bin(item_code, qty):
	frappe.get_doc({"doctype": "Bin", "item_code": item_code, "warehouse": WAREHOUSE, "actual_qty": qty}).db_insert()


def _make_bom(name, rm_item, rm_qty):
	bom = frappe.get_doc({"doctype": "BOM", "name": name, "item": f"{name}-FG", "quantity": 1, "docstatus": 1,
		"is_active": 1, "items": [{"item_code": rm_item, "item_name": rm_item, "qty": rm_qty, "source_warehouse": WAREHOUSE}]})
	bom.db_insert()
	for idx, row in enumerate(bom.items, start=1):
		row.update({"parent": name, "parenttype": "BOM", "parentfield": "items", "idx": idx})
		row.db_insert()


def _make_work_order(name, bom_no, qty=1):
	"""A draft Work Order whose zone fields are already correct for the current Bin quantities."""
	wo = frappe.get_doc({"doctype": "Work Order", "name": name, "production_item": f"{bom_no}-FG", "bom_no": bom_no,
		"qty": qty, "status": "Not Started", "docstatus": 0})
	wo_module.update_material_requirements(wo)
	wo.custom_last_zone_update = PAST
	wo.creation = wo.modified = PAST
	wo.db_insert()
	return name


def _state(name):
	row = frappe.db.get_value("Work Order", name, list(wo_module.ZONE_FIELDS) + ["custom_last_zone_update", "modified"],
		as_dict=True)
	row["versions"] = frappe.db.count("Version", {"ref_doctype": "Work Order", "docname": name})
	return row


def _run_job():
	"""Run the job with commit stubbed and log_error captured; returns (commit mock, log_error mock)."""
	with patch.object(frappe.db, "commit") as commit, patch.object(frappe, "log_error") as log_error:
		update_zone_status()
	return commit, log_error


def _t182_errors(log_error):
	return [c.kwargs.get("reference_name") for c in log_error.call_args_list
		if str(c.kwargs.get("reference_name") or "").startswith("_T182")]


class TestZoneStatusTask(IntegrationTestCase):
	def test_a_unchanged_work_order_is_not_written(self):
		_make_bin("_T182-RM-A", 10)
		_make_bom("_T182-BOM-A", "_T182-RM-A", 2)
		name = _make_work_order("_T182-WO-A", "_T182-BOM-A")
		before = _state(name)
		self.assertEqual(before["custom_current_zone_status"], "Green Zone")

		commit, log_error = _run_job()

		after = _state(name)
		self.assertEqual(after, before)  # zone fields, stamp, modified and Version count all unchanged
		self.assertEqual(get_datetime(after["custom_last_zone_update"]), get_datetime(PAST))
		self.assertEqual(after["versions"], 0)
		self.assertEqual(commit.call_count, 1)
		self.assertEqual(_t182_errors(log_error), [])

	def test_b_zone_flip_writes_fields_without_save(self):
		_make_bin("_T182-RM-B", 10)
		_make_bom("_T182-BOM-B", "_T182-RM-B", 2)
		name = _make_work_order("_T182-WO-B", "_T182-BOM-B")
		before = _state(name)
		self.assertEqual(before["custom_current_zone_status"], "Green Zone")
		frappe.db.set_value("Bin", {"item_code": "_T182-RM-B", "warehouse": WAREHOUSE}, "actual_qty", 0,
			update_modified=False)

		with patch.object(frappe.model.document.Document, "save") as save:
			commit, log_error = _run_job()

		after = _state(name)
		self.assertEqual(after["custom_current_zone_status"], "Red Zone")
		self.assertEqual(after["custom_zone_status_color"], "#dc3545")
		self.assertEqual(float(after["custom_material_completion_percentage"]), 0.0)
		missing = frappe.parse_json(after["custom_missing_materials_json"])
		self.assertEqual([(m["item_code"], m["missing_qty"]) for m in missing], [("_T182-RM-B", 2.0)])
		self.assertGreater(get_datetime(after["custom_last_zone_update"]), get_datetime(PAST))
		self.assertEqual(after["modified"], before["modified"])  # update_modified=False
		self.assertEqual(after["versions"], 0)
		save.assert_not_called()
		self.assertEqual(_t182_errors(log_error), [])

	def test_c_one_failing_work_order_does_not_stop_the_others(self):
		_make_bin("_T182-RM-C", 10)
		_make_bom("_T182-BOM-C", "_T182-RM-C", 2)
		bad = _make_work_order("_T182-WO-C1", "_T182-BOM-C")
		good = _make_work_order("_T182-WO-C2", "_T182-BOM-C")
		frappe.db.set_value("Bin", {"item_code": "_T182-RM-C", "warehouse": WAREHOUSE}, "actual_qty", 0,
			update_modified=False)
		real = wo_module.update_material_requirements

		def flaky(doc):
			if doc.name == bad:
				raise RuntimeError("_T182 simulated failure")
			return real(doc)

		with patch.object(wo_module, "update_material_requirements", side_effect=flaky):
			commit, log_error = _run_job()

		self.assertEqual(_t182_errors(log_error), [bad])
		self.assertEqual(_state(bad)["custom_current_zone_status"], "Green Zone")  # untouched
		self.assertEqual(_state(good)["custom_current_zone_status"], "Red Zone")  # still updated
		self.assertEqual(commit.call_count, 1)
