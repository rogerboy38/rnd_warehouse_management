import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, flt
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
import json

class CustomStockEntry(StockEntry):
	"""Custom Stock Entry with Movement Type Master support and signature workflow"""
	
	def before_save(self):
		"""Execute before saving the Stock Entry"""
		super().before_save()
		self.sync_movement_type_details()
		self.validate_movement_type()
		self.set_zone_status()
		self.validate_signatures()
	
	def before_submit(self):
		"""Execute before submitting the Stock Entry"""
		super().before_submit()
		self.validate_required_signatures()
		self.validate_warehouse_permissions()
		self.validate_movement_type_requirements()
	
	def on_submit(self):
		"""Execute after submitting the Stock Entry"""
		super().on_submit()
		self.update_work_order_zone_status()
		self.create_gi_gt_slip_reference()
	
	def sync_movement_type_details(self):
		"""Sync Movement Type Master details to Stock Entry"""
		if not self.custom_sap_movement_type:
			return
		
		try:
			movement_type = frappe.get_doc("Movement Type Master", self.custom_sap_movement_type)
			
			# Populate read-only fields from Movement Type Master
			self.custom_movement_type_description = movement_type.description
			self.custom_movement_category = movement_type.category
			
			# Auto-set purpose if not already set
			if not self.purpose and movement_type.erpnext_stock_entry_purpose:
				self.purpose = movement_type.erpnext_stock_entry_purpose
				
		except frappe.DoesNotExistError:
			frappe.throw(_("Movement Type {0} does not exist in Movement Type Master").format(self.custom_sap_movement_type))
	
	def validate_movement_type(self):
		"""Validate Movement Type using Movement Type Master"""
		if not self.custom_sap_movement_type:
			return
		
		movement_type = frappe.get_doc("Movement Type Master", self.custom_sap_movement_type)
		
		# Check if movement type is active
		if not movement_type.is_active:
			frappe.throw(_("Movement Type {0} is not active").format(self.custom_sap_movement_type))
		
		# Validate warehouse requirements
		if movement_type.requires_source_warehouse:
			if not any(item.s_warehouse for item in self.items):
				frappe.throw(_("Movement Type {0} requires a source warehouse").format(movement_type.movement_code))
				
		if movement_type.requires_target_warehouse:
			if not any(item.t_warehouse for item in self.items):
				frappe.throw(_("Movement Type {0} requires a target warehouse").format(movement_type.movement_code))
		
		# Execute custom validation rules if defined
		if movement_type.validation_rules:
			self.execute_custom_validation(movement_type)
	
	def execute_custom_validation(self, movement_type):
		"""Execute custom validation rules from Movement Type Master"""
		try:
			exec_context = {
				"frappe": frappe,
				"stock_entry": self,
				"movement_type": movement_type,
				"valid": True,
				"message": ""
			}
			
			exec(movement_type.validation_rules, exec_context)
			
			if not exec_context.get("valid", True):
				frappe.throw(exec_context.get("message", "Custom validation failed"))
			except Exception as e:
				frappe.log_error(f"Movement Type Validation Error: {str(e)}")
				frappe.throw(_("Validation rule execution failed: {0}").format(str(e)))
	
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
		if not self.custom_sap_movement_type:
			return
			
		movement_type = frappe.get_doc("Movement Type Master", self.custom_sap_movement_type)
		
		# Check if approval is required
		if movement_type.requires_approval:
			# Always require warehouse supervisor signature for approved movements
			if not self.custom_warehouse_supervisor_signature:
				frappe.throw(_("Warehouse Supervisor signature is required for Movement Type {0}").format(movement_type.movement_code))
			
			# Check for kitting signature for specific movement types (311 and other transfer types)
			if movement_type.category == "Production" and movement_type.stock_movement_type == "Transfer":
				if not self.custom_kitting_supervisor_signature:
					frappe.throw(_("Kitting Supervisor signature is required for Movement Type {0}").format(movement_type.movement_code))
					
			# Check authorization level
			if movement_type.authorization_level in ["Manager", "Director"]:
				user_roles = frappe.get_roles(frappe.session.user)
				required_roles = {
					"Manager": ["Warehouse Manager", "Stock Manager", "System Manager"],
					"Director": ["Director", "System Manager"]
				}
				
				if not any(role in user_roles for role in required_roles.get(movement_type.authorization_level, [])):
					frappe.throw(_("Movement Type {0} requires {1} level authorization").format(
						movement_type.movement_code, movement_type.authorization_level))
	
	def validate_movement_type_requirements(self):
		"""Additional validation for movement type requirements before submission"""
		if not self.custom_sap_movement_type:
			return
			
		movement_type = frappe.get_doc("Movement Type Master", self.custom_sap_movement_type)
		
		# Check if negative stock is allowed
		if not movement_type.allow_negative_stock:
			for item in self.items:
				if item.s_warehouse:
					available_qty = frappe.db.get_value(
						"Bin",
						{"item_code": item.item_code, "warehouse": item.s_warehouse},
						"actual_qty"
					) or 0
					
					if flt(available_qty) < flt(item.qty):
						frappe.throw(_("Insufficient stock for {0} in {1}. Available: {2}, Required: {3}").format(
							item.item_code, item.s_warehouse, available_qty, item.qty))
	
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
		"""Create reference for GI/GT Slip generation if enabled in Movement Type Master"""
		if not self.custom_sap_movement_type:
			return
			
		movement_type = frappe.get_doc("Movement Type Master", self.custom_sap_movement_type)
		
		# Only create GI-GT slip if enabled in Movement Type Master
		if movement_type.auto_create_gi_gt_slip:
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
		custom_stock_entry.sync_movement_type_details()
		custom_stock_entry.validate_movement_type()
		custom_stock_entry.set_zone_status()
		custom_stock_entry.validate_signatures()
		
		# Update the original doc with calculated values
		for field in ['custom_zone_status', 'custom_zone_status_color', 'custom_material_completion_percentage',
					  'custom_movement_type_description', 'custom_movement_category', 'purpose']:
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
	
	# Determine appropriate movement type based on purpose
	movement_type_mapping = {
		"Material Consumption for Manufacture": "261",  # FrontFlush - Goods Issue for Production
		"Material Transfer for Manufacture": "311",    # BackFlush - Transfer for Kitting
		"Material Issue": "201",                       # Goods Issue for Cost Center
		"Material Receipt": "101",                     # Goods Receipt for Purchase Order
		"Material Transfer": "303"                     # Transfer Posting - Storage Location to Storage Location
	}
	
	if purpose in movement_type_mapping:
		stock_entry.custom_sap_movement_type = movement_type_mapping[purpose]
	
	# Set Work Order reference
	stock_entry.custom_work_order_reference = work_order
	
	return stock_entry


@frappe.whitelist()
def get_movement_types_for_purpose(purpose=None):
	"""Get available movement types, optionally filtered by ERPNext purpose"""
	filters = {"is_active": 1}
	
	if purpose:
		filters["erpnext_stock_entry_purpose"] = purpose
	
	movement_types = frappe.get_all(
		"Movement Type Master",
		filters=filters,
		fields=["movement_code", "description", "category", "stock_movement_type", "requires_approval"],
		order_by="movement_code"
	)
	
	return movement_types


@frappe.whitelist()
def get_movement_type_details_for_ui(movement_code):
	"""Get movement type details for UI display"""
	if not movement_code:
		return None
		
	try:
		movement_type = frappe.get_doc("Movement Type Master", movement_code)
		return {
			"movement_code": movement_type.movement_code,
			"description": movement_type.description,
			"category": movement_type.category,
			"stock_movement_type": movement_type.stock_movement_type,
			"requires_approval": movement_type.requires_approval,
			"authorization_level": movement_type.authorization_level,
			"erpnext_stock_entry_purpose": movement_type.erpnext_stock_entry_purpose,
			"requires_source_warehouse": movement_type.requires_source_warehouse,
			"requires_target_warehouse": movement_type.requires_target_warehouse,
			"auto_create_gi_gt_slip": movement_type.auto_create_gi_gt_slip
		}
	except frappe.DoesNotExistError:
		return None


# ========== PHASE 2: APPROVAL WORKFLOW FUNCTIONS ==========

@frappe.whitelist()
def request_approval(stock_entry_name):
	"""Request approval for a stock entry"""
	from rnd_warehouse_management.warehouse_management.doctype.stock_entry_approval_rule.stock_entry_approval_rule import get_next_approvers
	from rnd_warehouse_management.warehouse_management.doctype.stock_entry_audit_log.stock_entry_audit_log import log_stock_entry_event
	
	stock_entry = frappe.get_doc("Stock Entry", stock_entry_name)
	
	# Check if movement type requires approval
	if not stock_entry.custom_sap_movement_type:
		frappe.throw(_("Movement Type is required to request approval"))
	
	movement_type = frappe.get_doc("Movement Type Master", stock_entry.custom_sap_movement_type)
	
	if not movement_type.requires_approval:
		frappe.throw(_("This movement type does not require approval"))
	
	# Get next approvers (Level 1)
	approvers = get_next_approvers(
		stock_entry.custom_sap_movement_type,
		current_level=0,
		stock_entry_data=stock_entry.as_dict()
	)
	
	if not approvers:
		frappe.throw(_("No approval rules configured for this movement type"))
	
	# Update stock entry status
	stock_entry.custom_approval_status = "Pending Level 1"
	stock_entry.custom_current_approval_level = 0
	stock_entry.custom_approval_requested_on = now_datetime()
	
	# Set pending approver (first approver if multiple)
	stock_entry.custom_pending_approver = approvers[0]["user"]
	
	stock_entry.save(ignore_permissions=True)
	
	# Create audit log
	log_stock_entry_event(
		stock_entry=stock_entry.name,
		event_type="Approval Requested",
		approval_level=1,
		approval_status="Pending",
		additional_data={"approvers": approvers}
	)
	
	# Send notifications
	for approver in approvers:
		if approver.get("send_notification"):
			send_approval_notification(
				stock_entry=stock_entry,
				approver=approver["user"],
				approval_level=1
			)
	
	frappe.db.commit()
	
	return {
		"success": True,
		"message": _("Approval request sent to {0} approvers").format(len(approvers)),
		"approvers": approvers
	}


@frappe.whitelist()
def approve_stock_entry(stock_entry_name, comments=None, signature_data=None):
	"""Approve a stock entry at current level"""
	from rnd_warehouse_management.warehouse_management.doctype.stock_entry_approval_rule.stock_entry_approval_rule import get_next_approvers
	from rnd_warehouse_management.warehouse_management.doctype.stock_entry_audit_log.stock_entry_audit_log import log_stock_entry_event
	
	stock_entry = frappe.get_doc("Stock Entry", stock_entry_name)
	current_level = stock_entry.custom_current_approval_level
	
	# Validate user has permission to approve
	if not can_approve(stock_entry, frappe.session.user):
		frappe.throw(_("You do not have permission to approve this Stock Entry"))
	
	# Update approval level
	new_level = current_level + 1
	stock_entry.custom_current_approval_level = new_level
	stock_entry.custom_approval_status = f"Level {new_level} Approved"
	
	# Add approval comments
	if comments:
		existing_comments = stock_entry.custom_approval_comments or ""
		timestamp = frappe.utils.now_datetime()
		new_comment = f"<p><b>{frappe.session.user}</b> (Level {new_level}) - {timestamp}:</p><p>{comments}</p><hr>"
		stock_entry.custom_approval_comments = new_comment + existing_comments
	
	# Create audit log
	log_stock_entry_event(
		stock_entry=stock_entry.name,
		event_type="Approval Granted",
		approval_level=new_level,
		approval_status="Approved",
		comments=comments,
		signature_data=signature_data
	)
	
	# Check if there are more approval levels
	approvers = get_next_approvers(
		stock_entry.custom_sap_movement_type,
		current_level=new_level,
		stock_entry_data=stock_entry.as_dict()
	)
	
	if approvers:
		# More approval levels required
		stock_entry.custom_approval_status = f"Pending Level {new_level + 1}"
		stock_entry.custom_pending_approver = approvers[0]["user"]
		
		# Send notification to next approver
		for approver in approvers:
			if approver.get("send_notification"):
				send_approval_notification(
					stock_entry=stock_entry,
					approver=approver["user"],
					approval_level=new_level + 1
				)
		
		# Create audit log for next level request
		log_stock_entry_event(
			stock_entry=stock_entry.name,
			event_type="Approval Requested",
			approval_level=new_level + 1,
			approval_status="Pending",
			additional_data={"approvers": approvers}
		)
	else:
		# No more approvals required - fully approved
		stock_entry.custom_approval_status = "Fully Approved"
		stock_entry.custom_pending_approver = None
	
	stock_entry.save(ignore_permissions=True)
	frappe.db.commit()
	
	return {
		"success": True,
		"message": _("Stock Entry approved at Level {0}").format(new_level),
		"approval_status": stock_entry.custom_approval_status,
		"next_approvers": approvers if approvers else None
	}


@frappe.whitelist()
def reject_stock_entry(stock_entry_name, rejection_reason):
	"""Reject a stock entry"""
	from rnd_warehouse_management.warehouse_management.doctype.stock_entry_audit_log.stock_entry_audit_log import log_stock_entry_event
	
	if not rejection_reason:
		frappe.throw(_("Rejection reason is required"))
	
	stock_entry = frappe.get_doc("Stock Entry", stock_entry_name)
	
	# Validate user has permission to reject
	if not can_approve(stock_entry, frappe.session.user):
		frappe.throw(_("You do not have permission to reject this Stock Entry"))
	
	# Update status
	stock_entry.custom_approval_status = "Rejected"
	stock_entry.custom_rejection_reason = rejection_reason
	stock_entry.custom_pending_approver = None
	
	# Add rejection comment
	existing_comments = stock_entry.custom_approval_comments or ""
	timestamp = frappe.utils.now_datetime()
	rejection_comment = f"<p><b>{frappe.session.user}</b> (REJECTED) - {timestamp}:</p><p>{rejection_reason}</p><hr>"
	stock_entry.custom_approval_comments = rejection_comment + existing_comments
	
	stock_entry.save(ignore_permissions=True)
	
	# Create audit log
	log_stock_entry_event(
		stock_entry=stock_entry.name,
		event_type="Approval Rejected",
		approval_level=stock_entry.custom_current_approval_level + 1,
		approval_status="Rejected",
		comments=rejection_reason
	)
	
	# Notify creator
	send_rejection_notification(stock_entry, rejection_reason)
	
	frappe.db.commit()
	
	return {
		"success": True,
		"message": _("Stock Entry rejected")
	}


def can_approve(stock_entry, user):
	"""Check if user can approve the stock entry at current level"""
	from rnd_warehouse_management.warehouse_management.doctype.stock_entry_approval_rule.stock_entry_approval_rule import get_next_approvers
	
	if not stock_entry.custom_sap_movement_type:
		return False
	
	# Get approvers for next level
	approvers = get_next_approvers(
		stock_entry.custom_sap_movement_type,
		current_level=stock_entry.custom_current_approval_level,
		stock_entry_data=stock_entry.as_dict()
	)
	
	if not approvers:
		return False
	
	# Check if user is in approver list
	for approver in approvers:
		if approver["user"] == user:
			return True
	
	# Check if user has the approver role
	user_roles = frappe.get_roles(user)
	for approver in approvers:
		if approver["role"] in user_roles:
			return True
	
	return False


@frappe.whitelist()
def get_pending_approvals(user=None):
	"""Get pending approvals for a user"""
	if not user:
		user = frappe.session.user
	
	user_roles = frappe.get_roles(user)
	
	# Get all pending stock entries
	pending_entries = frappe.get_all(
		"Stock Entry",
		filters={
			"custom_approval_status": ["like", "Pending%"],
			"docstatus": 0
		},
		fields=["name", "posting_date", "custom_sap_movement_type", 
				"custom_approval_status", "custom_current_approval_level", 
				"custom_pending_approver", "owner"]
	)
	
	# Filter by approver permission
	approval_list = []
	for entry in pending_entries:
		stock_entry = frappe.get_doc("Stock Entry", entry.name)
		if can_approve(stock_entry, user):
			approval_list.append(entry)
	
	return approval_list


@frappe.whitelist()
def get_approval_summary(stock_entry_name):
	"""Get approval summary for a stock entry"""
	from rnd_warehouse_management.warehouse_management.doctype.stock_entry_audit_log.stock_entry_audit_log import get_approval_history
	from rnd_warehouse_management.warehouse_management.doctype.stock_entry_approval_rule.stock_entry_approval_rule import get_approval_rules_for_movement_type
	
	stock_entry = frappe.get_doc("Stock Entry", stock_entry_name)
	
	if not stock_entry.custom_sap_movement_type:
		return None
	
	# Get approval rules
	approval_rules = get_approval_rules_for_movement_type(
		stock_entry.custom_sap_movement_type,
		stock_entry.as_dict()
	)
	
	# Get approval history
	approval_history = get_approval_history(stock_entry.name)
	
	return {
		"current_status": stock_entry.custom_approval_status,
		"current_level": stock_entry.custom_current_approval_level,
		"pending_approver": stock_entry.custom_pending_approver,
		"total_levels": len(approval_rules),
		"approval_rules": approval_rules,
		"approval_history": approval_history,
		"can_approve": can_approve(stock_entry, frappe.session.user)
	}


def send_approval_notification(stock_entry, approver, approval_level):
	"""Send approval notification to approver"""
	try:
		frappe.sendmail(
			recipients=[approver],
			subject=_("Approval Request: Stock Entry {0}").format(stock_entry.name),
			message=_("""<p>Dear {0},</p>
			<p>You have a new approval request for Stock Entry <b>{1}</b></p>
			<p><b>Movement Type:</b> {2} - {3}</p>
			<p><b>Approval Level:</b> {4}</p>
			<p><b>Posted Date:</b> {5}</p>
			<p>Please review and approve/reject this stock entry.</p>
			<p><a href="{6}">View Stock Entry</a></p>
			""").format(
				frappe.db.get_value("User", approver, "full_name"),
				stock_entry.name,
				stock_entry.custom_sap_movement_type,
				stock_entry.custom_movement_type_description,
				approval_level,
				stock_entry.posting_date,
				frappe.utils.get_url_to_form("Stock Entry", stock_entry.name)
			),
			reference_doctype="Stock Entry",
			reference_name=stock_entry.name
		)
	except Exception as e:
		frappe.log_error(f"Failed to send approval notification: {str(e)}")


def send_rejection_notification(stock_entry, rejection_reason):
	"""Send rejection notification to stock entry creator"""
	try:
		frappe.sendmail(
			recipients=[stock_entry.owner],
			subject=_("Stock Entry Rejected: {0}").format(stock_entry.name),
			message=_("""<p>Dear {0},</p>
			<p>Your Stock Entry <b>{1}</b> has been rejected.</p>
			<p><b>Rejection Reason:</b></p>
			<p>{2}</p>
			<p><a href="{3}">View Stock Entry</a></p>
			""").format(
				frappe.db.get_value("User", stock_entry.owner, "full_name"),
				stock_entry.name,
				rejection_reason,
				frappe.utils.get_url_to_form("Stock Entry", stock_entry.name)
			),
			reference_doctype="Stock Entry",
			reference_name=stock_entry.name
		)
	except Exception as e:
		frappe.log_error(f"Failed to send rejection notification: {str(e)}")


# ========== PHASE 2: AUTO-ESCALATION LOGIC (TASK 7) ==========

def check_and_escalate_overdue_approvals():
	"""Scheduled task to check and escalate overdue approvals"""
	from frappe.utils import get_datetime, time_diff_in_hours
	from rnd_warehouse_management.warehouse_management.doctype.stock_entry_audit_log.stock_entry_audit_log import log_stock_entry_event
	
	# Get all pending stock entries
	pending_entries = frappe.get_all(
		"Stock Entry",
		filters={
			"custom_approval_status": ["like", "Pending%"],
			"docstatus": 0,
			"custom_approval_requested_on": ["is", "set"]
		},
		fields=["name", "custom_sap_movement_type", "custom_approval_requested_on", 
				"custom_current_approval_level", "custom_pending_approver", "owner"]
	)
	
	escalated_count = 0
	
	for entry_data in pending_entries:
		try:
			stock_entry = frappe.get_doc("Stock Entry", entry_data.name)
			
			# Check if escalation is needed
			if should_escalate(stock_entry):
				escalate_approval(stock_entry)
				escalated_count += 1
				
		except Exception as e:
			frappe.log_error(
				f"Escalation failed for {entry_data.name}: {str(e)}",
				"Approval Escalation Error"
			)
	
	frappe.db.commit()
	
	# Log summary
	frappe.logger().info(f"Escalation check completed. Escalated {escalated_count} approvals.")
	
	return {
		"checked": len(pending_entries),
		"escalated": escalated_count
	}


def should_escalate(stock_entry):
	"""Check if a stock entry should be escalated"""
	from frappe.utils import get_datetime, time_diff_in_hours
	from rnd_warehouse_management.warehouse_management.doctype.stock_entry_approval_rule.stock_entry_approval_rule import get_approval_rules_for_movement_type
	
	if not stock_entry.custom_sap_movement_type:
		return False
	
	if not stock_entry.custom_approval_requested_on:
		return False
	
	# Get approval rules for current level
	approval_rules = get_approval_rules_for_movement_type(
		stock_entry.custom_sap_movement_type,
		stock_entry.as_dict()
	)
	
	if not approval_rules:
		return False
	
	# Get rule for current approval level
	current_level = stock_entry.custom_current_approval_level + 1  # Next level pending
	current_rule = next(
		(rule for rule in approval_rules if rule.approval_level == current_level),
		None
	)
	
	if not current_rule or not current_rule.escalation_days:
		return False
	
	# Calculate hours since approval requested
	request_time = get_datetime(stock_entry.custom_approval_requested_on)
	current_time = get_datetime(now_datetime())
	hours_pending = time_diff_in_hours(current_time, request_time)
	
	# Convert escalation days to hours
	escalation_hours = current_rule.escalation_days * 24
	
	return hours_pending >= escalation_hours


@frappe.whitelist()
def escalate_approval(stock_entry_name, reason=None):
	"""Escalate an approval to the next level or notify administrators"""
	from rnd_warehouse_management.warehouse_management.doctype.stock_entry_approval_rule.stock_entry_approval_rule import get_next_approvers
	from rnd_warehouse_management.warehouse_management.doctype.stock_entry_audit_log.stock_entry_audit_log import log_stock_entry_event
	
	# Handle both doc object and string name
	if isinstance(stock_entry_name, str):
		stock_entry = frappe.get_doc("Stock Entry", stock_entry_name)
	else:
		stock_entry = stock_entry_name
	
	if not reason:
		reason = _("Approval overdue - automatic escalation")
	
	current_level = stock_entry.custom_current_approval_level
	
	# Get next level approvers
	next_level_approvers = get_next_approvers(
		stock_entry.custom_sap_movement_type,
		current_level=current_level + 1,
		stock_entry_data=stock_entry.as_dict()
	)
	
	# Send escalation notifications
	if next_level_approvers:
		# Escalate to next level approvers
		for approver in next_level_approvers:
			send_escalation_notification(
				stock_entry=stock_entry,
				approver=approver["user"],
				current_approver=stock_entry.custom_pending_approver,
				escalation_reason=reason
			)
	else:
		# No next level - escalate to system managers
		system_managers = frappe.get_all(
			"Has Role",
			filters={"role": "System Manager", "parenttype": "User"},
			fields=["parent as user"]
		)
		
		for manager in system_managers:
			send_escalation_notification(
				stock_entry=stock_entry,
				approver=manager["user"],
				current_approver=stock_entry.custom_pending_approver,
				escalation_reason=reason,
				is_final_escalation=True
			)
	
	# Send reminder to current approver
	if stock_entry.custom_pending_approver:
		send_approval_reminder(
			stock_entry=stock_entry,
			approver=stock_entry.custom_pending_approver,
			days_overdue=frappe.utils.date_diff(
				nowdate(),
				frappe.utils.getdate(stock_entry.custom_approval_requested_on)
			)
		)
	
	# Create audit log
	log_stock_entry_event(
		stock_entry=stock_entry.name,
		event_type="Escalated",
		approval_level=current_level + 1,
		approval_status="Escalated",
		comments=reason
	)
	
	stock_entry.save(ignore_permissions=True)
	frappe.db.commit()
	
	return {
		"success": True,
		"message": _("Approval escalated successfully")
	}


def send_escalation_notification(stock_entry, approver, current_approver, escalation_reason, is_final_escalation=False):
	"""Send escalation notification"""
	from frappe.utils import get_datetime, time_diff_in_hours
	
	try:
		request_time = get_datetime(stock_entry.custom_approval_requested_on)
		current_time = get_datetime(now_datetime())
		hours_overdue = int(time_diff_in_hours(current_time, request_time))
		
		if is_final_escalation:
			subject = _("CRITICAL: Approval Overdue - Stock Entry {0}").format(stock_entry.name)
			message_template = """<p>Dear System Administrator,</p>
			<p><b>CRITICAL ESCALATION:</b> Stock Entry <b>{0}</b> has been pending approval for {1} hours.</p>
			<p><b>Movement Type:</b> {2} - {3}</p>
			<p><b>Current Approver:</b> {4}</p>
			<p><b>Escalation Reason:</b> {5}</p>
			<p>This requires immediate attention as all approval levels have been exceeded.</p>
			<p><a href="{6}">View Stock Entry</a></p>
			"""
		else:
			subject = _("Escalation: Approval Request - Stock Entry {0}").format(stock_entry.name)
			message_template = """<p>Dear {7},</p>
			<p>An approval request has been escalated to you.</p>
			<p><b>Stock Entry:</b> {0}</p>
			<p><b>Movement Type:</b> {2} - {3}</p>
			<p><b>Hours Overdue:</b> {1}</p>
			<p><b>Original Approver:</b> {4}</p>
			<p><b>Escalation Reason:</b> {5}</p>
			<p>Please review and take action on this stock entry.</p>
			<p><a href="{6}">View Stock Entry</a></p>
			"""
		
		frappe.sendmail(
			recipients=[approver],
			subject=subject,
			message=_(message_template).format(
				stock_entry.name,
				hours_overdue,
				stock_entry.custom_sap_movement_type,
				stock_entry.custom_movement_type_description,
				frappe.db.get_value("User", current_approver, "full_name") if current_approver else "N/A",
				escalation_reason,
				frappe.utils.get_url_to_form("Stock Entry", stock_entry.name),
				frappe.db.get_value("User", approver, "full_name")
			),
			reference_doctype="Stock Entry",
			reference_name=stock_entry.name,
			priority=1 if is_final_escalation else 0
		)
	except Exception as e:
		frappe.log_error(f"Failed to send escalation notification: {str(e)}")


def send_approval_reminder(stock_entry, approver, days_overdue):
	"""Send reminder to current approver"""
	try:
		frappe.sendmail(
			recipients=[approver],
			subject=_("REMINDER: Approval Pending - Stock Entry {0}").format(stock_entry.name),
			message=_("""<p>Dear {0},</p>
			<p><b>REMINDER:</b> You have a pending approval for Stock Entry <b>{1}</b></p>
			<p><b>Movement Type:</b> {2} - {3}</p>
			<p><b>Days Pending:</b> {4}</p>
			<p>Please review and approve/reject this stock entry as soon as possible.</p>
			<p><a href="{5}">View Stock Entry</a></p>
			""").format(
				frappe.db.get_value("User", approver, "full_name"),
				stock_entry.name,
				stock_entry.custom_sap_movement_type,
				stock_entry.custom_movement_type_description,
				days_overdue,
				frappe.utils.get_url_to_form("Stock Entry", stock_entry.name)
			),
			reference_doctype="Stock Entry",
			reference_name=stock_entry.name
		)
	except Exception as e:
		frappe.log_error(f"Failed to send approval reminder: {str(e)}")