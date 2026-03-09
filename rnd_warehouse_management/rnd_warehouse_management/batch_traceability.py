
# batch_traceability.py - Phase 5.5: Batch Traceability & Quality Chain
"""Phase 5.5: Batch Traceability & Quality Chain
Batch genealogy, CoA generation, hold/release workflow, traceability reports."""
import frappe
from frappe import _
from frappe.utils import now_datetime, nowdate, getdate
import json


# =============================================================================
# BATCH GENEALOGY - Parent/child batch tracking through manufacturing
# =============================================================================

@frappe.whitelist()
def get_batch_genealogy(batch_id):
    """Trace a batch backwards through all manufacturing steps.
    Returns tree of parent batches, QI results, and stock entries."""
    if not frappe.db.exists("Batch", batch_id):
        frappe.throw(_("Batch {0} not found").format(batch_id))
    
    batch = frappe.get_doc("Batch", batch_id)
    tree = _build_genealogy_node(batch_id, depth=0, max_depth=10)
    return tree


def _build_genealogy_node(batch_id, depth=0, max_depth=10):
    """Recursively build genealogy tree for a batch."""
    if depth > max_depth:
        return {"batch_id": batch_id, "truncated": True}
    
    batch = frappe.db.get_value(
        "Batch", batch_id,
        ["name", "item", "batch_qty", "expiry_date", "manufacturing_date",
         "custom_parent_batch", "custom_quality_status"],
        as_dict=True
    )
    if not batch:
        return {"batch_id": batch_id, "error": "not found"}
    
    node = {
        "batch_id": batch.name,
        "item": batch.item,
        "batch_qty": batch.batch_qty,
        "expiry_date": str(batch.expiry_date) if batch.expiry_date else None,
        "manufacturing_date": str(batch.manufacturing_date) if batch.manufacturing_date else None,
        "quality_status": batch.get("custom_quality_status") or "Pending",
        "depth": depth,
        "children": [],
        "quality_inspections": [],
        "stock_entries": []
    }
    
    # Get QI records for this batch
    qis = frappe.db.get_all(
        "Quality Inspection",
        filters={"batch_no": batch_id},
        fields=["name", "status", "inspection_type", "inspected_by", "modified"],
        order_by="modified desc",
        limit=10
    )
    node["quality_inspections"] = qis
    
    # Get stock entries involving this batch
    sles = frappe.db.sql("""
        SELECT DISTINCT voucher_no, voucher_type, warehouse,
               posting_date, actual_qty
        FROM `tabStock Ledger Entry`
        WHERE batch_no = %s AND is_cancelled = 0
        ORDER BY posting_date DESC
        LIMIT 20
    """, batch_id, as_dict=True)
    node["stock_entries"] = sles
    
    # Find source batches (parent batch from manufacturing)
    if batch.get("custom_parent_batch"):
        parent_node = _build_genealogy_node(batch.custom_parent_batch, depth+1, max_depth)
        node["children"].append(parent_node)
    
    # Also find source batches from Stock Entry items (Material Transfer for Manufacture)
    source_batches = frappe.db.sql("""
        SELECT DISTINCT sed.batch_no
        FROM `tabStock Entry Detail` sed
        JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE se.purpose IN ("Manufacture", "Material Transfer for Manufacture")
        AND se.docstatus = 1
        AND sed.batch_no IS NOT NULL
        AND sed.batch_no != ""
        AND sed.batch_no != %s
        AND se.name IN (
            SELECT DISTINCT voucher_no
            FROM `tabStock Ledger Entry`
            WHERE batch_no = %s AND is_cancelled = 0 AND actual_qty > 0
        )
    """, (batch_id, batch_id), as_dict=True)
    
    for sb in source_batches:
        if sb.batch_no and sb.batch_no != batch_id:
            child_node = _build_genealogy_node(sb.batch_no, depth+1, max_depth)
            node["children"].append(child_node)
    
    return node


# =============================================================================
# CERTIFICATE OF ANALYSIS (CoA) GENERATION
# =============================================================================

@frappe.whitelist()
def generate_coa(batch_id):
    """Generate Certificate of Analysis data for a batch."""
    if not frappe.db.exists("Batch", batch_id):
        frappe.throw(_("Batch {0} not found").format(batch_id))
    
    batch = frappe.get_doc("Batch", batch_id)
    
    # Get all QI records
    qis = frappe.db.get_all(
        "Quality Inspection",
        filters={"batch_no": batch_id, "docstatus": 1},
        fields=["name", "status", "inspection_type", "inspected_by",
                "report_date", "item_code", "item_name"],
        order_by="report_date asc"
    )
    
    # Get inspection readings for each QI
    coa_parameters = []
    for qi in qis:
        readings = frappe.db.get_all(
            "Quality Inspection Reading",
            filters={"parent": qi.name},
            fields=["specification", "value", "min_value", "max_value",
                    "status", "formula_based_criteria"],
            order_by="idx"
        )
        for r in readings:
            r["qi_name"] = qi.name
            r["qi_status"] = qi.status
            coa_parameters.append(r)
    
    overall_status = "Passed"
    for qi in qis:
        if qi.status == "Rejected":
            overall_status = "Failed"
            break
    
    # Get item info
    item = frappe.db.get_value(
        "Item", batch.item,
        ["item_name", "item_group", "description"],
        as_dict=True
    ) or {}
    
    coa = {
        "batch_id": batch_id,
        "item_code": batch.item,
        "item_name": item.get("item_name", ""),
        "item_group": item.get("item_group", ""),
        "manufacturing_date": str(batch.manufacturing_date) if batch.manufacturing_date else None,
        "expiry_date": str(batch.expiry_date) if batch.expiry_date else None,
        "batch_qty": batch.batch_qty,
        "overall_status": overall_status,
        "quality_inspections": qis,
        "parameters": coa_parameters,
        "generated_on": str(now_datetime()),
        "generated_by": frappe.session.user
    }
    
    return coa


# =============================================================================
# BATCH HOLD/RELEASE WORKFLOW
# =============================================================================

@frappe.whitelist()
def hold_batch(batch_id, reason="", create_nc=True):
    """Place a batch on hold - move to quarantine zone, create NC."""
    if not frappe.db.exists("Batch", batch_id):
        frappe.throw(_("Batch {0} not found").format(batch_id))
    
    # Update batch status
    frappe.db.set_value("Batch", batch_id, "custom_quality_status", "On Hold")
    
    result = {
        "batch_id": batch_id,
        "status": "On Hold",
        "reason": reason,
        "timestamp": str(now_datetime()),
        "actions_taken": []
    }
    
    # Create Non-Conformity if requested
    if create_nc:
        try:
            nc_exists = frappe.db.exists("Non Conformance", {"custom_batch_reference": batch_id})
            if not nc_exists:
                # Check if doctype exists
                if frappe.db.exists("DocType", "Non Conformance"):
                    nc = frappe.get_doc({
                        "doctype": "Non Conformance",
                        "title": f"Batch Hold: {batch_id}",
                        "description": f"Batch {batch_id} placed on hold. Reason: {reason}",
                        "custom_batch_reference": batch_id,
                        "status": "Open"
                    })
                    nc.insert(ignore_permissions=True)
                    result["actions_taken"].append(f"NC created: {nc.name}")
                else:
                    result["actions_taken"].append("NC doctype not available - skipped")
            else:
                result["actions_taken"].append(f"NC already exists for batch")
        except Exception as e:
            result["actions_taken"].append(f"NC creation failed: {str(e)}")
    
    frappe.db.commit()
    return result


@frappe.whitelist()
def release_batch(batch_id):
    """Release a batch from hold - verify all QI passing, no open NCs."""
    if not frappe.db.exists("Batch", batch_id):
        frappe.throw(_("Batch {0} not found").format(batch_id))
    
    # Check for failed QIs
    failed_qis = frappe.db.count(
        "Quality Inspection",
        filters={"batch_no": batch_id, "status": "Rejected", "docstatus": 1}
    )
    
    # Check for open NCs
    open_ncs = 0
    if frappe.db.exists("DocType", "Non Conformance"):
        open_ncs = frappe.db.count(
            "Non Conformance",
            filters={"custom_batch_reference": batch_id, "status": ["!=", "Closed"]}
        )
    
    can_release = failed_qis == 0 and open_ncs == 0
    
    result = {
        "batch_id": batch_id,
        "can_release": can_release,
        "failed_qis": failed_qis,
        "open_ncs": open_ncs,
        "timestamp": str(now_datetime())
    }
    
    if can_release:
        frappe.db.set_value("Batch", batch_id, "custom_quality_status", "Passed")
        frappe.db.commit()
        result["status"] = "Released"
        result["message"] = "Batch released successfully - all QI passed, no open NCs"
    else:
        blockers = []
        if failed_qis:
            blockers.append(f"{failed_qis} failed Quality Inspection(s)")
        if open_ncs:
            blockers.append(f"{open_ncs} open Non-Conformance(s)")
        result["status"] = "Blocked"
        result["message"] = f"Cannot release: {', '.join(blockers)}"
    
    return result


# =============================================================================
# TRACEABILITY REPORT
# =============================================================================

@frappe.whitelist()
def get_full_traceability(batch_id):
    """Complete traceability report for a batch."""
    genealogy = get_batch_genealogy(batch_id)
    coa = generate_coa(batch_id)
    
    # Get current locations
    locations = frappe.db.sql("""
        SELECT warehouse, SUM(actual_qty) as qty
        FROM `tabStock Ledger Entry`
        WHERE batch_no = %s AND is_cancelled = 0
        GROUP BY warehouse
        HAVING SUM(actual_qty) > 0
    """, batch_id, as_dict=True)
    
    return {
        "batch_id": batch_id,
        "genealogy": genealogy,
        "certificate_of_analysis": coa,
        "current_locations": locations,
        "generated_on": str(now_datetime())
    }


print("batch_traceability.py loaded")
