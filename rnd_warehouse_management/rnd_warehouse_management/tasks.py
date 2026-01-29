import frappe
from frappe.utils import nowdate, now_datetime

def update_zone_status():
	"""Scheduled task to update Work Order zone status"""
	try:
		# Get all active Work Orders
		work_orders = frappe.get_all(
			"Work Order",
			filters={"status": ["not in", ["Completed", "Stopped", "Cancelled"]]},
			fields=["name", "bom_no", "qty"]
		)
		
		for wo in work_orders:
			if wo.bom_no:
				from rnd_warehouse_management.warehouse_management.work_order import update_work_order_zone_status
				update_work_order_zone_status(wo.name)
		
		frappe.log(f"Updated zone status for {len(work_orders)} Work Orders")
	except Exception as e:
		frappe.log_error(f"Zone status update task failed: {str(e)}")

def cleanup_expired_signatures():
	"""Clean up expired signature data (older than 1 year)"""
	try:
		# Get Stock Entries with old signatures
		one_year_ago = frappe.utils.add_years(nowdate(), -1)
		
		old_entries = frappe.get_all(
			"Stock Entry",
			filters={
				"custom_warehouse_supervisor_sign_date": ["<", one_year_ago],
				"docstatus": 1
			},
			fields=["name"]
		)
		
		# Archive signature data (move to separate table or clear sensitive data)
		for entry in old_entries:
			# For security, clear signature images but keep timestamp
			frappe.db.set_value(
				"Stock Entry",
				entry.name,
				{
					"custom_warehouse_supervisor_signature": None,
					"custom_kitting_supervisor_signature": None
				}
			)
		
		frappe.db.commit()
		frappe.log(f"Cleaned up signature data for {len(old_entries)} entries")
	except Exception as e:
		frappe.log_error(f"Signature cleanup task failed: {str(e)}")

def generate_warehouse_reports():
	"""Generate daily warehouse utilization reports"""
	try:
		# Get warehouse utilization data
		warehouses = frappe.get_all(
			"Warehouse",
			filters={"custom_max_capacity": [">=", 0]},
			fields=["name", "warehouse_type", "custom_max_capacity"]
		)
		
		for warehouse in warehouses:
			if warehouse.custom_max_capacity:
				# Calculate current stock value
				current_value = frappe.db.sql("""
					SELECT SUM(stock_value) as total_value
					FROM `tabBin`
					WHERE warehouse = %s
				""", warehouse.name, as_dict=True)[0]
				
				total_value = current_value.get("total_value", 0) or 0
				utilization = (total_value / warehouse.custom_max_capacity) * 100
				
				# Update warehouse utilization
				frappe.db.set_value(
					"Warehouse",
					warehouse.name,
					{
						"custom_current_utilization": utilization,
						"custom_last_capacity_update": now_datetime()
					}
				)
		
		frappe.db.commit()
		frappe.log(f"Updated utilization for {len(warehouses)} warehouses")
	except Exception as e:
		frappe.log_error(f"Warehouse report generation failed: {str(e)}")

def send_daily_warehouse_summary():
	"""Send daily warehouse summary email"""
	try:
		# Get warehouse managers
		managers = frappe.get_all(
			"Has Role",
			filters={"role": "Warehouse Manager"},
			fields=["parent as user"]
		)
		
		if not managers:
			return
		
		# Generate summary data
		summary_data = generate_summary_data()
		
		# Send email to warehouse managers
		for manager in managers:
			user_email = frappe.db.get_value("User", manager.user, "email")
			if user_email:
				send_warehouse_summary_email(user_email, summary_data)
		
		frappe.log(f"Sent warehouse summary to {len(managers)} managers")
	except Exception as e:
		frappe.log_error(f"Daily warehouse summary failed: {str(e)}")

def generate_summary_data():
	"""Generate warehouse summary data"""
	# Get key metrics
	pending_approvals = frappe.db.count(
		"Stock Entry",
		{"workflow_state": ["in", ["Pending Warehouse Approval", "Warehouse Approved"]]}
	)
	
	red_zone_orders = frappe.db.count(
		"Work Order",
		{"custom_current_zone_status": "Red Zone", "status": ["not in", ["Completed", "Cancelled"]]}
	)
	
	green_zone_orders = frappe.db.count(
		"Work Order",
		{"custom_current_zone_status": "Green Zone", "status": ["not in", ["Completed", "Cancelled"]]}
	)
	
	return {
		"pending_approvals": pending_approvals,
		"red_zone_orders": red_zone_orders,
		"green_zone_orders": green_zone_orders,
		"date": nowdate()
	}

def send_warehouse_summary_email(email, data):
	"""Send warehouse summary email to a user"""
	frappe.sendmail(
		recipients=[email],
		subject=f"Daily Warehouse Summary - {data['date']}",
		message=f"""
		<h3>Daily Warehouse Management Summary</h3>
		<p><strong>Date:</strong> {data['date']}</p>
		<ul>
			<li><strong>Pending Approvals:</strong> {data['pending_approvals']}</li>
			<li><strong>Red Zone Work Orders:</strong> {data['red_zone_orders']}</li>
			<li><strong>Green Zone Work Orders:</strong> {data['green_zone_orders']}</li>
		</ul>
		<p>Please review the pending approvals and zone status in the system.</p>
		""",
		now=True
	)