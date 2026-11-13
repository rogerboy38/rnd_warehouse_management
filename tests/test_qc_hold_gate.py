"""TASKS-337 item 6, DB-free: the QC hold gate on Stock Entry submit."""

import json
import os
import sys
import types
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
PKG = os.path.join(ROOT, "rnd_warehouse_management")

from rnd_warehouse_management.rnd_warehouse_management import qc_hold_gate as g  # noqa: E402


def row(s=None, t=None, batch=None, bundle=None, item="IT"):
	return {"item_code": item, "s_warehouse": s, "t_warehouse": t, "batch_no": batch, "serial_and_batch_bundle": bundle}


class Doc(dict):
	flags = types.SimpleNamespace(ignore_validate=False)

	def __init__(self, rows, **kw):
		super().__init__(items=rows)
		self.flags = types.SimpleNamespace(ignore_validate=kw.get("ignore_validate", False))
		self.add_comment = mock.MagicMock()


def fake_frappe(hold=("QC",), amb_of=None, status_of=None, has_wh_field=True, has_batch_field=True,
		bundles=None, roles=("Stock User",), amb_doctype=True, batch_items=("IT",)):
	"""amb_of: batch -> Batch AMB name; status_of: Batch AMB name -> quality_status."""
	amb_of, status_of, bundles = amb_of or {}, status_of or {}, bundles or {}
	f = mock.MagicMock()

	def get_meta(dt):
		m = mock.MagicMock()
		m.has_field.side_effect = lambda fn: (has_wh_field if dt == "Warehouse" else has_batch_field)
		return m

	def get_value(dt, name, field=None, *a, **k):
		if dt == "Warehouse":
			return 1 if name in hold else 0
		if dt == "Item":
			return 1 if name in batch_items else 0
		if dt == "Batch":
			return amb_of.get(name)
		if dt == "Batch AMB":
			return status_of.get(name)

	f.get_meta.side_effect = get_meta
	f.db.get_value.side_effect = get_value
	f.db.exists.return_value = amb_doctype
	f.get_all.side_effect = lambda dt, filters=None, fields=None: [
		types.SimpleNamespace(batch_no=b) for b in bundles.get((filters or {}).get("parent"), [])
	]
	f.get_roles.return_value = list(roles)
	f.session.user = "u"
	f.throw.side_effect = RuntimeError
	return f


class TestGate(unittest.TestCase):
	def run_gate(self, doc, method="before_submit", **kw):
		f = fake_frappe(**kw)
		with mock.patch.object(g, "frappe", f), mock.patch.object(g, "_", lambda s: s):
			try:
				g.check_qc_hold_release(doc, method)
				return False, f
			except RuntimeError:
				return True, f

	LOT = {"amb_of": {"B1": "A1"}}

	def test_passed_lot_leaves(self):
		self.assertFalse(self.run_gate(Doc([row("QC", "FG", "B1")]), **self.LOT, status_of={"A1": "Passed"})[0])

	def test_every_other_status_is_refused(self):
		for st in ("Pending", "Failed", "Hold", "", None):
			self.assertTrue(self.run_gate(Doc([row("QC", "FG", "B1")]), **self.LOT, status_of={"A1": st})[0], st)

	def test_lot_without_batch_amb_is_refused(self):
		self.assertTrue(self.run_gate(Doc([row("QC", "FG", "B1")]))[0])

	def test_site_without_the_batch_link_field_refuses_a_held_lot(self):
		self.assertTrue(self.run_gate(Doc([row("QC", "FG", "B1")]), **self.LOT, has_batch_field=False)[0])

	def test_batch_tracked_row_naming_no_lot_is_refused(self):
		# ERPNext would pick the lot itself while posting the ledger, after this hook
		refused, f = self.run_gate(Doc([row("QC", "FG")]))
		self.assertTrue(refused)
		self.assertIn("no lot is named", f.throw.call_args.args[0])

	def test_row_of_an_item_that_is_not_batch_tracked_is_not_judged(self):
		self.assertFalse(self.run_gate(Doc([row("QC", "FG", item="PLAIN")]))[0])

	def test_transfer_between_two_hold_warehouses_is_allowed(self):
		self.assertFalse(self.run_gate(Doc([row("QC", "QC2", "B1")]), hold=("QC", "QC2"), **self.LOT,
			status_of={"A1": "Failed"})[0])

	def test_return_into_hold_is_allowed(self):
		self.assertFalse(self.run_gate(Doc([row("FG", "QC", "B1")]), **self.LOT, status_of={"A1": "Failed"})[0])

	def test_manufacture_consumption_from_hold_is_judged(self):
		self.assertTrue(self.run_gate(Doc([row("QC", None, "B1"), row(None, "FG", "B9")]), **self.LOT,
			status_of={"A1": "Pending"})[0])

	def test_finished_item_row_and_receipts_are_untouched(self):
		self.assertFalse(self.run_gate(Doc([row(None, "QC", "B1")]), **self.LOT)[0])

	def test_bundle_batches_are_judged(self):
		self.assertTrue(self.run_gate(Doc([row("QC", "FG", None, "SBB-1")]), bundles={"SBB-1": ["B1", "B2"]},
			amb_of={"B1": "A1", "B2": "A2"}, status_of={"A1": "Passed", "A2": "Failed"})[0])
		self.assertFalse(self.run_gate(Doc([row("QC", "FG", None, "SBB-1")]), bundles={"SBB-1": ["B1", "B2"]},
			amb_of={"B1": "A1", "B2": "A2"}, status_of={"A1": "Passed", "A2": "Passed"})[0])

	def test_inert_until_a_warehouse_is_flagged_or_the_field_exists(self):
		self.assertFalse(self.run_gate(Doc([row("QC", "FG", "B1")]), hold=())[0])
		self.assertFalse(self.run_gate(Doc([row("QC", "FG", "B1")]), has_wh_field=False)[0])

	def test_override_role_passes_and_is_recorded(self):
		d = Doc([row("QC", "FG", "B1")])
		refused, f = self.run_gate(d, **self.LOT, status_of={"A1": "Failed"}, roles=("Stock User", g.OVERRIDE_ROLE))
		self.assertFalse(refused)
		d.add_comment.assert_called_once()
		self.assertIn("B1", d.add_comment.call_args.args[1])

	def test_backstop_on_submit_runs_only_when_validation_was_skipped(self):
		self.assertFalse(self.run_gate(Doc([row("QC", "FG", "B1")]), "on_submit", **self.LOT)[0])
		self.assertTrue(self.run_gate(Doc([row("QC", "FG", "B1")], ignore_validate=True), "on_submit", **self.LOT)[0])

	def test_message_names_lot_and_warehouse_not_more(self):
		f = fake_frappe(**self.LOT, status_of={"A1": "Failed"})
		with mock.patch.object(g, "frappe", f), mock.patch.object(g, "_", lambda s: s):
			with self.assertRaises(RuntimeError):
				g.check_qc_hold_release(Doc([row("QC", "FG", "B1")]), "before_submit")
		msg = f.throw.call_args.args[0]
		self.assertIn("B1 (QC)", msg)
		self.assertIn("Failed", msg)


class TestShipping(unittest.TestCase):
	def test_custom_field_fixture_row(self):
		rows = json.load(open(os.path.join(PKG, "fixtures", "custom_field.json"), encoding="utf-8"))
		(r,) = [x for x in rows if x["name"] == "Warehouse-custom_qc_hold"]
		self.assertEqual((r["dt"], r["fieldname"], r["fieldtype"], r["module"]), ("Warehouse", g.HOLD_FIELD, "Check", "RND"))

	def test_override_role_ships_and_is_in_the_fixture_filter(self):
		roles = json.load(open(os.path.join(PKG, "fixtures", "role.json"), encoding="utf-8"))
		self.assertIn(g.OVERRIDE_ROLE, [r["name"] for r in roles])
		self.assertIn(g.OVERRIDE_ROLE, open(os.path.join(PKG, "hooks.py"), encoding="utf-8").read())

	def test_stock_entry_hooks_call_the_gate(self):
		src = open(os.path.join(PKG, "rnd_warehouse_management", "stock_entry.py"), encoding="utf-8").read()
		self.assertEqual(src.count("check_qc_hold_release(doc, method)"), 2)


if __name__ == "__main__":
	unittest.main()
