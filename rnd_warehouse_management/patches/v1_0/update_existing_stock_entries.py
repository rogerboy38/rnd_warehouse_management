import frappe
from frappe import _

def execute():
	"""Update existing Stock Entries to support new custom fields"""
	frappe.log("Updating existing Stock Entries...")
	
	# Get all existing Stock Entries
	stock_entries = frappe.get_all(
		"Stock Entry",
		filters={"docstatus": 1},  # Only submitted entries
		fields=["name", "purpose"]
	)
	
	updated_count = 0
	
	for entry in stock_entries:
		try:
			# Set default SAP movement type based on purpose
			sap_movement_type = None
			if entry.purpose == "Material Issue":
				sap_movement_type = "261"  # FrontFlush
			elif entry.purpose == "Material Transfer":
				sap_movement_type = "311"  # BackFlush
			
			if sap_movement_type:
				# Update with default values
				frappe.db.set_value(
					"Stock Entry",
					entry.name,
					{
						"custom_sap_movement_type": sap_movement_type,
						"custom_zone_status": "Red Zone",  # Default to Red Zone
						"custom_material_completion_percentage": 0,
						"custom_gi_gt_slip_number": f"GI-GT-{entry.name}"
					}
				)
				updated_count += 1
		
		except Exception as e:
			frappe.log_error(f"Failed to update Stock Entry {entry.name}: {str(e)}")
	
	frappe.db.commit()
	frappe.log(f"Updated {updated_count} existing Stock Entries")