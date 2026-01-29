import frappe
from frappe import _
from frappe.utils import flt

def before_save(doc, method=None):
	"""Hook: Before saving Warehouse"""
	validate_warehouse_configuration(doc)
	set_default_transit_warehouse(doc)
	update_temperature_settings(doc)

def validate_warehouse_configuration(doc):
	"""Validate warehouse configuration based on type"""
	if not doc.warehouse_type:
		return
	
	# Define validation rules for different warehouse types
	validation_rules = {
		"Raw Material": {
			"required_fields": [],
			"naming_pattern": "Raw Material",
			"temperature_controlled": False
		},
		"Work In Progress": {
			"required_fields": [],
			"naming_pattern": ["WIP", "Production", "Kitting", "Zone"],
			"temperature_controlled": False
		},
		"Finished Goods": {
			"required_fields": [],
			"naming_pattern": "FG",
			"temperature_controlled": True
		},
		"Transit": {
			"required_fields": [],
			"naming_pattern": "Transit",
			"is_group": False,
			"temperature_controlled": False
		},
		"Rejected": {
			"required_fields": [],
			"naming_pattern": "Rejected",
			"is_rejected": True,
			"temperature_controlled": False
		}
	}
	
	rules = validation_rules.get(doc.warehouse_type)
	if not rules:
		return
	
	# Validate naming pattern
	naming_patterns = rules.get("naming_pattern", [])
	if isinstance(naming_patterns, str):
		naming_patterns = [naming_patterns]
	
	if naming_patterns:
		valid_name = any(pattern.lower() in doc.warehouse_name.lower() for pattern in naming_patterns)
		if not valid_name:
			frappe.msgprint(_("Warning: Warehouse name '{0}' doesn't follow recommended pattern for {1} warehouses")
				.format(doc.warehouse_name, doc.warehouse_type), alert=True)
	
	# Auto-set properties based on warehouse type
	if doc.warehouse_type == "Transit":
		doc.is_group = 0  # Transit warehouses should not be group warehouses
	
	if doc.warehouse_type == "Rejected":
		doc.is_rejected_warehouse = 1
	
	# Set temperature control recommendations
	if rules.get("temperature_controlled") and not doc.custom_temperature_control:
		frappe.msgprint(_("Consider enabling temperature control for {0} warehouse").format(doc.warehouse_type), alert=True)

def set_default_transit_warehouse(doc):
	"""Set default in-transit warehouse based on warehouse type and location"""
	if doc.warehouse_type == "Transit":
		return  # Transit warehouses don't need in-transit warehouses
	
	if not doc.default_in_transit_warehouse:
		# Try to find or suggest a transit warehouse
		transit_warehouse_name = f"{doc.warehouse_name.replace(' - ', ' Transit - ')}"
		if "Transit" not in transit_warehouse_name:
			transit_warehouse_name = f"{doc.warehouse_name.split(' - ')[0]} Transit - {doc.company}"
		
		# Check if transit warehouse exists
		existing_transit = frappe.db.exists("Warehouse", transit_warehouse_name)
		if existing_transit:
			doc.default_in_transit_warehouse = existing_transit
		else:
			# Suggest creating a transit warehouse
			frappe.msgprint(_("Consider creating a transit warehouse: {0}").format(transit_warehouse_name), alert=True)

def update_temperature_settings(doc):
	"""Update temperature-related settings"""
	if doc.custom_temperature_control:
		# Validate temperature range
		if doc.custom_target_temperature:
			target_temp = flt(doc.custom_target_temperature)
			if target_temp < -50 or target_temp > 50:
				frappe.throw(_("Target temperature should be between -50°C and 50°C"))
		
		# Set default temperature if not specified
		if not doc.custom_target_temperature:
			if doc.warehouse_type == "Finished Goods":
				doc.custom_target_temperature = 20  # Room temperature for FG
			elif doc.warehouse_type == "Raw Material":
				doc.custom_target_temperature = 15  # Cooler for raw materials
			else:
				doc.custom_target_temperature = 25  # Standard warehouse temperature

@frappe.whitelist()
def create_warehouse_hierarchy(company, locations=None):
	"""API endpoint to create complete warehouse hierarchy"""
	try:
		if not locations:
			locations = ["AMB-W"]  # Default location
		
		created_warehouses = []
		
		for location in locations:
			warehouses_to_create = [
				# Raw Material Division
				{"name": f"Raw Material Main - {location}", "type": "Raw Material", "parent": None},
				{"name": f"Raw Material Transit - {location}", "type": "Transit", "parent": f"Raw Material Main - {location}"},
				{"name": f"Raw Material Rejected - {location}", "type": "Rejected", "parent": f"Raw Material Main - {location}"},
				
				# Production Division
				{"name": f"Production WIP - {location}", "type": "Work In Progress", "parent": None},
				{"name": f"Production Transit - {location}", "type": "Transit", "parent": f"Production WIP - {location}"},
				{"name": f"Kitting Area - {location}", "type": "Work In Progress", "parent": f"Production WIP - {location}"},
				{"name": f"Kitting Transit - {location}", "type": "Transit", "parent": f"Kitting Area - {location}"},
				{"name": f"Production Rejected - {location}", "type": "Rejected", "parent": f"Production WIP - {location}"},
				
				# Finished Goods Division
				{"name": f"FG Main - {location}", "type": "Finished Goods", "parent": None},
				{"name": f"FG to Sell - {location}", "type": "Finished Goods", "parent": f"FG Main - {location}"},
				{"name": f"FG Transit - {location}", "type": "Transit", "parent": f"FG Main - {location}"},
				{"name": f"FG Rejected - {location}", "type": "Rejected", "parent": f"FG Main - {location}"},
				
				# Work Order Zones
				{"name": f"Red Zone - {location}", "type": "Work In Progress", "parent": None},
				{"name": f"Green Zone - {location}", "type": "Work In Progress", "parent": None},
				{"name": f"Zone Transit - {location}", "type": "Transit", "parent": None}
			]
			
			for warehouse_config in warehouses_to_create:
				if not frappe.db.exists("Warehouse", warehouse_config["name"]):
					warehouse = frappe.get_doc({
						"doctype": "Warehouse",
						"warehouse_name": warehouse_config["name"],
						"warehouse_type": warehouse_config["type"],
						"parent_warehouse": warehouse_config["parent"],
						"company": company,
						"is_group": 1 if warehouse_config["type"] != "Transit" else 0,
						"is_rejected_warehouse": 1 if warehouse_config["type"] == "Rejected" else 0
					})
					
					try:
						warehouse.insert(ignore_permissions=True)
						created_warehouses.append(warehouse.name)
					except Exception as e:
						frappe.log_error(f"Failed to create warehouse {warehouse_config['name']}: {str(e)}")
			
		return {
			"status": "success",
			"message": f"Created {len(created_warehouses)} warehouses",
			"created_warehouses": created_warehouses
		}
	except Exception as e:
		frappe.log_error(f"Warehouse hierarchy creation failed: {str(e)}")
		return {"status": "error", "message": str(e)}

@frappe.whitelist()
def get_warehouse_dashboard_data(warehouse=None):
	"""API endpoint to get warehouse dashboard data"""
	try:
		filters = {}
		if warehouse:
			filters["name"] = warehouse
		
		warehouses = frappe.get_all(
			"Warehouse",
			filters=filters,
			fields=["name", "warehouse_type", "is_group", "parent_warehouse", "company", "custom_temperature_control", "custom_target_temperature"]
		)
		
		# Get stock levels for each warehouse
		for wh in warehouses:
			stock_data = frappe.db.sql("""
				SELECT 
					COUNT(DISTINCT item_code) as item_count,
					SUM(actual_qty) as total_qty,
					SUM(stock_value) as total_value
				FROM `tabBin`
				WHERE warehouse = %s AND actual_qty > 0
			""", wh["name"], as_dict=True)
			
			if stock_data:
				wh.update(stock_data[0])
			else:
				wh.update({"item_count": 0, "total_qty": 0, "total_value": 0})
		
		return {
			"status": "success",
			"warehouses": warehouses
		}
	except Exception as e:
		frappe.log_error(f"Warehouse dashboard data fetch failed: {str(e)}")
		return {"status": "error", "message": str(e)}