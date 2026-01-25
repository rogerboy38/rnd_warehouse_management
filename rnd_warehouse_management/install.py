import frappe

def after_install():
    print("Starting RND Warehouse Management installation...")
    
    # Create Kitting Supervisor role if not exists
    if not frappe.db.exists("Role", "Kitting Supervisor"):
        role = frappe.get_doc({
            "doctype": "Role",
            "role_name": "Kitting Supervisor",
            "desk_access": 1
        })
        role.insert(ignore_permissions=True)
        print("Created role: Kitting Supervisor")
    
    print("RND Warehouse Management installation completed successfully!")
