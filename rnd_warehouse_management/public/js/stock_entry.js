// Stock Entry Form Enhancements for RND Warehouse Management

frappe.ui.form.on('Stock Entry', {
	// Form initialization
	refresh: function(frm) {
		// Add custom buttons
		add_custom_buttons(frm);
		
		// Style signature fields
		style_signature_fields(frm);
		
		// Update zone status display
		update_zone_status_display(frm);
		
		// Show SAP movement info
		show_sap_movement_info(frm);
	},
	
	// SAP Movement Type change handler
	custom_sap_movement_type: function(frm) {
		validate_sap_movement_type(frm);
		update_required_signatures(frm);
		set_purpose_based_on_sap_type(frm);
	},
	
	// Work Order Reference change handler
	custom_work_order_reference: function(frm) {
		if (frm.doc.custom_work_order_reference) {
			get_work_order_material_status(frm);
		}
	},
	
	// Purpose change handler
	purpose: function(frm) {
		suggest_sap_movement_type(frm);
	},
	
	// Before save validation
	before_save: function(frm) {
		validate_warehouse_requirements(frm);
		validate_signature_requirements(frm);
	}
});

// Signature field handlers
frappe.ui.form.on('Stock Entry', {
	custom_warehouse_supervisor_signature: function(frm) {
		if (frm.doc.custom_warehouse_supervisor_signature) {
			frm.set_value('custom_warehouse_supervisor_sign_date', frappe.datetime.now_datetime());
			show_signature_confirmation(frm, 'Warehouse Supervisor signature captured successfully!');
		}
	},
	
	custom_kitting_supervisor_signature: function(frm) {
		if (frm.doc.custom_kitting_supervisor_signature) {
			frm.set_value('custom_kitting_supervisor_sign_date', frappe.datetime.now_datetime());
			show_signature_confirmation(frm, 'Kitting Supervisor signature captured successfully!');
		}
	}
});

// Helper Functions

function add_custom_buttons(frm) {
	if (frm.doc.docstatus === 1 && frm.doc.custom_gi_gt_slip_number) {
		// Add button to print GI/GT Slip
		frm.add_custom_button(__('Print GI/GT Slip'), function() {
			print_gi_gt_slip(frm);
		}, __('Print'));
		
		// Add button to email GI/GT Slip
		frm.add_custom_button(__('Email GI/GT Slip'), function() {
			email_gi_gt_slip(frm);
		}, __('Print'));
	}
	
	if (frm.doc.custom_work_order_reference && !frm.doc.__islocal) {
		// Add button to refresh material status
		frm.add_custom_button(__('Refresh Material Status'), function() {
			get_work_order_material_status(frm);
		}, __('Actions'));
	}
	
	if (frm.doc.custom_sap_movement_type && !frm.doc.__islocal) {
		// Add button to validate SAP requirements
		frm.add_custom_button(__('Validate SAP Requirements'), function() {
			validate_sap_requirements(frm);
		}, __('Actions'));
	}
}

function style_signature_fields(frm) {
	// Add visual styling to signature fields
	const signature_fields = ['custom_warehouse_supervisor_signature', 'custom_kitting_supervisor_signature'];
	
	signature_fields.forEach(function(field) {
		const field_wrapper = frm.get_field(field).$wrapper;
		if (frm.doc[field]) {
			field_wrapper.addClass('signature-completed');
		} else {
			field_wrapper.removeClass('signature-completed');
		}
	});
}

function update_zone_status_display(frm) {
	if (frm.doc.custom_zone_status) {
		const zone_field = frm.get_field('custom_zone_status');
		if (zone_field) {
			const zone_wrapper = zone_field.$wrapper;
			
			// Remove existing classes
			zone_wrapper.removeClass('zone-red zone-green');
			
			// Add appropriate class
			if (frm.doc.custom_zone_status === 'Red Zone') {
				zone_wrapper.addClass('zone-red');
			} else if (frm.doc.custom_zone_status === 'Green Zone') {
				zone_wrapper.addClass('zone-green');
			}
		}
	}
}

function show_sap_movement_info(frm) {
	if (frm.doc.custom_sap_movement_type) {
		const movement_info = {
			'261': {
				title: 'FrontFlush - Goods Issue for Production',
				description: 'Material issued from Raw Material to Production for manufacturing',
				required_signatures: ['Warehouse Supervisor']
			},
			'311': {
				title: 'BackFlush - Transfer for Kitting',
				description: 'Material transfer from Production to Kitting area',
				required_signatures: ['Warehouse Supervisor', 'Kitting Supervisor']
			}
		};
		
		const info = movement_info[frm.doc.custom_sap_movement_type];
		if (info) {
			frm.dashboard.add_comment(info.description, 'blue');
		}
	}
}

function validate_sap_movement_type(frm) {
	if (!frm.doc.custom_sap_movement_type) return;
	
	const valid_types = ['261', '311'];
	if (!valid_types.includes(frm.doc.custom_sap_movement_type)) {
		frappe.msgprint({
			title: __('Invalid SAP Movement Type'),
			message: __('Please select a valid SAP Movement Type (261 or 311)'),
			indicator: 'red'
		});
	}
}

function update_required_signatures(frm) {
	if (!frm.doc.custom_sap_movement_type) return;
	
	const kitting_field = frm.get_field('custom_kitting_supervisor_signature');
	
	if (frm.doc.custom_sap_movement_type === '261') {
		// FrontFlush - only warehouse signature required
		kitting_field.df.reqd = 0;
		kitting_field.df.description = 'Not required for SAP Movement 261 (FrontFlush)';
	} else if (frm.doc.custom_sap_movement_type === '311') {
		// BackFlush - both signatures required
		kitting_field.df.reqd = 1;
		kitting_field.df.description = 'Required for SAP Movement 311 (BackFlush)';
	}
	
	frm.refresh_field('custom_kitting_supervisor_signature');
}

function set_purpose_based_on_sap_type(frm) {
	if (!frm.doc.custom_sap_movement_type) return;
	
	const purpose_mapping = {
		'261': 'Material Issue',
		'311': 'Material Transfer'
	};
	
	const suggested_purpose = purpose_mapping[frm.doc.custom_sap_movement_type];
	if (suggested_purpose && frm.doc.purpose !== suggested_purpose) {
		frappe.msgprint({
			title: __('Purpose Suggestion'),
			message: __('For SAP Movement {0}, the recommended purpose is {1}', [frm.doc.custom_sap_movement_type, suggested_purpose]),
			indicator: 'blue'
		});
	}
}

function suggest_sap_movement_type(frm) {
	if (!frm.doc.purpose || frm.doc.custom_sap_movement_type) return;
	
	const sap_mapping = {
		'Material Issue': '261',
		'Material Transfer': '311'
	};
	
	const suggested_sap = sap_mapping[frm.doc.purpose];
	if (suggested_sap) {
		frappe.msgprint({
			title: __('SAP Movement Suggestion'),
			message: __('For purpose {0}, consider using SAP Movement Type {1}', [frm.doc.purpose, suggested_sap]),
			indicator: 'blue'
		});
	}
}

function get_work_order_material_status(frm) {
	if (!frm.doc.custom_work_order_reference) return;
	
	frappe.call({
		method: 'rnd_warehouse_management.warehouse_management.work_order.get_work_order_material_status',
		args: {
			work_order_name: frm.doc.custom_work_order_reference
		},
		callback: function(r) {
			if (r.message && r.message.status === 'success') {
				const data = r.message;
				
				// Update zone status fields
				frm.set_value('custom_zone_status', data.zone_status);
				frm.set_value('custom_material_completion_percentage', data.completion_percentage);
				
				// Show material status dialog
				show_material_status_dialog(data.material_status);
				
				// Update display
				update_zone_status_display(frm);
			} else {
				frappe.msgprint({
					title: __('Error'),
					message: r.message.message || __('Failed to get material status'),
					indicator: 'red'
				});
			}
		}
	});
}

function show_material_status_dialog(material_status) {
	const dialog = new frappe.ui.Dialog({
		title: __('Work Order Material Status'),
		fields: [
			{
				fieldname: 'material_html',
				fieldtype: 'HTML'
			}
		]
	});
	
	// Generate HTML table for material status
	let html = '<table class="table table-bordered"><thead><tr>';
	html += '<th>Item Code</th><th>Item Name</th><th>Required Qty</th><th>Available Qty</th><th>Shortage</th><th>Status</th>';
	html += '</tr></thead><tbody>';
	
	material_status.forEach(function(item) {
		const status_class = item.status === 'Available' ? 'text-success' : 'text-danger';
		html += `<tr>`;
		html += `<td>${item.item_code}</td>`;
		html += `<td>${item.item_name}</td>`;
		html += `<td>${item.required_qty}</td>`;
		html += `<td>${item.available_qty}</td>`;
		html += `<td>${item.shortage}</td>`;
		html += `<td class="${status_class}">${item.status}</td>`;
		html += `</tr>`;
	});
	
	html += '</tbody></table>';
	
	dialog.fields_dict.material_html.$wrapper.html(html);
	dialog.show();
}

function validate_warehouse_requirements(frm) {
	// Validate warehouse types for SAP movements
	if (!frm.doc.custom_sap_movement_type) return;
	
	// This will be validated on the server side
	return true;
}

function validate_signature_requirements(frm) {
	if (!frm.doc.custom_sap_movement_type) return;
	
	// Check required signatures
	if (!frm.doc.custom_warehouse_supervisor_signature) {
		frappe.validated = false;
		frappe.msgprint({
			title: __('Missing Signature'),
			message: __('Warehouse Supervisor signature is required'),
			indicator: 'red'
		});
		return;
	}
	
	if (frm.doc.custom_sap_movement_type === '311' && !frm.doc.custom_kitting_supervisor_signature) {
		frappe.validated = false;
		frappe.msgprint({
			title: __('Missing Signature'),
			message: __('Kitting Supervisor signature is required for SAP Movement 311'),
			indicator: 'red'
		});
		return;
	}
}

function validate_sap_requirements(frm) {
	frappe.call({
		method: 'rnd_warehouse_management.warehouse_management.stock_entry.validate_sap_movement_type',
		args: {
			doc: frm.doc
		},
		callback: function(r) {
			if (r.message && r.message.status === 'success') {
				frappe.msgprint({
					title: __('Validation Successful'),
					message: __('All SAP movement requirements are satisfied'),
					indicator: 'green'
				});
			} else {
				frappe.msgprint({
					title: __('Validation Failed'),
					message: r.message.message || __('SAP movement validation failed'),
					indicator: 'red'
				});
			}
		}
	});
}

function show_signature_confirmation(frm, message) {
	frappe.show_alert({
		message: message,
		indicator: 'green'
	}, 3);
}

function print_gi_gt_slip(frm) {
	const print_format = 'GI/GT Slip with Signatures';
	const url = `/printview?doctype=Stock Entry&name=${frm.doc.name}&format=${print_format}&no_letterhead=0`;
	window.open(url, '_blank');
}

function email_gi_gt_slip(frm) {
	frappe.call({
		method: 'frappe.core.doctype.communication.email.make',
		args: {
			doctype: 'Stock Entry',
			name: frm.doc.name,
			print_format: 'GI/GT Slip with Signatures',
			subject: `GI/GT Slip - ${frm.doc.custom_gi_gt_slip_number || frm.doc.name}`
		},
		callback: function(r) {
			if (r.message) {
				frappe.msgprint(__('Email dialog opened'));
			}
		}
	});
}