import frappe
from frappe import _

def after_uninstall():
	"""Clean up after app uninstallation"""
	frappe.log("Starting RND Warehouse Management uninstallation...")
	
	# Remove custom roles (optional - be careful not to break existing data)
	remove_custom_roles()
	
	# Clean up custom permissions
	cleanup_permissions()
	
	frappe.log("RND Warehouse Management uninstallation completed.")
	frappe.msgprint(_("RND Warehouse Management has been uninstalled."))

def remove_custom_roles():
	"""Remove custom roles created by the app"""
	custom_roles = ["Warehouse Supervisor", "Kitting Supervisor", "Zone Manager"]
	
	for role_name in custom_roles:
		if frappe.db.exists("Role", role_name):
			# Check if role is assigned to any users
			assigned_users = frappe.get_all(
				"Has Role",
				filters={"role": role_name},
				pluck="parent"
			)
			
			if not assigned_users:
				# Safe to delete if not assigned to any users
				frappe.delete_doc("Role", role_name, ignore_permissions=True)
				frappe.log(f"Removed role: {role_name}")
			else:
				frappe.log(f"Kept role {role_name} as it's assigned to users: {assigned_users}")

def cleanup_permissions():
	"""Clean up custom permissions"""
	custom_roles = ["Warehouse Supervisor", "Kitting Supervisor", "Zone Manager"]
	
	for role in custom_roles:
		# Remove custom DocPerms for our roles
		custom_perms = frappe.get_all(
			"Custom DocPerm",
			filters={"role": role},
			pluck="name"
		)
		
		for perm_name in custom_perms:
			frappe.delete_doc("Custom DocPerm", perm_name, ignore_permissions=True)