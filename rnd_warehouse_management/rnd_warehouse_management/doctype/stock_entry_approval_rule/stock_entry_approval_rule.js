// Copyright (c) 2025, MiniMax Agent and contributors
// For license information, please see license.txt

frappe.ui.form.on('Stock Entry Approval Rule', {
	refresh: function(frm) {
		if (!frm.is_new()) {
			// Add button to test conditional logic
			if (frm.doc.conditional_logic) {
				frm.add_custom_button(__('Test Conditional Logic'), function() {
					test_conditional_logic(frm);
				});
			}
			
			// Add button to view applicable stock entries
			frm.add_custom_button(__('View Applicable Stock Entries'), function() {
				view_applicable_stock_entries(frm);
			});
		}
	},
	
	movement_type: function(frm) {
		if (frm.doc.movement_type) {
			// Load movement type details
			frappe.call({
				method: 'rnd_warehouse_management.warehouse_management.stock_entry.get_movement_type_details_for_ui',
				args: {
					movement_code: frm.doc.movement_type
				},
				callback: function(r) {
					if (r.message) {
						let mt = r.message;
						
						// Show info about movement type
						let info = `<b>Movement Type Info:</b><br>`;
						info += `Description: ${mt.description}<br>`;
						info += `Category: ${mt.category}<br>`;
						info += `Authorization Level: ${mt.authorization_level || 'Standard'}`;
						
						frappe.msgprint(info, __('Movement Type Information'));
						
						// Suggest approver role based on authorization level
						if (!frm.doc.approver_role) {
							let suggested_role = get_suggested_role(mt.authorization_level);
							if (suggested_role) {
								frm.set_value('approver_role', suggested_role);
							}
						}
					}
				}
			});
		}
	},
	
	approval_level: function(frm) {
		if (frm.doc.approval_level && frm.doc.movement_type) {
			// Check if a rule already exists
			frappe.call({
				method: 'frappe.client.get_list',
				args: {
					doctype: 'Stock Entry Approval Rule',
					filters: {
						movement_type: frm.doc.movement_type,
						approval_level: frm.doc.approval_level,
						enabled: 1,
						name: ['!=', frm.doc.name]
					},
					fields: ['name']
				},
				callback: function(r) {
					if (r.message && r.message.length > 0) {
						frappe.msgprint(
							__('Warning: An approval rule already exists for this movement type and level ({0})', [r.message[0].name]),
							__('Duplicate Rule')
						);
					}
				}
			});
		}
	}
});

function get_suggested_role(authorization_level) {
	const role_mapping = {
		'Standard': 'Stock User',
		'Supervisor': 'Warehouse Supervisor',
		'Manager': 'Warehouse Manager',
		'Director': 'Director'
	};
	
	return role_mapping[authorization_level] || 'Stock User';
}

function test_conditional_logic(frm) {
	let sample_data = prompt('Enter sample Stock Entry data (JSON format)');
	
	if (!sample_data) {
		return;
	}
	
	try {
		let data = JSON.parse(sample_data);
		
		frappe.call({
			method: 'rnd_warehouse_management.warehouse_management.doctype.stock_entry_approval_rule.stock_entry_approval_rule.evaluate_conditional_logic',
			args: {
				conditional_logic: frm.doc.conditional_logic,
				stock_entry_data: data
			},
			callback: function(r) {
				if (r.message) {
					frappe.msgprint(__('Conditional logic evaluates to: {0}', [r.message ? 'True' : 'False']));
				}
			}
		});
	} catch (e) {
		frappe.msgprint(__('Invalid JSON format'));
	}
}

function view_applicable_stock_entries(frm) {
	frappe.route_options = {
		"custom_sap_movement_type": frm.doc.movement_type
	};
	frappe.set_route("List", "Stock Entry");
}
