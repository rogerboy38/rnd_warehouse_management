# Tests for the "Work Order Scheduling" workflow (v2.2.0).
# Run with: bench --site <site> run-tests --app rnd_warehouse_management
#           --module rnd_warehouse_management.rnd_warehouse_management.tests.test_work_order_workflow
#
# (a) and (e) read the state a `bench migrate` left (sync_fixtures + after_migrate): run them on a site that was
# migrated with this version. Test records are _T189-named and created inside each test (IntegrationTestCase commits
# in setUpClass), so the class rollback removes them. frappe.set_user is used only on users these tests create.

from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow, get_transitions
from frappe.tests import IntegrationTestCase

from rnd_warehouse_management.rnd_warehouse_management import workflow_utils

WORKFLOW = "Work Order Scheduling"
STATES = [("Draft", "0", "Manufacturing User"), ("Draft", "0", "Planeacion"), ("Draft", "0", "Manufacturing Manager"),
	("Scheduled", "1", "Planeacion"), ("Scheduled", "1", "Manufacturing Manager"), ("Cancelled", "2", "Planeacion")]
TRANSITIONS = [("Draft", "Schedule", "Scheduled", "Planeacion"), ("Draft", "Schedule", "Scheduled", "System Manager"),
	("Scheduled", "Cancel", "Cancelled", "Planeacion"), ("Scheduled", "Cancel", "Cancelled", "Manufacturing Manager")]
USERS = {
	"mu": ["Manufacturing User"],
	"mu-plan": ["Manufacturing User", "Planeacion"],
	"mu-mm": ["Manufacturing User", "Manufacturing Manager"],
	"plan-only": ["Planeacion"],
	"mm-only": ["Manufacturing Manager"],
}


def _user(key):
	email = f"_t189.{key}@example.com"
	if not frappe.db.exists("User", email):
		u = frappe.get_doc({"doctype": "User", "email": email, "first_name": f"_T189 {key}", "send_welcome_email": 0,
			"user_type": "System User"})
		u.flags.no_welcome_mail = True
		u.insert(ignore_permissions=True)
		u.add_roles(*USERS[key])
	return email


def _bom_and_items():
	"""A BOM whose items do not collide with an Item Group name: _T189-FG <- 2 x _T189-RM."""
	company = frappe.get_all("Company", pluck="name")[0]
	abbr = frappe.db.get_value("Company", company, "abbr")
	for code in ("_T189-FG", "_T189-RM"):
		if not frappe.db.exists("Item", code):
			frappe.get_doc({"doctype": "Item", "item_code": code, "item_name": code, "item_group": "Products",
				"stock_uom": "Nos", "is_stock_item": 1, "include_item_in_manufacturing": 1}).insert(ignore_permissions=True)
	bom = frappe.db.get_value("BOM", {"item": "_T189-FG", "docstatus": 1, "is_active": 1})
	if not bom:
		b = frappe.get_doc({"doctype": "BOM", "item": "_T189-FG", "company": company, "quantity": 1, "is_active": 1,
			"is_default": 1, "rm_cost_as_per": "Valuation Rate", "items": [{"item_code": "_T189-RM", "qty": 2, "rate": 10}]})
		b.insert(ignore_permissions=True)
		b.submit()
		bom = b.name
	return company, abbr, bom


def _draft_work_order():
	company, abbr, bom = _bom_and_items()
	wo = frappe.get_doc({"doctype": "Work Order", "production_item": "_T189-FG", "bom_no": bom, "qty": 1, "company": company,
		"wip_warehouse": f"Work In Progress - {abbr}", "fg_warehouse": f"Finished Goods - {abbr}",
		"source_warehouse": f"Stores - {abbr}"})
	wo.insert(ignore_permissions=True)
	return wo


def _actions(doc):
	return sorted({t.action for t in get_transitions(doc)})


class TestA_MigrateResult(IntegrationTestCase):
	"""Reads what `bench migrate` left; writes nothing (runs before TestB, whose drafts create Open actions)."""

	def test_a_migrate_installed_the_workflow(self):
		active = frappe.get_all("Workflow", filters={"document_type": "Work Order", "is_active": 1}, pluck="name")
		self.assertEqual(active, [WORKFLOW])
		self.assertFalse(frappe.db.exists("Workflow", "Starting Work Order"))
		wf = frappe.get_doc("Workflow", WORKFLOW)
		self.assertEqual([(s.state, s.doc_status, s.allow_edit) for s in wf.states], STATES)
		self.assertEqual([(t.state, t.action, t.next_state, t.allowed) for t in wf.transitions], TRANSITIONS)
		self.assertTrue(all(not s.update_field and not s.update_value for s in wf.states))
		self.assertEqual((wf.workflow_state_field, wf.override_status, wf.send_email_alert, wf.enable_action_confirmation),
			("workflow_state", 1, 0, 0))
		self.assertTrue(all(t.allow_self_approval == 1 and not t.condition for t in wf.transitions))
		for dt, names in (("Workflow State", ["Draft", "Scheduled", "Cancelled"]), ("Workflow Action Master", ["Schedule", "Cancel"]),
				("Role", ["Planeacion"])):
			for name in names:
				self.assertTrue(frappe.db.exists(dt, name), f"{dt} {name}")
		self.assertEqual(frappe.db.get_value("Role", "Planeacion", ["desk_access", "is_custom"]), (1, 1))
		se = frappe.get_all("Workflow", filters={"document_type": "Stock Entry", "is_active": 1}, pluck="name")
		self.assertEqual(se, ["Stock Entry Dual Signature Approval"])

	def test_e_after_migrate_mapped_and_is_idempotent(self):
		# the migrate already ran it: every Work Order's state matches its docstatus, no Open Work Order action is left
		mismatched = frappe.db.sql("""select name from `tabWork Order` where (docstatus = 0 and ifnull(workflow_state, '') != 'Draft')
			or (docstatus = 1 and ifnull(workflow_state, '') != 'Scheduled') or (docstatus = 2 and ifnull(workflow_state, '') != 'Cancelled')""")
		self.assertEqual(mismatched, ())
		# no Open Work Order action is left in an OLD state (Open actions in the new states are legitimate)
		self.assertEqual(frappe.db.count("Workflow Action", {"reference_doctype": "Work Order", "status": "Open",
			"workflow_state": ["not in", ["Draft", "Scheduled", "Cancelled"]]}), 0)
		self.assertFalse(frappe.db.exists("Workflow", "Starting Work Order"))
		# a second call writes nothing
		with patch.object(frappe.db, "set_value", wraps=frappe.db.set_value) as set_value, patch.object(frappe, "delete_doc") as delete_doc:
			result = workflow_utils.after_migrate_work_order_workflow()
		self.assertEqual(result, {"deleted": 0, "mapped": 0, "closed": 0})
		self.assertEqual((set_value.call_count, delete_doc.call_count), (0, 0))


class TestB_WorkflowBehaviour(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_b_transitions_per_role(self):
		draft = _draft_work_order()
		self.assertEqual(draft.workflow_state, "Draft")
		expected_draft = {"mu": [], "mu-plan": ["Schedule"], "mu-mm": []}
		for key, want in expected_draft.items():
			frappe.set_user(_user(key))
			self.assertEqual(_actions(draft), want, key)
		frappe.set_user("Administrator")
		scheduled = apply_workflow(_draft_work_order(), "Schedule")
		expected_scheduled = {"mu-mm": ["Cancel"], "mu-plan": ["Cancel"], "mu": []}
		for key, want in expected_scheduled.items():
			frappe.set_user(_user(key))
			self.assertEqual(_actions(frappe.get_doc("Work Order", scheduled.name)), want, key)
		# measured fact: Planeacion or Manufacturing Manager alone hold no Work Order permission (ERPNext grants
		# Work Order to Manufacturing User and Stock User only), so get_transitions' read check refuses them
		for key in ("plan-only", "mm-only"):
			frappe.set_user(_user(key))
			with self.assertRaises(frappe.PermissionError):
				get_transitions(frappe.get_doc("Work Order", draft.name))

	def test_b2_planeacion_lists_every_draft(self):
		draft = _draft_work_order()  # owned by Administrator
		frappe.set_user(_user("mu-plan"))
		self.assertIn(draft.name, frappe.get_list("Work Order", filters={"docstatus": 0}, pluck="name"))
		frappe.set_user(_user("mu"))
		self.assertNotIn(draft.name, frappe.get_list("Work Order", filters={"docstatus": 0}, pluck="name"))

	def test_c_schedule_is_the_submit(self):
		wo = _draft_work_order()
		versions_before = frappe.db.count("Version", {"ref_doctype": "Work Order", "docname": wo.name})
		frappe.set_user(_user("mu-plan"))
		# under the test runner Document._save defaults ignore_version to frappe.in_test (frappe/model/document.py),
		# so no Version is ever written in tests; apply_workflow -> submit() cannot pass ignore_version=False, so the
		# runner's suppression is lifted for this one call to observe what a site does
		with patch.object(frappe, "in_test", False):
			wo = apply_workflow(frappe.get_doc("Work Order", wo.name), "Schedule")
		frappe.set_user("Administrator")
		wo.reload()
		self.assertEqual((wo.docstatus, wo.status, wo.workflow_state), (1, "Not Started", "Scheduled"))  # (f) status is ERPNext's
		versions = frappe.get_all("Version", filters={"ref_doctype": "Work Order", "docname": wo.name}, fields=["data"],
			order_by="creation asc")
		self.assertEqual(len(versions) - versions_before, 1)
		self.assertIn('"docstatus"', versions[-1].data)
		self.assertEqual([(r.item_code, r.required_qty) for r in wo.required_items], [("_T189-RM", 2.0)])

	def test_d_cancel_then_amend(self):
		wo = apply_workflow(_draft_work_order(), "Schedule")
		frappe.set_user(_user("mu-mm"))
		wo = apply_workflow(frappe.get_doc("Work Order", wo.name), "Cancel")
		frappe.set_user("Administrator")
		wo.reload()
		self.assertEqual((wo.docstatus, wo.workflow_state), (2, "Cancelled"))

		def desk_amend(original):
			"""as create_new.js amends: every field copied, no_copy ignored (so workflow_state comes along)"""
			new = frappe.copy_doc(original, ignore_no_copy=True)
			new.amended_from = original.name
			new.docstatus = 0
			return new

		amended = desk_amend(wo)
		self.assertEqual(amended.workflow_state, "Cancelled")  # the copy carries the state, as on the desk
		amended.insert(ignore_permissions=True)
		self.assertEqual((amended.docstatus, amended.workflow_state, amended.amended_from), (0, "Draft", wo.name))

		# positive control: without the before_insert reset, the same amend fails validate_workflow
		control = desk_amend(wo)
		with patch.object(workflow_utils, "reset_workflow_state_on_amend", lambda doc, method=None: None):
			with self.assertRaises(frappe.ValidationError):
				control.insert(ignore_permissions=True)

	def test_d2_reset_also_applies_to_stock_entry(self):
		doc = frappe.get_doc({"doctype": "Stock Entry", "amended_from": "_T189-SE-ORIGINAL", "workflow_state": "Approved"})
		workflow_utils.reset_workflow_state_on_amend(doc)
		self.assertIsNone(doc.workflow_state)
		plain = frappe.get_doc({"doctype": "Stock Entry", "workflow_state": "Approved"})
		workflow_utils.reset_workflow_state_on_amend(plain)
		self.assertEqual(plain.workflow_state, "Approved")
		hooks = frappe.get_hooks("doc_events")
		for dt in ("Work Order", "Stock Entry"):
			self.assertIn("rnd_warehouse_management.rnd_warehouse_management.workflow_utils.reset_workflow_state_on_amend",
				hooks[dt]["before_insert"])

	def test_e2_mapping_on_seeded_data(self):
		# within this test's transaction: put prod's shapes back on fresh records, then run the function
		drafts = [_draft_work_order() for _ in range(2)]
		submitted = apply_workflow(_draft_work_order(), "Schedule")
		for wo, state in ((drafts[0], "Not Started"), (drafts[1], "Start"), (submitted, "Start")):
			frappe.db.set_value("Work Order", wo.name, "workflow_state", state, update_modified=False)
		old_action = frappe.get_doc({"doctype": "Workflow Action", "reference_doctype": "Work Order", "reference_name": drafts[0].name,
			"workflow_state": "Not Started", "status": "Open", "user": "Administrator"}).insert(ignore_permissions=True)
		# a planner's legitimate pending action in the new workflow's first state: it must survive every migrate
		pending = frappe.get_doc({"doctype": "Workflow Action", "reference_doctype": "Work Order", "reference_name": drafts[1].name,
			"workflow_state": "Draft", "status": "Open", "user": "Administrator"}).insert(ignore_permissions=True)
		new_states = ["Draft", "Scheduled", "Cancelled"]
		open_new_before = frappe.get_all("Workflow Action", filters={"reference_doctype": "Work Order", "status": "Open",
			"workflow_state": ["in", new_states]}, pluck="name")
		self.assertIn(pending.name, open_new_before)
		result = workflow_utils.after_migrate_work_order_workflow()
		self.assertEqual(result, {"deleted": 0, "mapped": 3, "closed": 1})  # only the old-state action
		self.assertEqual(frappe.db.get_value("Workflow Action", old_action.name, "status"), "Completed")
		self.assertEqual(frappe.db.get_value("Workflow Action", pending.name, "status"), "Open")
		open_new_after = frappe.get_all("Workflow Action", filters={"reference_doctype": "Work Order", "status": "Open",
			"workflow_state": ["in", new_states]}, pluck="name")
		self.assertEqual(sorted(open_new_after), sorted(open_new_before))  # every new-state Open action untouched
		self.assertEqual([frappe.db.get_value("Work Order", w.name, "workflow_state") for w in (*drafts, submitted)],
			["Draft", "Draft", "Scheduled"])
		self.assertEqual(workflow_utils.after_migrate_work_order_workflow(), {"deleted": 0, "mapped": 0, "closed": 0})
