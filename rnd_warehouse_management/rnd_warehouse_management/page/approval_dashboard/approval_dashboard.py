import frappe
from frappe import _
from frappe.utils import nowdate, add_days, get_datetime

@frappe.whitelist()
def get_dashboard_data(filters=None):
	"""Get approval dashboard data"""
	if not filters:
		filters = {}
	
	user = frappe.session.user
	user_roles = frappe.get_roles(user)
	
	# Get pending approvals
	pending_approvals = get_pending_approvals_for_dashboard(user, filters)
	
	# Get approval history
	approval_history = get_my_approval_history(user, filters)
	
	# Get statistics
	stats = get_approval_statistics(user)
	
	return {
		"pending_approvals": pending_approvals,
		"approval_history": approval_history,
		"statistics": stats
	}


def get_pending_approvals_for_dashboard(user, filters):
	"""Get all pending approvals for the user"""
	from rnd_warehouse_management.warehouse_management.stock_entry import can_approve
	
	# Build filter conditions
	filter_conditions = {
		"custom_approval_status": ["like", "Pending%"],
		"docstatus": 0
	}
	
	# Add movement type filter
	if filters.get("movement_type"):
		filter_conditions["custom_sap_movement_type"] = filters["movement_type"]
	
	# Add date filter
	if filters.get("from_date"):
		filter_conditions["posting_date"] = [">=", filters["from_date"]]
	
	if filters.get("to_date"):
		filter_conditions["posting_date"] = ["<=", filters["to_date"]]
	
	# Get all pending stock entries
	pending_entries = frappe.get_all(
		"Stock Entry",
		filters=filter_conditions,
		fields=[
			"name", "posting_date", "custom_sap_movement_type", 
			"custom_movement_type_description", "custom_approval_status", 
			"custom_current_approval_level", "custom_pending_approver", 
			"custom_approval_requested_on", "owner", "creation"
		],
		order_by="creation desc"
	)
	
	# Filter by approval permission
	filtered_entries = []
	for entry in pending_entries:
		stock_entry = frappe.get_doc("Stock Entry", entry.name)
		if can_approve(stock_entry, user):
			# Calculate days pending
			if entry.get("custom_approval_requested_on"):
				days_pending = frappe.utils.date_diff(
					nowdate(),
					frappe.utils.getdate(entry.custom_approval_requested_on)
				)
				entry["days_pending"] = days_pending
				
				# Determine urgency
				if days_pending > 3:
					entry["urgency"] = "High"
				elif days_pending > 1:
					entry["urgency"] = "Medium"
				else:
					entry["urgency"] = "Low"
			else:
				entry["days_pending"] = 0
				entry["urgency"] = "Low"
			
			filtered_entries.append(entry)
	
	return filtered_entries


def get_my_approval_history(user, filters):
	"""Get approval history for the user"""
	# Build filter conditions
	filter_conditions = {
		"event_type": ["in", ["Approval Granted", "Approval Rejected"]],
		"user": user
	}
	
	# Add date filter
	if filters.get("from_date"):
		filter_conditions["event_timestamp"] = [">=", filters["from_date"] + " 00:00:00"]
	
	if filters.get("to_date"):
		filter_conditions["event_timestamp"] = ["<=", filters["to_date"] + " 23:59:59"]
	
	# Get audit logs
	audit_logs = frappe.get_all(
		"Stock Entry Audit Log",
		filters=filter_conditions,
		fields=[
			"stock_entry", "event_type", "event_timestamp", 
			"approval_level", "approval_status", "comments"
		],
		order_by="event_timestamp desc",
		limit=50
	)
	
	# Enrich with stock entry details
	for log in audit_logs:
		try:
			entry_data = frappe.db.get_value(
				"Stock Entry",
				log.stock_entry,
				["custom_sap_movement_type", "custom_movement_type_description"],
				as_dict=True
			)
			if entry_data:
				log["movement_type"] = entry_data.get("custom_sap_movement_type")
				log["movement_description"] = entry_data.get("custom_movement_type_description")
		except Exception:
			pass
	
	return audit_logs


def get_approval_statistics(user):
	"""Get approval statistics for the user"""
	user_roles = frappe.get_roles(user)
	
	# Count pending approvals
	pending_count = frappe.db.count(
		"Stock Entry",
		filters={
			"custom_approval_status": ["like", "Pending%"],
			"docstatus": 0
		}
	)
	
	# Count approvals granted this month
	first_day_of_month = frappe.utils.get_first_day(nowdate())
	approved_this_month = frappe.db.count(
		"Stock Entry Audit Log",
		filters={
			"user": user,
			"event_type": "Approval Granted",
			"event_timestamp": [">=", first_day_of_month + " 00:00:00"]
		}
	)
	
	# Count rejections this month
	rejected_this_month = frappe.db.count(
		"Stock Entry Audit Log",
		filters={
			"user": user,
			"event_type": "Approval Rejected",
			"event_timestamp": [">=", first_day_of_month + " 00:00:00"]
		}
	)
	
	# Count overdue approvals (>3 days pending)
	three_days_ago = add_days(nowdate(), -3)
	overdue_count = frappe.db.count(
		"Stock Entry",
		filters={
			"custom_approval_status": ["like", "Pending%"],
			"docstatus": 0,
			"custom_approval_requested_on": ["<=", three_days_ago + " 23:59:59"]
		}
	)
	
	return {
		"pending_count": pending_count,
		"approved_this_month": approved_this_month,
		"rejected_this_month": rejected_this_month,
		"overdue_count": overdue_count
	}


@frappe.whitelist()
def bulk_approve(stock_entry_names, comments=None):
	"""Bulk approve multiple stock entries"""
	if isinstance(stock_entry_names, str):
		import json
		stock_entry_names = json.loads(stock_entry_names)
	
	results = {
		"success": [],
		"failed": []
	}
	
	for entry_name in stock_entry_names:
		try:
			frappe.call(
				"rnd_warehouse_management.warehouse_management.stock_entry.approve_stock_entry",
				stock_entry_name=entry_name,
				comments=comments
			)
			results["success"].append(entry_name)
		except Exception as e:
			results["failed"].append({"name": entry_name, "error": str(e)})
	
	frappe.db.commit()
	
	return results


@frappe.whitelist()
def get_movement_types_for_filter():
	"""Get available movement types for filtering"""
	movement_types = frappe.get_all(
		"Movement Type Master",
		filters={"is_active": 1, "requires_approval": 1},
		fields=["movement_code", "description"],
		order_by="movement_code"
	)
	
	return movement_types
