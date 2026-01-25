"""
Temperature Management Utilities for Warehouse Management
Best practices implementation for industrial temperature monitoring
"""
import frappe
from frappe import _
import re

class TemperatureManager:
    """Manage temperature specifications and monitoring"""
    
    # Conversion factors
    CONVERSION = {
        '°C_to_°F': lambda c: (c * 9/5) + 32,
        '°F_to_°C': lambda f: (f - 32) * 5/9,
        '°C_to_K': lambda c: c + 273.15,
        'K_to_°C': lambda k: k - 273.15,
        '°F_to_K': lambda f: (f - 32) * 5/9 + 273.15,
        'K_to_°F': lambda k: (k - 273.15) * 9/5 + 32
    }
    
    @staticmethod
    def convert_temperature(value, from_unit, to_unit):
        """Convert temperature between units"""
        if not value or from_unit == to_unit:
            return value
        
        conversion_key = f"{from_unit.replace('°', '').replace('(', '').replace(')', '').strip()}_to_{to_unit.replace('°', '').replace('(', '').replace(')', '').strip()}"
        
        if conversion_key in TemperatureManager.CONVERSION:
            return round(TemperatureManager.CONVERSION[conversion_key](value), 2)
        
        # Default: assume same unit or return original
        return value
    
    @staticmethod
    def parse_temperature_string(temperature_str):
        """
        Parse temperature specification string into structured data.
        
        Supports formats:
        - "2-8°C" → {"min": 2, "max": 8, "unit": "°C", "type": "range"}
        - "20°C" → {"value": 20, "unit": "°C", "type": "single"}
        - "25°C/60%RH" → {"value": 25, "unit": "°C", "humidity": 60, "type": "with_humidity"}
        - "68°F" → {"value": 68, "unit": "°F", "type": "single"}
        
        Returns dict or None if invalid.
        """
        if not temperature_str:
            return None
        
        temperature_str = str(temperature_str).strip()
        result = {"original": temperature_str}
        
        # Extract unit
        unit_pattern = r'([°℃℉CFK]+(?:\([^)]+\))?)'
        unit_match = re.search(unit_pattern, temperature_str)
        
        if unit_match:
            result["unit"] = unit_match.group(1)
            # Standardize
            if "°C" in result["unit"] or "Celsius" in result["unit"]:
                result["unit"] = "°C"
            elif "°F" in result["unit"] or "Fahrenheit" in result["unit"]:
                result["unit"] = "°F"
            elif "K" in result["unit"] or "Kelvin" in result["unit"]:
                result["unit"] = "K"
        
        # Extract humidity if present
        humidity_match = re.search(r'/(\d+(?:\.\d+)?)%\s*RH', temperature_str, re.IGNORECASE)
        if humidity_match:
            result["humidity"] = float(humidity_match.group(1))
            result["has_humidity"] = True
        
        # Remove humidity part for temperature parsing
        temp_part = re.sub(r'/\d+(?:\.\d+)?%\s*RH', '', temperature_str, flags=re.IGNORECASE)
        
        # Check for range (e.g., "2-8", "15 - 25", "5~10")
        range_pattern = r'(\d+(?:\.\d+)?)\s*[-~]\s*(\d+(?:\.\d+)?)'
        range_match = re.search(range_pattern, temp_part)
        
        if range_match:
            result["min"] = float(range_match.group(1))
            result["max"] = float(range_match.group(2))
            result["type"] = "range"
            result["target"] = (result["min"] + result["max"]) / 2  # Calculate midpoint
        else:
            # Single value
            value_pattern = r'(\d+(?:\.\d+)?)'
            value_match = re.search(value_pattern, temp_part)
            if value_match:
                result["value"] = float(value_match.group(1))
                result["type"] = "single"
                result["target"] = result["value"]
        
        return result
    
    @staticmethod
    def calculate_range_from_target(target, tolerance_percent, unit="°C"):
        """
        Calculate min/max range from target temperature and tolerance.
        
        Args:
            target (float): Target temperature
            tolerance_percent (float): Allowed deviation percentage
            unit (str): Temperature unit
            
        Returns:
            dict: {"min": value, "max": value}
        """
        if not target or not tolerance_percent:
            return {"min": None, "max": None}
        
        tolerance_value = target * (tolerance_percent / 100)
        
        return {
            "min": round(target - tolerance_value, 1),
            "max": round(target + tolerance_value, 1)
        }
    
    @staticmethod
    def check_temperature_status(current, min_temp, max_temp, unit="°C"):
        """
        Check if current temperature is within acceptable range.
        
        Returns:
            str: "Within Range", "Below Minimum", "Above Maximum", "No Data"
        """
        if current is None:
            return "No Data"
        
        if min_temp is not None and current < min_temp:
            return "Below Minimum"
        elif max_temp is not None and current > max_temp:
            return "Above Maximum"
        else:
            return "Within Range"
    
    @staticmethod
    def generate_display_specification(warehouse_doc):
        """
        Generate human-readable temperature specification.
        
        Example outputs:
        - "2-8°C (Target: 5°C)"
        - "20°C ±2°C"
        - "25°C/60%RH"
        - "Not temperature controlled"
        """
        if not warehouse_doc.get("custom_is_temperature_controlled"):
            return "Not temperature controlled"
        
        unit = warehouse_doc.get("custom_temperature_unit", "°C")
        target = warehouse_doc.get("custom_target_temperature")
        min_temp = warehouse_doc.get("custom_min_temperature")
        max_temp = warehouse_doc.get("custom_max_temperature")
        
        if min_temp is not None and max_temp is not None:
            return f"{min_temp}-{max_temp}{unit} (Target: {target}{unit})"
        elif target is not None:
            return f"{target}{unit}"
        else:
            return f"Temperature controlled ({unit})"
    
    @staticmethod
    def migrate_legacy_data():
        """
        Migrate existing temperature data from old format to new structured format.
        """
        warehouses = frappe.get_all("Warehouse",
            fields=["name", "custom_target_temperature", "warehouse_name"]
        )
        
        migrated = 0
        for wh in warehouses:
            old_temp = wh.custom_target_temperature
            
            if old_temp:
                # Parse old data
                parsed = TemperatureManager.parse_temperature_string(str(old_temp))
                
                if parsed:
                    update_data = {
                        "custom_is_temperature_controlled": 1
                    }
                    
                    if "unit" in parsed:
                        update_data["custom_temperature_unit"] = parsed["unit"]
                    
                    if parsed.get("type") == "range":
                        update_data["custom_min_temperature"] = parsed.get("min")
                        update_data["custom_max_temperature"] = parsed.get("max")
                        update_data["custom_target_temperature"] = parsed.get("target")
                    elif parsed.get("type") == "single":
                        update_data["custom_target_temperature"] = parsed.get("value")
                    
                    # Update warehouse
                    frappe.db.set_value("Warehouse", wh.name, update_data)
                    migrated += 1
        
        frappe.db.commit()
        return migrated

@frappe.whitelist()
def validate_temperature_spec(spec):
    """API endpoint to validate temperature specification"""
    parsed = TemperatureManager.parse_temperature_string(spec)
    
    if not parsed or ("type" not in parsed):
        return {
            "valid": False,
            "message": "Invalid format. Examples: '2-8°C', '20°C', '25°C/60%RH'"
        }
    
    return {
        "valid": True,
        "parsed": parsed,
        "message": f"Valid {parsed['type']} specification"
    }

@frappe.whitelist()
def auto_calculate_range(target, tolerance_percent, unit="°C"):
    """Calculate min/max from target and tolerance"""
    target = float(target) if target else 0
    tolerance = float(tolerance_percent) if tolerance_percent else 0
    
    result = TemperatureManager.calculate_range_from_target(target, tolerance, unit)
    return result

@frappe.whitelist()
def check_temperature_alerts(warehouse_name):
    """Check if warehouse temperature needs attention"""
    warehouse = frappe.get_doc("Warehouse", warehouse_name)
    
    if not warehouse.custom_is_temperature_controlled:
        return {"status": "OK", "message": "Not temperature controlled"}
    
    status = TemperatureManager.check_temperature_status(
        warehouse.custom_current_temperature,
        warehouse.custom_min_temperature,
        warehouse.custom_max_temperature,
        warehouse.custom_temperature_unit
    )
    
    return {
        "status": status,
        "current": warehouse.custom_current_temperature,
        "unit": warehouse.custom_temperature_unit,
        "range": f"{warehouse.custom_min_temperature}-{warehouse.custom_max_temperature}{warehouse.custom_temperature_unit}"
    }
