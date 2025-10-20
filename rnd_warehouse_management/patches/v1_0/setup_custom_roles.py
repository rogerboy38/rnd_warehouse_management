import frappe
from frappe import _

def execute():
	"""Setup custom roles for warehouse management"""
	frappe.log("Setting up custom roles...")
	
	# Define custom roles
	custom_roles = [
		{
			"role_name": "Warehouse Supervisor",
			"description": "Supervises warehouse operations and provides first-level approval for stock movements"
		},
		{
			"role_name": "Kitting Supervisor",
			"description": "Supervises kitting operations and provides second-level approval for material transfers"
		},
		{
			"role_name": "Zone Manager",
			"description": "Manages Red/Green zone operations and Work Order material status"
		}
	]
	
	created_count = 0
	
	for role_data in custom_roles:
		if not frappe.db.exists("Role", role_data["role_name"]):
			try:
				role = frappe.get_doc({
					"doctype": "Role",
					"role_name": role_data["role_name"],
					"description": role_data["description"]
				})
				role.insert(ignore_permissions=True)
				created_count += 1
				frappe.log(f"Created role: {role_data['role_name']}")
			except Exception as e:
				frappe.log_error(f"Failed to create role {role_data['role_name']}: {str(e)}")
	
	frappe.db.commit()
	frappe.log(f"Created {created_count} custom roles")