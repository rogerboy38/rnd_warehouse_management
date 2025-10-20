// Work Order Form Enhancements for RND Warehouse Management

frappe.ui.form.on('Work Order', {
	// Form initialization
	refresh: function(frm) {
		// Add custom buttons
		add_work_order_buttons(frm);
		
		// Style zone status fields
		style_zone_status_fields(frm);
		
		// Show zone status dashboard
		show_zone_status_dashboard(frm);
	},
	
	// BOM change handler
	bom_no: function(frm) {
		if (frm.doc.bom_no) {
			update_material_requirements(frm);
		}
	},
	
	// Quantity change handler
	qty: function(frm) {
		if (frm.doc.bom_no) {
			update_material_requirements(frm);
		}
	}
});

// Helper Functions

function add_work_order_buttons(frm) {
	if (!frm.doc.__islocal) {
		// Add button to check material status
		frm.add_custom_button(__('Check Material Status'), function() {
			check_material_status(frm);
		}, __('Material Management'));
		
		// Add button to update zone status
		frm.add_custom_button(__('Update Zone Status'), function() {
			update_zone_status(frm);
		}, __('Material Management'));
		
		// Add button to create stock entry
		if (frm.doc.custom_current_zone_status === 'Green Zone') {
			frm.add_custom_button(__('Create Stock Entry'), function() {
				create_stock_entry_for_work_order(frm);
			}, __('Material Management'));
		}
		
		// Add button to view related stock entries
		frm.add_custom_button(__('View Stock Entries'), function() {
			view_related_stock_entries(frm);
		}, __('Material Management'));
	}
}

function style_zone_status_fields(frm) {
	if (frm.doc.custom_current_zone_status) {
		const zone_field = frm.get_field('custom_current_zone_status');
		if (zone_field) {
			const zone_wrapper = zone_field.$wrapper;
			
			// Remove existing classes
			zone_wrapper.removeClass('zone-red zone-green');
			
			// Add appropriate class
			if (frm.doc.custom_current_zone_status === 'Red Zone') {
				zone_wrapper.addClass('zone-red');
			} else if (frm.doc.custom_current_zone_status === 'Green Zone') {
				zone_wrapper.addClass('zone-green');
			}
		}
	}
	
	// Style completion percentage
	if (frm.doc.custom_material_completion_percentage !== undefined) {
		const completion_field = frm.get_field('custom_material_completion_percentage');
		if (completion_field) {
			const completion_wrapper = completion_field.$wrapper;
			const percentage = frm.doc.custom_material_completion_percentage;
			
			completion_wrapper.removeClass('completion-low completion-medium completion-high');
			
			if (percentage < 50) {
				completion_wrapper.addClass('completion-low');
			} else if (percentage < 100) {
				completion_wrapper.addClass('completion-medium');
			} else {
				completion_wrapper.addClass('completion-high');
			}
		}
	}
}

function show_zone_status_dashboard(frm) {
	if (frm.doc.custom_current_zone_status) {
		const status = frm.doc.custom_current_zone_status;
		const percentage = frm.doc.custom_material_completion_percentage || 0;
		const last_update = frm.doc.custom_last_zone_update;
		
		let color = status === 'Green Zone' ? 'green' : 'red';
		let message = `Zone Status: ${status} (${percentage.toFixed(1)}% materials available)`;
		
		if (last_update) {
			message += ` - Last updated: ${frappe.datetime.str_to_user(last_update)}`;
		}
		
		frm.dashboard.add_comment(message, color);
		
		// Add material shortage information if in Red Zone
		if (status === 'Red Zone' && frm.doc.custom_missing_materials_json) {
			try {
				const missing_materials = JSON.parse(frm.doc.custom_missing_materials_json);
				if (missing_materials.length > 0) {
					const shortage_message = `Missing ${missing_materials.length} material(s). Click 'Check Material Status' for details.`;
					frm.dashboard.add_comment(shortage_message, 'orange');
				}
			} catch (e) {
				// Ignore JSON parsing errors
			}
		}
	}
}

function check_material_status(frm) {
	frappe.call({
		method: 'rnd_warehouse_management.warehouse_management.work_order.get_work_order_material_status',
		args: {
			work_order_name: frm.doc.name
		},
		callback: function(r) {
			if (r.message && r.message.status === 'success') {
				show_material_status_dialog(r.message.material_status, r.message);
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

function update_zone_status(frm) {
	frappe.call({
		method: 'rnd_warehouse_management.warehouse_management.work_order.update_work_order_zone_status',
		args: {
			work_order_name: frm.doc.name
		},
		callback: function(r) {
			if (r.message && r.message.status === 'success') {
				// Update form fields
				frm.set_value('custom_current_zone_status', r.message.zone_status);
				frm.set_value('custom_material_completion_percentage', r.message.completion_percentage);
				frm.set_value('custom_last_zone_update', r.message.last_updated);
				
				// Refresh displays
				style_zone_status_fields(frm);
				show_zone_status_dashboard(frm);
				
				frappe.show_alert({
					message: __('Zone status updated successfully'),
					indicator: 'green'
				}, 3);
			} else {
				frappe.msgprint({
					title: __('Error'),
					message: r.message.message || __('Failed to update zone status'),
					indicator: 'red'
				});
			}
		}
	});
}

function update_material_requirements(frm) {
	// This will be handled server-side when BOM or qty changes
	// Just refresh the zone status
	setTimeout(function() {
		update_zone_status(frm);
	}, 1000);
}

function create_stock_entry_for_work_order(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __('Create Stock Entry'),
		fields: [
			{
				fieldname: 'purpose',
				label: __('Purpose'),
				fieldtype: 'Select',
				options: 'Material Issue\nMaterial Transfer',
				reqd: 1,
				default: 'Material Issue'
			},
			{
				fieldname: 'sap_movement_type',
				label: __('SAP Movement Type'),
				fieldtype: 'Select',
				options: '261 (FrontFlush - Goods Issue for Production)\n311 (BackFlush - Transfer for Kitting)',
				reqd: 1,
				default: '261'
			},
			{
				fieldname: 'qty',
				label: __('Quantity'),
				fieldtype: 'Float',
				default: frm.doc.qty
			}
		],
		primary_action_label: __('Create'),
		primary_action(values) {
			frappe.call({
				method: 'rnd_warehouse_management.warehouse_management.stock_entry.make_custom_stock_entry',
				args: {
					work_order: frm.doc.name,
					purpose: values.purpose,
					qty: values.qty
				},
				callback: function(r) {
					if (r.message) {
						// Set SAP movement type
						r.message.custom_sap_movement_type = values.sap_movement_type.split(' ')[0];
						
						// Open the new Stock Entry
						frappe.model.sync(r.message);
						frappe.set_route('Form', 'Stock Entry', r.message.name);
					}
				}
			});
			
			dialog.hide();
		}
	});
	
	dialog.show();
}

function view_related_stock_entries(frm) {
	frappe.route_options = {
		'custom_work_order_reference': frm.doc.name
	};
	frappe.set_route('List', 'Stock Entry');
}

function show_material_status_dialog(material_status, summary_data) {
	const dialog = new frappe.ui.Dialog({
		title: __('Material Status for Work Order'),
		size: 'large',
		fields: [
			{
				fieldname: 'summary_html',
				fieldtype: 'HTML'
			},
			{
				fieldname: 'material_html',
				fieldtype: 'HTML'
			}
		]
	});
	
	// Generate summary HTML
	let summary_html = '<div class="material-summary">';
	summary_html += `<h4>Summary</h4>`;
	summary_html += `<p><strong>Zone Status:</strong> <span class="${summary_data.zone_status === 'Green Zone' ? 'text-success' : 'text-danger'}">${summary_data.zone_status}</span></p>`;
	summary_html += `<p><strong>Completion:</strong> ${summary_data.completion_percentage.toFixed(1)}%</p>`;
	summary_html += '</div><hr>';
	
	// Generate detailed material HTML
	let material_html = '<h4>Detailed Material Status</h4>';
	material_html += '<table class="table table-bordered table-condensed">';
	material_html += '<thead><tr>';
	material_html += '<th>Item Code</th><th>Item Name</th><th>Required</th><th>Available</th><th>Shortage</th><th>Warehouse</th><th>Status</th>';
	material_html += '</tr></thead><tbody>';
	
	material_status.forEach(function(item) {
		const status_class = item.status === 'Available' ? 'text-success' : 'text-danger';
		const row_class = item.status === 'Available' ? '' : 'warning';
		
		material_html += `<tr class="${row_class}">`;
		material_html += `<td><strong>${item.item_code}</strong></td>`;
		material_html += `<td>${item.item_name}</td>`;
		material_html += `<td>${item.required_qty.toFixed(3)}</td>`;
		material_html += `<td>${item.available_qty.toFixed(3)}</td>`;
		material_html += `<td>${item.shortage.toFixed(3)}</td>`;
		material_html += `<td>${item.warehouse}</td>`;
		material_html += `<td class="${status_class}"><strong>${item.status}</strong></td>`;
		material_html += `</tr>`;
	});
	
	material_html += '</tbody></table>';
	
	dialog.fields_dict.summary_html.$wrapper.html(summary_html);
	dialog.fields_dict.material_html.$wrapper.html(material_html);
	dialog.show();
}