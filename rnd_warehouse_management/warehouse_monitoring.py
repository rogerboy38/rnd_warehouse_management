"""
Warehouse Environmental Monitoring Utilities
Handles temperature and humidity validation, parsing, and calculations
"""
import frappe
from frappe import _
import re

class WarehouseMonitoring:
    """Manage warehouse environmental monitoring"""
    
    @staticmethod
    def parse_temperature_string(temp_str):
        """
        Parse temperature specification string into components.
        
        Examples:
        - "2-8°C" → {"min": 2.0, "max": 8.0, "unit": "°C", "is_range": True}
        - "20°C" → {"value": 20.0, "unit": "°C", "is_range": False}
        - "25°C/60%RH" → {"value": 25.0, "unit": "°C", "humidity": 60, "has_humidity": True}
        - "68°F" → {"value": 68.0, "unit": "°F", "is_range": False}
        
        Returns dict with parsed components or None if invalid.
        """
        if not temp_str:
            return None
        
        temp_str = str(temp_str).strip()
        result = {"original": temp_str}
        
        # Extract unit
        if '°C' in temp_str or 'C' in temp_str:
            result["unit"] = "°C"
        elif '°F' in temp_str or 'F' in temp_str:
            result["unit"] = "°F"
        elif 'K' in temp_str:
            result["unit"] = "K"
        else:
            result["unit"] = "°C"  # Default
        
        # Extract humidity if present
        humidity_match = re.search(r'/(\d+)%RH', temp_str, re.IGNORECASE)
        if humidity_match:
            result["humidity"] = float(humidity_match.group(1))
            result["has_humidity"] = True
        
        # Remove humidity part for temperature parsing
        temp_part = re.sub(r'/\d+%RH', '', temp_str, flags=re.IGNORECASE)
        
        # Check for range (e.g., "2-8", "15 - 25", "5~10")
        range_match = re.search(r'(\d+(?:\.\d+)?)\s*[-~]\s*(\d+(?:\.\d+)?)', temp_part)
        if range_match:
            result["min"] = float(range_match.group(1))
            result["max"] = float(range_match.group(2))
            result["is_range"] = True
            result["target"] = (result["min"] + result["max"]) / 2
        else:
            # Single value
            value_match = re.search(r'(\d+(?:\.\d+)?)', temp_part)
            if value_match:
                result["value"] = float(value_match.group(1))
                result["is_range"] = False
                result["target"] = result["value"]
        
        return result
    
    @staticmethod
    def calculate_temperature_spec_display(doc):
        """
        Generate display specification from temperature fields.
        
        Example outputs:
        - "2-8°C (Target: 5°C)"
        - "20°C ±2°C"
        - "25°C/60%RH"
        - "Not temperature controlled"
        """
        if not doc.custom_temperature_controlled:
            return "Not temperature controlled"
        
        unit = doc.custom_temperature_uom or "°C"
        
        # Extract just the unit symbol (remove text in parentheses)
        unit_symbol = unit.split(' ')[0] if ' ' in unit else unit
        
        if doc.custom_min_temperature is not None and doc.custom_max_temperature is not None:
            spec = f"{doc.custom_min_temperature}-{doc.custom_max_temperature}{unit_symbol}"
            if doc.custom_target_temperature:
                spec += f" (Target: {doc.custom_target_temperature}{unit_symbol})"
            return spec
        elif doc.custom_target_temperature:
            return f"{doc.custom_target_temperature}{unit_symbol}"
        else:
            return f"Temperature controlled ({unit_symbol})"
    
    @staticmethod
    def validate_temperature_ranges(doc):
        """Validate temperature ranges and set status"""
        if not doc.custom_temperature_controlled:
            return
        
        # Validate min < max
        if (doc.custom_min_temperature is not None and 
            doc.custom_max_temperature is not None):
            
            if doc.custom_min_temperature >= doc.custom_max_temperature:
                frappe.throw(_("Minimum temperature must be less than maximum temperature"))
            
            # Validate target is within range
            if doc.custom_target_temperature:
                if (doc.custom_target_temperature < doc.custom_min_temperature or 
                    doc.custom_target_temperature > doc.custom_max_temperature):
                    frappe.throw(_("Target temperature must be within min-max range"))
        
        # Update status based on current temperature
        if doc.custom_current_temperature is not None:
            if (doc.custom_min_temperature and 
                doc.custom_current_temperature < doc.custom_min_temperature):
                doc.custom_temperature_status = "Below Minimum"
            elif (doc.custom_max_temperature and 
                  doc.custom_current_temperature > doc.custom_max_temperature):
                doc.custom_temperature_status = "Above Maximum"
            else:
                doc.custom_temperature_status = "Within Range"
            
            doc.custom_last_temperature_check = frappe.utils.now_datetime()
    
    @staticmethod
    def validate_humidity_ranges(doc):
        """Validate humidity ranges"""
        if not doc.custom_humidity_controlled:
            return
        
        if (doc.custom_min_humidity is not None and 
            doc.custom_max_humidity is not None):
            
            if doc.custom_min_humidity >= doc.custom_max_humidity:
                frappe.throw(_("Minimum humidity must be less than maximum humidity"))
            
            if doc.custom_target_humidity:
                if (doc.custom_target_humidity < doc.custom_min_humidity or 
                    doc.custom_target_humidity > doc.custom_max_humidity):
                    frappe.throw(_("Target humidity must be within min-max range"))

def validate_warehouse_monitoring(doc, method=None):
    """Main validation function for warehouse monitoring"""
    # Update display specification
    if hasattr(doc, 'custom_temperature_controlled'):
        doc.custom_temperature_spec_display = WarehouseMonitoring.calculate_temperature_spec_display(doc)
    
    # Validate ranges
    WarehouseMonitoring.validate_temperature_ranges(doc)
    WarehouseMonitoring.validate_humidity_ranges(doc)

@frappe.whitelist()
def parse_and_update_temperature(warehouse_name, temperature_str):
    """Parse temperature string and update warehouse fields"""
    doc = frappe.get_doc("Warehouse", warehouse_name)
    parsed = WarehouseMonitoring.parse_temperature_string(temperature_str)
    
    if not parsed:
        frappe.throw(_("Invalid temperature format. Examples: '2-8°C', '20°C', '25°C/60%RH'"))
    
    updates = {
        "custom_requires_monitoring": 1,
        "custom_temperature_controlled": 1,
        "custom_temperature_uom": parsed.get("unit", "°C")
    }
    
    if parsed.get("is_range"):
        updates.update({
            "custom_min_temperature": parsed.get("min"),
            "custom_max_temperature": parsed.get("max"),
            "custom_target_temperature": parsed.get("target")
        })
    else:
        updates["custom_target_temperature"] = parsed.get("value")
    
    # Update humidity if present
    if parsed.get("has_humidity"):
        updates.update({
            "custom_humidity_controlled": 1,
            "custom_target_humidity": parsed.get("humidity")
        })
    
    for field, value in updates.items():
        if hasattr(doc, field):
            setattr(doc, field, value)
    
    doc.save()
    return {"success": True, "message": _("Temperature specification updated")}

@frappe.whitelist()
def check_environmental_status(warehouse_name):
    """Check environmental status of warehouse"""
    doc = frappe.get_doc("Warehouse", warehouse_name)
    
    status = {
        "temperature": {
            "controlled": doc.custom_temperature_controlled,
            "status": doc.custom_temperature_status,
            "current": doc.custom_current_temperature,
            "range": f"{doc.custom_min_temperature}-{doc.custom_max_temperature}" 
                     if doc.custom_min_temperature and doc.custom_max_temperature else "Not set",
            "unit": doc.custom_temperature_uom
        },
        "humidity": {
            "controlled": doc.custom_humidity_controlled,
            "current": doc.custom_current_humidity,
            "range": f"{doc.custom_min_humidity}%-{doc.custom_max_humidity}%"
                     if doc.custom_min_humidity and doc.custom_max_humidity else "Not set"
        }
    }
    
    return status
