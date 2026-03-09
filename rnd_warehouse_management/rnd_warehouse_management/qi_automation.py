"""
Quality Inspection Automation for Phase 5.2
Auto-creates Quality Inspection on Stock Entry (Manufacture) submission
"""
import frappe
from frappe.utils import now_datetime, nowdate

def create_quality_inspection_on_manufacture(doc, method=None):
    """Auto-create Quality Inspection when a Manufacture Stock Entry is submitted"""
    # Only trigger for Manufacture purpose
    if doc.purpose != "Manufacture" and doc.stock_entry_type != "Manufacture":
        return
    
    # Get finished goods items from the stock entry
    for item in doc.items:
        # Only create QI for finished goods (items with target warehouse, positive qty)
        if not item.t_warehouse or item.is_finished_item != 1:
            continue
        
        # Check if item has a quality inspection template
        qi_template = frappe.db.get_value("Item", item.item_code, "quality_inspection_template")
        if not qi_template:
            continue
        
        try:
            # Get template parameters
            template_doc = frappe.get_doc("Quality Inspection Template", qi_template)
            
            # Create Quality Inspection
            qi = frappe.get_doc({
                "doctype": "Quality Inspection",
                "inspection_type": "In Process",
                "reference_type": "Stock Entry",
                "reference_name": doc.name,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "sample_size": 1,
                "inspected_by": frappe.session.user,
                "quality_inspection_template": qi_template,
                "batch_no": item.batch_no or "",
                "status": "Pending",
                "posting_date": nowdate(),
                "posting_time": now_datetime().strftime("%H:%M:%S"),
                "description": f"Auto-generated QI for {doc.name} - {item.item_code}"
            })
            
            # Copy readings from template
            if template_doc.item_quality_inspection_parameter:
                for param in template_doc.item_quality_inspection_parameter:
                    qi.append("readings", {
                        "specification": param.specification,
                        "value": "",
                        "min_value": param.min_value if hasattr(param, 'min_value') else 0,
                        "max_value": param.max_value if hasattr(param, 'max_value') else 0,
                        "status": "Pending"
                    })
            
            qi.insert(ignore_permissions=True)
            
            # Link QI back to Work Order if exists
            if doc.work_order:
                qi.db_set("custom_work_order", doc.work_order)
            
            frappe.msgprint(
                f"Quality Inspection {qi.name} auto-created for {item.item_code}",
                title="QI Auto-Created",
                indicator="blue"
            )
            
        except Exception as e:
            frappe.log_error(
                f"Failed to create QI for SE {doc.name}, Item {item.item_code}: {str(e)}",
                "QI Auto-Creation Error"
            )


def create_non_conformity_on_qi_failure(doc, method=None):
    """Auto-create Non-Conformity when Quality Inspection is rejected"""
    if doc.status != "Rejected":
        return
    
    # Check if NC already exists for this QI
    existing_nc = frappe.db.exists("Non Conformance", {"custom_quality_inspection": doc.name})
    if existing_nc:
        return
    
    try:
        # Get failed parameters
        failed_params = []
        if hasattr(doc, 'readings'):
            for reading in doc.readings:
                if reading.status == "Rejected":
                    failed_params.append(f"{reading.specification}: {reading.reading_1} (Range: {reading.min_value}-{reading.max_value})")
        
        nc = frappe.get_doc({
            "doctype": "Non Conformance",
            "title": f"QI Failure - {doc.item_code} - {doc.name}",
            "nc_type": "Product Non-Conformity",
            "description": f"Quality Inspection {doc.name} REJECTED for item {doc.item_code}.\n\nFailed Parameters:\n" + "\n".join(failed_params),
            "custom_quality_inspection": doc.name,
            "custom_batch_no": doc.batch_no or "",
            "custom_item_code": doc.item_code or "",
            "status": "Open"
        })
        nc.insert(ignore_permissions=True)
        
        frappe.msgprint(
            f"Non-Conformity {nc.name} auto-created for rejected QI {doc.name}",
            title="NC Auto-Created",
            indicator="red"
        )
        
    except Exception as e:
        frappe.log_error(
            f"Failed to create NC for QI {doc.name}: {str(e)}",
            "NC Auto-Creation Error"
        )
