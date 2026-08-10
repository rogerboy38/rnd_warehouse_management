"""Backfill: normalise stale `custom_missing_materials_json` on SUBMITTED Work Orders.

WHY THIS EXISTS
---------------
`work_order.py:53` renamed a dict key inside the stored JSON, `warehouse` -> `source_warehouse`,
as part of the fix for the "Unknown column 'warehouse'" defect. Work Orders written by the
older revision still carry the OLD key. The recomputed value therefore differs from the stored
value on every run -- by a key name only, with zero semantic drift -- and frappe refuses the
save because these fields are `allow_on_submit=0` on a submitted document.

That is a DEADLOCK: the field can only stop differing if it is written, and it cannot be
written. It recurs hourly, forever, until the stored state is normalised or the write path
changes.

RELATIONSHIP TO THE db_set FIX
------------------------------
If the `db_set` path in `update_work_order_zone_status` is deployed, the first run normalises
these documents on its own and this script is unnecessary. It exists for the case where the
stored state must be corrected WITHOUT deploying a code change, and as an auditable record of
exactly which rows were touched.

USAGE  (read-only by default -- it will not write unless you ask it to)
-----
    bench --site <site> execute \
        rnd_warehouse_management.scripts.backfill_zone_tracking_json.run

    bench --site <site> execute \
        rnd_warehouse_management.scripts.backfill_zone_tracking_json.run \
        --kwargs "{'apply': True}"

`apply=False` (the default) prints the before/after for every candidate and writes nothing.
"""

import frappe

from rnd_warehouse_management.rnd_warehouse_management.work_order import (
	ZONE_TRACKING_FIELDS,
	update_material_requirements,
)

#: Only documents in a non-terminal status are touched -- the same population the hourly job
#: iterates. A Completed/Stopped/Cancelled Work Order is out of scope by construction.
TERMINAL_STATUSES = ("Completed", "Stopped", "Cancelled")


def _candidates(names=None):
	filters = {"docstatus": 1, "status": ["not in", TERMINAL_STATUSES]}
	if names:
		filters["name"] = ["in", names]
	return frappe.get_all("Work Order", filters=filters, fields=["name", "bom_no"])


def run(apply=False, names=None):
	"""Report (and optionally normalise) submitted Work Orders whose stored zone JSON is stale.

	:param apply: write the recomputed values with db_set. Default False = dry run.
	:param names: optional list of Work Order names to restrict to.
	"""
	apply = bool(apply)
	touched, skipped, unchanged = [], [], []

	for wo in _candidates(names):
		if not wo.bom_no:
			skipped.append((wo.name, "no BOM"))
			continue
		if not frappe.db.exists("BOM", wo.bom_no):
			skipped.append((wo.name, f"BOM missing: {wo.bom_no}"))
			continue
		if frappe.db.get_value("BOM", wo.bom_no, "docstatus") != 1:
			skipped.append((wo.name, f"BOM not submitted: {wo.bom_no}"))
			continue

		doc = frappe.get_doc("Work Order", wo.name)
		before = {f: doc.get(f) for f in ZONE_TRACKING_FIELDS}
		update_material_requirements(doc)
		after = {f: doc.get(f) for f in ZONE_TRACKING_FIELDS}

		changed = {f: (before[f], after[f]) for f in ZONE_TRACKING_FIELDS if before[f] != after[f]}
		if not changed:
			unchanged.append(wo.name)
			continue

		touched.append((wo.name, changed))
		print(f"\n{wo.name}:")
		for field, (old, new) in changed.items():
			if field == "custom_missing_materials_json":
				# NB: counting the substring 'warehouse"' would ALSO match inside
				# 'source_warehouse"'. Count the two keys separately, or the diagnostic
				# reports the old key as present after it has been renamed away.
				old_key = (old or "").count('"warehouse"')
				new_key = (old or "").count('"source_warehouse"')
				old_key_after = (new or "").count('"warehouse"')
				new_key_after = (new or "").count('"source_warehouse"')
				print(
					f"    {field}: len {len(old or '')} -> {len(new or '')} · "
					f'"warehouse" keys {old_key} -> {old_key_after} · '
					f'"source_warehouse" keys {new_key} -> {new_key_after}'
				)
			else:
				print(f"    {field}: {old!r} -> {new!r}")

		if apply:
			# db_set, not save(): these fields are allow_on_submit=0 and the document is
			# submitted. update_modified=False -- derived tracking state, not a user edit.
			doc.db_set({f: after[f] for f in ZONE_TRACKING_FIELDS}, update_modified=False)

	if apply:
		frappe.db.commit()

	print(
		f"\n{'APPLIED' if apply else 'DRY RUN'}: "
		f"{len(touched)} would change, {len(unchanged)} already current, {len(skipped)} skipped"
	)
	for name, why in skipped:
		print(f"    skipped {name}: {why}")
	return {"touched": [n for n, _ in touched], "unchanged": unchanged, "skipped": skipped}
