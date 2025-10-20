import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, flt
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
import json

class CustomStockEntry(StockEntry):
	"""Custom Stock Entry with SAP Movement Type support and signature workflow"""
	
	def before_save(self):
		"""Execute before saving the Stock Entry"""
		super().before_save()
		self.validate_sap_movement_type()
		self.set_zone_status()
		self.validate_signatures()
	
	def before_submit(self):
		"""Execute before submitting the Stock Entry"""
		super().before_submit()
		self.validate_required_signatures()
		self.validate_warehouse_permissions()
	
	def on_submit(self):
		"""Execute after submitting the Stock Entry"""
		super().on_submit()
		self.update_work_order_zone_status()
		self.create_gi_gt_slip_reference()
	
	def validate_sap_movement_type(self):
		"""Validate SAP Movement Type and set appropriate warehouse mappings"""
		if not self.custom_sap_movement_type:
			return
		
		# Define SAP Movement Type mappings
		sap_mappings = {
			"261": {  # FrontFlush - Goods Issue for Production
				"purpose": "Material Issue",
				"required_signatures": ["warehouse_supervisor"],
				"allowed_source_warehouses": ["Raw Material", "Work In Progress"],
				"allowed_target_warehouses": ["Work In Progress", "Production WIP"],
				"zone_transition": "to_red"
			},
			"311": {  # BackFlush - Transfer for Kitting
				"purpose": "Material Transfer",
				"required_signatures": ["warehouse_supervisor", "kitting_supervisor"],
				"allowed_source_warehouses": ["Work In Progress", "Production WIP"],
				"allowed_target_warehouses": ["Work In Progress", "Kitting Area"],
				"zone_transition": "to_green"
			}
		}
		
		mapping = sap_mappings.get(self.custom_sap_movement_type)
		if not mapping:
			frappe.throw(_("Invalid SAP Movement Type: {0}").format(self.custom_sap_movement_type))
		
		# Set purpose based on SAP movement type
		if not self.purpose:
			self.purpose = mapping["purpose"]
		
		# Validate warehouse types
		self.validate_warehouse_types(mapping)
	
	def validate_warehouse_types(self, mapping):
		"""Validate that source and target warehouses match SAP movement requirements"""
		for item in self.items:
			if item.s_warehouse:
				source_type = frappe.db.get_value("Warehouse", item.s_warehouse, "warehouse_type")
				if source_type not in mapping["allowed_source_warehouses"]:
					frappe.throw(_("Source warehouse {0} type '{1}' not allowed for SAP Movement {2}")
						.format(item.s_warehouse, source_type, self.custom_sap_movement_type))
			
			if item.t_warehouse:
				target_type = frappe.db.get_value("Warehouse", item.t_warehouse, "warehouse_type")
				if target_type not in mapping["allowed_target_warehouses"]:
					frappe.throw(_("Target warehouse {0} type '{1}' not allowed for SAP Movement {2}")
						.format(item.t_warehouse, target_type, self.custom_sap_movement_type))
	
	def set_zone_status(self):
		"""Set Red/Green zone status based on material availability"""
		if not self.custom_work_order_reference:
			return
		
		# Check material completeness for the Work Order
		material_completeness = self.calculate_material_completeness()
		
		if material_completeness >= 100:
			self.custom_zone_status = "Green Zone"  # Complete materials
			self.custom_zone_status_color = "#28a745"  # Green
		else:
			self.custom_zone_status = "Red Zone"    # Incomplete materials
			self.custom_zone_status_color = "#dc3545"  # Red
		
		self.custom_material_completion_percentage = material_completeness
	
	def calculate_material_completeness(self):
		"""Calculate percentage of materials available for Work Order"""
		if not self.custom_work_order_reference:
			return 0
		
		# Get Work Order BOM requirements
		work_order = frappe.get_doc("Work Order", self.custom_work_order_reference)
		if not work_order.bom_no:
			return 0
		
		# Get BOM items and check availability
		bom_items = frappe.get_all(
			"BOM Item",
			filters={"parent": work_order.bom_no},
			fields=["item_code", "qty", "warehouse"]
		)
		
		total_items = len(bom_items)
		complete_items = 0
		
		for bom_item in bom_items:
			# Check stock availability
			available_qty = frappe.db.get_value(
				"Bin",
				{"item_code": bom_item.item_code, "warehouse": bom_item.warehouse},
				"actual_qty"
			) or 0
			
			if flt(available_qty) >= flt(bom_item.qty * work_order.qty):
				complete_items += 1
		
		return (complete_items / total_items * 100) if total_items > 0 else 0
	
	def validate_signatures(self):
		"""Validate signature requirements based on workflow state"""
		if self.workflow_state == "Warehouse Approved":
			if not self.custom_warehouse_supervisor_signature:
				frappe.throw(_("Warehouse Supervisor signature is required for approval"))
			if not self.custom_warehouse_supervisor_sign_date:
				self.custom_warehouse_supervisor_sign_date = now_datetime()
				
		elif self.workflow_state == "Kitting Approved":
			if not self.custom_kitting_supervisor_signature:
				frappe.throw(_("Kitting Supervisor signature is required for final approval"))
			if not self.custom_kitting_supervisor_sign_date:
				self.custom_kitting_supervisor_sign_date = now_datetime()
	
	def validate_required_signatures(self):
		"""Validate that all required signatures are present before submission"""
		if self.custom_sap_movement_type == "311":  # BackFlush requires both signatures
			if not self.custom_warehouse_supervisor_signature:
				frappe.throw(_("Warehouse Supervisor signature is required for SAP Movement 311"))
			if not self.custom_kitting_supervisor_signature:
				frappe.throw(_("Kitting Supervisor signature is required for SAP Movement 311"))
				
		elif self.custom_sap_movement_type == "261":  # FrontFlush requires warehouse signature
			if not self.custom_warehouse_supervisor_signature:
				frappe.throw(_("Warehouse Supervisor signature is required for SAP Movement 261"))
	
	def validate_warehouse_permissions(self):
		"""Validate user permissions for warehouse operations"""
		user_roles = frappe.get_roles(frappe.session.user)
		
		# Check if user has permission to operate on specific warehouses
		for item in self.items:
			for warehouse in [item.s_warehouse, item.t_warehouse]:
				if warehouse:
					warehouse_type = frappe.db.get_value("Warehouse", warehouse, "warehouse_type")
					
					# Define required roles for warehouse types
					required_roles = {
						"Raw Material": ["Warehouse Manager", "Stock User"],
						"Work In Progress": ["Production Manager", "Warehouse Manager"],
						"Finished Goods": ["Warehouse Manager", "Sales User"],
						"Transit": ["Warehouse Manager", "Stock User"]
					}
					
					warehouse_required_roles = required_roles.get(warehouse_type, [])
					if warehouse_required_roles and not any(role in user_roles for role in warehouse_required_roles):
						frappe.throw(_("Insufficient permissions for {0} warehouse: {1}")
							.format(warehouse_type, warehouse))
	
	def update_work_order_zone_status(self):
		"""Update Work Order with current zone status"""
		if not self.custom_work_order_reference:
			return
		
		# Update Work Order with zone status
		frappe.db.set_value(
			"Work Order",
			self.custom_work_order_reference,
			{
				"custom_current_zone_status": self.custom_zone_status,
				"custom_material_completion_percentage": self.custom_material_completion_percentage,
				"custom_last_stock_entry": self.name,
				"custom_last_zone_update": now_datetime()
			}
		)
		
		frappe.db.commit()
	
	def create_gi_gt_slip_reference(self):
		"""Create reference for GI/GT Slip generation"""
		self.custom_gi_gt_slip_number = f"GI-GT-{self.name}"
		self.custom_gi_gt_slip_generated_on = now_datetime()
		
		# Save the reference
		frappe.db.set_value(
			"Stock Entry",
			self.name,
			{
				"custom_gi_gt_slip_number": self.custom_gi_gt_slip_number,
				"custom_gi_gt_slip_generated_on": self.custom_gi_gt_slip_generated_on
			}
		)

# Hook functions for Stock Entry events
def before_save(doc, method=None):
	"""Hook: Before saving Stock Entry"""
	if hasattr(doc, 'custom_sap_movement_type') and doc.custom_sap_movement_type:
		custom_stock_entry = CustomStockEntry(doc.as_dict())
		custom_stock_entry.before_save()
		
		# Update the original doc with calculated values
		for field in ['custom_zone_status', 'custom_zone_status_color', 'custom_material_completion_percentage']:
			if hasattr(custom_stock_entry, field):
				setattr(doc, field, getattr(custom_stock_entry, field))

def before_submit(doc, method=None):
	"""Hook: Before submitting Stock Entry"""
	if hasattr(doc, 'custom_sap_movement_type') and doc.custom_sap_movement_type:
		custom_stock_entry = CustomStockEntry(doc.as_dict())
		custom_stock_entry.before_submit()

def on_submit(doc, method=None):
	"""Hook: After submitting Stock Entry"""
	if hasattr(doc, 'custom_sap_movement_type') and doc.custom_sap_movement_type:
		custom_stock_entry = CustomStockEntry(doc.as_dict())
		custom_stock_entry.on_submit()

def before_cancel(doc, method=None):
	"""Hook: Before cancelling Stock Entry"""
	pass

def on_update_after_submit(doc, method=None):
	"""Hook: After updating submitted Stock Entry"""
	pass

def get_permission_query_conditions(user):
	"""Permission query conditions for Stock Entry"""
	if not user:
		user = frappe.session.user
	
	user_roles = frappe.get_roles(user)
	
	# Define role-based warehouse access
	role_warehouse_access = {
		"Warehouse Manager": "1=1",  # Access to all
		"Stock User": "1=1",        # Access to all
		"Production Manager": "(`tabStock Entry`.purpose in ('Material Issue', 'Material Transfer'))",
		"Sales User": "(`tabStock Entry`.purpose = 'Material Issue' AND `tabStock Entry`.to_warehouse LIKE '%FG%')"
	}
	
	conditions = []
	for role in user_roles:
		if role in role_warehouse_access:
			conditions.append(role_warehouse_access[role])
	
	return " OR ".join(conditions) if conditions else "0=1"

@frappe.whitelist()
def make_custom_stock_entry(work_order, purpose, qty=None):
	"""Custom method to create Stock Entry with SAP movement type"""
	from erpnext.stock.doctype.stock_entry.stock_entry import make_stock_entry
	
	# Create standard stock entry
	stock_entry = make_stock_entry(work_order, purpose, qty)
	
	# Add custom SAP movement type based on purpose
	if purpose == "Material Issue":
		stock_entry.custom_sap_movement_type = "261"  # FrontFlush
	elif purpose == "Material Transfer":
		stock_entry.custom_sap_movement_type = "311"  # BackFlush
	
	# Set Work Order reference
	stock_entry.custom_work_order_reference = work_order
	
	return stock_entry