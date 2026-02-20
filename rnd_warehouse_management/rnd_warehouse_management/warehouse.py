import frappe
from frappe import _
from frappe.utils import flt

def before_save(doc, method=None):
	"""Hook: Before saving Warehouse"""
	validate_warehouse_configuration(doc)
	set_default_transit_warehouse(doc)
	update_temperature_settings(doc)

def validate_warehouse_configuration(doc):
	"""Validate warehouse configuration based on type"""
	if not doc.warehouse_type:
		return
	
	# Define validation rules for different warehouse types
	validation_rules = {
		"Raw Material": {
			"required_fields": [],
			"naming_pattern": "Raw Material",
			"temperature_controlled": False
		},
		"Work In Progress": {
			"required_fields": [],
			"naming_pattern": ["WIP", "Production", "Kitting", "Zone"],
			"temperature_controlled": False
		},
		"Finished Goods": {
			"required_fields": [],
			"naming_pattern": "FG",
			"temperature_controlled": True
		},
		"Transit": {
			"required_fields": [],
			"naming_pattern": "Transit",
			"is_group": False,
			"temperature_controlled": False
		},
		"Rejected": {
			"required_fields": [],
			"naming_pattern": "Rejected",
			"is_rejected": True,
			"temperature_controlled": False
		}
	}
	
	rules = validation_rules.get(doc.warehouse_type)
	if not rules:
		return
	
	# Validate naming pattern
	naming_patterns = rules.get("naming_pattern", [])
	if isinstance(naming_patterns, str):
		naming_patterns = [naming_patterns]
	
	if naming_patterns:
		valid_name = any(pattern.lower() in doc.warehouse_name.lower() for pattern in naming_patterns)
		if not valid_name:
			frappe.msgprint(_("Warning: Warehouse name '{0}' doesn't follow recommended pattern for {1} warehouses")
				.format(doc.warehouse_name, doc.warehouse_type), alert=True)
	
	# Auto-set properties based on warehouse type
	if doc.warehouse_type == "Transit":
		doc.is_group = 0  # Transit warehouses should not be group warehouses
	
	if doc.warehouse_type == "Rejected":
		doc.is_rejected_warehouse = 1
	
	# Set temperature control recommendations
	if rules.get("temperature_controlled") and not doc.custom_temperature_control:
		frappe.msgprint(_("Consider enabling temperature control for {0} warehouse").format(doc.warehouse_type), alert=True)

def set_default_transit_warehouse(doc):
	"""Set default in-transit warehouse based on warehouse type and location"""
	if doc.warehouse_type == "Transit":
		return  # Transit warehouses don't need in-transit warehouses
	
	if not doc.default_in_transit_warehouse:
		# Try to find or suggest a transit warehouse
		transit_warehouse_name = f"{doc.warehouse_name.replace(' - ', ' Transit - ')}"
		if "Transit" not in transit_warehouse_name:
			transit_warehouse_name = f"{doc.warehouse_name.split(' - ')[0]} Transit - {doc.company}"
		
		# Check if transit warehouse exists
		existing_transit = frappe.db.exists("Warehouse", transit_warehouse_name)
		if existing_transit:
			doc.default_in_transit_warehouse = existing_transit
		else:
			# Suggest creating a transit warehouse
			frappe.msgprint(_("Consider creating a transit warehouse: {0}").format(transit_warehouse_name), alert=True)

def update_temperature_settings(doc):
	"""Update temperature-related settings"""
	if doc.custom_temperature_control:
		# Validate temperature range
		if doc.custom_target_temperature:
			target_temp = flt(doc.custom_target_temperature)
			if target_temp < -50 or target_temp > 50:
				frappe.throw(_("Target temperature should be between -50°C and 50°C"))
		
		# Set default temperature if not specified
		if not doc.custom_target_temperature:
			if doc.warehouse_type == "Finished Goods":
				doc.custom_target_temperature = 20  # Room temperature for FG
			elif doc.warehouse_type == "Raw Material":
				doc.custom_target_temperature = 15  # Cooler for raw materials
			else:
				doc.custom_target_temperature = 25  # Standard warehouse temperature

@frappe.whitelist()
def create_warehouse_hierarchy(company, locations=None):
	"""API endpoint to create complete warehouse hierarchy"""
	try:
		if not locations:
			locations = ["AMB-W"]  # Default location
		
		created_warehouses = []
		
		for location in locations:
			warehouses_to_create = [
				# Raw Material Division
				{"name": f"Raw Material Main - {location}", "type": "Raw Material", "parent": None},
				{"name": f"Raw Material Transit - {location}", "type": "Transit", "parent": f"Raw Material Main - {location}"},
				{"name": f"Raw Material Rejected - {location}", "type": "Rejected", "parent": f"Raw Material Main - {location}"},
				
				# Production Division
				{"name": f"Production WIP - {location}", "type": "Work In Progress", "parent": None},
				{"name": f"Production Transit - {location}", "type": "Transit", "parent": f"Production WIP - {location}"},
				{"name": f"Kitting Area - {location}", "type": "Work In Progress", "parent": f"Production WIP - {location}"},
				{"name": f"Kitting Transit - {location}", "type": "Transit", "parent": f"Kitting Area - {location}"},
				{"name": f"Production Rejected - {location}", "type": "Rejected", "parent": f"Production WIP - {location}"},
				
				# Finished Goods Division
				{"name": f"FG Main - {location}", "type": "Finished Goods", "parent": None},
				{"name": f"FG to Sell - {location}", "type": "Finished Goods", "parent": f"FG Main - {location}"},
				{"name": f"FG Transit - {location}", "type": "Transit", "parent": f"FG Main - {location}"},
				{"name": f"FG Rejected - {location}", "type": "Rejected", "parent": f"FG Main - {location}"},
				
				# Work Order Zones
				{"name": f"Red Zone - {location}", "type": "Work In Progress", "parent": None},
				{"name": f"Green Zone - {location}", "type": "Work In Progress", "parent": None},
				{"name": f"Zone Transit - {location}", "type": "Transit", "parent": None}
			]
			
			for warehouse_config in warehouses_to_create:
				if not frappe.db.exists("Warehouse", warehouse_config["name"]):
					warehouse = frappe.get_doc({
						"doctype": "Warehouse",
						"warehouse_name": warehouse_config["name"],
						"warehouse_type": warehouse_config["type"],
						"parent_warehouse": warehouse_config["parent"],
						"company": company,
						"is_group": 1 if warehouse_config["type"] != "Transit" else 0,
						"is_rejected_warehouse": 1 if warehouse_config["type"] == "Rejected" else 0
					})
					
					try:
						warehouse.insert(ignore_permissions=True)
						created_warehouses.append(warehouse.name)
					except Exception as e:
						frappe.log_error(f"Failed to create warehouse {warehouse_config['name']}: {str(e)}")
			
		return {
			"status": "success",
			"message": f"Created {len(created_warehouses)} warehouses",
			"created_warehouses": created_warehouses
		}
	except Exception as e:
		frappe.log_error(f"Warehouse hierarchy creation failed: {str(e)}")
		return {"status": "error", "message": str(e)}

@frappe.whitelist()
def get_warehouse_dashboard_data(warehouse=None):
	"""API endpoint to get warehouse dashboard data"""
	try:
		filters = {}
		if warehouse:
			filters["name"] = warehouse
		
		warehouses = frappe.get_all(
			"Warehouse",
			filters=filters,
			fields=["name", "warehouse_type", "is_group", "parent_warehouse", "company", "custom_temperature_control", "custom_target_temperature"]
		)
		
		# Get stock levels for each warehouse
		for wh in warehouses:
			stock_data = frappe.db.sql("""
				SELECT 
					COUNT(DISTINCT item_code) as item_count,
					SUM(actual_qty) as total_qty,
					SUM(stock_value) as total_value
				FROM `tabBin`
				WHERE warehouse = %s AND actual_qty > 0
			""", wh["name"], as_dict=True)
			
			if stock_data:
				wh.update(stock_data[0])
			else:
				wh.update({"item_count": 0, "total_qty": 0, "total_value": 0})
		
		return {
			"status": "success",
			"warehouses": warehouses
		}
	except Exception as e:
		frappe.log_error(f"Warehouse dashboard data fetch failed: {str(e)}")
		return {"status": "error", "message": str(e)}

# =============================================================================
# ADDITIONS TO: rnd_warehouse_management/rnd_warehouse_management/warehouse.py
# =============================================================================
# These functions are APPENDED to the existing warehouse.py file.
# The existing file already contains:
#   - before_save(doc, method) hook
#   - validate_warehouse_configuration(doc)
#   - set_default_transit_warehouse(doc)
#   - update_temperature_settings(doc)
#   - create_warehouse_hierarchy(company, locations)  @whitelist
#   - get_warehouse_dashboard_data(warehouse)         @whitelist
#
# Correct import path for hooks.py / frappe.call():
#   rnd_warehouse_management.rnd_warehouse_management.warehouse.<function_name>
# =============================================================================

# --- Add these imports at the top of the existing warehouse.py ---
from datetime import date, timedelta
from typing import List, Optional


# ---------------------------------------------------------------------------
# NEW: ITEM STOCK LOCATIONS - Where is item X across all warehouses?
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_item_stock_locations(item_code: str) -> List[dict]:
    """Return all warehouses/bins that hold stock for a given item.

    Args:
        item_code: ERPNext Item code

    Returns:
        List of dicts with warehouse, actual_qty, reserved_qty, available_qty
    """
    if not item_code:
        frappe.throw(_("item_code is required"))

    data = frappe.db.sql(
        """
        SELECT
            b.item_code,
            b.warehouse,
            b.actual_qty,
            b.reserved_qty,
            b.projected_qty,
            b.reserved_qty_for_production,
            b.reserved_qty_for_sub_contract,
            (b.actual_qty - b.reserved_qty) AS available_qty,
            w.warehouse_type,
            w.parent_warehouse,
            w.custom_temperature_control
        FROM `tabBin` b
        LEFT JOIN `tabWarehouse` w ON w.name = b.warehouse
        WHERE b.item_code = %(item_code)s
          AND b.actual_qty != 0
        ORDER BY b.warehouse
        """,
        {"item_code": item_code},
        as_dict=True,
    )

    return data


# ---------------------------------------------------------------------------
# NEW: KARDEX - Stock ledger slice per warehouse/item/date range
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_kardex(
    warehouse=None,
    item_code=None,
    from_date=None,
    to_date=None,
    limit=500,
):
    """Return stock ledger entries (Kardex) with running balance.

    Args:
        warehouse: Filter by warehouse name
        item_code: Filter by item code
        from_date: Start date YYYY-MM-DD
        to_date: End date YYYY-MM-DD
        limit: Max rows to return (default 500)

    Returns:
        List of SLE dicts ordered by posting_date, posting_time
    """
    filters = {}
    conditions = ["sle.is_cancelled = 0"]

    if warehouse:
        conditions.append("sle.warehouse = %(warehouse)s")
        filters["warehouse"] = warehouse
    if item_code:
        conditions.append("sle.item_code = %(item_code)s")
        filters["item_code"] = item_code
    if from_date:
        conditions.append("sle.posting_date >= %(from_date)s")
        filters["from_date"] = from_date
    if to_date:
        conditions.append("sle.posting_date <= %(to_date)s")
        filters["to_date"] = to_date

    where_clause = "WHERE " + " AND ".join(conditions)
    filters["limit"] = int(limit)

    entries = frappe.db.sql(
        f"""
        SELECT
            sle.posting_date,
            sle.posting_time,
            sle.item_code,
            sle.item_name,
            sle.warehouse,
            sle.actual_qty,
            sle.qty_after_transaction,
            sle.voucher_type,
            sle.voucher_no,
            sle.batch_no,
            sle.serial_no,
            sle.incoming_rate,
            sle.valuation_rate,
            sle.stock_value_difference,
            sle.project
        FROM `tabStock Ledger Entry` sle
        {where_clause}
        ORDER BY sle.posting_date, sle.posting_time, sle.creation
        LIMIT %(limit)s
        """,
        filters,
        as_dict=True,
    )

    return entries


# ---------------------------------------------------------------------------
# NEW: OOS RISK LIST - Items OOS now or at risk of stockout
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_oos_risk_list(
    company,
    warehouse=None,
    lookback_days=90,
    include_zero_demand=False,
):
    """Return items that are OOS now or at risk of stockout.

    Risk logic:
        - OOS NOW:       available_qty <= 0
        - AT_RISK:       available_qty > 0 AND days_of_supply < lead_time_days
        - BELOW_REORDER: available_qty > 0 AND available_qty <= reorder_level

    Args:
        company: ERPNext Company name
        warehouse: Optional - filter to a single warehouse
        lookback_days: Days of history to compute daily demand (default 90)
        include_zero_demand: Include items with no recent demand

    Returns:
        List of risk dicts sorted by status then days_of_supply ASC
    """
    if not company:
        frappe.throw(_("company is required"))

    end_date = date.today()
    start_date = end_date - timedelta(days=int(lookback_days))

    # 1) Get all bins for company
    wh_cond = "AND b.warehouse = %(warehouse)s" if warehouse else ""
    bins = frappe.db.sql(
        f"""
        SELECT
            b.item_code,
            b.warehouse,
            b.actual_qty,
            b.reserved_qty,
            b.projected_qty
        FROM `tabBin` b
        INNER JOIN `tabWarehouse` w ON w.name = b.warehouse
        WHERE w.company = %(company)s
          {wh_cond}
        """,
        {"company": company, "warehouse": warehouse or ""},
        as_dict=True,
    )

    if not bins:
        return []

    item_codes = list({b.item_code for b in bins})

    # 2) Compute demand (issues) per item/warehouse from SLE
    demand_rows = frappe.db.sql(
        """
        SELECT
            item_code,
            warehouse,
            SUM(CASE WHEN actual_qty < 0 THEN -actual_qty ELSE 0 END) AS total_issues
        FROM `tabStock Ledger Entry`
        WHERE company = %(company)s
          AND item_code IN %(item_codes)s
          AND posting_date BETWEEN %(start_date)s AND %(end_date)s
          AND is_cancelled = 0
        GROUP BY item_code, warehouse
        """,
        {
            "company": company,
            "item_codes": tuple(item_codes),
            "start_date": str(start_date),
            "end_date": str(end_date),
        },
        as_dict=True,
    )
    demand_map = {(d.item_code, d.warehouse): d.total_issues for d in demand_rows}

    # 3) Fetch item master fields
    item_info = {
        r.item_code: r
        for r in frappe.db.get_all(
            "Item",
            fields=["name as item_code", "item_name", "item_group", "lead_time_days"],
            filters={"name": ["in", item_codes]},
        )
    }

    # 4) Fetch reorder levels
    reorder_rows = frappe.db.get_all(
        "Item Reorder",
        fields=["parent as item_code", "warehouse", "warehouse_reorder_level", "warehouse_reorder_qty"],
        filters={"parent": ["in", item_codes]},
    )
    reorder_map = {(r.item_code, r.warehouse): r for r in reorder_rows}

    # 5) Build risk list
    results = []
    for b in bins:
        key = (b.item_code, b.warehouse)
        total_issues = demand_map.get(key, 0) or 0
        daily_demand = total_issues / int(lookback_days) if total_issues else 0

        available = flt(b.actual_qty) - flt(b.reserved_qty)

        info = item_info.get(b.item_code) or frappe._dict()
        lead_time_days = flt(info.lead_time_days)

        reorder = reorder_map.get(key) or frappe._dict()
        reorder_level = flt(reorder.get("warehouse_reorder_level"))
        reorder_qty = flt(reorder.get("warehouse_reorder_qty"))

        days_of_supply = (available / daily_demand) if daily_demand > 0 else None

        is_oos_now = available <= 0
        at_risk = (
            not is_oos_now
            and lead_time_days > 0
            and days_of_supply is not None
            and days_of_supply < lead_time_days
        )
        below_reorder = (
            not is_oos_now
            and reorder_level > 0
            and available <= reorder_level
        )

        if not (is_oos_now or at_risk or below_reorder):
            if not include_zero_demand:
                continue

        status = "OOS" if is_oos_now else ("AT_RISK" if at_risk else "BELOW_REORDER")

        results.append({
            "item_code": b.item_code,
            "item_name": info.get("item_name") or b.item_code,
            "item_group": info.get("item_group"),
            "warehouse": b.warehouse,
            "actual_qty": b.actual_qty,
            "reserved_qty": b.reserved_qty,
            "available_qty": available,
            "projected_qty": b.projected_qty,
            "reorder_level": reorder_level,
            "reorder_qty": reorder_qty,
            "lead_time_days": lead_time_days,
            "daily_demand": round(daily_demand, 4),
            "days_of_supply": round(days_of_supply, 1) if days_of_supply is not None else None,
            "status": status,
        })

    status_order = {"OOS": 0, "AT_RISK": 1, "BELOW_REORDER": 2}
    results.sort(
        key=lambda r: (status_order.get(r["status"], 9), r["days_of_supply"] or 0)
    )

    return results


# ---------------------------------------------------------------------------
# NEW: HELPER - List warehouses by type
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_warehouses_by_type(company, warehouse_type=None):
    """Return warehouses for a company, optionally filtered by type."""
    filters = {"company": company, "is_group": 0, "disabled": 0}
    if warehouse_type:
        filters["warehouse_type"] = warehouse_type

    return frappe.db.get_all(
        "Warehouse",
        fields=["name", "warehouse_name", "warehouse_type", "parent_warehouse",
                "custom_temperature_control", "custom_target_temperature"],
        filters=filters,
        order_by="warehouse_type, name",
    )


