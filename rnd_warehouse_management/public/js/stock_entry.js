// Stock Entry Form Enhancements for RND Warehouse Management

frappe.ui.form.on('Stock Entry', {
	// Form initialization
	refresh: function(frm) {
		// Add custom buttons
		add_custom_buttons(frm);
		
		// Phase 2: Add approval workflow buttons
		add_approval_workflow_buttons(frm);
		
		// Style signature fields
		style_signature_fields(frm);
		
		// Update zone status display
		update_zone_status_display(frm);
		
		// Phase 2: Display approval workflow timeline
		display_approval_workflow_timeline(frm);
		
		// Load and show movement type info if selected
		if (frm.doc.custom_sap_movement_type) {
			load_movement_type_details(frm);
		}
	},
	
	// SAP Movement Type change handler
	custom_sap_movement_type: function(frm) {
		if (frm.doc.custom_sap_movement_type) {
			load_movement_type_details(frm);
		}
	},
	
	// Work Order Reference change handler
	custom_work_order_reference: function(frm) {
		if (frm.doc.custom_work_order_reference) {
			get_work_order_material_status(frm);
		}
	},
	
	// Purpose change handler
	purpose: function(frm) {
		suggest_movement_types_for_purpose(frm);
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

function load_movement_type_details(frm) {
	if (!frm.doc.custom_sap_movement_type) return;
	
	frappe.call({
		method: 'rnd_warehouse_management.warehouse_management.stock_entry.get_movement_type_details_for_ui',
		args: {
			movement_code: frm.doc.custom_sap_movement_type
		},
		callback: function(r) {
			if (r.message) {
				const mt = r.message;
				
				// Update read-only fields
				frm.set_value('custom_movement_type_description', mt.description);
				frm.set_value('custom_movement_category', mt.category);
				
				// Auto-set purpose if not already set
				if (!frm.doc.purpose && mt.erpnext_stock_entry_purpose) {
					frm.set_value('purpose', mt.erpnext_stock_entry_purpose);
				}
				
				// Update signature requirements
				update_signature_requirements_from_movement_type(frm, mt);
				
				// Show movement type info
				show_movement_type_info(frm, mt);
			}
		}
	});
}

function update_signature_requirements_from_movement_type(frm, movement_type) {
	const warehouse_sig_field = frm.get_field('custom_warehouse_supervisor_signature');
	const kitting_sig_field = frm.get_field('custom_kitting_supervisor_signature');
	
	if (movement_type.requires_approval) {
		// Always require warehouse supervisor signature for approved movements
		warehouse_sig_field.df.reqd = 1;
		warehouse_sig_field.df.description = `Required for ${movement_type.authorization_level} level authorization`;
		
		// Require kitting signature for production transfers
		if (movement_type.category === 'Production' && movement_type.stock_movement_type === 'Transfer') {
			kitting_sig_field.df.reqd = 1;
			kitting_sig_field.df.description = 'Required for production transfers (kitting operations)';
		} else {
			kitting_sig_field.df.reqd = 0;
			kitting_sig_field.df.description = 'Not required for this movement type';
		}
	} else {
		warehouse_sig_field.df.reqd = 0;
		kitting_sig_field.df.reqd = 0;
	}
	
	frm.refresh_field('custom_warehouse_supervisor_signature');
	frm.refresh_field('custom_kitting_supervisor_signature');
}

function show_movement_type_info(frm, movement_type) {
	if (!movement_type) return;
	
	const info_html = `
		<div class="alert alert-info" style="margin-bottom: 10px;">
			<strong>Movement Type ${movement_type.movement_code}:</strong> ${movement_type.description}<br/>
			<strong>Category:</strong> ${movement_type.category} | 
			<strong>Type:</strong> ${movement_type.stock_movement_type} | 
			<strong>Approval:</strong> ${movement_type.requires_approval ? 'Required (' + movement_type.authorization_level + ')' : 'Not Required'}
		</div>
	`;
	
	frm.dashboard.add_comment(info_html, 'blue', true);
}

function suggest_movement_types_for_purpose(frm) {
	if (!frm.doc.purpose || frm.doc.custom_sap_movement_type) return;
	
	frappe.call({
		method: 'rnd_warehouse_management.warehouse_management.stock_entry.get_movement_types_for_purpose',
		args: {
			purpose: frm.doc.purpose
		},
		callback: function(r) {
			if (r.message && r.message.length > 0) {
				const movement_types = r.message;
				let message = `<p>Available movement types for <strong>${frm.doc.purpose}</strong>:</p><ul>`;
				
				movement_types.forEach(function(mt) {
					message += `<li><strong>${mt.movement_code}</strong>: ${mt.description}</li>`;
				});
				
				message += '</ul>';
				
				frappe.msgprint({
					title: __('Suggested Movement Types'),
					message: message,
					indicator: 'blue'
				});
			}
		}
	});
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

// ========== PHASE 2: APPROVAL WORKFLOW UI FUNCTIONS ==========

function add_approval_workflow_buttons(frm) {
	if (!frm.doc.custom_sap_movement_type || frm.doc.__islocal) return;
	
	const approval_status = frm.doc.custom_approval_status;
	
	// Request Approval button
	if (!approval_status || approval_status === 'Draft' || approval_status === 'Rejected') {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Request Approval'), function() {
				request_approval_action(frm);
			}, __('Approval'));
		}
	}
	
	// Approve button (if user has permission)
	if (approval_status && approval_status.includes('Pending')) {
		frappe.call({
			method: 'rnd_warehouse_management.warehouse_management.stock_entry.get_approval_summary',
			args: { stock_entry_name: frm.doc.name },
			async: false,
			callback: function(r) {
				if (r.message && r.message.can_approve) {
					frm.add_custom_button(__('Approve'), function() {
						approve_stock_entry_action(frm);
					}, __('Approval'));
					
					frm.add_custom_button(__('Reject'), function() {
						reject_stock_entry_action(frm);
					}, __('Approval'));
				}
			}
		});
	}
	
	// View Approval History button
	if (approval_status && approval_status !== 'Draft') {
		frm.add_custom_button(__('View Approval History'), function() {
			view_approval_history(frm);
		}, __('Approval'));
	}
}

function request_approval_action(frm) {
	frappe.confirm(
		__('Do you want to request approval for this Stock Entry?'),
		function() {
			frappe.call({
				method: 'rnd_warehouse_management.warehouse_management.stock_entry.request_approval',
				args: { stock_entry_name: frm.doc.name },
				callback: function(r) {
					if (r.message && r.message.success) {
						frappe.show_alert({
							message: r.message.message,
							indicator: 'green'
						}, 5);
						frm.reload_doc();
					} else {
						frappe.msgprint({
							title: __('Error'),
							message: r.message || __('Failed to request approval'),
							indicator: 'red'
						});
					}
				}
			});
		}
	);
}

function approve_stock_entry_action(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __('Approve Stock Entry'),
		fields: [
			{
				fieldname: 'comments',
				fieldtype: 'Small Text',
				label: __('Approval Comments'),
				description: __('Optional comments for this approval')
			},
			{
				fieldname: 'section_break',
				fieldtype: 'Section Break'
			},
			{
				fieldname: 'signature_data',
				fieldtype: 'Attach Image',
				label: __('Digital Signature (Optional)'),
				description: __('Upload your digital signature')
			}
		],
		primary_action_label: __('Approve'),
		primary_action: function(values) {
			frappe.call({
				method: 'rnd_warehouse_management.warehouse_management.stock_entry.approve_stock_entry',
				args: {
					stock_entry_name: frm.doc.name,
					comments: values.comments,
					signature_data: values.signature_data
				},
				callback: function(r) {
					if (r.message && r.message.success) {
						frappe.show_alert({
							message: r.message.message,
							indicator: 'green'
						}, 5);
						dialog.hide();
						frm.reload_doc();
					} else {
						frappe.msgprint({
							title: __('Error'),
							message: r.message || __('Failed to approve'),
							indicator: 'red'
						});
					}
				}
			});
		}
	});
	
	dialog.show();
}

function reject_stock_entry_action(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __('Reject Stock Entry'),
		fields: [
			{
				fieldname: 'rejection_reason',
				fieldtype: 'Small Text',
				label: __('Rejection Reason'),
				reqd: 1,
				description: __('Please provide a reason for rejection')
			}
		],
		primary_action_label: __('Reject'),
		primary_action: function(values) {
			frappe.call({
				method: 'rnd_warehouse_management.warehouse_management.stock_entry.reject_stock_entry',
				args: {
					stock_entry_name: frm.doc.name,
					rejection_reason: values.rejection_reason
				},
				callback: function(r) {
					if (r.message && r.message.success) {
						frappe.show_alert({
							message: r.message.message,
							indicator: 'orange'
						}, 5);
						dialog.hide();
						frm.reload_doc();
					} else {
						frappe.msgprint({
							title: __('Error'),
							message: r.message || __('Failed to reject'),
							indicator: 'red'
						});
					}
				}
			});
		}
	});
	
	dialog.show();
}

function display_approval_workflow_timeline(frm) {
	if (!frm.doc.custom_sap_movement_type || !frm.doc.custom_approval_status || frm.doc.custom_approval_status === 'Draft') {
		return;
	}
	
	frappe.call({
		method: 'rnd_warehouse_management.warehouse_management.stock_entry.get_approval_summary',
		args: { stock_entry_name: frm.doc.name },
		callback: function(r) {
			if (r.message) {
				const summary = r.message;
				const timeline_html = build_approval_timeline_html(summary);
				
				// Display timeline in form
				if (timeline_html) {
					frm.dashboard.add_comment(timeline_html, 'blue', true);
				}
			}
		}
	});
}

function build_approval_timeline_html(summary) {
	if (!summary || !summary.approval_rules || summary.approval_rules.length === 0) {
		return null;
	}
	
	let html = '<div class="approval-workflow-timeline">';
	html += '<h5 style="margin-bottom: 15px;"><i class="fa fa-tasks"></i> Approval Workflow Progress</h5>';
	html += '<div class="timeline-steps">';
	
	const total_levels = summary.total_levels;
	const current_level = summary.current_level;
	const current_status = summary.current_status;
	
	// Build timeline steps
	for (let i = 1; i <= total_levels; i++) {
		const is_completed = i <= current_level;
		const is_current = i === (current_level + 1) && current_status.includes('Pending');
		const is_rejected = current_status === 'Rejected';
		
		let step_class = 'timeline-step';
		let icon = 'fa-circle-o';
		let status_text = 'Pending';
		
		if (is_rejected && is_current) {
			step_class += ' timeline-step-rejected';
			icon = 'fa-times-circle';
			status_text = 'Rejected';
		} else if (is_completed) {
			step_class += ' timeline-step-completed';
			icon = 'fa-check-circle';
			status_text = 'Approved';
		} else if (is_current) {
			step_class += ' timeline-step-current';
			icon = 'fa-clock-o';
			status_text = 'Pending';
		}
		
		html += `<div class="${step_class}">`;
		html += `<div class="timeline-icon"><i class="fa ${icon}"></i></div>`;
		html += `<div class="timeline-content">`;
		html += `<strong>Level ${i}</strong><br/>`;
		html += `<span class="text-muted">${status_text}</span>`;
		
		// Show approver info from history
		if (summary.approval_history && summary.approval_history.length > 0) {
			const level_history = summary.approval_history.filter(h => h.approval_level === i);
			if (level_history.length > 0) {
				const latest = level_history[level_history.length - 1];
				html += `<br/><small>${latest.user} - ${latest.event_timestamp}</small>`;
				if (latest.comments) {
					html += `<br/><small><em>${latest.comments}</em></small>`;
				}
			}
		}
		
		html += `</div>`;
		html += `</div>`;
	}
	
	html += '</div>';
	
	// Add status badge
	let badge_color = 'blue';
	if (current_status === 'Fully Approved') badge_color = 'green';
	else if (current_status === 'Rejected') badge_color = 'red';
	else if (current_status.includes('Pending')) badge_color = 'orange';
	
	html += `<div style="margin-top: 10px;">`;
	html += `<span class="indicator-pill ${badge_color}">${current_status}</span>`;
	html += `</div>`;
	
	html += '</div>';
	
	return html;
}

function view_approval_history(frm) {
	frappe.call({
		method: 'rnd_warehouse_management.warehouse_management.stock_entry.get_approval_summary',
		args: { stock_entry_name: frm.doc.name },
		callback: function(r) {
			if (r.message && r.message.approval_history) {
				const history = r.message.approval_history;
				
				const dialog = new frappe.ui.Dialog({
					title: __('Approval History'),
					fields: [{ fieldname: 'history_html', fieldtype: 'HTML' }],
					size: 'large'
				});
				
				let html = '<table class="table table-bordered"><thead><tr>';
				html += '<th>Date/Time</th><th>Event</th><th>Level</th><th>User</th><th>Status</th><th>Comments</th>';
				html += '</tr></thead><tbody>';
				
				history.forEach(function(log) {
					const status_class = log.approval_status === 'Approved' ? 'text-success' : 
										 log.approval_status === 'Rejected' ? 'text-danger' : 'text-warning';
					
					html += `<tr>`;
					html += `<td>${log.event_timestamp || ''}</td>`;
					html += `<td>${log.event_type || ''}</td>`;
					html += `<td>${log.approval_level || 'N/A'}</td>`;
					html += `<td>${log.user || ''}</td>`;
					html += `<td class="${status_class}">${log.approval_status || ''}</td>`;
					html += `<td>${log.comments || ''}</td>`;
					html += `</tr>`;
				});
				
				html += '</tbody></table>';
				
				dialog.fields_dict.history_html.$wrapper.html(html);
				dialog.show();
			} else {
				frappe.msgprint(__('No approval history available'));
			}
		}
	});
}