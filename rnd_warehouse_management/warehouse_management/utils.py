"""
RND Warehouse Management Utility Functions
==========================================

Implementation of the missing warehouse management functions for the existing
RND Warehouse Management ERPNext app.

Functions:
- get_material_assessment_status: Material availability assessment for production
- get_inventory_turnover: Inventory turnover analysis and optimization
- get_stock_aging_report: Stock aging analysis for warehouse management
- get_reorder_suggestions: Intelligent reorder recommendations

Author: MiniMax Agent
Date: 2025-01-08
Integration: RND Warehouse Management v1.0
"""

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, flt, cint, add_days, date_diff, getdate
from datetime import datetime, timedelta
import json

# ===================================================================
# 1. MATERIAL ASSESSMENT STATUS
# ===================================================================

@frappe.whitelist()
def get_material_assessment_status(material_code):
    """
    Get comprehensive material assessment status for Red Zone/Green Zone management.
    
    Args:
        material_code (str): Item code to assess
        
    Returns:
        dict: Complete material assessment including zone status, availability, and work order impacts
    """
    try:
        # Validate item exists
        if not frappe.db.exists("Item", material_code):
            return {"status": "error", "message": f"Item {material_code} does not exist"}
        
        # Get item details
        item = frappe.get_doc("Item", material_code)
        
        # Calculate total available quantity across all warehouses
        total_available = frappe.db.sql("""
            SELECT 
                COALESCE(SUM(actual_qty), 0) as total_qty,
                COALESCE(SUM(reserved_qty), 0) as reserved_qty
            FROM `tabBin`
            WHERE item_code = %s
        """, (material_code,), as_dict=True)[0]
        
        # Get active work orders requiring this material
        work_orders_data = frappe.db.sql("""
            SELECT 
                wo.name as work_order,
                wo.qty as wo_qty,
                wo.custom_current_zone_status,
                wo.custom_material_completion_percentage,
                bi.qty as required_qty_per_unit,
                (bi.qty * wo.qty) as total_required_qty
            FROM `tabWork Order` wo
            INNER JOIN `tabBOM Item` bi ON bi.parent = wo.bom_no
            WHERE wo.docstatus = 1 
                AND wo.status IN ('Not Started', 'In Process')
                AND bi.item_code = %s
            ORDER BY wo.planned_start_date
        """, (material_code,), as_dict=True)
        
        # Calculate total requirements
        total_requirement = sum(wo.total_required_qty for wo in work_orders_data)
        available_qty = flt(total_available.total_qty)
        reserved_qty = flt(total_available.reserved_qty)
        free_qty = available_qty - reserved_qty
        
        # Determine status and zone
        if free_qty >= total_requirement:
            status = "Available"
            zone_status = "Green Zone"
            completion_percentage = 100
        elif free_qty > 0:
            status = "Shortage"
            zone_status = "Red Zone"
            completion_percentage = (free_qty / total_requirement) * 100 if total_requirement > 0 else 0
        elif available_qty > 0:
            status = "Critical"
            zone_status = "Red Zone"
            completion_percentage = 0
        else:
            status = "Unavailable"
            zone_status = "Red Zone"
            completion_percentage = 0
        
        # Build work orders affected list
        work_orders_affected = []
        remaining_free_qty = free_qty
        
        for wo in work_orders_data:
            shortage = max(0, wo.total_required_qty - max(0, remaining_free_qty))
            remaining_free_qty = max(0, remaining_free_qty - wo.total_required_qty)
            
            work_orders_affected.append({
                "work_order": wo.work_order,
                "required_qty": wo.total_required_qty,
                "shortage": shortage,
                "zone_status": wo.custom_current_zone_status,
                "completion_percentage": wo.custom_material_completion_percentage
            })
        
        # Get last assessment time from Material Assessment Log
        last_assessment = frappe.db.get_value(
            "Material Assessment Log", 
            {"item_code": material_code}, 
            "assessment_date", 
            order_by="creation desc"
        )
        
        return {
            "status": "success",
            "material_code": material_code,
            "item_name": item.item_name,
            "assessment_status": status,
            "zone_status": zone_status,
            "available_qty": available_qty,
            "reserved_qty": reserved_qty,
            "free_qty": free_qty,
            "total_requirement": total_requirement,
            "completion_percentage": round(completion_percentage, 2),
            "last_assessment": last_assessment or now_datetime(),
            "work_orders_affected": work_orders_affected,
            "uom": item.stock_uom,
            "timestamp": now_datetime()
        }
        
    except Exception as e:
        frappe.log_error(f"Material assessment failed for {material_code}: {str(e)}")
        return {"status": "error", "message": str(e)}

# ===================================================================
# 2. INVENTORY TURNOVER ANALYSIS
# ===================================================================

@frappe.whitelist()
def get_inventory_turnover(warehouse, item_code=None, period_days=365):
    """
    Calculate inventory turnover ratios for optimization and performance analysis.
    
    Args:
        warehouse (str): Warehouse to analyze
        item_code (str, optional): Specific item, if None analyzes all items
        period_days (int): Analysis period in days (default: 365)
        
    Returns:
        dict: Turnover analysis with ratios, classifications, and recommendations
    """
    try:
        # Validate warehouse exists
        if not frappe.db.exists("Warehouse", warehouse):
            return {"status": "error", "message": f"Warehouse {warehouse} does not exist"}
        
        # Calculate date range
        to_date = getdate()
        from_date = add_days(to_date, -period_days)
        
        # Build item filter condition
        item_condition = ""
        if item_code:
            if not frappe.db.exists("Item", item_code):
                return {"status": "error", "message": f"Item {item_code} does not exist"}
            item_condition = f"AND sle.item_code = '{item_code}'"
        
        # Calculate COGS and average inventory from Stock Ledger Entries
        turnover_data = frappe.db.sql(f"""
            SELECT 
                sle.item_code,
                i.item_name,
                SUM(CASE 
                    WHEN sle.actual_qty < 0 THEN ABS(sle.actual_qty * sle.valuation_rate)
                    ELSE 0 
                END) as cogs,
                AVG(CASE 
                    WHEN sle.qty_after_transaction > 0 THEN sle.qty_after_transaction * sle.valuation_rate
                    ELSE 0 
                END) as avg_inventory_value,
                AVG(CASE 
                    WHEN sle.qty_after_transaction > 0 THEN sle.qty_after_transaction
                    ELSE 0 
                END) as avg_inventory_qty,
                COUNT(*) as transaction_count
            FROM `tabStock Ledger Entry` sle
            INNER JOIN `tabItem` i ON i.name = sle.item_code
            WHERE sle.warehouse = %s
                AND sle.posting_date BETWEEN %s AND %s
                AND sle.is_cancelled = 0
                {item_condition}
            GROUP BY sle.item_code, i.item_name
            HAVING cogs > 0 AND avg_inventory_value > 0
            ORDER BY cogs DESC
        """, (warehouse, from_date, to_date), as_dict=True)
        
        if not turnover_data:
            return {
                "status": "no_data",
                "message": "No inventory movements found for the specified period",
                "warehouse": warehouse,
                "item_code": item_code,
                "period_days": period_days,
                "from_date": from_date,
                "to_date": to_date
            }
        
        # Calculate turnover metrics for each item
        turnover_results = []
        total_turnover = 0
        
        for item_data in turnover_data:
            turnover_ratio = item_data.cogs / item_data.avg_inventory_value
            days_in_inventory = period_days / turnover_ratio if turnover_ratio > 0 else float('inf')
            
            # Classify based on turnover ratio (industry benchmarks)
            if turnover_ratio >= 6:
                classification = "Fast Moving"
            elif turnover_ratio >= 3:
                classification = "Normal"
            elif turnover_ratio >= 1:
                classification = "Slow Moving"
            else:
                classification = "Dead Stock"
            
            # Generate recommendations
            recommendations = []
            if turnover_ratio < 2:
                recommendations.extend([
                    "Consider reducing reorder quantity",
                    "Review demand forecasting",
                    "Evaluate supplier alternatives"
                ])
            elif turnover_ratio > 8:
                recommendations.extend([
                    "Consider increasing safety stock",
                    "Review supplier lead times",
                    "Optimize reorder frequency"
                ])
            
            item_result = {
                "item_code": item_data.item_code,
                "item_name": item_data.item_name,
                "turnover_ratio": round(turnover_ratio, 2),
                "average_inventory_qty": round(item_data.avg_inventory_qty, 2),
                "average_inventory_value": round(item_data.avg_inventory_value, 2),
                "cogs": round(item_data.cogs, 2),
                "days_in_inventory": round(days_in_inventory, 1) if days_in_inventory != float('inf') else 0,
                "classification": classification,
                "transaction_count": item_data.transaction_count,
                "recommendations": recommendations
            }
            
            turnover_results.append(item_result)
            total_turnover += turnover_ratio
        
        # Calculate overall metrics
        avg_turnover = total_turnover / len(turnover_results) if turnover_results else 0
        
        # Industry benchmark comparison
        industry_average = 4.5  # Configurable benchmark
        performance = "Above Average" if avg_turnover > industry_average else "Below Average"
        
        # Summary statistics
        summary_stats = {
            "fast_moving": len([i for i in turnover_results if i["classification"] == "Fast Moving"]),
            "normal": len([i for i in turnover_results if i["classification"] == "Normal"]),
            "slow_moving": len([i for i in turnover_results if i["classification"] == "Slow Moving"]),
            "dead_stock": len([i for i in turnover_results if i["classification"] == "Dead Stock"])
        }
        
        result = {
            "status": "success",
            "warehouse": warehouse,
            "item_code": item_code,
            "period_days": period_days,
            "analysis_date": to_date,
            "from_date": from_date,
            "to_date": to_date,
            "average_turnover_ratio": round(avg_turnover, 2),
            "benchmark_comparison": {
                "industry_average": industry_average,
                "performance": performance,
                "variance": round(avg_turnover - industry_average, 2)
            },
            "total_items_analyzed": len(turnover_results),
            "items": turnover_results if item_code else turnover_results[:50],  # Limit for performance
            "summary": summary_stats,
            "timestamp": now_datetime()
        }
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Inventory turnover calculation failed: {str(e)}")
        return {"status": "error", "message": str(e)}

# ===================================================================
# 3. STOCK AGING REPORT
# ===================================================================

@frappe.whitelist()
def get_stock_aging_report(warehouse, days_threshold=30):
    """
    Generate comprehensive stock aging analysis for warehouse management.
    
    Args:
        warehouse (str): Warehouse to analyze
        days_threshold (int): Days for aging categories (default: 30)
        
    Returns:
        dict: Detailed aging report with categories, values, and recommendations
    """
    try:
        # Validate warehouse exists
        if not frappe.db.exists("Warehouse", warehouse):
            return {"status": "error", "message": f"Warehouse {warehouse} does not exist"}
        
        current_date = getdate()
        
        # Get current stock with first receipt dates and batch information
        aging_data = frappe.db.sql("""
            SELECT 
                b.item_code,
                i.item_name,
                i.item_group,
                b.actual_qty,
                b.valuation_rate,
                (b.actual_qty * b.valuation_rate) as total_value,
                COALESCE(first_receipt.first_receipt_date, CURDATE()) as first_receipt_date,
                COALESCE(latest_receipt.latest_receipt_date, CURDATE()) as latest_receipt_date,
                batch_info.batch_no,
                batch_info.batch_expiry,
                COALESCE(DATEDIFF(CURDATE(), first_receipt.first_receipt_date), 0) as aging_days
            FROM `tabBin` b
            INNER JOIN `tabItem` i ON i.name = b.item_code
            LEFT JOIN (
                SELECT 
                    item_code,
                    warehouse,
                    MIN(posting_date) as first_receipt_date
                FROM `tabStock Ledger Entry`
                WHERE actual_qty > 0 AND is_cancelled = 0
                GROUP BY item_code, warehouse
            ) first_receipt ON first_receipt.item_code = b.item_code 
                AND first_receipt.warehouse = b.warehouse
            LEFT JOIN (
                SELECT 
                    item_code,
                    warehouse,
                    MAX(posting_date) as latest_receipt_date
                FROM `tabStock Ledger Entry`
                WHERE actual_qty > 0 AND is_cancelled = 0
                GROUP BY item_code, warehouse
            ) latest_receipt ON latest_receipt.item_code = b.item_code 
                AND latest_receipt.warehouse = b.warehouse
            LEFT JOIN (
                SELECT DISTINCT
                    sle.item_code,
                    sle.warehouse,
                    batch.name as batch_no,
                    batch.expiry_date as batch_expiry
                FROM `tabStock Ledger Entry` sle
                INNER JOIN `tabBatch` batch ON batch.name = sle.batch_no
                WHERE sle.actual_qty > 0 AND sle.is_cancelled = 0
                GROUP BY sle.item_code, sle.warehouse, batch.name
            ) batch_info ON batch_info.item_code = b.item_code 
                AND batch_info.warehouse = b.warehouse
            WHERE b.warehouse = %s
                AND b.actual_qty > 0
            ORDER BY aging_days DESC, b.item_code
        """, (warehouse,), as_dict=True)
        
        if not aging_data:
            return {
                "status": "no_data",
                "message": "No stock found in the specified warehouse",
                "warehouse": warehouse,
                "analysis_date": current_date
            }
        
        # Define aging categories
        aging_categories = {
            f"0-{days_threshold}": {"value": 0, "percentage": 0, "items": 0, "qty": 0},
            f"{days_threshold+1}-{days_threshold*2}": {"value": 0, "percentage": 0, "items": 0, "qty": 0},
            f"{days_threshold*2+1}-{days_threshold*3}": {"value": 0, "percentage": 0, "items": 0, "qty": 0},
            f"{days_threshold*3+1}-{days_threshold*6}": {"value": 0, "percentage": 0, "items": 0, "qty": 0},
            f"{days_threshold*6+1}+": {"value": 0, "percentage": 0, "items": 0, "qty": 0}
        }
        
        detailed_items = []
        total_value = 0
        
        for item in aging_data:
            aging_days = item.aging_days
            
            # Determine aging category and action required
            if aging_days <= days_threshold:
                category = f"0-{days_threshold}"
                action_required = "Monitor"
            elif aging_days <= days_threshold * 2:
                category = f"{days_threshold+1}-{days_threshold*2}"
                action_required = "Monitor"
            elif aging_days <= days_threshold * 3:
                category = f"{days_threshold*2+1}-{days_threshold*3}"
                action_required = "Review"
            elif aging_days <= days_threshold * 6:
                category = f"{days_threshold*3+1}-{days_threshold*6}"
                action_required = "Liquidate"
            else:
                category = f"{days_threshold*6+1}+"
                action_required = "Dispose"
            
            # Update category totals
            aging_categories[category]["value"] += item.total_value
            aging_categories[category]["items"] += 1
            aging_categories[category]["qty"] += item.actual_qty
            total_value += item.total_value
            
            # Check for expiry concerns
            expiry_concern = False
            if item.batch_expiry:
                days_to_expiry = date_diff(item.batch_expiry, current_date)
                if days_to_expiry <= 30:
                    expiry_concern = True
                    action_required = "Urgent - Near Expiry"
            
            # Add to detailed items
            detailed_items.append({
                "item_code": item.item_code,
                "item_name": item.item_name,
                "item_group": item.item_group,
                "batch_no": item.batch_no,
                "qty": item.actual_qty,
                "valuation_rate": item.valuation_rate,
                "total_value": round(item.total_value, 2),
                "aging_days": aging_days,
                "category": category,
                "first_receipt_date": item.first_receipt_date,
                "latest_receipt_date": item.latest_receipt_date,
                "batch_expiry": item.batch_expiry,
                "expiry_concern": expiry_concern,
                "action_required": action_required
            })
        
        # Calculate percentages
        for category in aging_categories.values():
            category["percentage"] = round((category["value"] / total_value) * 100, 2) if total_value > 0 else 0
        
        # Generate recommendations
        recommendations = []
        old_stock_value = aging_categories[f"{days_threshold*3+1}-{days_threshold*6}"]["value"] + \
                         aging_categories[f"{days_threshold*6+1}+"]["value"]
        
        if old_stock_value > 0:
            old_percentage = (old_stock_value / total_value) * 100
            recommendations.append(f"Review items aged over {days_threshold*3} days ({old_percentage:.1f}% of total value)")
        
        very_old_items = aging_categories[f"{days_threshold*6+1}+"]["items"]
        if very_old_items > 0:
            recommendations.append(f"Consider disposal of {very_old_items} very old items (aged over {days_threshold*6} days)")
        
        slow_moving_value = aging_categories[f"{days_threshold*2+1}-{days_threshold*3}"]["value"]
        if slow_moving_value > total_value * 0.2:
            recommendations.append("Consider promotional activities for slow-moving items")
        
        # Count items with expiry concerns
        expiry_items = len([item for item in detailed_items if item["expiry_concern"]])
        if expiry_items > 0:
            recommendations.append(f"Urgent: {expiry_items} items approaching expiry date")
        
        return {
            "status": "success",
            "warehouse": warehouse,
            "analysis_date": current_date,
            "days_threshold": days_threshold,
            "total_value": round(total_value, 2),
            "total_items": len(detailed_items),
            "aging_categories": aging_categories,
            "detailed_items": detailed_items,
            "recommendations": recommendations,
            "summary": {
                "total_items_over_90_days": sum(1 for item in detailed_items if item["aging_days"] > 90),
                "total_value_over_90_days": round(sum(item["total_value"] for item in detailed_items if item["aging_days"] > 90), 2),
                "items_with_expiry_concern": expiry_items,
                "action_required_items": {
                    "monitor": len([item for item in detailed_items if item["action_required"] == "Monitor"]),
                    "review": len([item for item in detailed_items if item["action_required"] == "Review"]),
                    "liquidate": len([item for item in detailed_items if item["action_required"] == "Liquidate"]),
                    "dispose": len([item for item in detailed_items if item["action_required"] == "Dispose"]),
                    "urgent_expiry": len([item for item in detailed_items if "Urgent" in item["action_required"]])
                }
            },
            "timestamp": now_datetime()
        }
        
    except Exception as e:
        frappe.log_error(f"Stock aging report failed for {warehouse}: {str(e)}")
        return {"status": "error", "message": str(e)}

# ===================================================================
# 4. REORDER SUGGESTIONS
# ===================================================================

@frappe.whitelist()
def get_reorder_suggestions(warehouse):
    """
    Generate intelligent reorder suggestions based on consumption patterns and reorder levels.
    
    Args:
        warehouse (str): Warehouse to analyze for reorder suggestions
        
    Returns:
        dict: Comprehensive reorder suggestions with priorities and calculations
    """
    try:
        # Validate warehouse exists
        if not frappe.db.exists("Warehouse", warehouse):
            return {"status": "error", "message": f"Warehouse {warehouse} does not exist"}
        
        current_date = getdate()
        
        # Get items with reorder levels set for this warehouse
        items_with_reorder = frappe.db.sql("""
            SELECT DISTINCT
                ir.parent as item_code,
                i.item_name,
                i.item_group,
                ir.warehouse_reorder_level as reorder_level,
                ir.warehouse_reorder_qty as reorder_qty,
                ir.material_request_type,
                COALESCE(b.actual_qty, 0) as current_stock,
                COALESCE(b.reserved_qty, 0) as reserved_qty,
                COALESCE(i.safety_stock, 0) as safety_stock,
                COALESCE(i.lead_time_days, 7) as lead_time_days,
                COALESCE(i.min_order_qty, 0) as min_order_qty,
                COALESCE(i.max_order_qty, 0) as max_order_qty,
                i.stock_uom,
                supplier.supplier_name,
                supplier.last_purchase_rate
            FROM `tabItem Reorder` ir
            INNER JOIN `tabItem` i ON i.name = ir.parent
            LEFT JOIN `tabBin` b ON b.item_code = ir.parent AND b.warehouse = ir.warehouse
            LEFT JOIN (
                SELECT 
                    poi.item_code,
                    s.supplier_name,
                    poi.rate as last_purchase_rate,
                    ROW_NUMBER() OVER (PARTITION BY poi.item_code ORDER BY po.transaction_date DESC) as rn
                FROM `tabPurchase Order Item` poi
                INNER JOIN `tabPurchase Order` po ON po.name = poi.parent
                INNER JOIN `tabSupplier` s ON s.name = po.supplier
                WHERE po.docstatus = 1
            ) supplier ON supplier.item_code = ir.parent AND supplier.rn = 1
            WHERE ir.warehouse = %s
                AND i.disabled = 0
                AND i.is_stock_item = 1
            ORDER BY ir.parent
        """, (warehouse,), as_dict=True)
        
        if not items_with_reorder:
            return {
                "status": "no_reorder_levels",
                "message": "No items found with reorder levels set for this warehouse",
                "warehouse": warehouse,
                "analysis_date": current_date
            }
        
        suggestions = []
        summary = {"high_priority": 0, "medium_priority": 0, "low_priority": 0, "total_order_value": 0}
        
        for item in items_with_reorder:
            # Calculate consumption over last 30 days
            consumption_data = frappe.db.sql("""
                SELECT 
                    COALESCE(SUM(ABS(actual_qty)), 0) as total_consumed,
                    COUNT(DISTINCT posting_date) as active_days
                FROM `tabStock Ledger Entry`
                WHERE item_code = %s
                    AND warehouse = %s
                    AND actual_qty < 0
                    AND posting_date >= %s
                    AND is_cancelled = 0
            """, (item.item_code, warehouse, add_days(current_date, -30)), as_dict=True)[0]
            
            # Calculate average daily consumption
            total_consumed = consumption_data.total_consumed or 0
            avg_daily_consumption = (total_consumed / 30) if total_consumed > 0 else 0
            
            # Get pending purchase order quantities
            pending_po_qty = frappe.db.sql("""
                SELECT COALESCE(SUM(poi.qty - poi.received_qty), 0) as pending_qty
                FROM `tabPurchase Order Item` poi
                INNER JOIN `tabPurchase Order` po ON po.name = poi.parent
                WHERE poi.item_code = %s
                    AND po.docstatus = 1
                    AND po.status IN ('To Receive', 'To Bill', 'To Receive and Bill')
                    AND poi.qty > poi.received_qty
            """, (item.item_code,), as_dict=True)[0].pending_qty or 0
            
            # Calculate stock projections
            free_stock = item.current_stock - item.reserved_qty
            projected_stock = free_stock + pending_po_qty
            
            # Calculate days of stock remaining
            days_of_stock = (projected_stock / avg_daily_consumption) if avg_daily_consumption > 0 else float('inf')
            
            # Determine if reorder is needed
            lead_time_days = item.lead_time_days
            safety_stock = item.safety_stock
            
            # Calculate effective reorder point
            calculated_reorder_point = (avg_daily_consumption * lead_time_days) + safety_stock
            effective_reorder_level = max(item.reorder_level or 0, calculated_reorder_point)
            
            if projected_stock <= effective_reorder_level:
                # Calculate suggested order quantity
                target_coverage_days = lead_time_days * 2  # 2x lead time coverage
                target_stock = (avg_daily_consumption * target_coverage_days) + safety_stock
                suggested_qty = max(target_stock - projected_stock, item.min_order_qty or 1)
                
                # Apply min/max order quantity constraints
                if item.max_order_qty and suggested_qty > item.max_order_qty:
                    suggested_qty = item.max_order_qty
                if item.min_order_qty and suggested_qty < item.min_order_qty:
                    suggested_qty = item.min_order_qty
                
                # Use configured reorder qty if available
                if item.reorder_qty and item.reorder_qty > suggested_qty:
                    suggested_qty = item.reorder_qty
                
                # Determine urgency and reason
                if projected_stock <= 0:
                    urgency = "High"
                    reason = "Out of stock"
                    summary["high_priority"] += 1
                elif days_of_stock <= lead_time_days:
                    urgency = "High"
                    reason = "Stock will run out before next delivery"
                    summary["high_priority"] += 1
                elif days_of_stock <= lead_time_days * 1.5:
                    urgency = "Medium"
                    reason = "Approaching reorder level"
                    summary["medium_priority"] += 1
                else:
                    urgency = "Low"
                    reason = "Below reorder level"
                    summary["low_priority"] += 1
                
                # Calculate order value
                last_rate = item.last_purchase_rate or 0
                order_value = suggested_qty * last_rate
                summary["total_order_value"] += order_value
                
                suggestion = {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "item_group": item.item_group,
                    "current_stock": item.current_stock,
                    "reserved_qty": item.reserved_qty,
                    "free_stock": free_stock,
                    "reorder_level": effective_reorder_level,
                    "configured_reorder_level": item.reorder_level,
                    "calculated_reorder_level": round(calculated_reorder_point, 2),
                    "reorder_qty": item.reorder_qty,
                    "projected_stock": projected_stock,
                    "days_of_stock": round(days_of_stock, 1) if days_of_stock != float('inf') else 0,
                    "avg_daily_consumption": round(avg_daily_consumption, 2),
                    "consumption_last_30_days": total_consumed,
                    "lead_time_days": lead_time_days,
                    "safety_stock": safety_stock,
                    "suggested_order_qty": round(suggested_qty, 2),
                    "urgency": urgency,
                    "reason": reason,
                    "supplier": item.supplier_name or "Not Set",
                    "last_purchase_rate": last_rate,
                    "estimated_order_value": round(order_value, 2),
                    "pending_po_qty": pending_po_qty,
                    "material_request_type": item.material_request_type or "Purchase",
                    "stock_uom": item.stock_uom
                }
                
                suggestions.append(suggestion)
        
        # Sort suggestions by urgency and then by days of stock
        urgency_order = {"High": 1, "Medium": 2, "Low": 3}
        suggestions.sort(key=lambda x: (urgency_order[x["urgency"]], x["days_of_stock"]))
        
        # Generate next actions
        next_actions = []
        if summary["high_priority"] > 0:
            next_actions.append(f"Create {summary['high_priority']} high-priority material requests")
        if summary["medium_priority"] > 0:
            next_actions.append(f"Review {summary['medium_priority']} medium-priority items")
        if summary["low_priority"] > 0:
            next_actions.append(f"Monitor {summary['low_priority']} low-priority items")
        
        return {
            "status": "success",
            "warehouse": warehouse,
            "analysis_date": current_date,
            "total_items_analyzed": len(items_with_reorder),
            "reorder_required": len(suggestions),
            "suggestions": suggestions,
            "summary": {
                "high_priority": summary["high_priority"],
                "medium_priority": summary["medium_priority"],
                "low_priority": summary["low_priority"],
                "total_order_value": round(summary["total_order_value"], 2)
            },
            "next_actions": next_actions,
            "timestamp": now_datetime()
        }
        
    except Exception as e:
        frappe.log_error(f"Reorder suggestions failed for {warehouse}: {str(e)}")
        return {"status": "error", "message": str(e)}

# ===================================================================
# HELPER FUNCTIONS AND DASHBOARD
# ===================================================================

def create_material_assessment_log(item_code, work_order=None, assessment_data=None):
    """Create a material assessment log entry"""
    try:
        # Check if Material Assessment Log DocType exists
        if not frappe.db.exists("DocType", "Material Assessment Log"):
            frappe.log_error("Material Assessment Log DocType not found")
            return None
            
        log_doc = frappe.get_doc({
            "doctype": "Material Assessment Log",
            "item_code": item_code,
            "work_order": work_order,
            "assessment_date": now_datetime(),
            "zone_status": assessment_data.get("zone_status") if assessment_data else "Red Zone",
            "completion_percentage": assessment_data.get("completion_percentage", 0) if assessment_data else 0,
            "assessed_by": frappe.session.user,
            "assessment_details": frappe.as_json(assessment_data) if assessment_data else None
        })
        log_doc.insert(ignore_permissions=True)
        return log_doc.name
    except Exception as e:
        frappe.log_error(f"Failed to create material assessment log: {str(e)}")
        return None

@frappe.whitelist()
def get_warehouse_summary_dashboard(warehouse):
    """Get comprehensive warehouse dashboard summary"""
    try:
        result = {
            "warehouse": warehouse,
            "last_updated": now_datetime(),
            "summary": {
                "total_items": 0,
                "total_value": 0,
                "total_qty": 0
            },
            "material_assessment": {
                "total_items": 0, 
                "red_zone": 0, 
                "green_zone": 0,
                "critical_items": 0
            },
            "turnover_summary": {
                "avg_turnover": 0, 
                "fast_moving": 0, 
                "slow_moving": 0,
                "dead_stock": 0
            },
            "aging_summary": {
                "total_value": 0, 
                "old_stock_percentage": 0,
                "items_over_90_days": 0
            },
            "reorder_summary": {
                "items_to_reorder": 0, 
                "high_priority": 0,
                "total_order_value": 0
            }
        }
        
        # Get basic warehouse statistics
        bin_data = frappe.db.sql("""
            SELECT 
                COUNT(*) as total_items,
                SUM(actual_qty * valuation_rate) as total_value,
                SUM(actual_qty) as total_qty
            FROM `tabBin`
            WHERE warehouse = %s AND actual_qty > 0
        """, (warehouse,), as_dict=True)[0]
        
        result["summary"]["total_items"] = bin_data.total_items or 0
        result["summary"]["total_value"] = round(bin_data.total_value or 0, 2)
        result["summary"]["total_qty"] = round(bin_data.total_qty or 0, 2)
        
        # Get Work Order zone status summary
        zone_data = frappe.db.sql("""
            SELECT 
                custom_current_zone_status,
                COUNT(*) as count
            FROM `tabWork Order`
            WHERE status NOT IN ('Completed', 'Cancelled', 'Stopped')
                AND custom_current_zone_status IS NOT NULL
            GROUP BY custom_current_zone_status
        """, as_dict=True)
        
        for zone in zone_data:
            if zone.custom_current_zone_status == "Red Zone":
                result["material_assessment"]["red_zone"] = zone.count
            elif zone.custom_current_zone_status == "Green Zone":
                result["material_assessment"]["green_zone"] = zone.count
        
        result["material_assessment"]["total_items"] = result["material_assessment"]["red_zone"] + result["material_assessment"]["green_zone"]
        
        return result
        
    except Exception as e:
        frappe.log_error(f"Warehouse dashboard summary failed: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def batch_update_material_assessments(warehouse=None):
    """Batch update material assessments for multiple items"""
    try:
        # Get all active work orders
        filters = {"status": ["not in", ["Completed", "Stopped", "Cancelled"]]}
        if warehouse:
            # Get work orders that use materials from this warehouse
            filters["bom_no"] = ["!=", ""]
        
        work_orders = frappe.get_all("Work Order", filters=filters, fields=["name", "bom_no"])
        
        updated_count = 0
        for wo in work_orders:
            if wo.bom_no:
                # Get BOM items
                bom_items = frappe.get_all("BOM Item", filters={"parent": wo.bom_no}, fields=["item_code"])
                
                for bom_item in bom_items:
                    # Update material assessment for each item
                    assessment = get_material_assessment_status(bom_item.item_code)
                    if assessment.get("status") == "success":
                        updated_count += 1
        
        return {
            "status": "success",
            "message": f"Updated material assessments for {updated_count} items",
            "updated_count": updated_count,
            "timestamp": now_datetime()
        }
        
    except Exception as e:
        frappe.log_error(f"Batch material assessment update failed: {str(e)}")
        return {"status": "error", "message": str(e)}

# ===================================================================
# JINJA TEMPLATE HELPER FUNCTIONS (for Print Formats)
# ===================================================================

def get_signature_image(doc, field_name):
    """
    Get signature image URL from document field for use in Print Formats.
    
    Args:
        doc: The document object
        field_name (str): Field name containing the signature image URL
        
    Returns:
        str: Signature image URL or empty string
    """
    try:
        if hasattr(doc, field_name):
            signature_url = getattr(doc, field_name)
            return signature_url or ""
        return ""
    except Exception as e:
        frappe.log_error(f"Error retrieving signature image: {str(e)}")
        return ""

def format_sap_movement_type(movement_type):
    """
    Format SAP movement type code with description for display in templates.
    
    Args:
        movement_type (str): SAP movement type code (e.g., '261', '311')
        
    Returns:
        str: Formatted movement type with description
    """
    try:
        if not movement_type:
            return ""
        
        # Get movement type details from Movement Type Master
        movement_doc = frappe.db.get_value(
            "Movement Type Master",
            {"movement_code": movement_type},
            ["movement_code", "movement_description", "short_text"],
            as_dict=True
        )
        
        if movement_doc:
            return f"{movement_doc.movement_code} - {movement_doc.short_text or movement_doc.movement_description}"
        
        # Fallback for common movement types
        common_types = {
            "261": "261 - FrontFlush (Goods Issue for Production)",
            "311": "311 - BackFlush (Transfer for Kitting)",
            "101": "101 - Goods Receipt",
            "201": "201 - Goods Issue",
            "301": "301 - Transfer Posting"
        }
        
        return common_types.get(movement_type, f"{movement_type} - SAP Movement")
        
    except Exception as e:
        frappe.log_error(f"Error formatting SAP movement type: {str(e)}")
        return movement_type or ""

def get_zone_status_badge(zone_status):
    """
    Generate HTML badge for zone status display in templates.
    
    Args:
        zone_status (str): Zone status ('Red Zone', 'Green Zone', etc.)
        
    Returns:
        str: HTML markup for zone status badge
    """
    try:
        if not zone_status:
            return ""
        
        # Determine badge color and icon
        if "Red" in zone_status or "red" in zone_status:
            color_class = "zone-red"
            bg_color = "#dc3545"
            icon = "⚠️"
        elif "Green" in zone_status or "green" in zone_status:
            color_class = "zone-green"
            bg_color = "#28a745"
            icon = "✓"
        else:
            color_class = "zone-default"
            bg_color = "#6c757d"
            icon = "•"
        
        # Generate HTML badge
        badge_html = f"""
        <span class='zone-status {color_class}' style='background-color: {bg_color}; color: white; padding: 5px 10px; border-radius: 3px; font-weight: bold; display: inline-block;'>
            {icon} {zone_status}
        </span>
        """
        
        return badge_html
        
    except Exception as e:
        frappe.log_error(f"Error generating zone status badge: {str(e)}")
        return zone_status or ""
