"""QC hold gate (TASKS-337 item 6, Hugh's decision 59).

A Stock Entry that takes a lot OUT of a QC hold warehouse is refused at submit unless that lot's Batch AMB
`quality_status` is "Passed". It runs on the server, as a `doc_events` hook, so Desk, the REST API and the agent
meet the same check (a per-write `ignore_permissions` does not skip a doc event).

  * QC hold warehouse = Warehouse.custom_qc_hold (Check, shipped by this app's Custom Field fixture). While the
    field does not exist, or no warehouse carries it, the gate does nothing: shipping the code changes no behaviour
    until someone flags a warehouse.
  * Lot -> Batch AMB: Stock Entry Detail.batch_no (or the batches of its Serial and Batch Bundle) -> Batch
    .custom_batch_amb (Link, shipped by amb_w_spc) -> Batch AMB.quality_status.
  * "Out of QC" = the row's source warehouse is a hold warehouse and its target is not (a move between two hold
    warehouses, a return into one, a receipt and a finished-item row stay allowed; a Manufacture row that CONSUMES
    from a hold warehouse is a row like any other).
  * A lot with no Batch AMB link, or whose Batch AMB is not Passed, is refused (fail closed). A row with no batch
    at all is not judged: there is no lot to look up.
  * Override: only a user holding the role `QC Hold Override`; each overridden submit leaves a Comment on the
    Stock Entry naming the user and the lots.
"""

import frappe
from frappe import _

HOLD_FIELD = "custom_qc_hold"
BATCH_AMB_FIELD = "custom_batch_amb"
PASSED = "Passed"
OVERRIDE_ROLE = "QC Hold Override"


def _hold_flag(warehouse, cache):
	if not warehouse:
		return False
	if warehouse not in cache:
		cache[warehouse] = bool(frappe.db.get_value("Warehouse", warehouse, HOLD_FIELD))
	return cache[warehouse]


def row_leaves_hold(row, cache):
	"""True when the row's source is a hold warehouse and its target is not one."""
	return _hold_flag(row.get("s_warehouse"), cache) and not _hold_flag(row.get("t_warehouse"), cache)


def row_batches(row):
	"""The batches a row moves: its own batch_no plus the entries of its Serial and Batch Bundle."""
	out = []
	if row.get("batch_no"):
		out.append(row.get("batch_no"))
	bundle = row.get("serial_and_batch_bundle")
	if bundle:
		for e in frappe.get_all("Serial and Batch Entry", filters={"parent": bundle}, fields=["batch_no"]):
			if e.batch_no:
				out.append(e.batch_no)
	return list(dict.fromkeys(out))


def batch_verdict(batch):
	"""(ok, why) for one lot: its Batch AMB's quality_status must be Passed."""
	if not frappe.get_meta("Batch").has_field(BATCH_AMB_FIELD):
		return False, _("the Batch has no link to a Batch AMB on this site")
	amb = frappe.db.get_value("Batch", batch, BATCH_AMB_FIELD)
	if not amb:
		return False, _("no Batch AMB is linked")
	if not frappe.db.exists("DocType", "Batch AMB"):
		return False, _("Batch AMB is not installed")
	status = frappe.db.get_value("Batch AMB", amb, "quality_status") or ""
	if status == PASSED:
		return True, ""
	return False, _("quality status is {0}").format(status or _("empty"))


def refusals(doc):
	"""[(batch, source warehouse, why)] for every lot the entry takes out of a hold warehouse unjudged or not Passed."""
	if not frappe.get_meta("Warehouse").has_field(HOLD_FIELD):
		return []
	cache, out, seen = {}, [], set()
	for row in doc.get("items") or []:
		if not row_leaves_hold(row, cache):
			continue
		for batch in row_batches(row):
			if (batch, row.get("s_warehouse")) in seen:
				continue
			seen.add((batch, row.get("s_warehouse")))
			ok, why = batch_verdict(batch)
			if not ok:
				out.append((batch, row.get("s_warehouse"), why))
	return out


def check_qc_hold_release(doc, method=None):
	"""doc_events hook for Stock Entry (before_submit; on_submit as a backstop when validation was skipped)."""
	if method == "on_submit" and not doc.flags.ignore_validate:
		return  # before_submit already ran
	bad = refusals(doc)
	if not bad:
		return
	lines = "\n".join(f"- {b} ({w}): {why}" for b, w, why in bad)
	if OVERRIDE_ROLE in frappe.get_roles():
		doc.add_comment(
			"Info",
			_("QC hold override by {0}: {1}").format(frappe.session.user, ", ".join(b for b, _w, _y in bad)),
		)
		return
	frappe.throw(
		_("Lots in a QC hold warehouse can leave it only when their Batch AMB quality status is Passed:")
		+ "\n"
		+ lines,
		title=_("QC hold"),
	)
