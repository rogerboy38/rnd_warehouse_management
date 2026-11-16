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

Applying it again after a way back (TASKS-353 decision 108): `rollback()` also removes this patch's own Patch Log row.
Frappe runs a patch line only when no Patch Log row holds that exact string, so the next migrate of this code runs
`execute` again and the level-1 rows come back together with the field level, with no step by hand. Without that, the
fixture would put the field at level 1 while the patch stayed "already run": a level-1 field with no level-1 rows.
"""

import json

import frappe
import frappe.defaults
from frappe.utils import cint

DOCTYPE = "Warehouse"
FIELD = "custom_qc_hold"
EDIT_ROLES = ("Quality Manager", "System Manager")
STATE_KEY = "rnd_hold_flag_docperms"
PATCH_NAME = "rnd_warehouse_management.patches.v2_4.hold_flag_permlevel"   # the line in patches.txt = Patch Log.patch


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
		state, wrong = _read_record(prior)
		if wrong:
			# TASKS-365 R-1: a record damaged by hand. Nothing is changed and the migrate goes on (no exception).
			_say(
				f"the record `{STATE_KEY}` (a site default) cannot be read: {wrong}. The patch changed NOTHING: no "
				"level-1 row was made and the record is left as it is. Repair the record or delete it, then run "
				f"`bench --site <site> run-patch {PATCH_NAME} --force`"
			)
			return
	if setup_custom_perms(DOCTYPE):
		# the standard rows were copied unchanged. The copy is recorded row by row, so that the way back can tell the
		# patch's rows from rows a person adds later (TASKS-361 P-A)
		state["base_copied"] = True
		state["copied"] = frappe.get_all("Custom DocPerm", filters={"parent": DOCTYPE}, pluck="name")
	level0, gone = _existing_roles_only(_rows(0))
	add, upgrade = plan(level0, _rows(1))
	for row in add:
		if not frappe.db.exists("Role", row["role"]):
			_say(f"role {row['role']} does not exist on this site; no level-1 row made for it")
			continue
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


LOG_NAME = "rnd_hold_flag"


def _say(text):
	"""One line in the migrate output AND in a log file (TASKS-365 L-1). Frappe's default logger drops a warning (its
	level is ERROR), so the line goes to a logger of its own, at WARNING: `<bench>/logs/rnd_hold_flag.log` and
	`<bench>/sites/<site>/logs/rnd_hold_flag.log`. Where the bench streams its logs (FRAPPE_STREAM_LOGGING, as a
	container stack does) the same line goes to the process's stderr instead of the two files."""
	import logging

	line = f"hold_flag_permlevel: {text}"
	print(line)
	logger = frappe.logger(LOG_NAME)
	logger.setLevel(logging.WARNING)
	logger.warning(line)


def _read_record(raw):
	"""(record, None) when `raw` is the JSON object the patch writes, else (None, what is wrong), in plain words."""
	try:
		rec = json.loads(raw)
	except Exception:
		return None, "its text is not JSON"
	if not isinstance(rec, dict):
		return None, f"it holds `{json.dumps(rec)[:40]}`, not the object the patch writes"
	for key in ("added", "upgraded"):
		if not isinstance(rec.setdefault(key, []), list):
			return None, f"its `{key}` is not a list"
	if rec.get("copied") is not None and not isinstance(rec["copied"], list):
		return None, "its `copied` is not a list"
	rec.setdefault("base_copied", False)
	return rec, None


def _existing_roles_only(rows):
	"""TASKS-361 P-B: a Custom DocPerm row may name a role that was deleted since. Frappe refuses to insert a new row
	for such a role (the link no longer resolves), which made the whole migrate fail. Such a row is left exactly as it
	is, named in one log line, and gets no level-1 row. Returns (rows whose role exists, the vanished role names)."""
	keep, gone = [], []
	for r in rows:
		if frappe.db.exists("Role", r["role"]):
			keep.append(r)
		elif r["role"] not in gone:
			gone.append(r["role"])
			_say(f"Custom DocPerm row {r.get('name')} on {DOCTYPE} names role {r['role']}, which no longer exists; the row is left as it is")
	return keep, gone


PERM_FLAGS = ("read", "write", "create", "delete", "submit", "cancel", "amend", "report", "export", "import", "share", "print", "email", "select")


def _sig(r):
	return (r["role"], cint(r.get("permlevel")), cint(r.get("if_owner")), tuple(cint(r.get(k)) for k in PERM_FLAGS))


def _against_standard(names):
	"""(custom rows of `names` that equal no standard row, standard rows that no such custom row equals): what a person
	changed or added, and what is missing, counted row for row (TASKS-365 W-1)."""
	fields = ["name", "role", "permlevel", "if_owner", *PERM_FLAGS]
	custom = [_sig(r) for r in frappe.get_all("Custom DocPerm", filters={"parent": DOCTYPE, "name": ["in", names or ["-"]]}, fields=fields)]
	standard = [_sig(r) for r in frappe.get_all("DocPerm", filters={"parent": DOCTYPE}, fields=fields)]
	for sig in list(custom):
		if sig in standard:
			standard.remove(sig)
			custom.remove(sig)
	return len(custom), len(standard)


def _is_plain_copy(names):
	"""True when the Custom DocPerm rows `names` are, one for one, the standard DocPerm rows of the doctype: the copy the
	patch made, untouched since. Anything else (a row added, a right changed, a row removed) is a person's work."""
	fields = ["name", "role", "permlevel", "if_owner", *PERM_FLAGS]
	sig = lambda r: (r["role"], cint(r.get("permlevel")), cint(r.get("if_owner")), tuple(cint(r.get(k)) for k in PERM_FLAGS))
	custom = sorted(sig(r) for r in frappe.get_all("Custom DocPerm", filters={"parent": DOCTYPE, "name": ["in", names or ["-"]]}, fields=fields))
	standard = sorted(sig(r) for r in frappe.get_all("DocPerm", filters={"parent": DOCTYPE}, fields=fields))
	return bool(names) and custom == standard


def rollback():
	"""The way back. It removes ONLY rows the patch itself made, known by the record the patch wrote in the site default
	`rnd_hold_flag_docperms` (never "every Custom DocPerm row of Warehouse", TASKS-361 P-A):
	  * the level-1 rows it added are deleted, the `write` it granted on rows that already existed is taken back;
	  * the copy of the standard rows is deleted only when the patch made it AND what is left on the site is exactly
	    that copy, untouched. If a person has added or changed a row since, the copy stays: on its own, a hand-made
	    row would replace the standard rows for everybody (a Custom DocPerm set shadows the standard one).
	The Custom Field returns to permlevel 0 when the older code is migrated (its fixture says 0); this also sets it now."""
	raw = frappe.db.get_default(STATE_KEY)
	if not raw:
		_forget_patch()     # nothing of ours on the site; make sure a later migrate of this code runs the patch
		return _nothing_recorded()
	state, wrong = _read_record(raw)
	if wrong:
		# TASKS-365 R-1: said plainly, nothing changed, no exception (bench hid the cause behind a NameError)
		note = (
			f"the record `{STATE_KEY}` (a site default) cannot be read: {wrong}. The way back changed NOTHING: no row "
			"removed, the field's level and the Patch Log as they were. Repair the record and run the way back again; "
			"or delete the record, after which the way back can no longer tell the patch's rows from a person's"
		)
		_say(note)
		return note
	for name in state.get("added", []):
		if frappe.db.exists("Custom DocPerm", name):
			frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True)
	for name in state.get("upgraded", []):
		if frappe.db.exists("Custom DocPerm", name):
			frappe.db.set_value("Custom DocPerm", name, "write", 0)
	copy_note = "no copy was made"
	if state.get("base_copied"):
		left = frappe.get_all("Custom DocPerm", filters={"parent": DOCTYPE}, pluck="name")
		copied = state.get("copied")
		ours = [n for n in left if n in copied] if copied is not None else left      # a record of an older patch has no list
		by_hand = [n for n in left if n not in ours]
		if not left:
			copy_note = "copy: no Custom DocPerm row of Warehouse is left on the site (removed by hand since); nothing to remove, the site is on the standard rows"
			_say(copy_note)
		elif not by_hand and _is_plain_copy(ours):
			for name in ours:
				frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True)
			copy_note = f"copy removed: {len(ours)} rows"
		else:
			# TASKS-365 W-1: the count says what was found, in each case
			not_standard, missing = _against_standard(ours)
			if copied is not None:
				found = f"{len(by_hand)} row(s) added by hand, {not_standard} copied row(s) changed, {len(copied) - len(ours)} copied row(s) deleted since"
			else:   # a record of the older patch: no list of the copied rows, so the rows are told apart by comparison only
				found = f"{not_standard} row(s) that equal no standard row (added or changed by hand), {missing} standard row(s) with no equal row left"
			copy_note = f"copy KEPT ({len(left)} rows left as they are): {found}; a person's rows stand on the copy"
			_say(copy_note)
	if frappe.db.exists("Custom Field", f"{DOCTYPE}-{FIELD}"):
		frappe.db.set_value("Custom Field", f"{DOCTYPE}-{FIELD}", "permlevel", 0)
	# through frappe.defaults, which also drops the cached copy: a plain delete of the row leaves the record in the
	# cache, and a second way back would act on it (found by the real-migrate run of TASKS-353)
	frappe.defaults.clear_default(key=STATE_KEY, parent="__default")
	_forget_patch()
	frappe.clear_cache(doctype=DOCTYPE)
	return f"removed {len(state.get('added', []))} level-1 rows, undid {len(state.get('upgraded', []))} upgrades, {copy_note}"


def _nothing_recorded():
	"""TASKS-365 R-1: no record on the site (the patch never ran, the way back already ran, or the record was deleted
	by hand). The way back says what it finds and what it can and cannot do without the record."""
	level1 = frappe.get_all("Custom DocPerm", filters={"parent": DOCTYPE, "permlevel": 1}, pluck="name")
	level = cint(frappe.db.get_value("Custom Field", f"{DOCTYPE}-{FIELD}", "permlevel")) if frappe.db.exists("Custom Field", f"{DOCTYPE}-{FIELD}") else 0
	note = "nothing recorded: nothing removed"
	if level1 or level:
		note += (
			f". Found on the site: the field at level {level}, {len(level1)} level-1 Custom DocPerm row(s) of {DOCTYPE}. "
			f"Without the record `{STATE_KEY}` the way back cannot tell the patch's rows from a person's, so it removes "
			"no row and leaves the field's level. It did one thing: the patch is forgotten, so the next migrate of this "
			"code runs it again and writes a new record (rows that exist are not duplicated). To go back by hand: delete "
			"the level-1 rows in Role Permission Manager"
		)
		_say(note)
	return note


def _forget_patch():
	"""Decision 108: after a way back the patch must run again at the next migrate of this code."""
	frappe.db.delete("Patch Log", {"patch": PATCH_NAME})
