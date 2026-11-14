"""QC hold gate (TASKS-337 item 6, Hugh's decision 59).

A Stock Entry that takes a lot OUT of a QC hold warehouse is refused at submit, and so is the CANCEL of a Stock
Entry that put a lot INTO one (cancelling takes it out again), unless that lot's Batch AMB `quality_status` is
"Passed". It runs on the server, as a `doc_events` hook, so Desk, the REST API and the agent
meet the same check (a per-write `ignore_permissions` does not skip a doc event).

  * QC hold warehouse = Warehouse.custom_qc_hold (Check, shipped by this app's Custom Field fixture). While the
    field does not exist, or no warehouse carries it, the gate does nothing: shipping the code changes no behaviour
    until someone flags a warehouse.
  * Lot -> Batch AMB: Stock Entry Detail.batch_no (or the batches of its Serial and Batch Bundle) -> Batch
    .custom_batch_amb (Link, shipped by amb_w_spc) -> Batch AMB.quality_status.
  * "Out of QC" = the row's source warehouse is a hold warehouse and its target is not (a move between two hold
    warehouses, a return into one, a receipt and a finished-item row stay allowed; a Manufacture row that CONSUMES
    from a hold warehouse is a row like any other).
  * A lot with no Batch AMB link, or whose Batch AMB is not Passed, is refused (fail closed). A row of a
    batch-tracked item that names no lot (no batch_no, no bundle) is refused too: ERPNext would pick the lot
    itself while posting the ledger (Stock Settings "auto create bundle for outward"), after this hook. A row of an
    item that is not batch-tracked is not judged: there is no lot.
  * Override: only a user holding the role `QC Hold Override`; each override leaves ONE Info Comment on the Stock
    Entry: user, action, and per lot its status ("no Batch AMB" when unlinked), quantity and warehouse. The Comment
    is written inside the submit/cancel transaction, so it rolls back with a submit that fails afterwards.

WHERE it runs (Frappe 16.17.5, `model/document.py` `run_before_save_methods`): `before_validate` runs for save and
submit BEFORE the `ignore_validate` return, so it is the first line for a submit even when a caller sets
`doc.flags.ignore_validate`; `before_submit`/`before_cancel` are skipped by that flag, and `before_validate` does not
run for cancel at all. So: submit = `before_validate` (first line) + `on_submit` (second line, after ERPNext has
posted the ledger; it unwinds only when the caller rolls back); cancel = `before_cancel` (first line) + `on_cancel`
(second line, only needed when `ignore_validate` skipped the first).

Not covered (a later slice, decision 70): Delivery Note, Sales Invoice (update stock), Purchase Receipt / Purchase
Invoice returns, Stock Reconciliation, Subcontracting Receipt, Asset Capitalization, POS and any other document that
posts stock without a Stock Entry; amend of a Stock Entry is a cancel plus a new submit (both gated).
"""

import frappe
from frappe import _

HOLD_FIELD = "custom_qc_hold"
BATCH_AMB_FIELD = "custom_batch_amb"
PASSED = "Passed"
OVERRIDE_ROLE = "QC Hold Override"
# Decision 94 (TASKS-349): only these roles may set or clear the hold flag of a Warehouse. `QC Hold Override` is NOT
# one of them: it lets a person release lots through a Stock Entry (one record per release), it does not let them
# lift the hold of a whole warehouse. Administrator holds every role, so it passes as System Manager.
HOLD_FLAG_ROLES = ("Quality Manager", "System Manager")


def _hold_flag(warehouse, cache):
	if not warehouse:
		return False
	if warehouse not in cache:
		cache[warehouse] = bool(frappe.db.get_value("Warehouse", warehouse, HOLD_FIELD))
	return cache[warehouse]


def row_leaves_hold(row, cache, reverse=False):
	"""True when the row's source is a hold warehouse and its target is not one. `reverse` judges the row as a
	cancel does: the stock goes back from the target to the source."""
	src, tgt = (row.get("t_warehouse"), row.get("s_warehouse")) if reverse else (row.get("s_warehouse"), row.get("t_warehouse"))
	return _hold_flag(src, cache) and not _hold_flag(tgt, cache)


def row_batches(row):
	"""[(batch, qty)] a row moves. A submitted row has a Serial and Batch Bundle built from its batch_no, so the
	bundle's entries are the authority when there is one; the row's own batch_no (row quantity) counts only for a
	lot the bundle does not list (an unsaved or just-validated row has no bundle yet)."""
	by_batch = {}
	bundle = row.get("serial_and_batch_bundle")
	if bundle:
		for e in frappe.get_all("Serial and Batch Entry", filters={"parent": bundle}, fields=["batch_no", "qty"]):
			if e.batch_no:
				by_batch[e.batch_no] = by_batch.get(e.batch_no, 0) + abs(e.get("qty") or 0)
	if row.get("batch_no") and row.get("batch_no") not in by_batch:
		by_batch[row.get("batch_no")] = abs(row.get("qty") or 0)
	return list(by_batch.items())


def batch_verdict(batch):
	"""(ok, why, status) for one lot: its Batch AMB's quality_status must be Passed. `status` is what a record shows."""
	if not frappe.get_meta("Batch").has_field(BATCH_AMB_FIELD):
		return False, _("the Batch has no link to a Batch AMB on this site"), "no Batch AMB link field"
	amb = frappe.db.get_value("Batch", batch, BATCH_AMB_FIELD)
	if not amb:
		return False, _("no Batch AMB is linked"), "no Batch AMB"
	if not frappe.db.exists("DocType", "Batch AMB"):
		return False, _("Batch AMB is not installed"), "Batch AMB not installed"
	status = frappe.db.get_value("Batch AMB", amb, "quality_status") or ""
	if status == PASSED:
		return True, "", status
	return False, _("quality status is {0}").format(status or _("empty")), status or "empty"


# ERPNext 16.17.0 `StockEntry.validate_warehouse`: which side a purpose needs. `before_validate` (the gate's first
# line, the only one `ignore_validate` cannot skip) runs BEFORE that method fills a row's warehouses from the header
# `from_warehouse` / `to_warehouse`, so the gate resolves them itself, for judging only.
_SOURCE_MANDATORY = (
	"Material Issue", "Material Transfer", "Send to Subcontractor", "Material Transfer for Manufacture",
	"Material Consumption for Manufacture", "Return Raw Material to Customer", "Subcontracting Delivery",
)
_TARGET_MANDATORY = (
	"Material Receipt", "Material Transfer", "Send to Subcontractor", "Material Transfer for Manufacture",
	"Receive from Customer", "Subcontracting Return",
)


class _EffectiveRow:
	"""A row as ERPNext will see it after validate_warehouse: same fields, resolved warehouses. Never written back."""

	def __init__(self, row, s_warehouse, t_warehouse):
		self._row, self._over = row, {"s_warehouse": s_warehouse, "t_warehouse": t_warehouse}

	def get(self, key, default=None):
		return self._over[key] if key in self._over else self._row.get(key, default)


def effective_rows(doc):
	"""The entry's rows with the warehouses `validate_warehouse` would give them (header fallback, purpose rules,
	Manufacture / Disassemble with a BOM). Pure: nothing on `doc` is changed."""
	purpose = doc.get("purpose") or doc.get("stock_entry_type")
	src_only = purpose in _SOURCE_MANDATORY and purpose not in _TARGET_MANDATORY
	tgt_only = purpose in _TARGET_MANDATORY and purpose not in _SOURCE_MANDATORY
	frm = None if tgt_only else doc.get("from_warehouse")
	to = None if src_only else doc.get("to_warehouse")
	rows = doc.get("items") or []
	has_bom = any(r.get("bom_no") for r in rows)
	out = []
	for r in rows:
		s, t = r.get("s_warehouse"), r.get("t_warehouse")
		if src_only:
			t = None
		elif tgt_only:
			s = None
		if not s and not t:
			s, t = frm, to
		if purpose in _SOURCE_MANDATORY and not s:
			s = frm
		if purpose in _TARGET_MANDATORY and not t:
			t = to
		if has_bom and purpose in ("Manufacture", "Disassemble"):
			finished = bool(r.get("is_finished_item") or r.get("type") or r.get("is_legacy_scrap_item"))
			if (purpose == "Manufacture") == finished:
				s = None          # a finished / scrap row of a Manufacture (a consumed row of a Disassemble) only receives
			else:
				t = None
		out.append(_EffectiveRow(r, s, t))
	return out


def refusals(doc, reverse=False):
	"""[(batch, warehouse, why, status, qty)] for every lot the entry takes out of a hold warehouse unjudged or not
	Passed (`reverse`: as a cancel would). A submit is judged on the rows as validate_warehouse will leave them."""
	if not frappe.get_meta("Warehouse").has_field(HOLD_FIELD):
		return []
	cache, out, seen = {}, [], {}
	for row in (doc.get("items") or []) if reverse else effective_rows(doc):
		if not row_leaves_hold(row, cache, reverse):
			continue
		wh = row.get("t_warehouse") if reverse else row.get("s_warehouse")
		batches = row_batches(row)
		if not batches:
			if frappe.db.get_value("Item", row.get("item_code"), "has_batch_no"):
				out.append((row.get("item_code"), wh, _("no lot is named on the row"), "no lot named", abs(row.get("qty") or 0)))
			continue
		for batch, qty in batches:
			key = (batch, wh)
			if key in seen:
				# the same lot twice in one entry: judged once, quantities added to the record
				i = seen[key]
				if i is not None:
					b, w, why, st, q = out[i]
					out[i] = (b, w, why, st, q + qty)
				continue
			ok, why, status = batch_verdict(batch)
			seen[key] = None
			if not ok:
				seen[key] = len(out)
				out.append((batch, wh, why, status, qty))
	return out


def _record(doc, action, bad, method=None):
	"""One Info Comment per entry and action: who, what, and per lot its status, quantity and warehouse.
	A submit is recorded at `on_submit` only: at `before_validate` / `before_submit` a document submitted in one call
	has a name but no row yet (the Comment's link would not validate), and one that is refused later must leave no
	Comment. A cancel is recorded at `before_cancel` (the row exists)."""
	flag = f"qc_hold_override_{action}"
	if doc.flags.get(flag):
		return
	if action == "submit" and method != "on_submit":
		return
	doc.flags[flag] = True
	lines = "; ".join(f"{b} (status {st}, qty {frappe.utils.flt(q)}, from {w})" for b, w, _y, st, q in bad)
	doc.add_comment(
		"Info",
		_("QC hold override ({0}) by {1}: {2}").format(action, frappe.session.user, lines),
	)


# the method -> (action, reverse, only_when_validation_was_skipped) table
_METHODS = {
	"before_validate": ("submit", False, False),   # only for _action == "submit"; runs even under ignore_validate
	"before_submit": ("submit", False, False),     # kept so an older hooks.py entry still judges; deduplicated by the flag
	"on_submit": ("submit", False, False),         # second line, after the ledger
	"before_cancel": ("cancel", True, False),
	"on_cancel": ("cancel", True, True),           # second line; only when ignore_validate skipped before_cancel
}


def check_qc_hold_release(doc, method=None):
	"""doc_events hook for Stock Entry. Returns {"action", "judged", "refused", "overridden"} (None when the method is
	not one of the five), so a test can see that the gate really judged."""
	if method not in _METHODS:
		return None
	action, reverse, only_if_skipped = _METHODS[method]
	if method == "before_validate" and getattr(doc, "_action", None) != "submit":
		return None  # a plain save of a draft
	if only_if_skipped and not doc.flags.ignore_validate:
		return None  # before_cancel already ran
	bad = refusals(doc, reverse)
	result = {"action": action, "refused": [b[0] for b in bad], "overridden": False}
	if not bad:
		return result
	lines = "\n".join(f"- {b} ({w}): {why}" for b, w, why, _s, _q in bad)
	if OVERRIDE_ROLE in frappe.get_roles():
		_record(doc, action, bad, method)
		result["overridden"] = True
		return result
	if action == "cancel":
		msg = _("Cancelling this entry would take lots out of a QC hold warehouse; they can leave it only when their Batch AMB quality status is Passed:")
	else:
		msg = _("Lots in a QC hold warehouse can leave it only when their Batch AMB quality status is Passed:")
	frappe.throw(msg + "\n" + lines, title=_("QC hold"))


def check_hold_flag_change(doc, method=None):
	"""Warehouse `before_validate` hook (decision 94). A change of `custom_qc_hold` in either direction, and a new
	Warehouse inserted with the flag set, needs Quality Manager or System Manager. A save that does not touch the
	flag is not judged. It runs at before_validate, which Frappe runs for a save BEFORE it honours `ignore_validate`
	(a per-write `ignore_permissions` does not skip a doc event either). Returns {"judged", "was", "now"} so a test
	can see that the hook really decided. Not covered: `frappe.db.set_value`/`db_set`/SQL, which run no doc event."""
	if not frappe.get_meta("Warehouse").has_field(HOLD_FIELD):
		return None
	now = 1 if doc.get(HOLD_FIELD) else 0
	is_new = doc.is_new() if callable(getattr(doc, "is_new", None)) else not doc.get("name")
	was = 0 if is_new else (1 if frappe.db.get_value("Warehouse", doc.name, HOLD_FIELD) else 0)
	if was == now:
		return {"judged": False, "was": was, "now": now}
	if set(HOLD_FLAG_ROLES) & set(frappe.get_roles()):
		return {"judged": True, "was": was, "now": now}
	frappe.throw(
		_("Only {0} may {1} \"QC Hold Warehouse\" on a Warehouse: it applies or lifts the hold for every lot in it.").format(
			_(" or ").join(HOLD_FLAG_ROLES), _("set") if now else _("clear")),
		frappe.PermissionError,
		title=_("QC hold"),
	)


def warn_group_flag(doc, method=None):
	"""Warehouse hook: the gate judges the exact warehouse a row names and does not follow a group's children, so a
	flag on a group would silently do nothing. Refuse it with a message that says what to do."""
	if doc.get(HOLD_FIELD) and doc.get("is_group"):
		frappe.throw(
			_("{0} is a group warehouse: the QC hold gate judges the warehouse a row names and does not follow a group's children. Untick \"QC Hold Warehouse\" here and flag each leaf warehouse instead.").format(doc.name or doc.get("warehouse_name")),
			title=_("QC hold"),
		)
