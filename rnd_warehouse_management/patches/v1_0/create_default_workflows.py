import frappe
from frappe import _

def execute():
	"""Create default workflows for Stock Entry"""
	frappe.log("Creating default workflows...")
	
	# Check if workflow already exists
	if frappe.db.exists("Workflow", "Stock Entry Dual Signature Approval"):
		frappe.log("Workflow already exists, skipping creation")
		return
	
	try:
		# Create workflow from fixture data
		from frappe.core.doctype.data_import.data_import import import_doc
		
		# Import workflow fixtures
		fixture_files = [
			"workflow.json",
			"workflow_state.json",
			"workflow_action_master.json",
			"workflow_transition.json"
		]
		
		for fixture_file in fixture_files:
			fixture_path = frappe.get_app_path("rnd_warehouse_management", "fixtures", fixture_file)
			if frappe.os.path.exists(fixture_path):
				with open(fixture_path, 'r') as f:
					data = frappe.parse_json(f.read())
					for record in data:
						if not frappe.db.exists(record["doctype"], record.get("name") or record.get("workflow_name")):
							doc = frappe.get_doc(record)
							doc.insert(ignore_permissions=True)
		
		frappe.db.commit()
		frappe.log("Default workflows created successfully")
	
	except Exception as e:
		frappe.log_error(f"Failed to create default workflows: {str(e)}")