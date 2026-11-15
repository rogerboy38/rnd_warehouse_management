"""TASKS-350 decision 102: `Warehouse.custom_qc_hold` moves to permission level 1, so that only Quality Manager and System
Manager see the flag as EDITABLE. Everyone who can read a Warehouse today can still read the flag (read-only); nobody gains
or loses anything on any other field.

What it ships (post_model_sync patch; the Custom Field row itself, with permlevel 1, arrives by the app's fixture):

  * Custom DocPerm rows at permlevel 1 on Warehouse: `read` for every role that has a permlevel-0 `read` row on Warehouse
    today (same `if_owner`), and `read` + `write` for Quality Manager and System Manager.
  * Warehouse already carries Custom DocPerm rows on the test environment and on prod, and a bare Custom DocPerm set REPLACES
    the standard rows. So the patch first makes sure the Custom DocPerm set exists: when it does, it is not touched at
    permlevel 0; when it does not (a site that still runs on the standard rows), the standard rows are copied into it
    unchanged first (what Frappe's own role manager does), so the effective permission at permlevel 0 stays what it was.

The rows it creates (and whether it copied the standard rows) are recorded in a site default, so `rollback()` removes
exactly those and nothing else. `rollback()` is the way back: `bench --site <site> execute
rnd_warehouse_management.patches.v2_4.hold_flag_permlevel.rollback`, then deploy the older code and migrate (the older
fixture puts the field back to permlevel 0). Idempotent: running `execute` twice adds nothing.
"""

import json

import frappe

DOCTYPE = "Warehouse"
FIELD = "custom_qc_hold"
EDIT_ROLES = ("Quality Manager", "System Manager")
STATE_KEY = "rnd_hold_flag_docperms"


def plan(level0_rows, level1_rows):
	"""Pure: from the permlevel-0 rows and the permlevel-1 rows that exist, the level-1 rows to add and the existing
	level-1 rows of the two edit roles that lack `write`. Rows are dicts with role, if_owner, read, write."""
	have = {(r["role"], int(r.get("if_owner") or 0)): r for r in level1_rows}
	add, upgrade = [], []
	want = {}
	for r in level0_rows:
		if r.get("read"):
			want[(r["role"], int(r.get("if_owner") or 0))] = {"role": r["role"], "if_owner": int(r.get("if_owner") or 0), "read": 1, "write": 0}
	for role in EDIT_ROLES:
		want[(role, 0)] = {"role": role, "if_owner": 0, "read": 1, "write": 1}
	for key, row in sorted(want.items()):
		cur = have.get(key)
		if cur is None:
			add.append(row)
		elif row["write"] and not cur.get("write"):
			upgrade.append(cur["name"] if "name" in cur else key)
	return add, upgrade


def _rows(permlevel):
	return frappe.get_all(
		"Custom DocPerm", filters={"parent": DOCTYPE, "permlevel": permlevel},
		fields=["name", "role", "if_owner", "read", "write"],
	)


def execute():
	if not frappe.db.exists("DocType", DOCTYPE):
		return
	from frappe.permissions import setup_custom_perms

	state = {"base_copied": False, "added": [], "upgraded": []}
	prior = frappe.db.get_default(STATE_KEY)
	if prior:
		try:
			state = json.loads(prior)
		except Exception:
			pass
	if setup_custom_perms(DOCTYPE):
		state["base_copied"] = True          # the standard rows were copied unchanged; rollback removes the copy
	add, upgrade = plan(_rows(0), _rows(1))
	for row in add:
		d = frappe.new_doc("Custom DocPerm")
		d.update({"parent": DOCTYPE, "parenttype": "DocType", "parentfield": "permissions", "permlevel": 1, **row})
		d.insert(ignore_permissions=True)
		state["added"].append(d.name)
	for name in upgrade:
		if frappe.db.exists("Custom DocPerm", name):
			frappe.db.set_value("Custom DocPerm", name, "write", 1)
			state["upgraded"].append(name)
	frappe.db.set_default(STATE_KEY, json.dumps(state))
	frappe.clear_cache(doctype=DOCTYPE)


def rollback():
	"""The way back: delete exactly the rows `execute` added, undo the `write` it granted on rows that already existed, and
	remove the copy of the standard rows only if `execute` made it. The Custom Field returns to permlevel 0 when the older
	code is migrated (its fixture says 0); this also sets it now."""
	raw = frappe.db.get_default(STATE_KEY)
	if not raw:
		return "nothing recorded: nothing removed"
	state = json.loads(raw)
	for name in state.get("added", []):
		if frappe.db.exists("Custom DocPerm", name):
			frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True)
	for name in state.get("upgraded", []):
		if frappe.db.exists("Custom DocPerm", name):
			frappe.db.set_value("Custom DocPerm", name, "write", 0)
	if state.get("base_copied"):
		for name in frappe.get_all("Custom DocPerm", filters={"parent": DOCTYPE}, pluck="name"):
			frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True)
	if frappe.db.exists("Custom Field", f"{DOCTYPE}-{FIELD}"):
		frappe.db.set_value("Custom Field", f"{DOCTYPE}-{FIELD}", "permlevel", 0)
	frappe.db.delete("DefaultValue", {"parent": "__default", "defkey": STATE_KEY})
	frappe.clear_cache(doctype=DOCTYPE)
	return f"removed {len(state.get('added', []))} rows, undid {len(state.get('upgraded', []))} upgrades, copy removed: {bool(state.get('base_copied'))}"
