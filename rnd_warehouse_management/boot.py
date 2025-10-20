import frappe

def boot_session(bootinfo):
	"""Add RND Warehouse Management data to boot info"""
	
	# Add warehouse types mapping
	bootinfo.warehouse_types = {
		"Raw Material": "Stores raw materials and components",
		"Work In Progress": "Items currently being manufactured or assembled",
		"Finished Goods": "Completed products ready for sale",
		"Transit": "Virtual warehouse for items in movement",
		"Rejected": "Storage for rejected or defective materials"
	}
	
	# Add SAP movement types
	bootinfo.sap_movement_types = {
		"261": {
			"name": "FrontFlush - Goods Issue for Production",
			"description": "Issue materials from storage to production",
			"purpose": "Material Issue",
			"required_signatures": ["warehouse_supervisor"]
		},
		"311": {
			"name": "BackFlush - Transfer for Kitting",
			"description": "Transfer materials from production to kitting area",
			"purpose": "Material Transfer",
			"required_signatures": ["warehouse_supervisor", "kitting_supervisor"]
		}
	}
	
	# Add zone status information
	bootinfo.zone_status_info = {
		"Red Zone": {
			"color": "#dc3545",
			"description": "Incomplete materials - Work Order cannot proceed",
			"icon": "fa fa-exclamation-triangle"
		},
		"Green Zone": {
			"color": "#28a745",
			"description": "All materials available - Work Order ready for production",
			"icon": "fa fa-check-circle"
		}
	}
	
	# Add current user's warehouse permissions
	user_warehouses = get_user_warehouse_permissions(frappe.session.user)
	bootinfo.user_warehouses = user_warehouses
	
	# Add app version and features
	bootinfo.rnd_warehouse_management = {
		"version": "1.0.0",
		"features": [
			"SAP Movement Types (261, 311)",
			"Dual Signature Workflow",
			"Red/Green Zone Logic",
			"GI/GT Slip Generation",
			"Warehouse Type Management",
			"Transit Warehouse Tracking"
		]
	}

def get_user_warehouse_permissions(user):
	"""Get warehouses accessible by the current user"""
	try:
		user_roles = frappe.get_roles(user)
		
		# Define role-based warehouse access
		role_warehouse_mapping = {
			"Warehouse Manager": "all",
			"Stock User": "all",
			"Warehouse Supervisor": ["Raw Material", "Work In Progress", "Transit"],
			"Kitting Supervisor": ["Work In Progress", "Finished Goods", "Transit"],
			"Production Manager": ["Work In Progress", "Raw Material"]
		}
		
		allowed_types = set()
		for role in user_roles:
			if role in role_warehouse_mapping:
				access = role_warehouse_mapping[role]
				if access == "all":
					allowed_types.update(["Raw Material", "Work In Progress", "Finished Goods", "Transit", "Rejected"])
				elif isinstance(access, list):
					allowed_types.update(access)
		
		# Get actual warehouses
		if allowed_types:
			warehouses = frappe.get_all(
				"Warehouse",
				filters={"warehouse_type": ["in", list(allowed_types)]},
				fields=["name", "warehouse_type", "company"]
			)
			return warehouses
		else:
			return []
	except Exception:
		return []