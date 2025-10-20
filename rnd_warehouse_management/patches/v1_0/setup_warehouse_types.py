import frappe
from frappe import _

def execute():
	"""Setup warehouse types for existing warehouses"""
	frappe.log("Setting up warehouse types...")
	
	# Define warehouse type mappings based on naming patterns
	type_patterns = {
		"Raw Material": ["raw", "rm", "material"],
		"Work In Progress": ["wip", "production", "kitting", "zone"],
		"Finished Goods": ["fg", "finished", "sell"],
		"Transit": ["transit"],
		"Rejected": ["rejected", "reject"]
	}
	
	# Get all warehouses without warehouse_type
	warehouses = frappe.get_all(
		"Warehouse",
		filters={"warehouse_type": ["", None]},
		fields=["name", "warehouse_name"]
	)
	
	updated_count = 0
	
	for warehouse in warehouses:
		warehouse_name_lower = warehouse.warehouse_name.lower()
		assigned_type = None
		
		# Try to match warehouse type based on name patterns
		for warehouse_type, patterns in type_patterns.items():
			for pattern in patterns:
				if pattern in warehouse_name_lower:
					assigned_type = warehouse_type
					break
			if assigned_type:
				break
		
		# Default to "Finished Goods" if no pattern matches
		if not assigned_type:
			assigned_type = "Finished Goods"
		
		# Update warehouse
		frappe.db.set_value("Warehouse", warehouse.name, "warehouse_type", assigned_type)
		updated_count += 1
	
	frappe.db.commit()
	frappe.log(f"Updated warehouse types for {updated_count} warehouses")