# Copyright (c) 2025, MiniMax Agent and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import now_datetime, get_datetime
import json

class StockEntryAuditLog(Document):
	"""Stock Entry Audit Log DocType - Read-only audit trail"""
	
	def before_insert(self):
		"""Set default values before inserting"""
		if not self.user:
			self.user = frappe.session.user
		
		if not self.event_timestamp:
			self.event_timestamp = now_datetime()
		
		# Capture IP address
		if not self.ip_address:
			self.ip_address = frappe.local.request_ip if hasattr(frappe.local, 'request_ip') else None
		
		# Capture user's primary role
		if not self.user_role and self.user:
			user_roles = frappe.get_roles(self.user)
			if user_roles:
				# Priority roles for warehouse management
				priority_roles = ['System Manager', 'Warehouse Manager', 'Warehouse Supervisor', 
								  'Production Manager', 'Stock Manager', 'Stock User']
				
				for role in priority_roles:
					if role in user_roles:
						self.user_role = role
						break
				
				if not self.user_role:
					self.user_role = user_roles[0]
	
	def validate(self):
		"""Validate audit log entry"""
		# Validate additional_data is valid JSON if provided
		if self.additional_data:
			try:
				json.loads(self.additional_data)
			except json.JSONDecodeError:
				frappe.throw(_("Additional Data must be valid JSON"))


@frappe.whitelist()
def create_audit_log(stock_entry, event_type, **kwargs):
	"""Create an audit log entry"""
	audit_log = frappe.get_doc({
		"doctype": "Stock Entry Audit Log",
		"stock_entry": stock_entry,
		"event_type": event_type,
		"user": kwargs.get("user", frappe.session.user),
		"field_changed": kwargs.get("field_changed"),
		"previous_value": kwargs.get("previous_value"),
		"new_value": kwargs.get("new_value"),
		"approval_level": kwargs.get("approval_level"),
		"approval_status": kwargs.get("approval_status"),
		"comments": kwargs.get("comments"),
		"signature_data": kwargs.get("signature_data"),
		"additional_data": json.dumps(kwargs.get("additional_data")) if kwargs.get("additional_data") else None
	})
	
	audit_log.insert(ignore_permissions=True)
	frappe.db.commit()
	
	return audit_log.name


@frappe.whitelist()
def get_audit_trail(stock_entry, event_type=None):
	"""Get audit trail for a stock entry"""
	filters = {"stock_entry": stock_entry}
	
	if event_type:
		filters["event_type"] = event_type
	
	audit_logs = frappe.get_all(
		"Stock Entry Audit Log",
		filters=filters,
		fields=["name", "event_type", "event_timestamp", "user", "user_role", 
				"field_changed", "previous_value", "new_value", "approval_level", 
				"approval_status", "comments"],
		order_by="event_timestamp desc"
	)
	
	return audit_logs


@frappe.whitelist()
def get_approval_history(stock_entry):
	"""Get approval history for a stock entry"""
	audit_logs = frappe.get_all(
		"Stock Entry Audit Log",
		filters={
			"stock_entry": stock_entry,
			"event_type": ["in", ["Approval Requested", "Approval Granted", "Approval Rejected", "Escalated"]]
		},
		fields=["name", "event_type", "event_timestamp", "user", "user_role", 
				"approval_level", "approval_status", "comments", "signature_data"],
		order_by="event_timestamp asc"
	)
	
	return audit_logs


@frappe.whitelist()
def get_field_change_history(stock_entry, field_name=None):
	"""Get field change history for a stock entry"""
	filters = {
		"stock_entry": stock_entry,
		"event_type": "Modified"
	}
	
	if field_name:
		filters["field_changed"] = field_name
	
	audit_logs = frappe.get_all(
		"Stock Entry Audit Log",
		filters=filters,
		fields=["name", "event_timestamp", "user", "field_changed", 
				"previous_value", "new_value"],
		order_by="event_timestamp desc"
	)
	
	return audit_logs


def log_stock_entry_event(stock_entry, event_type, **kwargs):
	"""Helper function to log stock entry events"""
	try:
		return create_audit_log(stock_entry, event_type, **kwargs)
	except Exception as e:
		frappe.log_error(f"Failed to create audit log: {str(e)}")
		return None
