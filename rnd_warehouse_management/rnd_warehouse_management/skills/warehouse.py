# raven_ai_agent/skills/warehouse.py
# Warehouse Intelligence Skill for raven_ai_agent
# Place this file in: raven_ai_agent/skills/warehouse.py
# Register in skills __init__.py or skill registry

from __future__ import unicode_literals
from typing import Any, Dict, List, Optional

import frappe


class WarehouseSkill:
    """
    Warehouse Intelligence Skill for raven_ai_agent.

    Exposes 6 tools to the LLM for answering warehouse-related questions:
        1. get_item_stock_locations  - Where is item X?
        2. get_kardex                - Stock ledger / Kardex view
        3. get_oos_risk_list         - OOS now or at risk
        4. get_warehouse_status      - Dashboard for a warehouse
        5. get_work_order_zone_status - WO Red/Green zone + material readiness
        6. get_warehouses_by_type    - List warehouses by type

    Usage in agent:
        skill = WarehouseSkill()
        tools = skill.get_tools()          # pass to LLM function-calling
        result = skill.call(tool_name, args)  # execute tool by name
    """

    name = "warehouse"
    description = (
        "Answer questions about warehouses, inventory locations, stock movements, "
        "out-of-stock risk, work order material readiness, and warehouse dashboards."
    )

    # ------------------------------------------------------------------
    # Tool registry
    # ------------------------------------------------------------------

    def get_tools(self) -> List[Dict[str, Any]]:
        """Return tool definitions in OpenAI function-calling format."""
        return [
            {
                "name": "get_item_stock_locations",
                "description": (
                    "Get the current stock qty for a specific item across ALL warehouses. "
                    "Use this when the user asks 'where is item X', 'how much stock do we have "
                    "for X', or 'in which warehouses is X available'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_code": {
                            "type": "string",
                            "description": "ERPNext Item code (exact name).",
                        }
                    },
                    "required": ["item_code"],
                },
            },
            {
                "name": "get_kardex",
                "description": (
                    "Get stock ledger entries (Kardex) for a warehouse and/or item within "
                    "an optional date range. Use this when the user asks for movement history, "
                    "Kardex, 'show me transactions for X', or 'what happened with stock in WH-01'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "warehouse": {
                            "type": "string",
                            "description": "Warehouse name to filter by.",
                        },
                        "item_code": {
                            "type": "string",
                            "description": "Item code to filter by.",
                        },
                        "from_date": {
                            "type": "string",
                            "description": "Start date in YYYY-MM-DD format.",
                        },
                        "to_date": {
                            "type": "string",
                            "description": "End date in YYYY-MM-DD format.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max rows to return (default 500).",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "get_oos_risk_list",
                "description": (
                    "Get a list of items that are out of stock NOW or at risk of stockout soon. "
                    "Use this when the user asks 'what is out of stock', 'which items should I "
                    "replenish', 'OOS report', or 'at-risk items'. "
                    "Returns OOS status: OOS | AT_RISK | BELOW_REORDER."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "company": {
                            "type": "string",
                            "description": "ERPNext Company name.",
                        },
                        "warehouse": {
                            "type": "string",
                            "description": "Filter to a single warehouse (optional).",
                        },
                        "lookback_days": {
                            "type": "integer",
                            "description": "Days of history to estimate demand (default 90).",
                        },
                        "include_zero_demand": {
                            "type": "boolean",
                            "description": "Include items with no recent demand (default false).",
                        },
                    },
                    "required": ["company"],
                },
            },
            {
                "name": "get_warehouse_status",
                "description": (
                    "Get the dashboard/status for a specific warehouse: utilization, "
                    "shortages, zone status. Use this when the user asks about a specific "
                    "warehouse health, capacity, or overview."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "warehouse": {
                            "type": "string",
                            "description": "Warehouse name.",
                        }
                    },
                    "required": ["warehouse"],
                },
            },
            {
                "name": "get_work_order_zone_status",
                "description": (
                    "Get the zone status (Red/Green) and material readiness for a Work Order. "
                    "Use this when the user asks 'is WO-XXXX ready', 'which work orders are "
                    "blocked', or 'what material is missing for production'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "work_order_name": {
                            "type": "string",
                            "description": "Work Order document name.",
                        }
                    },
                    "required": ["work_order_name"],
                },
            },
            {
                "name": "get_warehouses_by_type",
                "description": (
                    "List all warehouses for a company, optionally filtered by type "
                    "(Raw Material, WIP, Finished Goods, Transit). Use this when the user "
                    "asks 'list all warehouses', or needs to know which warehouses exist."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "company": {
                            "type": "string",
                            "description": "ERPNext Company name.",
                        },
                        "warehouse_type": {
                            "type": "string",
                            "description": "Filter by type: Raw Material | WIP | Finished Goods | Transit.",
                        },
                    },
                    "required": ["company"],
                },
            },
        ]

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    def call(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """Dispatch a tool call by name."""
        dispatch = {
            "get_item_stock_locations": self.get_item_stock_locations,
            "get_kardex": self.get_kardex,
            "get_oos_risk_list": self.get_oos_risk_list,
            "get_warehouse_status": self.get_warehouse_status,
            "get_work_order_zone_status": self.get_work_order_zone_status,
            "get_warehouses_by_type": self.get_warehouses_by_type,
        }
        fn = dispatch.get(tool_name)
        if not fn:
            return {"error": f"Unknown warehouse tool: {tool_name}"}
        try:
            return fn(**args)
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"WarehouseSkill.{tool_name}")
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def get_item_stock_locations(
        self,
        item_code: str,
    ) -> List[Dict]:
        """Where is item X across all warehouses?"""
        return frappe.call(
            "rnd_warehouse_management.api.warehouse.get_item_stock_locations",
            item_code=item_code,
        )

    def get_kardex(
        self,
        warehouse: Optional[str] = None,
        item_code: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict]:
        """Stock ledger / Kardex for a warehouse, item, and/or date range."""
        return frappe.call(
            "rnd_warehouse_management.api.warehouse.get_kardex",
            warehouse=warehouse,
            item_code=item_code,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )

    def get_oos_risk_list(
        self,
        company: str,
        warehouse: Optional[str] = None,
        lookback_days: int = 90,
        include_zero_demand: bool = False,
    ) -> List[Dict]:
        """Items OOS now or at risk of stockout."""
        return frappe.call(
            "rnd_warehouse_management.api.warehouse.get_oos_risk_list",
            company=company,
            warehouse=warehouse,
            lookback_days=lookback_days,
            include_zero_demand=include_zero_demand,
        )

    def get_warehouse_status(
        self,
        warehouse: str,
    ) -> Dict:
        """Dashboard/status for a specific warehouse."""
        return frappe.call(
            "rnd_warehouse_management.api.warehouse.get_warehouse_dashboard_data",
            warehouse=warehouse,
        )

    def get_work_order_zone_status(
        self,
        work_order_name: str,
    ) -> Dict:
        """Zone status (Red/Green) + material readiness for a Work Order."""
        zone = frappe.call(
            "rnd_warehouse_management.api.work_order.get_work_order_zone_status",
            work_order_name=work_order_name,
        )
        material = frappe.call(
            "rnd_warehouse_management.api.work_order.get_work_order_material_status",
            work_order_name=work_order_name,
        )
        return {
            "work_order": work_order_name,
            "zone_status": zone,
            "material_status": material,
        }

    def get_warehouses_by_type(
        self,
        company: str,
        warehouse_type: Optional[str] = None,
    ) -> List[Dict]:
        """List warehouses for a company, optionally filtered by type."""
        return frappe.call(
            "rnd_warehouse_management.api.warehouse.get_warehouses_by_type",
            company=company,
            warehouse_type=warehouse_type,
        )


# ------------------------------------------------------------------
# Registration helper - call this from skills __init__.py
# ------------------------------------------------------------------

def register_skill(registry: dict) -> None:
    """Register WarehouseSkill in the agent skill registry.

    In skills/__init__.py or skill_loader.py add:
        from raven_ai_agent.skills.warehouse import register_skill
        register_skill(SKILL_REGISTRY)
    """
    skill = WarehouseSkill()
    registry[skill.name] = skill
