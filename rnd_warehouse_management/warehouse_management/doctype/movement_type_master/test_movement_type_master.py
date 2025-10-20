# Copyright (c) 2025, MiniMax Agent and Contributors
# See license.txt

import frappe
import unittest

class TestMovementTypeMaster(unittest.TestCase):
    def setUp(self):
        """Set up test data"""
        # Create a test movement type
        if not frappe.db.exists("Movement Type Master", "TEST-001"):
            doc = frappe.get_doc({
                "doctype": "Movement Type Master",
                "movement_code": "TEST-001",
                "description": "Test Movement Type",
                "category": "Goods Receipt",
                "stock_movement_type": "Increase",
                "requires_approval": 0,
                "is_active": 1
            })
            doc.insert()
    
    def tearDown(self):
        """Clean up test data"""
        if frappe.db.exists("Movement Type Master", "TEST-001"):
            frappe.delete_doc("Movement Type Master", "TEST-001")
    
    def test_movement_type_creation(self):
        """Test creating a movement type"""
        movement_type = frappe.get_doc("Movement Type Master", "TEST-001")
        self.assertEqual(movement_type.movement_code, "TEST-001")
        self.assertEqual(movement_type.category, "Goods Receipt")
    
    def test_unique_movement_code(self):
        """Test that movement codes must be unique"""
        with self.assertRaises(frappe.DuplicateEntryError):
            doc = frappe.get_doc({
                "doctype": "Movement Type Master",
                "movement_code": "TEST-001",
                "description": "Duplicate Test",
                "category": "Goods Issue",
                "stock_movement_type": "Decrease"
            })
            doc.insert()
    
    def test_get_movement_type_details(self):
        """Test retrieving movement type details"""
        from rnd_warehouse_management.warehouse_management.doctype.movement_type_master.movement_type_master import get_movement_type_details
        
        details = get_movement_type_details("TEST-001")
        self.assertIsNotNone(details)
        self.assertEqual(details["movement_code"], "TEST-001")
    
    def test_validate_movement_type(self):
        """Test movement type validation"""
        from rnd_warehouse_management.warehouse_management.doctype.movement_type_master.movement_type_master import validate_movement_type_for_stock_entry
        
        stock_entry_data = {
            "to_warehouse": "Test Warehouse"
        }
        
        result = validate_movement_type_for_stock_entry("TEST-001", stock_entry_data)
        self.assertTrue(result["valid"])
