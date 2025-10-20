import frappe
from frappe import _

def after_install():
	"""Post-installation setup tasks"""
	frappe.log("Starting RND Warehouse Management installation...")
	
	# Create custom roles
	create_custom_roles()
	
	# Set up default permissions
	setup_permissions()
	
	# Create default print formats
	setup_print_formats()
	
	# Create sample warehouses if none exist
	setup_sample_warehouses()
	
	# Install custom fields from fixtures
	install_custom_fields()
	
	# Set up workflows
	setup_workflows()
	
	frappe.log("RND Warehouse Management installation completed successfully!")
	frappe.msgprint(_("RND Warehouse Management has been installed successfully!"))

def create_custom_roles():
	"""Create custom roles for warehouse management"""
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
	
	for role_data in custom_roles:
		if not frappe.db.exists("Role", role_data["role_name"]):
			role = frappe.get_doc({
				"doctype": "Role",
				"role_name": role_data["role_name"],
				"description": role_data["description"]
			})
			role.insert(ignore_permissions=True)
			frappe.log(f"Created role: {role_data['role_name']}")

def setup_permissions():
	"""Set up role-based permissions"""
	# Permission mappings for custom roles
	permissions = [
		{
			"doctype": "Stock Entry",
			"role": "Warehouse Supervisor",
			"permlevel": 0,
			"read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1
		},
		{
			"doctype": "Stock Entry",
			"role": "Kitting Supervisor",
			"permlevel": 0,
			"read": 1, "write": 1, "submit": 1
		},
		{
			"doctype": "Work Order",
			"role": "Zone Manager",
			"permlevel": 0,
			"read": 1, "write": 1
		}
	]
	
	for perm in permissions:
		if not frappe.db.exists("Custom DocPerm", {
			"parent": perm["doctype"],
			"role": perm["role"]
		}):
			doc_perm = frappe.get_doc({
				"doctype": "Custom DocPerm",
				"parent": perm["doctype"],
				"parenttype": "DocType",
				"parentfield": "permissions",
				"role": perm["role"],
				"permlevel": perm["permlevel"],
				"read": perm.get("read", 0),
				"write": perm.get("write", 0),
				"create": perm.get("create", 0),
				"submit": perm.get("submit", 0),
				"cancel": perm.get("cancel", 0)
			})
			doc_perm.insert(ignore_permissions=True)

def setup_print_formats():
	"""Create default print formats"""
	# This will be implemented in the print format creation step
	pass

def setup_sample_warehouses():
	"""Create sample warehouse hierarchy if no warehouses exist"""
	company = frappe.db.get_single_value("Global Defaults", "default_company")
	if not company:
		company = frappe.get_all("Company", limit=1)
		if company:
			company = company[0].name
		else:
			return
	
	# Check if any warehouses exist
	existing_warehouses = frappe.get_all("Warehouse", limit=1)
	if existing_warehouses:
		return  # Don't create samples if warehouses already exist
	
	# Create basic warehouse structure
	from rnd_warehouse_management.warehouse_management.warehouse import create_warehouse_hierarchy
	create_warehouse_hierarchy(company)

def install_custom_fields():
	"""Install custom fields from fixtures"""
	# Custom fields will be automatically installed via fixtures
	pass

def setup_workflows():
	"""Set up default workflows"""
	# This will be implemented in the workflow creation step
	pass