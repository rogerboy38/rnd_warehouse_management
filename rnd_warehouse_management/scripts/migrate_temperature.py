import frappe
import re  # We'll need re for parsing

# Simplified TemperatureManager class since we can't import from utils
class SimpleTemperatureManager:
    """Simple temperature parser for migration"""
    
    @staticmethod
    def parse_temperature_string(temperature_str):
        """
        Simple temperature string parser for migration.
        """
        if not temperature_str:
            return None
        
        temperature_str = str(temperature_str).strip()
        result = {"original": temperature_str}
        
        # Extract unit
        if '°C' in temperature_str or 'C' in temperature_str:
            result["unit"] = "°C"
        elif '°F' in temperature_str or 'F' in temperature_str:
            result["unit"] = "°F"
        else:
            result["unit"] = "°C"  # Default
        
        # Check for range (e.g., "2-8", "15 - 25")
        range_match = re.search(r'(\d+(?:\.\d+)?)\s*[-~]\s*(\d+(?:\.\d+)?)', temperature_str)
        if range_match:
            result["min"] = float(range_match.group(1))
            result["max"] = float(range_match.group(2))
            result["type"] = "range"
            result["target"] = (result["min"] + result["max"]) / 2
        else:
            # Single value
            value_match = re.search(r'(\d+(?:\.\d+)?)', temperature_str)
            if value_match:
                result["value"] = float(value_match.group(1))
                result["type"] = "single"
                result["target"] = result["value"]
        
        return result
    
    @staticmethod
    def calculate_range_from_target(target, tolerance_percent, unit="°C"):
        """Calculate min/max from target and tolerance"""
        if not target or not tolerance_percent:
            return {"min": None, "max": None}
        
        tolerance_value = target * (tolerance_percent / 100)
        
        return {
            "min": round(target - tolerance_value, 1),
            "max": round(target + tolerance_value, 1)
        }

def migrate_all_warehouse_temperatures():
    """
    Simple migration for warehouse temperature data.
    """
    print("Starting simple temperature data migration...")
    
    # Get all warehouses
    warehouses = frappe.get_all("Warehouse", 
        fields=["name", "custom_target_temperature", "warehouse_name"])
    
    migrated = 0
    errors = []
    
    for wh in warehouses:
        try:
            old_temp = wh.custom_target_temperature
            
            if old_temp:
                # Parse the old temperature string
                parsed = SimpleTemperatureManager.parse_temperature_string(str(old_temp))
                
                if parsed and parsed.get("type"):
                    update_data = {
                        "custom_is_temperature_controlled": 1
                    }
                    
                    # Set unit
                    update_data["custom_temperature_unit"] = parsed.get("unit", "°C")
                    
                    # Set values based on type
                    if parsed.get("type") == "range":
                        update_data.update({
                            "custom_min_temperature": parsed.get("min"),
                            "custom_max_temperature": parsed.get("max"),
                            "custom_target_temperature": parsed.get("target")
                        })
                    elif parsed.get("type") == "single":
                        update_data["custom_target_temperature"] = parsed.get("value")
                    
                    # Update the warehouse
                    frappe.db.set_value("Warehouse", wh.name, update_data)
                    migrated += 1
                    
                    print(f"  ✅ {wh.warehouse_name}: '{old_temp}' → {parsed['type']}")
                else:
                    print(f"  ⚠️  {wh.warehouse_name}: Could not parse '{old_temp}'")
            else:
                # No temperature data
                frappe.db.set_value("Warehouse", wh.name, {
                    "custom_is_temperature_controlled": 0
                })
                
        except Exception as e:
            errors.append(f"{wh.warehouse_name}: {str(e)}")
            print(f"  ❌ {wh.warehouse_name}: Error - {str(e)[:50]}...")
    
    frappe.db.commit()
    
    print(f"\nMigration Summary:")
    print(f"  Total warehouses processed: {len(warehouses)}")
    print(f"  Successfully migrated: {migrated}")
    print(f"  Errors: {len(errors)}")
    
    return {
        "total": len(warehouses),
        "migrated": migrated,
        "errors": errors
    }

@frappe.whitelist()
def run_migration():
    """API endpoint to run migration"""
    result = migrate_all_warehouse_temperatures()
    return result
