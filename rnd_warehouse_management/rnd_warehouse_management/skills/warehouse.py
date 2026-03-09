
# skills/warehouse.py - Phase 5.4: Warehouse Intelligence Skill for Raven
"""Warehouse Intelligence Skill for raven_ai_agent.

Exposes tools to the LLM for warehouse-related questions:
1. get_item_stock_locations  - Where is item X?
2. get_kardex               - Stock ledger / Kardex view
3. get_oos_risk_list        - OOS now or at risk
4. get_warehouse_status     - Dashboard for a warehouse
5. get_work_order_zone_status - WO Red/Green zone + material readiness
6. get_warehouses_by_type   - List warehouses by type
7. get_zone_temperature_status - Zone temperature monitoring (Phase 5.3)
8. track_batch              - Batch location tracking
"""
from __future__ import unicode_literals
from typing import Any, Dict, List, Optional

import frappe


class WarehouseSkill:
    name = "warehouse"
    description = (
        "Answer questions about warehouses, inventory locations, stock movements, "
        "out-of-stock risk, work order material readiness, zone temperature monitoring, "
        "batch tracking, and warehouse dashboards."
    )

    # Module path prefix for API calls
    _API = "rnd_warehouse_management.rnd_warehouse_management.warehouse"
    _MON = "rnd_warehouse_management.rnd_warehouse_management.warehouse_monitoring"

    def get_tools(self) -> List[Dict[str, Any]]:
        """Return tool definitions in OpenAI function-calling format."""
        return [
            {
                "name": "get_item_stock_locations",
                "description": (
                    "Get current stock qty for an item across ALL warehouses. "
                    "Use when user asks where is item X or stock levels."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_code": {"type": "string", "description": "ERPNext Item code."}
                    },
                    "required": ["item_code"],
                },
            },
            {
                "name": "get_kardex",
                "description": (
                    "Get stock ledger entries (Kardex) for warehouse/item/date range. "
                    "Use for movement history or transaction queries."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "warehouse": {"type": "string", "description": "Warehouse name."},
                        "item_code": {"type": "string", "description": "Item code."},
                        "from_date": {"type": "string", "description": "Start date YYYY-MM-DD."},
                        "to_date": {"type": "string", "description": "End date YYYY-MM-DD."},
                        "limit": {"type": "integer", "description": "Max rows (default 500)."},
                    },
                    "required": [],
                },
            },
            {
                "name": "get_oos_risk_list",
                "description": (
                    "Get items that are OOS or at risk of stockout. "
                    "Returns OOS | AT_RISK | BELOW_REORDER status."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "company": {"type": "string", "description": "ERPNext Company."},
                        "warehouse": {"type": "string", "description": "Filter to warehouse."},
                        "lookback_days": {"type": "integer", "description": "Days of history (default 90)."},
                        "include_zero_demand": {"type": "boolean", "description": "Include zero demand items."},
                    },
                    "required": ["company"],
                },
            },
            {
                "name": "get_warehouse_status",
                "description": "Get dashboard/status for a specific warehouse.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "warehouse": {"type": "string", "description": "Warehouse name."}
                    },
                    "required": ["warehouse"],
                },
            },
            {
                "name": "get_work_order_zone_status",
                "description": (
                    "Get zone status (Red/Green) and material readiness for a Work Order."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "work_order_name": {"type": "string", "description": "Work Order name."}
                    },
                    "required": ["work_order_name"],
                },
            },
            {
                "name": "get_warehouses_by_type",
                "description": "List all warehouses for a company, optionally filtered by type.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "company": {"type": "string", "description": "ERPNext Company."},
                        "warehouse_type": {"type": "string", "description": "Filter by type."},
                    },
                    "required": ["company"],
                },
            },
            {
                "name": "get_zone_temperature_status",
                "description": (
                    "Get temperature status for all monitored warehouse zones. "
                    "Shows current temp, target, status (Normal/Warning/Critical)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            {
                "name": "track_batch",
                "description": (
                    "Find where a batch is located across warehouses. "
                    "Use when user asks where is batch X or batch location."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "batch_id": {"type": "string", "description": "Batch name/ID."}
                    },
                    "required": ["batch_id"],
                },
            },
        ]

    def call(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Dispatch a tool call by name."""
        dispatch = {
            "get_item_stock_locations": self.get_item_stock_locations,
            "get_kardex": self.get_kardex,
            "get_oos_risk_list": self.get_oos_risk_list,
            "get_warehouse_status": self.get_warehouse_status,
            "get_work_order_zone_status": self.get_work_order_zone_status,
            "get_warehouses_by_type": self.get_warehouses_by_type,
            "get_zone_temperature_status": self.get_zone_temperature_status,
            "track_batch": self.track_batch,
        }
        fn = dispatch.get(tool_name)
        if not fn:
            return {"error": f"Unknown warehouse tool: {tool_name}"}
        try:
            return fn(**args)
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"WarehouseSkill.{tool_name}")
            return {"error": str(e)}

    # --- Tool implementations ---

    def get_item_stock_locations(self, item_code: str) -> List[Dict]:
        return frappe.call(
            f"{self._API}.get_item_stock_locations", item_code=item_code
        )

    def get_kardex(self, warehouse=None, item_code=None, from_date=None, to_date=None, limit=500):
        return frappe.call(
            f"{self._API}.get_kardex",
            warehouse=warehouse, item_code=item_code,
            from_date=from_date, to_date=to_date, limit=limit,
        )

    def get_oos_risk_list(self, company, warehouse=None, lookback_days=90, include_zero_demand=False):
        return frappe.call(
            f"{self._API}.get_oos_risk_list",
            company=company, warehouse=warehouse,
            lookback_days=lookback_days, include_zero_demand=include_zero_demand,
        )

    def get_warehouse_status(self, warehouse: str) -> Dict:
        return frappe.call(
            f"{self._API}.get_warehouse_dashboard_data", warehouse=warehouse
        )

    def get_work_order_zone_status(self, work_order_name: str) -> Dict:
        """Get zone status and material readiness for a Work Order."""
        try:
            wo = frappe.get_doc("Work Order", work_order_name)
            # Determine zone based on warehouse
            wip_warehouse = wo.wip_warehouse
            zone_status = "Green"  # Default
            
            # Check material availability
            material_status = []
            for item in wo.required_items:
                bin_data = frappe.db.get_value(
                    "Bin",
                    {"item_code": item.item_code, "warehouse": item.source_warehouse or wip_warehouse},
                    ["actual_qty", "reserved_qty"],
                    as_dict=True
                ) or {"actual_qty": 0, "reserved_qty": 0}
                
                available = (bin_data.get("actual_qty") or 0) - (bin_data.get("reserved_qty") or 0)
                required = item.required_qty - item.transferred_qty
                is_short = available < required
                
                if is_short:
                    zone_status = "Red"
                
                material_status.append({
                    "item_code": item.item_code,
                    "required_qty": required,
                    "available_qty": available,
                    "is_short": is_short
                })
            
            return {
                "work_order": work_order_name,
                "status": wo.status,
                "zone_status": zone_status,
                "wip_warehouse": wip_warehouse,
                "material_status": material_status,
                "qty_to_produce": wo.qty,
                "produced_qty": wo.produced_qty
            }
        except Exception as e:
            return {"error": str(e)}

    def get_warehouses_by_type(self, company, warehouse_type=None):
        return frappe.call(
            f"{self._API}.get_warehouses_by_type",
            company=company, warehouse_type=warehouse_type,
        )

    def get_zone_temperature_status(self) -> List[Dict]:
        """Get temperature status for all monitored zones."""
        return frappe.call(f"{self._API}.get_zone_temperature_status")

    def track_batch(self, batch_id: str) -> Dict:
        """Find batch location across warehouses."""
        # Get batch info
        batch = frappe.db.get_value(
            "Batch", batch_id,
            ["name", "item", "batch_qty", "expiry_date", "manufacturing_date"],
            as_dict=True
        )
        if not batch:
            return {"error": f"Batch {batch_id} not found"}
        
        # Get stock locations for this batch
        locations = frappe.db.sql("""
            SELECT warehouse, SUM(actual_qty) as qty
            FROM `tabStock Ledger Entry`
            WHERE batch_no = %s AND is_cancelled = 0
            GROUP BY warehouse
            HAVING SUM(actual_qty) > 0
            ORDER BY qty DESC
        """, batch_id, as_dict=True)
        
        return {
            "batch_id": batch.name,
            "item": batch.item,
            "batch_qty": batch.batch_qty,
            "expiry_date": str(batch.expiry_date) if batch.expiry_date else None,
            "manufacturing_date": str(batch.manufacturing_date) if batch.manufacturing_date else None,
            "locations": locations,
            "total_qty": sum(l.qty for l in locations)
        }


def register_skill(registry: dict) -> None:
    """Register WarehouseSkill in the agent skill registry."""
    skill = WarehouseSkill()
    registry[skill.name] = skill
