// Copyright (c) 2025, MiniMax Agent and contributors
// For license information, please see license.txt

frappe.ui.form.on('Stock Entry Audit Log', {
	refresh: function(frm) {
		// Audit logs are read-only
		frm.disable_save();
		
		// Add button to view related stock entry
		if (frm.doc.stock_entry) {
			frm.add_custom_button(__('View Stock Entry'), function() {
				frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry);
			});
		}
		
		// Add button to view full audit trail
		if (frm.doc.stock_entry) {
			frm.add_custom_button(__('View Full Audit Trail'), function() {
				view_full_audit_trail(frm);
			});
		}
		
		// Display signature if present
		if (frm.doc.signature_data) {
			display_signature(frm);
		}
		
		// Parse and display additional data
		if (frm.doc.additional_data) {
			display_additional_data(frm);
		}
		
		// Add color coding based on event type
		apply_event_type_styling(frm);
	}
});

function view_full_audit_trail(frm) {
	frappe.call({
		method: 'rnd_warehouse_management.warehouse_management.doctype.stock_entry_audit_log.stock_entry_audit_log.get_audit_trail',
		args: {
			stock_entry: frm.doc.stock_entry
		},
		callback: function(r) {
			if (r.message && r.message.length > 0) {
				let html = '<table class="table table-bordered">';
				html += '<thead><tr><th>Timestamp</th><th>Event</th><th>User</th><th>Details</th></tr></thead><tbody>';
				
				r.message.forEach(function(log) {
					html += '<tr>';
					html += `<td>${frappe.datetime.str_to_user(log.event_timestamp)}</td>`;
					html += `<td><span class="label label-${get_event_label_color(log.event_type)}">${log.event_type}</span></td>`;
					html += `<td>${log.user} (${log.user_role || 'N/A'})</td>`;
					
					let details = '';
					if (log.field_changed) {
						details = `${log.field_changed}: ${log.previous_value || 'N/A'} → ${log.new_value || 'N/A'}`;
					} else if (log.comments) {
						details = log.comments;
					} else if (log.approval_status) {
						details = `Level ${log.approval_level}: ${log.approval_status}`;
					}
					html += `<td>${details}</td>`;
					html += '</tr>';
				});
				
				html += '</tbody></table>';
				
				frappe.msgprint({
					title: __('Complete Audit Trail'),
					indicator: 'blue',
					message: html
				});
			} else {
				frappe.msgprint(__('No audit trail found'));
			}
		}
	});
}

function display_signature(frm) {
	if (frm.doc.signature_data) {
		let signature_html = `<img src="${frm.doc.signature_data}" class="img-responsive" style="max-width: 300px; border: 1px solid #ccc; padding: 5px;"/>`;
		
		frm.get_field('signature_data').$wrapper.html(signature_html);
	}
}

function display_additional_data(frm) {
	if (frm.doc.additional_data) {
		try {
			let data = JSON.parse(frm.doc.additional_data);
			let html = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
			
			frm.set_df_property('additional_data', 'description', 'Parsed JSON data');
		} catch (e) {
			console.error('Failed to parse additional data:', e);
		}
	}
}

function apply_event_type_styling(frm) {
	const event_colors = {
		'Created': 'blue',
		'Modified': 'orange',
		'Submitted': 'green',
		'Cancelled': 'red',
		'Approval Requested': 'blue',
		'Approval Granted': 'green',
		'Approval Rejected': 'red',
		'Signature Added': 'purple',
		'Escalated': 'darkred',
		'Comment Added': 'gray'
	};
	
	let color = event_colors[frm.doc.event_type] || 'blue';
	frm.set_df_property('event_type', 'label_class', `label-${color}`);
}

function get_event_label_color(event_type) {
	const color_map = {
		'Created': 'info',
		'Modified': 'warning',
		'Submitted': 'success',
		'Cancelled': 'danger',
		'Approval Requested': 'info',
		'Approval Granted': 'success',
		'Approval Rejected': 'danger',
		'Signature Added': 'primary',
		'Escalated': 'danger',
		'Comment Added': 'default'
	};
	
	return color_map[event_type] || 'default';
}
