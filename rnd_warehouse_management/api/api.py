# rnd_warehouse_management.api
# API module for RND Warehouse Management - provides get_material_status

import frappe
from frappe import _


@frappe.whitelist()
def get_material_status(work_order):
    """
    API method: Get material status for a Work Order.

    This method is called from the Work Order form via:
        frappe.call({ method: 'rnd_warehouse_management.api.get_material_status', ... })

    Returns material availability status and completion percentage.
    """
    try:
        if not work_order:
            return {
                "status": "error",
                "message": "No work_order provided"
            }

        # Get Work Order document
        wo = frappe.get_doc("Work Order", work_order)

        # Check if BOM exists
        if not wo.bom_no:
            return {
                "status": "warning",
                "zone_status": "No BOM",
                "completion_percentage": 0,
                "message": "No BOM associated with this Work Order"
            }

        # Get BOM items with availability
        bom_items = frappe.get_all(
            "BOM Item",
            filters={"parent": wo.bom_no},
            fields=["item_code", "qty", "source_warehouse", "item_name", "description"]
        )

        if not bom_items:
            return {
                "status": "warning",
                "zone_status": "No Items",
                "completion_percentage": 0,
                "message": "BOM has no items"
            }

        # Calculate material availability
        total_items = len(bom_items)
        available_items = 0
        material_status = []

        for bom_item in bom_items:
            # Get required qty (BOM qty * WO qty)
            required_qty = frappe.utils.flt(bom_item.qty * wo.qty)

            # Get available qty from Bin
            available_qty = frappe.db.get_value(
                "Bin",
                {"item_code": bom_item.item_code, "warehouse": bom_item.source_warehouse},
                "actual_qty"
            ) or 0

            # Check if available
            is_available = available_qty >= required_qty
            if is_available:
                available_items += 1

            material_status.append({
                "item_code": bom_item.item_code,
                "item_name": bom_item.item_name,
                "description": bom_item.description or "",
                "required_qty": required_qty,
                "available_qty": available_qty,
                "shortage": max(0, required_qty - available_qty),
                "warehouse": bom_item.source_warehouse or "",
                "status": "Available" if is_available else "Shortage"
            })

        # Calculate completion percentage
        completion_percentage = (available_items / total_items * 100) if total_items > 0 else 0

        # Determine zone status
        if completion_percentage >= 100:
            zone_status = "Green Zone"
        elif completion_percentage >= 50:
            zone_status = "Yellow Zone"
        else:
            zone_status = "Red Zone"

        return {
            "status": "success",
            "zone_status": zone_status,
            "completion_percentage": round(completion_percentage, 2),
            "material_status": material_status,
            "work_order": work_order,
            "item_count": total_items,
            "available_count": available_items
        }

    except frappe.DoesNotExistError:
        return {
            "status": "error",
            "message": f"Work Order '{work_order}' not found"
        }
    except Exception as e:
        frappe.log_error(
            f"get_material_status API error for {work_order}: {str(e)}",
            "RND Warehouse API Error"
        )
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist()
def get_work_order_summary(work_order):
    """
    Get a summary of Work Order with material and production status.
    """
    try:
        wo = frappe.get_doc("Work Order", work_order)

        summary = {
            "work_order": work_order,
            "production_item": wo.production_item,
            "qty": wo.qty,
            "status": wo.status,
            "produced_qty": wo.produced_qty or 0,
            "bom_no": wo.bom_no,
            "warehouse": wo.fg_warehouse,
        }

        # Get material status if BOM exists
        if wo.bom_no:
            material_data = get_material_status(work_order)
            summary["material_status"] = material_data.get("zone_status", "Unknown")
            summary["completion_percentage"] = material_data.get("completion_percentage", 0)
        else:
            summary["material_status"] = "No BOM"
            summary["completion_percentage"] = 0

        return summary

    except Exception as e:
        return {"status": "error", "message": str(e)}