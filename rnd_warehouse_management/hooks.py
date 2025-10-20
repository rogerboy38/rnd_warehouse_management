from . import __version__ as app_version

app_name = "rnd_warehouse_management"
app_title = "RND Warehouse Management"
app_publisher = "MiniMax Agent"
app_description = "Professional warehouse management system with SAP-style movement types, dual-signature workflows, and Red/Green zone logic for ERPNext"
app_icon = "fa fa-warehouse"
app_color = "#3498db"
app_email = "support@minimax.com"
app_license = "MIT"
app_version = "2.1.0"
required_apps = ["frappe", "erpnext"]

# Additional Features
has_website_permission = {
	"Warehouse": "rnd_warehouse_management.permissions.warehouse_query",
	"Stock Entry": "rnd_warehouse_management.permissions.stock_entry_query"
}

# Website Settings
website_route_rules = [
	{"from_route": "/warehouse-dashboard", "to_route": "rnd_warehouse_management/dashboard"},
	{"from_route": "/gi-gt-slip/<path:name>", "to_route": "rnd_warehouse_management/print-gi-gt-slip"}
]

# Include JS and CSS
app_include_css = "/assets/rnd_warehouse_management/css/warehouse_management.css"
app_include_js = "/assets/rnd_warehouse_management/js/warehouse_management.js"

# Include Specific DocType Assets
doctype_js = {
	"Stock Entry": "public/js/stock_entry.js",
	"Work Order": "public/js/work_order.js",
	"Warehouse": "public/js/warehouse.js"
}

doctype_list_js = {
	"Stock Entry": "public/js/stock_entry_list.js"
}

# DocType Event Hooks
doc_events = {
	"Stock Entry": {
		"before_save": "rnd_warehouse_management.warehouse_management.stock_entry.before_save",
		"before_submit": "rnd_warehouse_management.warehouse_management.stock_entry.before_submit",
		"on_submit": "rnd_warehouse_management.warehouse_management.stock_entry.on_submit",
		"before_cancel": "rnd_warehouse_management.warehouse_management.stock_entry.before_cancel",
		"on_update_after_submit": "rnd_warehouse_management.warehouse_management.stock_entry.on_update_after_submit"
	},
	"Work Order": {
		"before_save": "rnd_warehouse_management.warehouse_management.work_order.before_save",
		"on_submit": "rnd_warehouse_management.warehouse_management.work_order.on_submit"
	},
	"Warehouse": {
		"before_save": "rnd_warehouse_management.warehouse_management.warehouse.before_save"
	}
}

# Custom Field Installation
fixtures = [
	{"dt": "Movement Type Master", "filters": [["Movement Type Master", "is_active", "=", 1]]},
	{"dt": "Stock Entry Approval Rule", "filters": [["Stock Entry Approval Rule", "enabled", "=", 1]]},
	"Custom Field",
	"Property Setter",
	"Custom Script",
	"Print Format",
	"Letter Head",
	"Workflow",
	"Workflow State",
	"Workflow Action Master",
	"Role",
	"Server Script"
]

# Workflow Override
override_whitelisted_methods = {
	"erpnext.stock.doctype.stock_entry.stock_entry.make_stock_entry": "rnd_warehouse_management.warehouse_management.stock_entry.make_custom_stock_entry"
}

# Scheduler Events (for background tasks)
scheduler_events = {
	"hourly": [
		"rnd_warehouse_management.warehouse_management.tasks.update_zone_status"
	],
	"daily": [
		"rnd_warehouse_management.warehouse_management.tasks.cleanup_expired_signatures",
		"rnd_warehouse_management.warehouse_management.tasks.generate_warehouse_reports",
		# Phase 2: Auto-escalation of overdue approvals (runs daily at 9 AM)
		"rnd_warehouse_management.warehouse_management.stock_entry.check_and_escalate_overdue_approvals"
	]
}

# Installation
after_install = "rnd_warehouse_management.install.after_install"
after_uninstall = "rnd_warehouse_management.uninstall.after_uninstall"

# Boot session data
boot_session = "rnd_warehouse_management.boot.boot_session"

# Permission Query Functions
permission_query_conditions = {
	"Stock Entry": "rnd_warehouse_management.warehouse_management.stock_entry.get_permission_query_conditions",
	"Work Order": "rnd_warehouse_management.warehouse_management.work_order.get_permission_query_conditions"
}

# Jinja Custom Methods
jinja = {
	"methods": [
		"rnd_warehouse_management.utils.get_signature_image",
		"rnd_warehouse_management.utils.format_sap_movement_type",
		"rnd_warehouse_management.utils.get_zone_status_badge"
	]
}