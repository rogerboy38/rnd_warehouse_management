# Copyright (c) 2025, MiniMax Agent and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class MovementTypeMaster(Document):
    """
    Movement Type Master DocType
    Manages SAP-equivalent movement types for warehouse operations
    """
    
    def validate(self):
        """Validate the Movement Type Master before saving"""
        self.validate_movement_code()
        self.validate_category_settings()
        self.set_audit_fields()
    
    def validate_movement_code(self):
        """Ensure movement code follows SAP naming conventions"""
        if not self.movement_code:
            frappe.throw("Movement Code is required")
        
        # Check if movement code already exists (excluding current document)
        if self.is_new():
            existing = frappe.db.exists("Movement Type Master", self.movement_code)
            if existing:
                frappe.throw(f"Movement Code {self.movement_code} already exists")
    
    def validate_category_settings(self):
        """Validate category-specific settings"""
        # Transfer movements must have both source and target warehouse requirements
        if self.stock_movement_type == "Transfer":
            if not self.requires_source_warehouse:
                self.requires_source_warehouse = 1
            if not self.requires_target_warehouse:
                self.requires_target_warehouse = 1
        
        # Goods Receipt should increase stock
        if self.category == "Goods Receipt" and self.stock_movement_type != "Increase":
            frappe.msgprint(
                f"Category 'Goods Receipt' typically uses 'Increase' stock movement type. "
                f"Current setting: {self.stock_movement_type}",
                indicator="orange",
                title="Warning"
            )
        
        # Goods Issue should decrease stock
        if self.category == "Goods Issue" and self.stock_movement_type != "Decrease":
            frappe.msgprint(
                f"Category 'Goods Issue' typically uses 'Decrease' stock movement type. "
                f"Current setting: {self.stock_movement_type}",
                indicator="orange",
                title="Warning"
            )
    
    def set_audit_fields(self):
        """Set audit trail fields"""
        if self.is_new():
            self.created_by = frappe.session.user
        self.modified_by = frappe.session.user
    
    def on_update(self):
        """Actions to perform after update"""
        # Clear any cached movement type data
        frappe.cache().delete_value("movement_type_list")


@frappe.whitelist()
def get_movement_type_details(movement_code):
    """
    Get detailed information about a specific movement type
    
    Args:
        movement_code (str): The movement type code (e.g., '261', '311')
    
    Returns:
        dict: Movement type details or None if not found
    """
    if not movement_code:
        return None
    
    movement_type = frappe.get_doc("Movement Type Master", movement_code)
    if not movement_type:
        return None
    
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
        "auto_create_gi_gt_slip": movement_type.auto_create_gi_gt_slip,
        "validation_rules": movement_type.validation_rules
    }


@frappe.whitelist()
def get_active_movement_types(category=None):
    """
    Get all active movement types, optionally filtered by category
    
    Args:
        category (str, optional): Filter by category
    
    Returns:
        list: List of active movement types
    """
    filters = {"is_active": 1}
    if category:
        filters["category"] = category
    
    movement_types = frappe.get_all(
        "Movement Type Master",
        filters=filters,
        fields=["movement_code", "description", "category", "stock_movement_type"],
        order_by="movement_code"
    )
    
    return movement_types


@frappe.whitelist()
def validate_movement_type_for_stock_entry(movement_code, stock_entry_data):
    """
    Validate if a movement type can be used for a given stock entry
    
    Args:
        movement_code (str): The movement type code
        stock_entry_data (dict): Stock entry data to validate against
    
    Returns:
        dict: Validation result with status and message
    """
    if not movement_code:
        return {
            "valid": False,
            "message": "Movement code is required"
        }
    
    try:
        movement_type = frappe.get_doc("Movement Type Master", movement_code)
    except frappe.DoesNotExistError:
        return {
            "valid": False,
            "message": f"Movement type {movement_code} does not exist"
        }
    
    if not movement_type.is_active:
        return {
            "valid": False,
            "message": f"Movement type {movement_code} is not active"
        }
    
    # Parse stock_entry_data if it's a string
    if isinstance(stock_entry_data, str):
        import json
        stock_entry_data = json.loads(stock_entry_data)
    
    # Validate warehouse requirements
    if movement_type.requires_source_warehouse and not stock_entry_data.get("from_warehouse"):
        return {
            "valid": False,
            "message": f"Movement type {movement_code} requires a source warehouse"
        }
    
    if movement_type.requires_target_warehouse and not stock_entry_data.get("to_warehouse"):
        return {
            "valid": False,
            "message": f"Movement type {movement_code} requires a target warehouse"
        }
    
    # Execute custom validation rules if defined
    if movement_type.validation_rules:
        try:
            # Create a safe execution context
            exec_context = {
                "frappe": frappe,
                "stock_entry": stock_entry_data,
                "movement_type": movement_type,
                "valid": True,
                "message": ""
            }
            
            exec(movement_type.validation_rules, exec_context)
            
            if not exec_context.get("valid", True):
                return {
                    "valid": False,
                    "message": exec_context.get("message", "Custom validation failed")
                }
        except Exception as e:
            frappe.log_error(f"Movement Type Validation Error: {str(e)}")
            return {
                "valid": False,
                "message": f"Validation rule execution failed: {str(e)}"
            }
    
    return {
        "valid": True,
        "message": "Validation successful",
        "movement_type_details": get_movement_type_details(movement_code)
    }
