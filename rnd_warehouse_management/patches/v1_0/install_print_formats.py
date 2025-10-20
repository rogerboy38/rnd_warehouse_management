import frappe
from frappe import _
import json
import os

def execute():
	"""Install print formats from fixtures"""
	frappe.log("Installing print formats...")
	
	try:
		# Load print format fixture
		fixture_path = frappe.get_app_path("rnd_warehouse_management", "fixtures", "print_format.json")
		
		if os.path.exists(fixture_path):
			with open(fixture_path, 'r') as f:
				data = json.load(f)
				
			for print_format_data in data:
				if not frappe.db.exists("Print Format", print_format_data["name"]):
					try:
						print_format = frappe.get_doc(print_format_data)
						print_format.insert(ignore_permissions=True)
						frappe.log(f"Created print format: {print_format_data['name']}")
					except Exception as e:
						frappe.log_error(f"Failed to create print format {print_format_data['name']}: {str(e)}")
				else:
					frappe.log(f"Print format {print_format_data['name']} already exists")
		
		frappe.db.commit()
		frappe.log("Print formats installation completed")
	
	except Exception as e:
		frappe.log_error(f"Failed to install print formats: {str(e)}")