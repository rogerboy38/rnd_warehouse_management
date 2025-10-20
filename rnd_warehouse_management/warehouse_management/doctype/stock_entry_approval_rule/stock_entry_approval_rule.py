# Copyright (c) 2025, MiniMax Agent and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _

class StockEntryApprovalRule(Document):
	"""Stock Entry Approval Rule DocType"""
	
	def validate(self):
		"""Validate the approval rule"""
		self.validate_approval_level()
		self.validate_conditional_logic()
		self.validate_unique_rule()
	
	def validate_approval_level(self):
		"""Validate approval level is within acceptable range"""
		if self.approval_level < 1 or self.approval_level > 5:
			frappe.throw(_("Approval Level must be between 1 and 5"))
	
	def validate_conditional_logic(self):
		"""Validate conditional logic syntax if provided"""
		if not self.conditional_logic:
			return
		
		try:
			# Test compile the conditional logic
			compile(self.conditional_logic, '<string>', 'eval')
		except SyntaxError as e:
			frappe.throw(_("Conditional Logic has syntax error: {0}").format(str(e)))
	
	def validate_unique_rule(self):
		"""Validate that no duplicate rule exists for same movement type and level"""
		if self.is_new():
			filters = {
				"movement_type": self.movement_type,
				"approval_level": self.approval_level,
				"enabled": 1
			}
		else:
			filters = {
				"movement_type": self.movement_type,
				"approval_level": self.approval_level,
				"enabled": 1,
				"name": ["!=", self.name]
			}
		
		existing = frappe.db.exists("Stock Entry Approval Rule", filters)
		if existing:
			frappe.throw(_("An active approval rule already exists for Movement Type {0} at Level {1}").format(
				self.movement_type, self.approval_level))


@frappe.whitelist()
def get_approval_rules_for_movement_type(movement_type, stock_entry_data=None):
	"""Get all applicable approval rules for a movement type"""
	if not movement_type:
		return []
	
	# Get all enabled rules for this movement type
	rules = frappe.get_all(
		"Stock Entry Approval Rule",
		filters={"movement_type": movement_type, "enabled": 1},
		fields=["name", "approval_level", "approver_role", "approver_user", 
				"approval_sequence", "escalation_days", "conditional_logic"],
		order_by="approval_level asc"
	)
	
	if not stock_entry_data:
		return rules
	
	# Filter rules based on conditional logic
	applicable_rules = []
	for rule in rules:
		if rule.conditional_logic:
			if evaluate_conditional_logic(rule.conditional_logic, stock_entry_data):
				applicable_rules.append(rule)
		else:
			applicable_rules.append(rule)
	
	return applicable_rules


def evaluate_conditional_logic(conditional_logic, stock_entry_data):
	"""Evaluate conditional logic for approval rule"""
	if not conditional_logic:
		return True
	
	try:
		# Create execution context
		context = {
			"stock_entry": frappe._dict(stock_entry_data),
			"frappe": frappe
		}
		
		# Evaluate the conditional logic
		result = eval(conditional_logic, {"__builtins__": {}}, context)
		return bool(result)
	except Exception as e:
		frappe.log_error(f"Conditional Logic Evaluation Error: {str(e)}")
		return False


@frappe.whitelist()
def get_next_approvers(movement_type, current_level=0, stock_entry_data=None):
	"""Get next approvers for a stock entry"""
	next_level = int(current_level) + 1
	
	# Get rules for next level
	rules = frappe.get_all(
		"Stock Entry Approval Rule",
		filters={
			"movement_type": movement_type,
			"approval_level": next_level,
			"enabled": 1
		},
		fields=["name", "approver_role", "approver_user", "approval_sequence", "send_notification"]
	)
	
	if not rules:
		return None
	
	# Filter based on conditional logic if stock_entry_data provided
	if stock_entry_data:
		applicable_rules = []
		for rule in rules:
			rule_doc = frappe.get_doc("Stock Entry Approval Rule", rule.name)
			if not rule_doc.conditional_logic or evaluate_conditional_logic(rule_doc.conditional_logic, stock_entry_data):
				applicable_rules.append(rule)
		rules = applicable_rules
	
	if not rules:
		return None
	
	# Build approver list
	approvers = []
	for rule in rules:
		if rule.approver_user:
			approvers.append({
				"user": rule.approver_user,
				"role": rule.approver_role,
				"sequence": rule.approval_sequence,
				"send_notification": rule.send_notification
			})
		else:
			# Get all users with the approver role
			users_with_role = frappe.get_all(
				"Has Role",
				filters={"role": rule.approver_role, "parenttype": "User"},
				fields=["parent as user"]
			)
			
			for user in users_with_role:
				approvers.append({
					"user": user.user,
					"role": rule.approver_role,
					"sequence": rule.approval_sequence,
					"send_notification": rule.send_notification
				})
	
	return approvers
