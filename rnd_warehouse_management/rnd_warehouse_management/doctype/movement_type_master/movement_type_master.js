// Copyright (c) 2025, MiniMax Agent and contributors
// For license information, please see license.txt

frappe.ui.form.on('Movement Type Master', {
    refresh: function(frm) {
        // Add custom buttons
        if (!frm.is_new()) {
            frm.add_custom_button(__('Test Validation Rules'), function() {
                test_validation_rules(frm);
            });
        }
        
        // Set default values for new documents
        if (frm.is_new()) {
            frm.set_value('is_active', 1);
            frm.set_value('authorization_level', 'Standard');
        }
    },
    
    category: function(frm) {
        // Auto-suggest stock_movement_type based on category
        if (frm.doc.category) {
            let suggested_movement_type = get_suggested_movement_type(frm.doc.category);
            if (suggested_movement_type && !frm.doc.stock_movement_type) {
                frm.set_value('stock_movement_type', suggested_movement_type);
            }
        }
    },
    
    stock_movement_type: function(frm) {
        // Auto-set warehouse requirements based on movement type
        if (frm.doc.stock_movement_type === 'Transfer') {
            frm.set_value('requires_source_warehouse', 1);
            frm.set_value('requires_target_warehouse', 1);
        } else if (frm.doc.stock_movement_type === 'Increase') {
            frm.set_value('requires_target_warehouse', 1);
            frm.set_value('requires_source_warehouse', 0);
        } else if (frm.doc.stock_movement_type === 'Decrease') {
            frm.set_value('requires_source_warehouse', 1);
            frm.set_value('requires_target_warehouse', 0);
        }
    },
    
    requires_approval: function(frm) {
        // Show authorization level field only if approval is required
        frm.toggle_reqd('authorization_level', frm.doc.requires_approval);
    }
});

function get_suggested_movement_type(category) {
    const mapping = {
        'Goods Receipt': 'Increase',
        'Goods Issue': 'Decrease',
        'Transfer Posting': 'Transfer',
        'Stock Adjustment': 'None',
        'Production': 'Decrease',
        'Reservation': 'None'
    };
    return mapping[category] || null;
}

function test_validation_rules(frm) {
    if (!frm.doc.validation_rules) {
        frappe.msgprint(__('No validation rules defined'));
        return;
    }
    
    // Create a test stock entry object
    let test_stock_entry = {
        from_warehouse: 'Test Warehouse - Source',
        to_warehouse: 'Test Warehouse - Target',
        items: [
            {
                item_code: 'TEST-ITEM-001',
                qty: 100
            }
        ]
    };
    
    frappe.call({
        method: 'rnd_warehouse_management.warehouse_management.doctype.movement_type_master.movement_type_master.validate_movement_type_for_stock_entry',
        args: {
            movement_code: frm.doc.movement_code,
            stock_entry_data: test_stock_entry
        },
        callback: function(r) {
            if (r.message) {
                if (r.message.valid) {
                    frappe.msgprint({
                        title: __('Validation Test Successful'),
                        message: __('The validation rules executed successfully'),
                        indicator: 'green'
                    });
                } else {
                    frappe.msgprint({
                        title: __('Validation Test Failed'),
                        message: r.message.message,
                        indicator: 'red'
                    });
                }
            }
        }
    });
}
