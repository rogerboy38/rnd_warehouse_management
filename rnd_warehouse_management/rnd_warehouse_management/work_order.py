import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, flt

def before_save(doc, method=None):
	"""Hook: Before saving Work Order"""
	set_initial_zone_status(doc)
	update_material_requirements(doc)

def on_submit(doc, method=None):
	"""Hook: After submitting Work Order"""
    # DISABLED: 	create_initial_material_assessment(doc)

def set_initial_zone_status(doc):
	"""Set initial zone status for new Work Orders"""
	if not doc.custom_current_zone_status:
		doc.custom_current_zone_status = "Red Zone"  # Default to Red Zone (incomplete)
		doc.custom_zone_status_color = "#dc3545"     # Red color
		doc.custom_material_completion_percentage = 0
		doc.custom_last_zone_update = now_datetime()

def update_material_requirements(doc):
	"""Update material requirements and availability"""
	if not doc.bom_no:
		return
	
	# Get BOM items
	bom_items = frappe.get_all(
		"BOM Item",
		filters={"parent": doc.bom_no},
		fields=["item_code", "qty", "source_warehouse", "item_name"]
	)
	
	# Calculate total required vs available
	total_items = len(bom_items)
	available_items = 0
	missing_materials = []
	
	for bom_item in bom_items:
		required_qty = flt(bom_item.qty * doc.qty)
		available_qty = get_available_qty(bom_item.item_code, bom_item.source_warehouse)
		
		if available_qty >= required_qty:
			available_items += 1
		else:
			missing_qty = required_qty - available_qty
			missing_materials.append({
				"item_code": bom_item.item_code,
				"item_name": bom_item.item_name,
				"required_qty": required_qty,
				"available_qty": available_qty,
				"missing_qty": missing_qty,
				"source_warehouse": bom_item.source_warehouse
			})
	
	# Update completion percentage
	completion_percentage = (available_items / total_items * 100) if total_items > 0 else 0
	doc.custom_material_completion_percentage = completion_percentage
	
	# Update zone status based on completion
	if completion_percentage >= 100:
		doc.custom_current_zone_status = "Green Zone"
		doc.custom_zone_status_color = "#28a745"  # Green
	else:
		doc.custom_current_zone_status = "Red Zone"
		doc.custom_zone_status_color = "#dc3545"  # Red
	
	# Store missing materials info
	doc.custom_missing_materials_json = frappe.as_json(missing_materials)

def get_available_qty(item_code, source_warehouse):
    """Get available quantity from warehouse"""
    try:
        # Get available stock
        available = frappe.db.get_value("Bin", 
            {"item_code": item_code, "warehouse": source_warehouse}, 
            "actual_qty")
        return flt(available) if available else 0
    except Exception:
        return 0

def create_initial_material_assessment(doc):
	"""Create initial material assessment record"""
	# Create a material assessment log
	assessment = frappe.get_doc({
		"doctype": "Material Assessment Log",
		"work_order": doc.name,
		"assessment_date": now_datetime(),
		"zone_status": doc.custom_current_zone_status,
		"completion_percentage": doc.custom_material_completion_percentage,
		"missing_materials": doc.custom_missing_materials_json,
		"assessed_by": frappe.session.user
	})
	
	try:
		assessment.insert(ignore_permissions=True)
	except Exception as e:
		# If custom DocType doesn't exist, just log the assessment
		frappe.log_error(f"Material Assessment Log creation failed: {str(e)}")

def get_permission_query_conditions(user):
	"""Permission query conditions for Work Order"""
	if not user:
		user = frappe.session.user
	
	user_roles = frappe.get_roles(user)
	
	# Define role-based access
	role_access = {
		"Production Manager": "1=1",  # Access to all
		"Warehouse Manager": "1=1",   # Access to all
		"Planeacion": "1=1",          # 2.2.0: the planner sees every Work Order (granted on top of Manufacturing User)
		"Manufacturing User": "(`tabWork Order`.owner = '{user}' OR `tabWork Order`.docstatus = 1)".format(user=user),
		"Stock User": "(`tabWork Order`.docstatus = 1)"  # Only submitted Work Orders
	}
	
	conditions = []
	for role in user_roles:
		if role in role_access:
			conditions.append(role_access[role])
	
	return " OR ".join(conditions) if conditions else "0=1"

#: The zone fields derived from current Bin quantities (custom_last_zone_update is the stamp).
ZONE_FIELDS = (
	"custom_current_zone_status",
	"custom_zone_status_color",
	"custom_material_completion_percentage",
	"custom_missing_materials_json",
)


def _zone_value_changed(fieldname, old, new):
	if fieldname == "custom_material_completion_percentage":
		# stored as a decimal column; compare at 6 places so a float re-computation of the same ratio is not a change
		return flt(old, 6) != flt(new, 6)
	return (old or "") != (new or "")


def refresh_zone_fields(work_order, force_stamp=False):
	"""Recompute the zone fields of a Work Order doc from current Bin quantities and write only what changed.

	No save(): no validate, no doc_events, no Version, no required_items re-derivation. The fields are
	written with db.set_value(update_modified=False). The stamp custom_last_zone_update is written when
	another zone field changed, or always when force_stamp is set (manual refresh).
	Returns the changed fieldnames (the stamp included when written)."""
	before = {f: work_order.get(f) for f in ZONE_FIELDS}
	update_material_requirements(work_order)
	changed = {f: work_order.get(f) for f in ZONE_FIELDS if _zone_value_changed(f, before[f], work_order.get(f))}
	if not changed and not force_stamp:
		return []
	changed["custom_last_zone_update"] = now_datetime()
	frappe.db.set_value("Work Order", work_order.name, changed, update_modified=False)
	work_order.custom_last_zone_update = changed["custom_last_zone_update"]
	return list(changed)


@frappe.whitelist()
def update_work_order_zone_status(work_order_name):
	"""API endpoint to manually update Work Order zone status (no save; see refresh_zone_fields)"""
	try:
		work_order = frappe.get_doc("Work Order", work_order_name, check_permission="read")
		refresh_zone_fields(work_order, force_stamp=True)

		return {
			"status": "success",
			"zone_status": work_order.custom_current_zone_status,
			"completion_percentage": work_order.custom_material_completion_percentage,
			"last_updated": work_order.custom_last_zone_update
		}
	except Exception as e:
		frappe.log_error(title="Work Order zone status update failed", message=frappe.get_traceback(),
			reference_doctype="Work Order", reference_name=work_order_name)
		return {"status": "error", "message": str(e)}

@frappe.whitelist()
def get_work_order_material_status(work_order_name):
	"""API endpoint to get detailed material status for a Work Order"""
	try:
		work_order = frappe.get_doc("Work Order", work_order_name)
		
		if not work_order.bom_no:
			return {"status": "error", "message": "No BOM associated with this Work Order"}
		
		# Get BOM items with availability
		bom_items = frappe.get_all(
			"BOM Item",
			filters={"parent": work_order.bom_no},
		fields=["item_code", "qty", "source_warehouse", "item_name", "description"]
		)
		
		material_status = []
		for bom_item in bom_items:
			required_qty = flt(bom_item.qty * work_order.qty)
			available_qty = get_available_qty(bom_item.item_code, bom_item.source_warehouse)
			
			material_status.append({
				"item_code": bom_item.item_code,
				"item_name": bom_item.item_name,
				"description": bom_item.description,
				"required_qty": required_qty,
				"available_qty": available_qty,
				"shortage": max(0, required_qty - available_qty),
				"source_warehouse": bom_item.source_warehouse,
				"status": "Available" if available_qty >= required_qty else "Shortage"
			})
		
		return {
			"status": "success",
			"work_order": work_order_name,
			"zone_status": work_order.custom_current_zone_status,
			"completion_percentage": work_order.custom_material_completion_percentage,
			"material_status": material_status
		}
	except Exception as e:
		frappe.log_error(f"Work Order material status check failed: {str(e)}")
		return {"status": "error", "message": str(e)}
