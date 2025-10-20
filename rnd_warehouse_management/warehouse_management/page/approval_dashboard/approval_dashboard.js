frappe.pages['approval-dashboard'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Approval Dashboard',
		single_column: true
	});
	
	wrapper.approval_dashboard = new ApprovalDashboard(wrapper, page);
}

class ApprovalDashboard {
	constructor(wrapper, page) {
		this.wrapper = wrapper;
		this.page = page;
		this.filters = {};
		this.selected_entries = [];
		
		this.setup_page();
		this.load_data();
	}
	
	setup_page() {
		// Add refresh button
		this.page.set_primary_action(__('Refresh'), () => {
			this.load_data();
		}, 'fa fa-refresh');
		
		// Add bulk approve button
		this.page.add_action_icon('fa fa-check-circle', () => {
			this.bulk_approve_action();
		}, __('Bulk Approve'));
		
		// Setup filters
		this.setup_filters();
		
		// Create tabs
		this.create_tabs();
	}
	
	setup_filters() {
		// Movement Type filter
		this.page.add_field({
			fieldname: 'movement_type',
			label: __('Movement Type'),
			fieldtype: 'Link',
			options: 'Movement Type Master',
			change: () => {
				this.filters.movement_type = this.page.fields_dict.movement_type.get_value();
				this.load_data();
			}
		});
		
		// Date range filter
		this.page.add_field({
			fieldname: 'from_date',
			label: __('From Date'),
			fieldtype: 'Date',
			default: frappe.datetime.add_days(frappe.datetime.get_today(), -30),
			change: () => {
				this.filters.from_date = this.page.fields_dict.from_date.get_value();
				this.load_data();
			}
		});
		
		this.page.add_field({
			fieldname: 'to_date',
			label: __('To Date'),
			fieldtype: 'Date',
			default: frappe.datetime.get_today(),
			change: () => {
				this.filters.to_date = this.page.fields_dict.to_date.get_value();
				this.load_data();
			}
		});
	}
	
	create_tabs() {
		const $page_content = $(this.wrapper).find('.page-content');
		$page_content.html(`
			<div class="dashboard-container">
				<!-- Statistics Cards -->
				<div class="stats-section" id="stats-section"></div>
				
				<!-- Tabs -->
				<ul class="nav nav-tabs" role="tablist">
					<li class="nav-item">
						<a class="nav-link active" data-toggle="tab" href="#pending-tab" role="tab">
							<i class="fa fa-clock-o"></i> ${__('Pending Approvals')}
						</a>
					</li>
					<li class="nav-item">
						<a class="nav-link" data-toggle="tab" href="#history-tab" role="tab">
							<i class="fa fa-history"></i> ${__('My History')}
						</a>
					</li>
				</ul>
				
				<!-- Tab Content -->
				<div class="tab-content">
					<div class="tab-pane active" id="pending-tab" role="tabpanel">
						<div id="pending-approvals-list"></div>
					</div>
					<div class="tab-pane" id="history-tab" role="tabpanel">
						<div id="approval-history-list"></div>
					</div>
				</div>
			</div>
		`);
	}
	
	load_data() {
		frappe.call({
			method: 'rnd_warehouse_management.warehouse_management.page.approval_dashboard.approval_dashboard.get_dashboard_data',
			args: { filters: this.filters },
			callback: (r) => {
				if (r.message) {
					this.render_statistics(r.message.statistics);
					this.render_pending_approvals(r.message.pending_approvals);
					this.render_approval_history(r.message.approval_history);
				}
			}
		});
	}
	
	render_statistics(stats) {
		const $stats = $(this.wrapper).find('#stats-section');
		$stats.html(`
			<div class="row" style="margin-bottom: 20px;">
				<div class="col-sm-3">
					<div class="stat-card stat-pending">
						<div class="stat-icon"><i class="fa fa-clock-o"></i></div>
						<div class="stat-content">
							<h3>${stats.pending_count || 0}</h3>
							<p>${__('Pending Approvals')}</p>
						</div>
					</div>
				</div>
				<div class="col-sm-3">
					<div class="stat-card stat-approved">
						<div class="stat-icon"><i class="fa fa-check-circle"></i></div>
						<div class="stat-content">
							<h3>${stats.approved_this_month || 0}</h3>
							<p>${__('Approved This Month')}</p>
						</div>
					</div>
				</div>
				<div class="col-sm-3">
					<div class="stat-card stat-rejected">
						<div class="stat-icon"><i class="fa fa-times-circle"></i></div>
						<div class="stat-content">
							<h3>${stats.rejected_this_month || 0}</h3>
							<p>${__('Rejected This Month')}</p>
						</div>
					</div>
				</div>
				<div class="col-sm-3">
					<div class="stat-card stat-overdue">
						<div class="stat-icon"><i class="fa fa-exclamation-triangle"></i></div>
						<div class="stat-content">
							<h3>${stats.overdue_count || 0}</h3>
							<p>${__('Overdue (>3 days)')}</p>
						</div>
					</div>
				</div>
			</div>
		`);
	}
	
	render_pending_approvals(approvals) {
		const $list = $(this.wrapper).find('#pending-approvals-list');
		
		if (!approvals || approvals.length === 0) {
			$list.html(`
				<div class="empty-state">
					<i class="fa fa-check-circle" style="font-size: 48px; color: #28a745;"></i>
					<p>${__('No pending approvals')}</p>
				</div>
			`);
			return;
		}
		
		let html = `
			<div class="approval-actions" style="margin: 15px 0;">
				<button class="btn btn-xs btn-primary" id="select-all-btn">${__('Select All')}</button>
				<button class="btn btn-xs btn-default" id="deselect-all-btn">${__('Deselect All')}</button>
			</div>
			<div class="approval-list">
		`;
		
		approvals.forEach((entry) => {
			const urgency_class = entry.urgency === 'High' ? 'urgency-high' : 
								  entry.urgency === 'Medium' ? 'urgency-medium' : 'urgency-low';
			
			html += `
				<div class="approval-card ${urgency_class}" data-name="${entry.name}">
					<div class="approval-checkbox">
						<input type="checkbox" class="entry-checkbox" data-name="${entry.name}">
					</div>
					<div class="approval-content">
						<div class="approval-header">
							<h4><a href="/app/stock-entry/${entry.name}" target="_blank">${entry.name}</a></h4>
							<span class="badge badge-warning">${entry.custom_approval_status}</span>
						</div>
						<div class="approval-details">
							<div><strong>${__('Movement Type')}:</strong> ${entry.custom_sap_movement_type} - ${entry.custom_movement_type_description || ''}</div>
							<div><strong>${__('Posting Date')}:</strong> ${entry.posting_date}</div>
							<div><strong>${__('Days Pending')}:</strong> ${entry.days_pending} days 
								<span class="urgency-badge ${urgency_class}">${entry.urgency}</span>
							</div>
							<div><strong>${__('Created By')}:</strong> ${entry.owner}</div>
						</div>
						<div class="approval-actions">
							<button class="btn btn-sm btn-success approve-btn" data-name="${entry.name}">
								<i class="fa fa-check"></i> ${__('Approve')}
							</button>
							<button class="btn btn-sm btn-danger reject-btn" data-name="${entry.name}">
								<i class="fa fa-times"></i> ${__('Reject')}
							</button>
							<button class="btn btn-sm btn-default view-btn" data-name="${entry.name}">
								<i class="fa fa-eye"></i> ${__('View')}
							</button>
						</div>
					</div>
				</div>
			`;
		});
		
		html += '</div>';
		$list.html(html);
		
		// Attach event handlers
		this.attach_approval_handlers();
	}
	
	render_approval_history(history) {
		const $list = $(this.wrapper).find('#approval-history-list');
		
		if (!history || history.length === 0) {
			$list.html(`
				<div class="empty-state">
					<i class="fa fa-history" style="font-size: 48px; color: #6c757d;"></i>
					<p>${__('No approval history')}</p>
				</div>
			`);
			return;
		}
		
		let html = `
			<table class="table table-bordered table-hover">
				<thead>
					<tr>
						<th>${__('Date/Time')}</th>
						<th>${__('Stock Entry')}</th>
						<th>${__('Movement Type')}</th>
						<th>${__('Action')}</th>
						<th>${__('Level')}</th>
						<th>${__('Status')}</th>
						<th>${__('Comments')}</th>
					</tr>
				</thead>
				<tbody>
		`;
		
		history.forEach((log) => {
			const status_class = log.approval_status === 'Approved' ? 'text-success' : 
								 log.approval_status === 'Rejected' ? 'text-danger' : 'text-warning';
			
			html += `
				<tr>
					<td>${log.event_timestamp || ''}</td>
					<td><a href="/app/stock-entry/${log.stock_entry}" target="_blank">${log.stock_entry}</a></td>
					<td>${log.movement_type || ''} - ${log.movement_description || ''}</td>
					<td>${log.event_type || ''}</td>
					<td>${log.approval_level || 'N/A'}</td>
					<td class="${status_class}"><strong>${log.approval_status || ''}</strong></td>
					<td>${log.comments || ''}</td>
				</tr>
			`;
		});
		
		html += `
				</tbody>
			</table>
		`;
		$list.html(html);
	}
	
	attach_approval_handlers() {
		const me = this;
		
		// Select/Deselect all
		$(me.wrapper).find('#select-all-btn').on('click', function() {
			$(me.wrapper).find('.entry-checkbox').prop('checked', true);
		});
		
		$(me.wrapper).find('#deselect-all-btn').on('click', function() {
			$(me.wrapper).find('.entry-checkbox').prop('checked', false);
		});
		
		// Approve button
		$(me.wrapper).find('.approve-btn').on('click', function() {
			const entry_name = $(this).data('name');
			me.approve_entry(entry_name);
		});
		
		// Reject button
		$(me.wrapper).find('.reject-btn').on('click', function() {
			const entry_name = $(this).data('name');
			me.reject_entry(entry_name);
		});
		
		// View button
		$(me.wrapper).find('.view-btn').on('click', function() {
			const entry_name = $(this).data('name');
			frappe.set_route('Form', 'Stock Entry', entry_name);
		});
	}
	
	approve_entry(entry_name) {
		const me = this;
		
		const dialog = new frappe.ui.Dialog({
			title: __('Approve Stock Entry'),
			fields: [
				{
					fieldname: 'comments',
					fieldtype: 'Small Text',
					label: __('Approval Comments')
				}
			],
			primary_action_label: __('Approve'),
			primary_action: function(values) {
				frappe.call({
					method: 'rnd_warehouse_management.warehouse_management.stock_entry.approve_stock_entry',
					args: {
						stock_entry_name: entry_name,
						comments: values.comments
					},
					callback: function(r) {
						if (r.message && r.message.success) {
							frappe.show_alert({ message: r.message.message, indicator: 'green' }, 5);
							dialog.hide();
							me.load_data();
						}
					}
				});
			}
		});
		
		dialog.show();
	}
	
	reject_entry(entry_name) {
		const me = this;
		
		const dialog = new frappe.ui.Dialog({
			title: __('Reject Stock Entry'),
			fields: [
				{
					fieldname: 'rejection_reason',
					fieldtype: 'Small Text',
					label: __('Rejection Reason'),
					reqd: 1
				}
			],
			primary_action_label: __('Reject'),
			primary_action: function(values) {
				frappe.call({
					method: 'rnd_warehouse_management.warehouse_management.stock_entry.reject_stock_entry',
					args: {
						stock_entry_name: entry_name,
						rejection_reason: values.rejection_reason
					},
					callback: function(r) {
						if (r.message && r.message.success) {
							frappe.show_alert({ message: r.message.message, indicator: 'orange' }, 5);
							dialog.hide();
							me.load_data();
						}
					}
				});
			}
		});
		
		dialog.show();
	}
	
	bulk_approve_action() {
		const me = this;
		const selected = [];
		
		$(me.wrapper).find('.entry-checkbox:checked').each(function() {
			selected.push($(this).data('name'));
		});
		
		if (selected.length === 0) {
			frappe.msgprint(__('Please select at least one entry'));
			return;
		}
		
		frappe.confirm(
			__('Are you sure you want to approve {0} entries?', [selected.length]),
			function() {
				frappe.call({
					method: 'rnd_warehouse_management.warehouse_management.page.approval_dashboard.approval_dashboard.bulk_approve',
					args: {
						stock_entry_names: selected,
						comments: 'Bulk approved from dashboard'
					},
					callback: function(r) {
						if (r.message) {
							const results = r.message;
							frappe.msgprint({
								title: __('Bulk Approve Results'),
								indicator: 'green',
								message: __('Approved: {0}, Failed: {1}', [results.success.length, results.failed.length])
							});
							me.load_data();
						}
					}
				});
			}
		);
	}
}
