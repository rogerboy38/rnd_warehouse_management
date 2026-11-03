"""The SAP movement types this app ships, in one place (TASKS-272, 2026-11-02).

Everything that lists movement types reads THIS list, so the three places that used to drift
(the Stock Entry `custom_sap_movement_type` Select options in fixtures/custom_field.json, the
boot info `bootinfo.sap_movement_types`, and the installer's Movement Type seed) cannot
disagree again: boot and install are generated from it, and tests/test_sap_movement_types.py
asserts the fixture files (movement_type.json records and the Select options) carry the same
16 codes with the same labels.

Label style of the Select option: `<code> (<description>)`. The 261/311 labels are prod's verbatim; the 561 label is the string the 42 submitted Stock
Entries on prod store — `561 (Initial Entry - Stock Balance)` — NOT the `… / Material Receipt` form
`0ca2d4e` shipped (a Select value outside `options` throws on every save that is not a cancel, so
that form would have made the 42 un-editable; TASKS-272b); the rest
take the first line of the Movement Type record's own description (313: its name + purpose),
281 is prod's Movement Type Master MT-281 description (Hugh's ruling 2026-11-03, TASKS-272c), 501 is
docs_TECHNICAL_SPECIFICATIONS.md MT-501.
"""

SAP_MOVEMENT_TYPES = [
	{"code": "101", "label": "Plant/General Material Receipt", "purpose": "Material Receipt", "default_stock_entry_type": "Material Receipt", "description": "Plant/General Material Receipt 101", "required_signatures": []},
	{"code": "102", "label": "Raw Material / Material Receipt", "purpose": "Material Receipt", "default_stock_entry_type": "Material Receipt", "description": "Raw Material / Material Receipt / 102", "required_signatures": []},
	{"code": "103", "label": "Finished Goods Delivery / Material Issue", "purpose": "Material Issue", "default_stock_entry_type": "Material Issue", "description": "Finished Goods Delivery / Material Issue / 103", "required_signatures": []},
	{"code": "104", "label": "Semi-Finished Goods Transfer / Material Transfer", "purpose": "Material Transfer", "default_stock_entry_type": "Material Transfer", "description": "Semi-Finished Goods Transfer / Material Transfer / 104", "required_signatures": []},
	{"code": "105", "label": "In Transit Transfer / Material Transfer", "purpose": "Material Transfer", "default_stock_entry_type": "Material Transfer", "description": "In Transit Transfer / Material Transfer / 105", "required_signatures": []},
	{"code": "106", "label": "Quality Control Transfer / Material Transfer", "purpose": "Material Transfer", "default_stock_entry_type": "Material Transfer", "description": "Quality Control Transfer / Material Transfer / 106", "required_signatures": []},
	{"code": "107", "label": "MRB Movement / Material Transfer", "purpose": "Material Transfer", "default_stock_entry_type": "Material Transfer", "description": "MRB Movement / Material Transfer / 107", "required_signatures": []},
	{"code": "108", "label": "Send to Subcontractor", "purpose": "Send to Subcontractor", "default_stock_entry_type": "Send to Subcontractor", "description": "Send to Subcontractor / 108 / 1 / Outgoing", "required_signatures": []},
	{"code": "109", "label": "Stores Movement / Material Issue", "purpose": "Material Issue", "default_stock_entry_type": "Material Issue", "description": "Stores Movement / Material Issue / 109 /", "required_signatures": []},
	{"code": "261", "label": "FrontFlush - Goods Issue for Production", "purpose": "Manufacture", "default_stock_entry_type": "Manufacture", "description": "Issue materials from storage to production", "required_signatures": ["warehouse_supervisor"]},
	{"code": "281", "label": "Goods Issue for Sampling", "purpose": "Material Issue", "default_stock_entry_type": "Material Issue", "description": "Goods Issue for Sampling", "required_signatures": []},
	{"code": "311", "label": "BackFlush - Transfer for Kitting", "purpose": "Material Consumption for Manufacture", "default_stock_entry_type": "Material Consumption for Manufacture", "description": "Transfer materials from production to kitting area", "required_signatures": ["warehouse_supervisor", "kitting_supervisor"]},
	{"code": "313", "label": "Kitting to WIP / Material Transfer for Manufacture", "purpose": "Material Transfer for Manufacture", "default_stock_entry_type": "Material Transfer for Manufacture", "description": "Raw Material / Material to Manufacture / 313 equivalent SAP transaction code \"MB1B\"", "required_signatures": []},
	{"code": "501", "label": "Receipt without Purchase Order", "purpose": "Material Receipt", "default_stock_entry_type": "Material Receipt", "description": "Receipt without Purchase Order (MT-501)", "required_signatures": []},
	{"code": "545", "label": "Receive from Subcontractor / Material Receipt", "purpose": "Material Receipt", "default_stock_entry_type": "Material Receipt", "description": "Receive from Subcontractor / Material Receipt / 545 / 1 / Incoming", "required_signatures": []},
	{"code": "561", "label": "Initial Entry - Stock Balance", "purpose": "Material Receipt", "default_stock_entry_type": "Material Receipt", "description": "Initial entry of stock balance (opening stock) as a Material Receipt", "required_signatures": ["warehouse_supervisor"]},
]

CODES = [m["code"] for m in SAP_MOVEMENT_TYPES]


def option_label(m):
	"""The Select option as stored on Stock Entry.custom_sap_movement_type."""
	return f'{m["code"]} ({m["label"]})'


def select_options():
	"""The Select field's options text: a leading blank option, then one line per code."""
	return "\n" + "\n".join(option_label(m) for m in SAP_MOVEMENT_TYPES)


def sap_code(value):
	"""The bare SAP code of a stored value: '311 (BackFlush - Transfer for Kitting)' -> '311', '311' -> '311', None -> ''."""
	return (value or "").strip().split(" ", 1)[0]


def boot_dict():
	"""bootinfo.sap_movement_types, keyed by code, same shape as before (name / description / purpose / required_signatures)."""
	return {m["code"]: {"name": m["label"], "description": m["description"], "purpose": m["purpose"],
	                    "required_signatures": list(m["required_signatures"])} for m in SAP_MOVEMENT_TYPES}
