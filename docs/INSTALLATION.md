# Installation Guide

This guide provides detailed instructions for installing and configuring the RND Warehouse Management app for ERPNext.

## Prerequisites

### System Requirements
- **ERPNext Version**: 15.0 or higher
- **Frappe Framework**: 15.0 or higher
- **Python**: 3.8 or higher
- **Operating System**: Ubuntu 20.04+ / CentOS 8+ / Debian 10+
- **Database**: MariaDB 10.5+ or PostgreSQL 13+
- **Memory**: Minimum 4GB RAM (8GB recommended)
- **Storage**: At least 2GB free space

### Access Requirements
- Administrator access to ERPNext instance
- SSH access to the server (for bench commands)
- Database administrator privileges
- Ability to restart services

## Installation Steps

### Step 1: Download the App

```bash
# Navigate to your Frappe bench directory
cd ~/frappe-bench

# Download the app from GitHub
bench get-app https://github.com/minimax/rnd_warehouse_management.git
```

**Alternative: Local Installation**
```bash
# If you have downloaded the app locally
bench get-app /path/to/rnd_warehouse_management
```

### Step 2: Install on Site

```bash
# Install the app on your site
bench --site [your-site-name] install-app rnd_warehouse_management
```

**Example:**
```bash
bench --site mycompany.localhost install-app rnd_warehouse_management
```

### Step 3: Migration and Setup

```bash
# Run database migrations
bench --site [your-site-name] migrate

# Clear cache
bench --site [your-site-name] clear-cache

# Restart services
bench restart

# Build assets
bench build
```

### Step 4: Verify Installation

1. **Login to ERPNext**
   - Access your ERPNext instance
   - Login with administrator credentials

2. **Check App Installation**
   - Go to: Settings → App Installer
   - Verify "RND Warehouse Management" is listed as installed

3. **Verify Custom Fields**
   - Navigate to: Stock → Stock Entry → New
   - Check for new fields: "SAP Movement Type", "Zone Status", etc.

4. **Check Workflows**
   - Go to: Settings → Workflow
   - Verify "Stock Entry Dual Signature Approval" workflow exists

## Post-Installation Configuration

### Step 1: Role Assignment

**Assign Warehouse Supervisor Role:**
1. Go to: Users → User List
2. Select warehouse staff users
3. Edit and add role: "Warehouse Supervisor"
4. Save changes

**Assign Kitting Supervisor Role:**
1. Select kitting staff users
2. Add role: "Kitting Supervisor"
3. Save changes

**Assign Zone Manager Role:**
1. Select production planning users
2. Add role: "Zone Manager"
3. Save changes

### Step 2: Warehouse Configuration

**Set Warehouse Types:**
1. Go to: Stock → Warehouse
2. For each warehouse, set appropriate "Warehouse Type":
   - Raw Material warehouses: "Raw Material"
   - Production areas: "Work In Progress"
   - Finished goods storage: "Finished Goods"
   - Movement tracking: "Transit"
   - Quality issues: "Rejected"

**Configure Transit Warehouses:**
1. Create transit warehouses for each main warehouse
2. Set "Warehouse Type" to "Transit"
3. Link to parent warehouses via "Default In-Transit Warehouse"

**Example Configuration:**
```
Raw Material Main - Company
└── Default In-Transit: Raw Material Transit - Company

Production WIP - Company  
└── Default In-Transit: Production Transit - Company

FG Main - Company
└── Default In-Transit: FG Transit - Company
```

### Step 3: Temperature Control (Optional)

For warehouses requiring temperature monitoring:
1. Edit warehouse settings
2. Enable "Temperature Control"
3. Set "Target Temperature" (in Celsius)
4. Save configuration

### Step 4: Workflow Activation

**Enable Stock Entry Workflow:**
1. Go to: Settings → Workflow
2. Find "Stock Entry Dual Signature Approval"
3. Ensure "Is Active" is checked
4. Review workflow states and transitions
5. Save if changes made

### Step 5: Print Format Setup

**Configure GI/GT Slip:**
1. Go to: Settings → Print Format
2. Find "GI/GT Slip with Signatures"
3. Test print with sample Stock Entry
4. Customize header/footer if needed

### Step 6: Permission Configuration

**Review Role Permissions:**
1. Go to: Users → Role Permissions Manager
2. Check permissions for:
   - Warehouse Supervisor
   - Kitting Supervisor  
   - Zone Manager
3. Adjust as needed for your organization

## Testing Installation

### Test 1: Create SAP Stock Entry

1. **Create New Stock Entry**
   - Go to: Stock → Stock Entry → New
   - Set Purpose: "Material Issue"
   - Select SAP Movement Type: "261 (FrontFlush)"
   - Add items and warehouses
   - Save

2. **Test Workflow**
   - Submit for approval
   - Login as Warehouse Supervisor
   - Provide digital signature
   - Approve the entry
   - Verify GI/GT slip generation

### Test 2: Zone Status Functionality

1. **Create Work Order**
   - Create Work Order with BOM
   - Check initial zone status (should be "Red Zone")

2. **Test Material Assessment**
   - Create Stock Entry linked to Work Order
   - Verify zone status updates
   - Check completion percentage

### Test 3: Print Format

1. **Generate GI/GT Slip**
   - Open approved Stock Entry
   - Click "Print GI/GT Slip"
   - Verify signature display
   - Test mobile responsiveness

## Troubleshooting

### Common Installation Issues

**App Not Found Error:**
```bash
# Check if app is properly downloaded
ls ~/frappe-bench/apps/rnd_warehouse_management

# If missing, re-download
bench get-app https://github.com/minimax/rnd_warehouse_management.git
```

**Migration Errors:**
```bash
# Check migration status
bench --site [site-name] console
>>> frappe.get_all("Patch Log", filters={"patch": ["like", "%rnd_warehouse%"]})

# Re-run specific patch if needed
bench --site [site-name] console  
>>> frappe.get_doc("Patch Log", {"patch": "patch_name"}).delete()
>>> frappe.db.commit()
# Then re-run migrate
```

**Custom Fields Not Appearing:**
```bash
# Clear cache and reload DocType
bench --site [site-name] clear-cache
bench --site [site-name] reload-doctype "Stock Entry"
bench --site [site-name] reload-doctype "Work Order"  
bench --site [site-name] reload-doctype "Warehouse"
```

**Workflow Not Working:**
```bash
# Check workflow configuration
bench --site [site-name] console
>>> workflow = frappe.get_doc("Workflow", "Stock Entry Dual Signature Approval")
>>> print(workflow.is_active)
>>> print(len(workflow.states))
>>> print(len(workflow.transitions))
```

**Permission Issues:**
```bash
# Reset permissions
bench --site [site-name] console
>>> frappe.clear_cache()
>>> frappe.reload_doctype("Stock Entry")
>>> frappe.db.commit()
```

### Performance Optimization

**Database Indexes:**
```sql
-- Add indexes for better performance
CREATE INDEX idx_stock_entry_sap_movement ON `tabStock Entry` (custom_sap_movement_type);
CREATE INDEX idx_stock_entry_zone_status ON `tabStock Entry` (custom_zone_status);
CREATE INDEX idx_work_order_zone_status ON `tabWork Order` (custom_current_zone_status);
```

**Cache Configuration:**
```bash
# Optimize Redis cache
# Add to common_site_config.json
{
  "redis_cache": "redis://localhost:11311",
  "redis_queue": "redis://localhost:11312",
  "redis_socketio": "redis://localhost:11313"
}
```

## Multi-Site Installation

For installing on multiple sites:

```bash
# Install on multiple sites
for site in site1.localhost site2.localhost site3.localhost; do
    bench --site $site install-app rnd_warehouse_management
    bench --site $site migrate
done

# Restart after all installations
bench restart
```

## Backup Before Installation

**Always backup before installing:**
```bash
# Backup database
bench --site [site-name] backup --with-files

# The backup will be saved to:
# ~/frappe-bench/sites/[site-name]/private/backups/
```

## Uninstallation (if needed)

```bash
# Uninstall app (removes customizations)
bench --site [site-name] uninstall-app rnd_warehouse_management

# Remove app files
bench remove-app rnd_warehouse_management
```

**⚠️ Warning**: Uninstalling will remove all custom fields, workflows, and data. Ensure you have backups.

## Support

If you encounter issues during installation:

1. **Check Logs:**
   ```bash
   tail -f ~/frappe-bench/logs/[site-name].log
   ```

2. **Contact Support:**
   - Email: support@minimax.com
   - GitHub Issues: [Create Issue](https://github.com/minimax/rnd_warehouse_management/issues)
   - Documentation: [Wiki](https://github.com/minimax/rnd_warehouse_management/wiki)

3. **Community:**
   - ERPNext Forum: [Discuss](https://discuss.erpnext.com)
   - Frappe Community: [Community Portal](https://frappe.io/community)

---

**Installation completed successfully? Check out the [Usage Guide](docs/USAGE.md) for next steps!**