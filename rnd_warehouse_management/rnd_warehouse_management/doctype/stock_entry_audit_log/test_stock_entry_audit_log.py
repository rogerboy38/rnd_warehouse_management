# Copyright (c) 2025, MiniMax Agent and Contributors
# See license.txt

import frappe
import unittest
import json
from frappe.utils import now_datetime

class TestStockEntryAuditLog(unittest.TestCase):
	"""Test cases for Stock Entry Audit Log"""
	
	def setUp(self):
		"""Set up test data"""
		# Create a test stock entry if not exists
		if not frappe.db.exists("Stock Entry", "TEST-SE-001"):
			stock_entry = frappe.get_doc({
				"doctype": "Stock Entry",
				"name": "TEST-SE-001",
				"stock_entry_type": "Material Issue",
				"purpose": "Material Issue"
			})
			stock_entry.insert(ignore_if_duplicate=True)
	
	def tearDown(self):
		"""Clean up test data"""
		# Delete test audit logs
		frappe.db.delete("Stock Entry Audit Log", {"stock_entry": "TEST-SE-001"})
		frappe.db.commit()
	
	def test_create_audit_log(self):
		"""Test creating an audit log entry"""
		from rnd_warehouse_management.warehouse_management.doctype.stock_entry_audit_log.stock_entry_audit_log import create_audit_log
		
		log_name = create_audit_log(
			stock_entry="TEST-SE-001",
			event_type="Created",
			user=frappe.session.user
		)
		
		self.assertTrue(log_name)
		
		# Verify log was created
		log = frappe.get_doc("Stock Entry Audit Log", log_name)
		self.assertEqual(log.stock_entry, "TEST-SE-001")
		self.assertEqual(log.event_type, "Created")
	
	def test_audit_log_with_field_changes(self):
		"""Test audit log with field change tracking"""
		from rnd_warehouse_management.warehouse_management.doctype.stock_entry_audit_log.stock_entry_audit_log import create_audit_log
		
		log_name = create_audit_log(
			stock_entry="TEST-SE-001",
			event_type="Modified",
			field_changed="purpose",
			previous_value="Material Receipt",
			new_value="Material Issue"
		)
		
		log = frappe.get_doc("Stock Entry Audit Log", log_name)
		self.assertEqual(log.field_changed, "purpose")
		self.assertEqual(log.previous_value, "Material Receipt")
		self.assertEqual(log.new_value, "Material Issue")
	
	def test_audit_log_with_approval(self):
		"""Test audit log with approval information"""
		from rnd_warehouse_management.warehouse_management.doctype.stock_entry_audit_log.stock_entry_audit_log import create_audit_log
		
		log_name = create_audit_log(
			stock_entry="TEST-SE-001",
			event_type="Approval Granted",
			approval_level=1,
			approval_status="Approved",
			comments="Approved by supervisor"
		)
		
		log = frappe.get_doc("Stock Entry Audit Log", log_name)
		self.assertEqual(log.approval_level, 1)
		self.assertEqual(log.approval_status, "Approved")
		self.assertEqual(log.comments, "Approved by supervisor")
	
	def test_audit_log_with_additional_data(self):
		"""Test audit log with additional JSON data"""
		from rnd_warehouse_management.warehouse_management.doctype.stock_entry_audit_log.stock_entry_audit_log import create_audit_log
		
		additional_data = {
			"warehouse": "Main Warehouse",
			"items_count": 5,
			"total_value": 10000
		}
		
		log_name = create_audit_log(
			stock_entry="TEST-SE-001",
			event_type="Created",
			additional_data=additional_data
		)
		
		log = frappe.get_doc("Stock Entry Audit Log", log_name)
		self.assertTrue(log.additional_data)
		
		# Parse and verify JSON data
		parsed_data = json.loads(log.additional_data)
		self.assertEqual(parsed_data["warehouse"], "Main Warehouse")
		self.assertEqual(parsed_data["items_count"], 5)
	
	def test_get_audit_trail(self):
		"""Test retrieving audit trail"""
		from rnd_warehouse_management.warehouse_management.doctype.stock_entry_audit_log.stock_entry_audit_log import create_audit_log, get_audit_trail
		
		# Create multiple audit logs
		create_audit_log(stock_entry="TEST-SE-001", event_type="Created")
		create_audit_log(stock_entry="TEST-SE-001", event_type="Modified")
		create_audit_log(stock_entry="TEST-SE-001", event_type="Submitted")
		
		# Get audit trail
		audit_trail = get_audit_trail("TEST-SE-001")
		
		self.assertTrue(len(audit_trail) >= 3)
	
	def test_get_approval_history(self):
		"""Test retrieving approval history"""
		from rnd_warehouse_management.warehouse_management.doctype.stock_entry_audit_log.stock_entry_audit_log import create_audit_log, get_approval_history
		
		# Create approval-related logs
		create_audit_log(stock_entry="TEST-SE-001", event_type="Approval Requested", approval_level=1)
		create_audit_log(stock_entry="TEST-SE-001", event_type="Approval Granted", approval_level=1, approval_status="Approved")
		
		# Get approval history
		approval_history = get_approval_history("TEST-SE-001")
		
		self.assertTrue(len(approval_history) >= 2)
		self.assertEqual(approval_history[0]["event_type"], "Approval Requested")
