import frappe

#: Work Order Scheduling: the workflow state that matches each docstatus
WORK_ORDER_STATE_BY_DOCSTATUS = {0: "Draft", 1: "Scheduled", 2: "Cancelled"}
#: the workflow this app shipped before 2.2.0; replaced by "Work Order Scheduling"
OLD_WORK_ORDER_WORKFLOW = "Starting Work Order"


def reset_workflow_state_on_amend(doc, method=None):
	"""before_insert (Work Order, Stock Entry): an amended copy carries the cancelled original's workflow_state
	(no_copy is ignored on amend) and would fail validate_workflow; clear it, the first save sets the first state."""
	if doc.get("amended_from"):
		doc.workflow_state = None


def after_migrate_work_order_workflow():
	"""after_migrate, after sync_fixtures has installed "Work Order Scheduling". Idempotent: every step writes only
	what differs. No save(), no Version, no notification, no commit (migrate commits)."""
	logger = frappe.logger("rnd_warehouse_management")

	# 1. the old workflow: deactivated by Workflow.validate when the new one was inserted; remove it. Its Workflow
	#    States (Not Started, Start) and Action Master (Start) are kept: other apps may reference them.
	deleted = 0
	if frappe.db.exists("Workflow", OLD_WORK_ORDER_WORKFLOW):
		frappe.delete_doc("Workflow", OLD_WORK_ORDER_WORKFLOW, force=1, ignore_permissions=True)
		deleted = 1

	# 2. Work Order workflow_state by docstatus, only where it differs (NULL included). Per document through the ORM's
	#    set_value with update_modified=False: a plain UPDATE, no Version row, no hooks; the row counts are small.
	mapped = 0
	if frappe.db.has_column("Work Order", "workflow_state"):
		for docstatus, state in WORK_ORDER_STATE_BY_DOCSTATUS.items():
			names = frappe.db.sql_list(
				"""select name from `tabWork Order` where docstatus = %s and ifnull(workflow_state, '') != %s""",
				(docstatus, state),
			)
			for name in names:
				frappe.db.set_value("Work Order", name, "workflow_state", state, update_modified=False)
			mapped += len(names)

	# 3. Open Workflow Actions on Work Order belong to the old workflow's states: close them. Workflow Action.status
	#    allows only Open / Completed, so they become Completed (= not pending any more), kept as history.
	closed = 0
	for name in frappe.get_all("Workflow Action", filters={"reference_doctype": "Work Order", "status": "Open"}, pluck="name"):
		frappe.db.set_value("Workflow Action", name, "status", "Completed", update_modified=False)
		closed += 1

	logger.info(
		f"after_migrate_work_order_workflow: old workflow deleted={deleted} work orders mapped={mapped} "
		f"open workflow actions closed={closed}"
	)
	return {"deleted": deleted, "mapped": mapped, "closed": closed}
