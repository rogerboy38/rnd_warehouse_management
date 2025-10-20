# Phase 1: Extended Movement Type Master System - Implementation Guide

## Overview

Phase 1 introduces the **Movement Type Master** system, a comprehensive framework for managing 75+ SAP-equivalent movement types in ERPNext. This replaces the hardcoded movement type logic (261, 311) with a flexible, configurable system.

## What's New in Phase 1

### 1. Movement Type Master DocType

A new DocType that centralizes all movement type configurations:

**Key Fields:**
- `movement_code` (e.g., 261, 311, 101): Unique identifier
- `description`: Human-readable description
- `category`: Goods Receipt, Goods Issue, Transfer Posting, etc.
- `stock_movement_type`: Increase, Decrease, Transfer, None
- `requires_approval`: Boolean flag
- `authorization_level`: Standard, Supervisor, Manager, Director
- `erpnext_stock_entry_purpose`: Auto-maps to ERPNext purposes
- `requires_source_warehouse`: Validation flag
- `requires_target_warehouse`: Validation flag
- `auto_create_gi_gt_slip`: Auto-generate GI-GT slips
- `validation_rules`: Custom Python validation logic

**Location:**
```
rnd_warehouse_management/warehouse_management/doctype/movement_type_master/
├── movement_type_master.json      # DocType definition
├── movement_type_master.py        # Server-side logic
├── movement_type_master.js        # Client-side logic
└── test_movement_type_master.py   # Unit tests
```

### 2. Pre-loaded Movement Types

The system includes 46 pre-configured SAP movement types covering:

**1XX - Goods Receipt:**
- 101: Goods Receipt for Purchase Order
- 102: Goods Receipt for PO - Reversal
- 103: Goods Receipt from Blocking Stock
- 122: Return Delivery to Vendor

**2XX - Goods Issue:**
- 201: Goods Issue for Cost Center
- 202: Goods Issue for Cost Center - Reversal
- 221: Goods Issue for Project
- 261: Goods Issue to Production (FrontFlush)
- 262: Goods Issue to Production - Reversal
- 281: Goods Issue for Sampling

**3XX - Transfer Posting:**
- 301: Transfer Posting - Plant to Plant
- 302: Transfer Posting - Plant to Plant - Reversal
- 303: Transfer Posting - Storage Location to Storage Location
- 304: Transfer Posting - Storage Location to Storage Location - Reversal
- 311: Transfer for Kitting (BackFlush)
- 312: Transfer for Kitting - Reversal
- 313: Transfer from Quality Inspection to Unrestricted Use
- 314-350: Various quality and blocking stock transfers
- 411-412: Consignment to own stock transfers

**5XX - Special Receipts:**
- 501-502: Goods Receipt Without Purchase Order
- 511-512: Goods Receipt from WIP
- 521-522: Goods Receipt from By-Product
- 541-542: Goods Receipt from Subcontractor
- 551-552: Goods Receipt for Scrapping
- 561-562: Initial Entry of Stock Balance

**6XX - Special Issues:**
- 601-602: Goods Issue for Delivery
- 641-642: Goods Issue to Subcontractor
- 653-654: Goods Issue for Scrapping

**7XX - Physical Inventory:**
- 701: Physical Inventory - Positive Adjustment
- 702: Physical Inventory - Negative Adjustment
- 711-712: Goods Receipt from Blocked Stock

**Fixture Location:**
```
rnd_warehouse_management/fixtures/movement_type_master.json
```

### 3. Enhanced Stock Entry Integration

**Updated Custom Fields:**
- `custom_sap_movement_type`: Changed from Select to Link (Movement Type Master)
- `custom_movement_type_description`: Auto-populated read-only field
- `custom_movement_category`: Auto-populated read-only field

**New Stock Entry Logic:**

The `stock_entry.py` file now includes:

1. **`sync_movement_type_details()`**: Auto-populates movement type details
2. **`validate_movement_type()`**: Validates using Movement Type Master
3. **`execute_custom_validation()`**: Runs custom validation rules
4. **`validate_movement_type_requirements()`**: Checks warehouse, stock, and authorization requirements
5. **Dynamic signature validation**: Based on movement type configuration

**API Endpoints:**
- `get_movement_types_for_purpose(purpose)`: Get movement types for a specific ERPNext purpose
- `get_movement_type_details_for_ui(movement_code)`: Get details for UI display
- `validate_movement_type_for_stock_entry(movement_code, stock_entry_data)`: Validate movement type

### 4. Enhanced Client-Side Experience

**Updated JavaScript (stock_entry.js):**

New functions:
- `load_movement_type_details(frm)`: Loads and displays movement type info
- `update_signature_requirements_from_movement_type(frm, mt)`: Dynamically sets signature requirements
- `show_movement_type_info(frm, mt)`: Displays movement type details in dashboard
- `suggest_movement_types_for_purpose(frm)`: Suggests appropriate movement types

**User Experience Improvements:**
- Real-time movement type validation
- Dynamic signature field requirements
- Auto-population of purpose based on movement type
- Smart suggestions based on ERPNext purpose
- Rich info display with category, type, and approval requirements

## Installation & Migration

### For Fresh Installation:

1. Install the app:
   ```bash
   bench get-app rnd_warehouse_management
   bench --site your-site install-app rnd_warehouse_management
   ```

2. The Movement Type Master fixtures will be auto-loaded during installation.

### For Upgrading from v1.0.0:

1. Pull the latest code:
   ```bash
   cd apps/rnd_warehouse_management
   git pull
   ```

2. Run migrations:
   ```bash
   bench --site your-site migrate
   ```

3. Install fixtures:
   ```bash
   bench --site your-site install-app rnd_warehouse_management
   ```

4. Clear cache:
   ```bash
   bench --site your-site clear-cache
   bench --site your-site clear-website-cache
   ```

5. Rebuild assets:
   ```bash
   bench build --app rnd_warehouse_management
   ```

### Data Migration for Existing Stock Entries:

Existing Stock Entries with `custom_sap_movement_type` values of "261" or "311" will continue to work seamlessly because:
- Movement codes 261 and 311 are pre-loaded in the Movement Type Master
- The Link field will automatically resolve to the correct Movement Type Master record

## Configuration Guide

### Creating Custom Movement Types:

1. Navigate to: **Stock > Movement Type Master > New**
2. Fill in the required fields:
   - Movement Code (e.g., "901" for custom movement)
   - Description
   - Category
   - Stock Movement Type
3. Set approval requirements:
   - Requires Approval checkbox
   - Authorization Level
4. Map to ERPNext:
   - ERPNext Stock Entry Purpose
   - Warehouse requirements
5. Optional: Add custom validation rules in Python

### Custom Validation Rules Example:

```python
# Example: Require PO reference for goods receipt
if stock_entry.purpose == 'Material Receipt':
    if not stock_entry.purchase_order:
        valid = False
        message = "Purchase Order reference is required for this movement type"
```

### Modifying Existing Movement Types:

1. Navigate to: **Stock > Movement Type Master**
2. Select the movement type to modify
3. Update fields as needed
4. Click **Save**

**Note:** Changes will apply to all new Stock Entries. Existing submitted Stock Entries remain unchanged.

## Testing Guide

### Unit Tests:

Run the test suite:
```bash
bench --site your-site run-tests --app rnd_warehouse_management --doctype "Movement Type Master"
```

### Manual Testing Checklist:

**Test 1: Movement Type Master CRUD**
- [ ] Create a new movement type
- [ ] View movement type details
- [ ] Update movement type
- [ ] Deactivate movement type (set is_active = 0)
- [ ] Verify inactive movement types are not selectable

**Test 2: Stock Entry Integration**
- [ ] Create a Stock Entry
- [ ] Select a movement type (e.g., 261)
- [ ] Verify description auto-populates
- [ ] Verify purpose auto-sets
- [ ] Verify signature requirements update
- [ ] Save and submit
- [ ] Verify validation rules execute

**Test 3: Approval Workflows**
- [ ] Create Stock Entry with movement type 261 (Supervisor level)
- [ ] Verify warehouse supervisor signature is required
- [ ] Create Stock Entry with movement type 311 (Supervisor level + kitting)
- [ ] Verify both signatures are required
- [ ] Create Stock Entry with movement type 701 (Manager level)
- [ ] Verify only Manager role can submit

**Test 4: Warehouse Requirements**
- [ ] Create Stock Entry with movement type 101 (requires target warehouse)
- [ ] Verify validation fails without target warehouse
- [ ] Create Stock Entry with movement type 201 (requires source warehouse)
- [ ] Verify validation fails without source warehouse
- [ ] Create Stock Entry with movement type 311 (requires both)
- [ ] Verify validation fails if either is missing

**Test 5: GI-GT Slip Auto-Generation**
- [ ] Create Stock Entry with movement type 261 (auto_create_gi_gt_slip = 1)
- [ ] Submit the Stock Entry
- [ ] Verify GI-GT slip number is generated
- [ ] Create Stock Entry with movement type 101 (auto_create_gi_gt_slip = 0)
- [ ] Submit the Stock Entry
- [ ] Verify no GI-GT slip number is generated

**Test 6: Custom Validation Rules**
- [ ] Create a movement type with custom validation rules
- [ ] Create a Stock Entry with that movement type
- [ ] Trigger the validation rule condition
- [ ] Verify custom validation executes and displays message

## API Usage Examples

### Python (Server-side):

```python
import frappe

# Get movement type details
from rnd_warehouse_management.warehouse_management.doctype.movement_type_master.movement_type_master import get_movement_type_details

details = get_movement_type_details("261")
print(details)
# Output: {'movement_code': '261', 'description': 'Goods Issue to Production (FrontFlush)', ...}

# Get active movement types by category
from rnd_warehouse_management.warehouse_management.doctype.movement_type_master.movement_type_master import get_active_movement_types

production_types = get_active_movement_types(category="Production")
for mt in production_types:
    print(f"{mt.movement_code}: {mt.description}")

# Validate movement type for stock entry
from rnd_warehouse_management.warehouse_management.doctype.movement_type_master.movement_type_master import validate_movement_type_for_stock_entry

stock_entry_data = {
    "from_warehouse": "Raw Material - WH",
    "to_warehouse": "Production - WH"
}

result = validate_movement_type_for_stock_entry("311", stock_entry_data)
if result["valid"]:
    print("Validation successful")
else:
    print(f"Validation failed: {result['message']}")
```

### JavaScript (Client-side):

```javascript
// Get movement types for a purpose
frappe.call({
    method: 'rnd_warehouse_management.warehouse_management.stock_entry.get_movement_types_for_purpose',
    args: {
        purpose: 'Material Issue'
    },
    callback: function(r) {
        console.log('Available movement types:', r.message);
    }
});

// Get movement type details
frappe.call({
    method: 'rnd_warehouse_management.warehouse_management.stock_entry.get_movement_type_details_for_ui',
    args: {
        movement_code: '261'
    },
    callback: function(r) {
        console.log('Movement type details:', r.message);
    }
});
```

## Troubleshooting

### Issue: Movement Type Master not appearing in list

**Solution:**
1. Clear cache: `bench --site your-site clear-cache`
2. Verify DocType exists: Check in DocType list
3. Check permissions: Ensure user has read permission

### Issue: Custom fields not showing in Stock Entry

**Solution:**
1. Reinstall fixtures: `bench --site your-site install-app rnd_warehouse_management`
2. Reload: `bench --site your-site reload-doctype "Stock Entry"`
3. Clear cache and rebuild

### Issue: Validation rules not executing

**Solution:**
1. Check Python syntax in validation_rules field
2. View error logs: `bench --site your-site console`
3. Check `frappe.log_error()` entries

### Issue: Movement types not auto-loading

**Solution:**
1. Manually import fixtures:
   ```bash
   bench --site your-site import-doc rnd_warehouse_management/fixtures/movement_type_master.json
   ```
2. Check fixture format (must be valid JSON)

## Performance Considerations

**Caching:**
- Movement Type Master records are cached after first load
- Cache is cleared on Movement Type Master update
- Use `frappe.cache().delete_value("movement_type_list")` to manually clear

**Database Queries:**
- Movement type lookups are optimized with indexes
- Avoid loading full Movement Type Master doc if only basic fields needed
- Use `frappe.get_value()` for single field lookups

**Best Practices:**
1. Keep validation rules simple and fast
2. Use `frappe.db.get_value()` instead of `frappe.get_doc()` when possible
3. Cache frequently used movement type data in Stock Entry

## Next Steps

With Phase 1 complete, the system is ready for:

**Phase 2: Enhanced Stock Entry Workflows**
- Extend stock_entry.py to support all 75+ movement types
- Implement movement type-specific validation rules
- Create multi-level approval workflow system
- Enhance GI-GT slip generation for all applicable movement types

**Future Enhancements:**
- Movement Type Analytics Dashboard
- Movement Type Usage Reports
- Movement Type Audit Trail
- Import/Export Movement Type Configurations

## Support & Documentation

For additional support:
- Review the main README.md
- Check docs/API.md for API reference
- Consult the Frappe Framework documentation: https://docs.frappe.io
- ERPNext Stock Module documentation: https://docs.erpnext.com/docs/user/manual/en/stock

## Version History

**v2.0.0 (Phase 1) - 2025-10-20**
- Introduced Movement Type Master DocType
- Pre-loaded 46 SAP movement types
- Enhanced Stock Entry integration
- Dynamic validation and signature requirements
- Improved client-side user experience

**v1.0.0 - Previous**
- Hardcoded support for movement types 261 and 311
- Basic dual-signature workflow
- Red/Green zone logic
