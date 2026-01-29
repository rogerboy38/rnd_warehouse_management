"""
Stock Entry customizations for RND Warehouse Management
"""
import frappe
from frappe.model.document import Document

class CustomStockEntry(Document):
	"""Custom Stock Entry with warehouse management features"""
	
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
		self.update_warehouse_utilization()
		self.log_temperature_compliance()
	
	def on_cancel(self):
		"""Execute after cancelling the Stock Entry"""
		super().on_cancel()
		self.reverse_warehouse_utilization()
		self.log_cancellation_reason()

	def validate_sap_movement_type(self):
		"""Validate SAP movement type mapping"""
		if self.custom_movement_type and not self.custom_sap_movement_type:
			# Map internal movement type to SAP code
			movement_type_doc = frappe.get_doc("Movement Type", self.custom_movement_type)
			if movement_type_doc and movement_type_doc.sap_movement_code:
				self.custom_sap_movement_type = movement_type_doc.sap_movement_code
	
	def set_zone_status(self):
		"""Set Red/Green zone status based on warehouses"""
		if self.to_warehouse:
			to_wh = frappe.get_doc("Warehouse", self.to_warehouse)
			if hasattr(to_wh, 'custom_is_zone_warehouse') and to_wh.custom_is_zone_warehouse:
				self.custom_zone_type = to_wh.custom_zone_type
	
	def validate_signatures(self):
		"""Validate required signatures based on movement type"""
		if self.custom_movement_type:
			movement_type = frappe.get_doc("Movement Type", self.custom_movement_type)
			if movement_type.requires_dual_signature:
				if not self.custom_operator_signature:
					frappe.throw("Operator signature is required for this movement type")
				if not self.custom_supervisor_signature:
					frappe.throw("Supervisor signature is required for this movement type")
	
	def validate_required_signatures(self):
		"""Validate all required signatures before submission"""
		if self.custom_movement_type:
			movement_type = frappe.get_doc("Movement Type", self.custom_movement_type)
			if movement_type.requires_dual_signature:
				if not self.custom_operator_signature:
					frappe.throw("Cannot submit: Operator signature is missing")
				if not self.custom_supervisor_signature:
					frappe.throw("Cannot submit: Supervisor signature is missing")
	
	def validate_warehouse_permissions(self):
		"""Validate user has permission for source/destination warehouses"""
		# Implementation depends on your permission structure
		pass
	
	def update_work_order_zone_status(self):
		"""Update work order with zone completion status"""
		if self.work_order and self.custom_zone_type:
			wo = frappe.get_doc("Work Order", self.work_order)
			if not hasattr(wo, 'custom_zone_status'):
				frappe.db.set_value("Work Order", self.work_order, "custom_zone_status", {})
			
			zone_status = frappe.parse_json(wo.custom_zone_status) if wo.custom_zone_status else {}
			zone_status[self.custom_zone_type] = "Completed"
			frappe.db.set_value("Work Order", self.work_order, "custom_zone_status", frappe.as_json(zone_status))
	
	def update_warehouse_utilization(self):
		"""Update warehouse utilization after stock movement"""
		warehouses_to_update = set()
		if self.from_warehouse:
			warehouses_to_update.add(self.from_warehouse)
		if self.to_warehouse:
			warehouses_to_update.add(self.to_warehouse)
		
		for warehouse in warehouses_to_update:
			self._update_single_warehouse_utilization(warehouse)
	
	def _update_single_warehouse_utilization(self, warehouse_name):
		"""Update utilization for a single warehouse"""
		from frappe.utils import now_datetime
		
		# Calculate current stock value in warehouse
		result = frappe.db.sql("""
			SELECT SUM(actual_qty * valuation_rate) as total_value
			FROM `tabStock Ledger Entry`
			WHERE warehouse = %s AND is_cancelled = 0
		""", warehouse_name)
		
		total_value = result[0][0] if result and result[0][0] else 0
		
		# Get warehouse capacity
		wh = frappe.get_doc("Warehouse", warehouse_name)
		if hasattr(wh, 'custom_max_capacity') and wh.custom_max_capacity:
			utilization = (total_value / wh.custom_max_capacity) * 100 if wh.custom_max_capacity > 0 else 0
			
			# Update warehouse
			frappe.db.set_value("Warehouse", warehouse_name, {
				"custom_current_utilization": round(utilization, 2),
				"custom_last_capacity_update": now_datetime()
			})
	
	def reverse_warehouse_utilization(self):
		"""Reverse warehouse utilization updates on cancellation"""
		# On cancellation, utilization will be recalculated on next stock movement
		# We just need to trigger a recalculation
		warehouses_to_update = set()
		if self.from_warehouse:
			warehouses_to_update.add(self.from_warehouse)
		if self.to_warehouse:
			warehouses_to_update.add(self.to_warehouse)
		
		for warehouse in warehouses_to_update:
			self._update_single_warehouse_utilization(warehouse)
	
	def log_temperature_compliance(self):
		"""Log temperature compliance for temperature-controlled warehouses"""
		if self.to_warehouse:
			wh = frappe.get_doc("Warehouse", self.to_warehouse)
			if hasattr(wh, 'custom_requires_monitoring') and wh.custom_requires_monitoring:
				# Check if temperature is within range at time of submission
				current_temp = wh.custom_current_temperature if hasattr(wh, 'custom_current_temperature') else None
				min_temp = wh.custom_min_temperature if hasattr(wh, 'custom_min_temperature') else None
				max_temp = wh.custom_max_temperature if hasattr(wh, 'custom_max_temperature') else None
				
				if current_temp is not None and min_temp is not None and max_temp is not None:
					if min_temp <= current_temp <= max_temp:
						status = "Within Range"
					else:
						status = "Out of Range"
					
					# Create compliance log
					frappe.get_doc({
						"doctype": "Temperature Compliance Log",
						"warehouse": self.to_warehouse,
						"stock_entry": self.name,
						"temperature": current_temp,
						"min_threshold": min_temp,
						"max_threshold": max_temp,
						"status": status,
						"timestamp": now_datetime()
					}).insert(ignore_permissions=True)
	
	def log_cancellation_reason(self):
		"""Log reason for stock entry cancellation"""
		# This would be implemented based on your business requirements
		pass

# Hooks
def on_update_after_submit(doc, method=None):
	"""Hook: After updating submitted Stock Entry"""
	pass

def get_permission_query_conditions(user):
	"""Permission query conditions for Stock Entry - FIXED VERSION"""
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
	
	# Check for full access roles first (Warehouse Manager, Stock User)
	full_access_roles = ["Warehouse Manager", "Stock User"]
	has_full_access = any(role in full_access_roles for role in user_roles)
	
	if has_full_access:
		return "1=1"
	
	# For non-full-access users, apply role-specific conditions
	conditions = []
	for role in user_roles:
		if role in role_warehouse_access:
			condition = role_warehouse_access[role]
			if condition not in conditions:  # Avoid duplicates
				conditions.append(condition)
	
	return " OR ".join(conditions) if conditions else "0=1"
