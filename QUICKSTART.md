# Quick Start Guide

## 5-Minute Setup

Get RND Warehouse Management running in your ERPNext instance in just 5 minutes!

### Step 1: Install the App (2 minutes)

```bash
# Navigate to your Frappe bench directory
cd ~/frappe-bench

# Get the app from GitHub
bench get-app https://github.com/minimax/rnd_warehouse_management.git

# Install on your site
bench --site [your-site-name] install-app rnd_warehouse_management

# Restart
bench restart
```

### Step 2: Assign Roles (1 minute)

1. Go to **User** list in ERPNext
2. Edit your user
3. Assign these roles:
   - Warehouse Supervisor
   - Kitting Supervisor (optional)
   - Zone Manager (for viewing reports)

### Step 3: Create a Test Warehouse (1 minute)

1. Go to **Stock > Warehouse > New**
2. Set:
   - Warehouse Name: "Test WIP"
   - Warehouse Type: "Work In Progress"
   - Company: Your company
3. Save

### Step 4: Create a Test Stock Entry (1 minute)

1. Go to **Stock > Stock Entry > New**
2. Set:
   - Purpose: "Material Issue"
   - SAP Movement Type: "261 (FrontFlush)"
3. Add an item
4. Set source and target warehouses
5. Save
6. Add your signature in the "Warehouse Supervisor Signature" field
7. Submit

**Done!** ✅ You've successfully created your first SAP-style stock entry with digital signature!

## Next Steps

### Configure Your Warehouses

Set up a proper warehouse hierarchy:

```
Your Company
├── Raw Materials
│   ├── Raw Material Main
│   └── Raw Material Transit
├── Production
│   ├── Production WIP
│   └── Kitting Area
└── Finished Goods
    ├── FG Main
    └── FG Ready to Ship
```

### Learn the Basics

1. **SAP Movement Types**
   - **261**: Goods Issue for Production (single signature)
   - **311**: Transfer for Kitting (dual signature)

2. **Zone Status**
   - **Red Zone**: Materials not ready
   - **Green Zone**: All materials available

3. **Utility Functions** (API)
   - Material Assessment Status
   - Inventory Turnover
   - Stock Aging Report
   - Reorder Suggestions

### Access Documentation

- **Full README**: See `README.md`
- **API Documentation**: See `docs/API.md`
- **Deployment Guide**: See `DEPLOYMENT_GUIDE.md`
- **Testing Guide**: See `docs/TESTING_GUIDE.md`

### Get Help

- **Issues**: [GitHub Issues](https://github.com/minimax/rnd_warehouse_management/issues)
- **Email**: support@minimax.com
- **Wiki**: [GitHub Wiki](https://github.com/minimax/rnd_warehouse_management/wiki)

## Common Tasks

### How to: Create SAP 261 Stock Entry

```python
# Via API
frappe.call({
    method: 'rnd_warehouse_management.warehouse_management.stock_entry.make_custom_stock_entry',
    args: {
        purpose: 'Material Issue',
        work_order: 'WO-001',
        qty: 10
    },
    callback: function(r) {
        console.log(r.message);
    }
});
```

### How to: Check Material Status

```python
# Via Python
from rnd_warehouse_management.warehouse_management.utils import get_material_assessment_status

result = get_material_assessment_status("ITEM-001")
print(result["zone_status"])  # Red Zone or Green Zone
```

### How to: Update Work Order Zone Status

```python
# Manually trigger update
from rnd_warehouse_management.warehouse_management.work_order import update_work_order_zone_status

update_work_order_zone_status("WO-001")
```

### How to: Generate Reorder Report

```python
# Get reorder suggestions
from rnd_warehouse_management.warehouse_management.utils import get_reorder_suggestions

suggestions = get_reorder_suggestions("Raw Material - TC")
for item in suggestions["suggestions"]:
    if item["urgency"] == "High":
        print(f"{item['item_code']}: Order {item['suggested_order_qty']} units")
```

## Troubleshooting

### Signature field not showing?

```bash
bench --site [site-name] clear-cache
bench build --app rnd_warehouse_management
bench restart
```

### Zone status not updating?

```python
# Manual update
bench --site [site-name] execute rnd_warehouse_management.warehouse_management.tasks.update_zone_status
```

### Permission errors?

```bash
# Reset permissions
bench --site [site-name] console
>>> frappe.clear_cache()
>>> frappe.db.commit()
```

---

**You're all set!** Start managing your warehouse with SAP-style efficiency! 🚀
