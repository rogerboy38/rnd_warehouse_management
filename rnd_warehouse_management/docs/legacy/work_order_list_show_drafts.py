"""
Archived Server Script: Work Order List Show Drafts

V13.6.0 P3 Server Script Migration
Decision: DEL / archived
Target app: rnd_warehouse_management

Original metadata:
- name: Work Order List Show Drafts
- script_type: API
- reference_doctype: None
- doctype_event: Before Insert
- event_frequency: All
- disabled: 1
- module: None
- api_method: frappe.client.get_list
- allow_guest: 0

Runtime status:
- Archived only.
- Do not import or hook this file.
- Original Server Script DB row will be deleted by the final P3 delete patch after validation.
"""

ORIGINAL_SCRIPT = r'''
# Remove docstatus filter to show drafts
filters = json.loads(frappe.form_dict.get('filters') or '[]')
new_filters = [f for f in filters if not (isinstance(f, list) and len(f) > 1 and f[1] == 'docstatus')]
frappe.form_dict['filters'] = json.dumps(new_filters)
'''
