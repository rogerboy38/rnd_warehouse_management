# Copyright (c) 2025, MiniMax Agent and Contributors
# See license.txt

import frappe
import unittest
from frappe.utils import nowdate

class TestStockEntryApprovalRule(unittest.TestCase):
	"""Test cases for Stock Entry Approval Rule"""
	
	def setUp(self):
		"""Set up test data"""
		# Create test movement type if not exists
		if not frappe.db.exists("Movement Type Master", "261"):
			frappe.get_doc({
				"doctype": "Movement Type Master",
				"movement_code": "261",
				"description": "Test Movement Type",
				"category": "Production",
				"is_active": 1
			}).insert()
	
	def tearDown(self):
		"""Clean up test data"""
		# Delete test approval rules
		frappe.db.delete("Stock Entry Approval Rule", {"movement_type": "261"})
		frappe.db.commit()
	
	def test_create_approval_rule(self):
		"""Test creating an approval rule"""
		rule = frappe.get_doc({
			"doctype": "Stock Entry Approval Rule",
			"movement_type": "261",
			"approval_level": 1,
			"approver_role": "Warehouse Supervisor",
			"approval_sequence": "Sequential",
			"enabled": 1
		})
		rule.insert()
		
		self.assertEqual(rule.movement_type, "261")
		self.assertEqual(rule.approval_level, 1)
	
	def test_duplicate_rule_validation(self):
		"""Test that duplicate rules are not allowed"""
		# Create first rule
		rule1 = frappe.get_doc({
			"doctype": "Stock Entry Approval Rule",
			"movement_type": "261",
			"approval_level": 1,
			"approver_role": "Warehouse Supervisor",
			"approval_sequence": "Sequential",
			"enabled": 1
		})
		rule1.insert()
		
		# Try to create duplicate
		rule2 = frappe.get_doc({
			"doctype": "Stock Entry Approval Rule",
			"movement_type": "261",
			"approval_level": 1,
			"approver_role": "Warehouse Manager",
			"approval_sequence": "Sequential",
			"enabled": 1
		})
		
		self.assertRaises(frappe.ValidationError, rule2.insert)
	
	def test_approval_level_validation(self):
		"""Test approval level validation"""
		# Test invalid level (too high)
		rule = frappe.get_doc({
			"doctype": "Stock Entry Approval Rule",
			"movement_type": "261",
			"approval_level": 10,  # Invalid
			"approver_role": "Warehouse Supervisor",
			"approval_sequence": "Sequential",
			"enabled": 1
		})
		
		self.assertRaises(frappe.ValidationError, rule.insert)
	
	def test_conditional_logic(self):
		"""Test conditional logic validation"""
		# Valid conditional logic
		rule = frappe.get_doc({
			"doctype": "Stock Entry Approval Rule",
			"movement_type": "261",
			"approval_level": 1,
			"approver_role": "Warehouse Supervisor",
			"approval_sequence": "Sequential",
			"conditional_logic": "stock_entry.total_value > 10000",
			"enabled": 1
		})
		rule.insert()
		
		self.assertEqual(rule.conditional_logic, "stock_entry.total_value > 10000")
	
	def test_invalid_conditional_logic(self):
		"""Test invalid conditional logic throws error"""
		rule = frappe.get_doc({
			"doctype": "Stock Entry Approval Rule",
			"movement_type": "261",
			"approval_level": 1,
			"approver_role": "Warehouse Supervisor",
			"approval_sequence": "Sequential",
			"conditional_logic": "invalid python syntax !!!",
			"enabled": 1
		})
		
		self.assertRaises(frappe.ValidationError, rule.insert)
