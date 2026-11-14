"""TASKS-337 item 6 / TASKS-342, DB-free: the QC hold gate. Every test here is built so that it FAILS when the gate
body is removed (`check_qc_hold_release` returning nothing) or when the hook is unhooked: a test that allows
something also asserts the gate's verdict for it (the function returns one) and pairs it with the same entry
refused when one thing is changed. The real dispatch (doc events, ledger, rollback) runs on a scratch site; see the
reply of TASKS-342."""

import importlib
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

hooks = importlib.import_module("rnd_warehouse_management.hooks")


def row(s=None, t=None, batch=None, bundle=None, item="IT", qty=5):
	return {"item_code": item, "s_warehouse": s, "t_warehouse": t, "batch_no": batch,
		"serial_and_batch_bundle": bundle, "qty": qty}


class Flags(dict):
	def __init__(self, ignore_validate=False):
		super().__init__()
		self.ignore_validate = ignore_validate


class Doc(dict):
	"""A Stock Entry as the gate sees it. `action` is Frappe's private `_action`."""

	def __init__(self, rows, action="submit", ignore_validate=False, name="SE-1"):
		super().__init__(items=rows)
		self._action = action
		self.name = name
		self.flags = Flags(ignore_validate)
		self.add_comment = mock.MagicMock()


def fake_frappe(hold=("QC",), amb_of=None, status_of=None, has_wh_field=True, has_batch_field=True,
		bundles=None, roles=("Stock User",), amb_doctype=True, batch_items=("IT",)):
	"""amb_of: batch -> Batch AMB name; status_of: Batch AMB name -> quality_status; bundles: bundle -> [(batch, qty)]."""
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
		types.SimpleNamespace(batch_no=b, qty=q, get=lambda k, d=None, _q=q: _q if k == "qty" else d)
		for b, q in bundles.get((filters or {}).get("parent"), [])
	]
	f.get_roles.return_value = list(roles)
	f.session.user = "u@x"
	f.utils.flt = float
	f.throw.side_effect = RuntimeError
	return f


class GateCase(unittest.TestCase):
	LOT = {"amb_of": {"B1": "A1"}}

	def gate(self, doc, method="before_validate", **kw):
		"""-> (verdict dict or None, refused?, fake frappe)"""
		f = fake_frappe(**kw)
		with mock.patch.object(g, "frappe", f), mock.patch.object(g, "_", lambda s: s):
			try:
				return g.check_qc_hold_release(doc, method), False, f
			except RuntimeError:
				return None, True, f

	def leaves(self, doc, method="before_validate", **kw):
		"""The gate JUDGED the entry and let it through: a verdict with nothing refused."""
		v, refused, f = self.gate(doc, method, **kw)
		self.assertFalse(refused, "refused")
		self.assertIsNotNone(v, "the gate returned no verdict: it did not run")
		self.assertEqual(v["refused"], [])
		return v

	def refused(self, doc, method="before_validate", **kw):
		v, refused, f = self.gate(doc, method, **kw)
		self.assertTrue(refused, "not refused")
		return f


class TestSubmit(GateCase):
	def test_passed_lot_leaves_and_the_same_lot_failed_does_not(self):
		self.leaves(Doc([row("QC", "FG", "B1")]), **self.LOT, status_of={"A1": "Passed"})
		self.refused(Doc([row("QC", "FG", "B1")]), **self.LOT, status_of={"A1": "Failed"})

	def test_every_other_status_is_refused(self):
		for st in ("Pending", "Failed", "Hold", "", None):
			self.refused(Doc([row("QC", "FG", "B1")]), **self.LOT, status_of={"A1": st})

	def test_lot_without_batch_amb_is_refused_with_its_status_word(self):
		f = self.refused(Doc([row("QC", "FG", "B1")]))
		self.assertIn("no Batch AMB", f.throw.call_args.args[0])

	def test_site_without_the_batch_link_field_refuses_a_held_lot(self):
		self.refused(Doc([row("QC", "FG", "B1")]), **self.LOT, has_batch_field=False)

	def test_batch_tracked_row_naming_no_lot_is_refused_and_a_plain_item_is_not(self):
		f = self.refused(Doc([row("QC", "FG")]))
		self.assertIn("no lot is named", f.throw.call_args.args[0])
		v = self.leaves(Doc([row("QC", "FG", item="PLAIN")]))
		self.assertEqual(v["action"], "submit")

	def test_transfer_between_two_hold_warehouses_is_allowed_but_out_of_them_is_not(self):
		kw = dict(**self.LOT, status_of={"A1": "Failed"})
		self.leaves(Doc([row("QC", "QC2", "B1")]), hold=("QC", "QC2"), **kw)
		self.refused(Doc([row("QC", "FG", "B1")]), hold=("QC", "QC2"), **kw)

	def test_return_into_hold_is_allowed_but_the_reverse_move_is_not(self):
		kw = dict(**self.LOT, status_of={"A1": "Failed"})
		self.leaves(Doc([row("FG", "QC", "B1")]), **kw)
		self.refused(Doc([row("QC", "FG", "B1")]), **kw)

	def test_manufacture_consumption_from_hold_is_judged(self):
		kw = dict(**self.LOT, status_of={"A1": "Pending"})
		self.refused(Doc([row("QC", None, "B1"), row(None, "FG", "B9")]), **kw)
		self.leaves(Doc([row("QC", None, "B1"), row(None, "FG", "B9")]), **dict(self.LOT, status_of={"A1": "Passed"}))

	def test_finished_item_row_and_receipts_are_untouched(self):
		kw = dict(**self.LOT, status_of={"A1": "Failed"})
		self.leaves(Doc([row(None, "QC", "B1")]), **kw)
		self.refused(Doc([row("QC", None, "B1")]), **kw)

	def test_bundle_batches_are_judged_and_the_row_lot_is_not_counted_twice(self):
		amb = {"B1": "A1", "B2": "A2"}
		bundles = {"SBB-1": [("B1", 3), ("B2", 2)]}
		self.refused(Doc([row("QC", "FG", None, "SBB-1")]), bundles=bundles, amb_of=amb, status_of={"A1": "Passed", "A2": "Failed"})
		self.leaves(Doc([row("QC", "FG", None, "SBB-1")]), bundles=bundles, amb_of=amb, status_of={"A1": "Passed", "A2": "Passed"})
		d = Doc([row("QC", "FG", "B1", "SBB-1", qty=3)], action="cancel")
		d.flags.ignore_validate = False
		v, refused, f = self.gate(d, "before_cancel", hold=("FG",), bundles={"SBB-1": [("B1", 3)]}, amb_of={"B1": "A1"}, status_of={"A1": "Failed"},
			roles=("QC Hold Override",))
		self.assertIn("qty 3.0", d.add_comment.call_args.args[1])  # a lot listed by its row AND its bundle: 3, not 6

	def test_inert_until_a_warehouse_is_flagged_and_the_field_exists(self):
		kw = dict(**self.LOT, status_of={"A1": "Failed"})
		self.leaves(Doc([row("QC", "FG", "B1")]), hold=(), **kw)
		self.leaves(Doc([row("QC", "FG", "B1")]), has_wh_field=False, **kw)
		self.refused(Doc([row("QC", "FG", "B1")]), **kw)  # the same entry once flagged

	def test_message_names_lot_warehouse_and_status(self):
		f = self.refused(Doc([row("QC", "FG", "B1")]), **self.LOT, status_of={"A1": "Failed"})
		msg = f.throw.call_args.args[0]
		for needle in ("B1 (QC)", "Failed"):
			self.assertIn(needle, msg)

	def test_before_validate_judges_a_submit_only_not_a_plain_save(self):
		kw = dict(**self.LOT, status_of={"A1": "Failed"})
		v, refused, _f = self.gate(Doc([row("QC", "FG", "B1")], action="save"), "before_validate", **kw)
		self.assertFalse(refused)
		self.assertIsNone(v)
		self.refused(Doc([row("QC", "FG", "B1")], action="submit"), "before_validate", **kw)

	def test_second_line_on_submit_judges_even_without_ignore_validate(self):
		kw = dict(**self.LOT, status_of={"A1": "Failed"})
		self.refused(Doc([row("QC", "FG", "B1")]), "on_submit", **kw)
		self.leaves(Doc([row("QC", "FG", "B1")]), "on_submit", **dict(self.LOT, status_of={"A1": "Passed"}))


class TestCancel(GateCase):
	def test_cancel_of_an_entry_that_put_a_lot_into_hold_is_judged(self):
		receipt = lambda: Doc([row(None, "QC", "B1")], action="cancel")  # noqa: E731
		kw = dict(**self.LOT, hold=("QC",))
		f = self.refused(receipt(), "before_cancel", status_of={"A1": "Failed"}, **kw)
		self.assertIn("Cancelling this entry", f.throw.call_args.args[0])
		v = self.leaves(receipt(), "before_cancel", status_of={"A1": "Passed"}, **kw)
		self.assertEqual(v["action"], "cancel")

	def test_cancel_of_an_entry_that_took_a_lot_out_of_hold_returns_it_and_is_allowed(self):
		kw = dict(**self.LOT, status_of={"A1": "Failed"})
		self.leaves(Doc([row("QC", "FG", "B1")], action="cancel"), "before_cancel", **kw)
		self.refused(Doc([row(None, "QC", "B1")], action="cancel"), "before_cancel", **kw)

	def test_on_cancel_is_the_second_line_only_when_validation_was_skipped(self):
		kw = dict(**self.LOT, status_of={"A1": "Failed"})
		v, refused, _f = self.gate(Doc([row(None, "QC", "B1")], action="cancel", ignore_validate=False), "on_cancel", **kw)
		self.assertFalse(refused)
		self.assertIsNone(v)
		self.refused(Doc([row(None, "QC", "B1")], action="cancel", ignore_validate=True), "on_cancel", **kw)


class TestHeaderOnlyWarehouses(GateCase):
	"""TASKS-344 H-1: before_validate (the first line, not skipped by ignore_validate) runs before ERPNext's
	validate_warehouse gives the rows their warehouses from the header; the gate resolves them itself, for judging only."""

	def header_doc(self, purpose, frm=None, to=None, rows=None, **kw):
		d = Doc(rows if rows is not None else [row(None, None, "B1")], **kw)
		d.update({"purpose": purpose, "from_warehouse": frm, "to_warehouse": to})
		return d

	def test_header_only_issue_and_transfer_are_refused_at_the_first_line(self):
		kw = dict(**self.LOT, status_of={"A1": "Failed"})
		self.refused(self.header_doc("Material Issue", frm="QC"), "before_validate", **kw)
		self.refused(self.header_doc("Material Transfer", frm="QC", to="FG"), "before_validate", **kw)
		self.refused(self.header_doc("Material Issue", frm="QC", ignore_validate=True), "before_validate", **kw)

	def test_the_same_header_only_entries_with_a_passed_lot_leave(self):
		kw = dict(**self.LOT, status_of={"A1": "Passed"})
		v = self.leaves(self.header_doc("Material Issue", frm="QC"), "before_validate", **kw)
		self.assertEqual(v["action"], "submit")
		self.leaves(self.header_doc("Material Transfer", frm="QC", to="FG"), "before_validate", **kw)

	def test_purpose_rules_of_validate_warehouse_are_followed(self):
		kw = dict(**self.LOT, status_of={"A1": "Failed"})
		# a receipt never reads a source: a stray header source does not make it an outgoing move
		self.leaves(self.header_doc("Material Receipt", frm="QC", to="QC"), "before_validate", **kw)
		# a transfer between two hold warehouses stays allowed
		self.leaves(self.header_doc("Material Transfer", frm="QC", to="QC2"), "before_validate", hold=("QC", "QC2"), **dict(kw))
		# an issue ignores the header target
		self.refused(self.header_doc("Material Issue", frm="QC", to="QC2"), "before_validate", hold=("QC", "QC2"), **dict(kw))

	def test_manufacture_with_a_bom_consumes_from_the_header_source_and_receives_finished(self):
		kw = dict(**self.LOT, status_of={"A1": "Failed"})
		consumed = dict(row(None, None, "B1"), bom_no="BOM-1", is_finished_item=0)
		finished = dict(row(None, None, "B9"), bom_no="BOM-1", is_finished_item=1)
		self.refused(self.header_doc("Manufacture", frm="QC", to="FG", rows=[consumed, finished]), "before_validate", **kw)
		self.leaves(self.header_doc("Manufacture", frm="QC", to="FG", rows=[finished]), "before_validate", **kw)

	def test_judging_does_not_change_the_document(self):
		d = self.header_doc("Material Issue", frm="QC")
		g_rows = g.effective_rows(d)
		self.assertEqual(g_rows[0].get("s_warehouse"), "QC")
		self.assertIsNone(d["items"][0]["s_warehouse"])


class TestOverrideRecord(GateCase):
	def test_override_role_passes_and_records_status_quantity_and_warehouse_once(self):
		d = Doc([row("QC", "FG", "B1", qty=7)])
		kw = dict(**self.LOT, status_of={"A1": "Failed"}, roles=("Stock User", g.OVERRIDE_ROLE))
		v, refused, f = self.gate(d, "before_validate", **kw)
		self.assertFalse(refused)
		self.assertTrue(v["overridden"])
		# TASKS-344 H-4: at before_validate a document submitted in one call has a name but no row yet; the
		# Comment is written at on_submit, once
		d.add_comment.assert_not_called()
		self.gate(d, "on_submit", **kw)
		d.add_comment.assert_called_once()
		text = d.add_comment.call_args.args[1]
		for needle in ("u@x", "submit", "B1", "status Failed", "qty 7.0", "from QC"):
			self.assertIn(needle, text)
		self.gate(d, "on_submit", **kw)
		d.add_comment.assert_called_once()

	def test_a_submit_refused_later_leaves_no_override_comment_and_a_cancel_records_at_before_cancel(self):
		d = Doc([row("QC", "FG", "B1")])
		kw = dict(**self.LOT, status_of={"A1": "Failed"}, roles=(g.OVERRIDE_ROLE,))
		self.gate(d, "before_validate", **kw)
		self.gate(d, "before_submit", **kw)
		d.add_comment.assert_not_called()
		c = Doc([row(None, "QC", "B1")], action="cancel")
		self.gate(c, "before_cancel", **kw)
		c.add_comment.assert_called_once()

	def test_an_unlinked_lot_is_recorded_as_no_batch_amb(self):
		d = Doc([row("QC", "FG", "B1")])
		self.gate(d, "on_submit", roles=(g.OVERRIDE_ROLE,))
		self.assertIn("status no Batch AMB", d.add_comment.call_args.args[1])

	def test_without_the_role_nothing_is_recorded(self):
		d = Doc([row("QC", "FG", "B1")])
		self.refused(d, **self.LOT, status_of={"A1": "Failed"})
		d.add_comment.assert_not_called()


class TestGroupWarehouse(unittest.TestCase):
	def wh(self, **kw):
		d = types.SimpleNamespace(name="WH-1", **kw)
		d.get = lambda k, default=None: getattr(d, k, default)
		return d

	def test_a_flagged_group_is_refused_with_what_to_do(self):
		f = mock.MagicMock()
		f.throw.side_effect = RuntimeError
		with mock.patch.object(g, "frappe", f), mock.patch.object(g, "_", lambda s: s):
			with self.assertRaises(RuntimeError):
				g.warn_group_flag(self.wh(custom_qc_hold=1, is_group=1))
			self.assertIn("leaf", f.throw.call_args.args[0].lower())
			f.throw.reset_mock()
			g.warn_group_flag(self.wh(custom_qc_hold=1, is_group=0))
			g.warn_group_flag(self.wh(custom_qc_hold=0, is_group=1))
			f.throw.assert_not_called()


class TestHoldFlagRoles(unittest.TestCase):
	"""Decision 94 (TASKS-349): who may set or clear `custom_qc_hold` on a Warehouse. Each test here fails when
	`check_hold_flag_change` is emptied or taken out of the Warehouse before_validate hook."""

	def wh(self, now, was=None, new=False):
		d = types.SimpleNamespace(name=None if new else "WH-1", custom_qc_hold=now, is_group=0)
		d.get = lambda k, default=None: getattr(d, k, default)
		d.is_new = lambda: new
		d._was = was
		return d

	def run_hook(self, d, roles, via_hooks=True, has_field=True):
		f = mock.MagicMock()
		f.get_roles.return_value = list(roles)
		f.PermissionError = PermissionError
		f.get_meta.return_value.has_field.return_value = has_field
		f.db.get_value.side_effect = lambda dt, name, field=None, *a, **k: d._was
		f.throw.side_effect = lambda msg, exc=None, **k: (_ for _ in ()).throw((exc or RuntimeError)(msg))
		with mock.patch.object(g, "frappe", f), mock.patch.object(g, "_", lambda s: s):
			if via_hooks:
				mod, _, fn = hooks.doc_events["Warehouse"]["before_validate"].rpartition(".")
				fnc = getattr(importlib.import_module(mod), fn)
				try:
					fnc(d, "before_validate")
					return "allowed", f
				except PermissionError:
					return "refused", f
			return g.check_hold_flag_change(d), f

	def test_the_two_roles_may_set_and_clear(self):
		for role in ("Quality Manager", "System Manager"):
			self.assertEqual(self.run_hook(self.wh(1, was=0), [role])[0], "allowed", role)
			self.assertEqual(self.run_hook(self.wh(0, was=1), [role])[0], "allowed", role)
			v, _f = self.run_hook(self.wh(1, was=0), [role], via_hooks=False)
			self.assertEqual((v["judged"], v["was"], v["now"]), (True, 0, 1))

	def test_administrator_holds_every_role_so_it_passes_as_system_manager(self):
		roles = ["Administrator", "System Manager", "Quality Manager", "Stock User", "QC Hold Override"]
		self.assertEqual(self.run_hook(self.wh(1, was=0), roles)[0], "allowed")

	def test_a_stock_user_is_refused_on_set_on_clear_and_on_insert(self):
		for label, d in (("set", self.wh(1, was=0)), ("clear", self.wh(0, was=1)), ("insert", self.wh(1, new=True))):
			self.assertEqual(self.run_hook(d, ["Stock User", "Item Manager"])[0], "refused", label)

	def test_the_override_role_alone_does_not_open_the_flag(self):
		self.assertEqual(self.run_hook(self.wh(0, was=1), [g.OVERRIDE_ROLE, "Stock User"])[0], "refused")

	def test_the_refusal_names_the_two_roles_and_says_what_it_does(self):
		d = self.wh(0, was=1)
		_r, f = self.run_hook(d, ["Stock User"])
		msg = f.throw.call_args.args[0]
		self.assertIn("Quality Manager", msg)
		self.assertIn("System Manager", msg)
		self.assertIn("clear", msg)

	def test_a_save_that_does_not_touch_the_flag_is_not_judged(self):
		for now, was in ((1, 1), (0, 0)):
			v, f = self.run_hook(self.wh(now, was=was), ["Stock User"], via_hooks=False)
			self.assertEqual((v["judged"], v["was"], v["now"]), (False, was, now))
			f.throw.assert_not_called()
		self.assertEqual(self.run_hook(self.wh(0, new=True), ["Stock User"])[0], "allowed")   # a new Warehouse without the flag

	def test_an_existing_warehouse_is_compared_with_the_database_not_with_the_loaded_copy(self):
		d = self.wh(0, was=1)
		_r, f = self.run_hook(d, ["Stock User"])
		f.db.get_value.assert_called_with("Warehouse", "WH-1", g.HOLD_FIELD)

	def test_without_the_field_on_the_site_the_hook_does_nothing(self):
		self.assertIsNone(self.run_hook(self.wh(1, was=0), ["Stock User"], via_hooks=False, has_field=False)[0])

	def test_the_hook_is_the_before_validate_of_a_warehouse_and_runs_before_the_group_check(self):
		"""before_validate runs for a save before Frappe honours `ignore_validate`: the refusal does not depend on it."""
		self.assertIn("before_validate", hooks.doc_events["Warehouse"])
		src = open(os.path.join(PKG, "rnd_warehouse_management", "warehouse.py"), encoding="utf-8").read()
		bv = src[src.index("def before_validate"):src.index("def before_save")]
		self.assertLess(bv.index("check_hold_flag_change"), bv.index("warn_group_flag"))
		self.assertNotIn("ignore_validate", bv.replace("`ignore_validate`", ""))


class TestWiring(GateCase):
	"""Through the real hooks.py and the real wrapper modules: unhook an event and its test fails."""

	def resolve(self, doctype, event):
		path = hooks.doc_events[doctype][event]
		mod, _, fn = path.rpartition(".")
		return getattr(importlib.import_module(mod), fn)

	def call(self, event, doc, **kw):
		f = fake_frappe(**kw)
		with mock.patch.object(g, "frappe", f), mock.patch.object(g, "_", lambda s: s):
			try:
				self.resolve("Stock Entry", event)(doc, event)
				return False
			except RuntimeError:
				return True

	def test_every_gate_event_is_hooked_and_reaches_the_gate(self):
		kw = dict(**self.LOT, status_of={"A1": "Failed"})
		self.assertTrue(self.call("before_validate", Doc([row("QC", "FG", "B1")]), **kw))
		self.assertTrue(self.call("on_submit", Doc([row("QC", "FG", "B1")]), **kw))
		self.assertTrue(self.call("before_cancel", Doc([row(None, "QC", "B1")], action="cancel"), **kw))
		self.assertTrue(self.call("on_cancel", Doc([row(None, "QC", "B1")], action="cancel", ignore_validate=True), **kw))

	def test_the_hooked_events_let_a_passed_entry_through_and_stop_the_same_entry_failed(self):
		for status, stops in (("Passed", False), ("Failed", True)):
			kw = dict(**self.LOT, status_of={"A1": status})
			self.assertEqual(self.call("before_validate", Doc([row("QC", "FG", "B1")]), **kw), stops)
			self.assertEqual(self.call("before_cancel", Doc([row(None, "QC", "B1")], action="cancel"), **kw), stops)

	def test_the_warehouse_hook_refuses_a_flagged_group(self):
		for event in ("before_save", "before_validate"):     # before_validate survives ignore_validate (TASKS-344 H-3)
			self.assertTrue(self.refuses_group(event), event)

	def refuses_group(self, event):
		path = hooks.doc_events["Warehouse"][event]
		mod, _, fn = path.rpartition(".")
		before_save = getattr(importlib.import_module(mod), fn)
		d = types.SimpleNamespace(name="WH-1", custom_qc_hold=1, is_group=1)
		d.get = lambda k, default=None: getattr(d, k, default)
		f = mock.MagicMock()
		f.throw.side_effect = RuntimeError
		with mock.patch.object(g, "frappe", f), mock.patch.object(g, "_", lambda s: s):
			try:
				before_save(d, event)
				return False
			except RuntimeError:
				return True


class TestShipping(unittest.TestCase):
	def test_custom_field_fixture_row_is_selected_by_the_hooks_fixture_filter(self):
		with open(os.path.join(PKG, "fixtures", "custom_field.json"), encoding="utf-8") as fh:
			rows = json.load(fh)
		(r,) = [x for x in rows if x["name"] == "Warehouse-custom_qc_hold"]
		self.assertEqual((r["dt"], r["fieldname"], r["fieldtype"]), ("Warehouse", g.HOLD_FIELD, "Check"))
		flt = [x for x in hooks.fixtures if x["doctype"] == "Custom Field"][0]["filters"]
		self.assertIn(["module", "=", r["module"]], flt)

	def test_override_role_row_is_selected_by_the_hooks_fixture_filter(self):
		with open(os.path.join(PKG, "fixtures", "role.json"), encoding="utf-8") as fh:
			roles = json.load(fh)
		self.assertIn(g.OVERRIDE_ROLE, [r["name"] for r in roles])
		flt = [x for x in hooks.fixtures if x["doctype"] == "Role"][0]["filters"]
		self.assertTrue(any(f[0] == "name" and f[1] == "in" and g.OVERRIDE_ROLE in f[2] for f in flt))


if __name__ == "__main__":
	unittest.main()
