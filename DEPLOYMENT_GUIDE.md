# RND Warehouse Management - Deployment Guide

## Production Deployment Checklist

### Pre-Deployment Preparation

#### 1. Environment Setup

```bash
# Create production site
cd ~/frappe-bench
bench new-site production.company.com --admin-password [strong-password]

# Install required apps
bench --site production.company.com install-app erpnext
```

#### 2. Get the App

```bash
# Option A: From GitHub (recommended)
cd ~/frappe-bench
bench get-app https://github.com/minimax/rnd_warehouse_management.git --branch v1.0.0

# Option B: From local directory
bench get-app /path/to/rnd_warehouse_management
```

#### 3. Install on Site

```bash
# Install the app
bench --site production.company.com install-app rnd_warehouse_management

# Verify installation
bench --site production.company.com list-apps
```

### Configuration

#### 4. Basic Configuration

```bash
# Enable production mode
bench --site production.company.com set-config developer_mode 0

# Set DNS
bench --site production.company.com add-to-hosts

# Configure email
bench --site production.company.com set-config mail_server smtp.company.com
bench --site production.company.com set-config mail_port 587
bench --site production.company.com set-config use_ssl 1
```

#### 5. Security Configuration

```bash
# Enable HTTPS
bench --site production.company.com enable-scheduler
bench setup lets-encrypt production.company.com

# Set session expiry (6 hours)
bench --site production.company.com set-config session_expiry "06:00:00"

# Disable developer mode (if not already done)
bench --site production.company.com set-config developer_mode 0
```

#### 6. Performance Optimization

```bash
# Enable Redis cache
bench --site production.company.com set-config redis_cache "redis://localhost:6379"

# Set workers for production
bench setup supervisor --yes
bench setup nginx --yes

# Restart services
sudo supervisorctl restart all
sudo service nginx reload
```

### Database Optimization

#### 7. Create Indexes

```sql
-- Connect to database
mysql -u [user] -p [database_name]

-- Add performance indexes
CREATE INDEX idx_stock_ledger_item_warehouse_date 
ON `tabStock Ledger Entry` (item_code, warehouse, posting_date);

CREATE INDEX idx_bin_warehouse_item 
ON `tabBin` (warehouse, item_code);

CREATE INDEX idx_work_order_status_zone 
ON `tabWork Order` (status, custom_current_zone_status);

CREATE INDEX idx_stock_entry_movement_type
ON `tabStock Entry` (custom_sap_movement_type, docstatus);

-- Verify indexes
SHOW INDEX FROM `tabStock Ledger Entry`;
```

### Initial Data Setup

#### 8. Configure Roles and Permissions

```python
# In ERPNext console
bench --site production.company.com console

# Create and assign roles
import frappe

# Create custom roles (if not already created)
for role in ["Warehouse Supervisor", "Kitting Supervisor", "Zone Manager"]:
    if not frappe.db.exists("Role", role):
        role_doc = frappe.get_doc({
            "doctype": "Role",
            "role_name": role,
            "desk_access": 1
        })
        role_doc.insert()

frappe.db.commit()
```

#### 9. Set Up Warehouses

```python
# Configure warehouse hierarchy
from rnd_warehouse_management.warehouse_management.warehouse import create_warehouse_hierarchy

create_warehouse_hierarchy(
    company="Your Company Name",
    locations=["Main Warehouse", "Production Floor", "Raw Materials"]
)
```

#### 10. Configure SAP Movement Types

```python
# Set up SAP movement type configurations
import frappe

# Add to site configuration if needed
frappe.db.set_value("System Settings", None, "enable_custom_sap_types", 1)
frappe.db.commit()
```

### Testing

#### 11. Functional Testing

```bash
# Run automated tests
bench --site production.company.com run-tests --app rnd_warehouse_management

# Test specific modules
bench --site production.company.com run-tests --app rnd_warehouse_management --module warehouse_management.stock_entry
```

#### 12. Manual Testing Checklist

- [ ] Create Stock Entry with SAP Movement Type 261
- [ ] Test Warehouse Supervisor signature capture
- [ ] Create Stock Entry with SAP Movement Type 311
- [ ] Test dual-signature workflow
- [ ] Verify GI/GT Slip generation
- [ ] Test Work Order zone status updates
- [ ] Verify material assessment calculations
- [ ] Test inventory turnover reports
- [ ] Verify stock aging analysis
- [ ] Test reorder suggestions
- [ ] Verify warehouse dashboard
- [ ] Test email notifications
- [ ] Verify mobile responsiveness
- [ ] Test API endpoints

### Monitoring Setup

#### 13. Configure Monitoring

```bash
# Set up log rotation
sudo nano /etc/logrotate.d/frappe-bench

# Add configuration:
/home/frappe/frappe-bench/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0644 frappe frappe
    sharedscripts
    postrotate
        supervisorctl restart frappe-bench-workers:
    endscript
}
```

#### 14. Set Up Scheduled Tasks Monitoring

```python
# Verify scheduled tasks
import frappe
from frappe.utils.scheduler import get_scheduled_jobs

jobs = get_scheduled_jobs()
print(jobs)

# Expected jobs:
# - rnd_warehouse_management.warehouse_management.tasks.update_zone_status (hourly)
# - rnd_warehouse_management.warehouse_management.tasks.cleanup_expired_signatures (daily)
# - rnd_warehouse_management.warehouse_management.tasks.generate_warehouse_reports (daily)
```

### Backup Configuration

#### 15. Automated Backups

```bash
# Set up automated backups
crontab -e

# Add daily backup at 2 AM
0 2 * * * cd /home/frappe/frappe-bench && /usr/local/bin/bench --site production.company.com backup --with-files

# Configure backup retention
bench --site production.company.com set-config backup_limit 30
```

#### 16. Backup Verification

```bash
# Test backup restoration
bench --site test-restore.company.com restore /path/to/backup.sql.gz

# Verify data integrity
bench --site test-restore.company.com console
>>> import frappe
>>> frappe.db.get_value("Stock Entry", {"docstatus": 1}, "name")
```

### Performance Tuning

#### 17. Database Optimization

```sql
-- Optimize tables
OPTIMIZE TABLE `tabStock Ledger Entry`;
OPTIMIZE TABLE `tabBin`;
OPTIMIZE TABLE `tabWork Order`;
OPTIMIZE TABLE `tabStock Entry`;

-- Analyze tables
ANALYZE TABLE `tabStock Ledger Entry`;
ANALYZE TABLE `tabBin`;
```

#### 18. Redis Configuration

```bash
# Edit redis configuration
sudo nano /etc/redis/redis.conf

# Recommended settings:
maxmemory 2gb
maxmemory-policy allkeys-lru

# Restart Redis
sudo service redis-server restart
```

### Go-Live

#### 19. Final Pre-Launch Checks

- [ ] All tests passing
- [ ] Backups configured and tested
- [ ] Monitoring in place
- [ ] SSL certificate installed
- [ ] DNS configured
- [ ] Email sending verified
- [ ] User accounts created
- [ ] Roles assigned
- [ ] Warehouses configured
- [ ] Print formats tested
- [ ] Performance tested under load
- [ ] Security audit completed

#### 20. Launch

```bash
# Clear all caches
bench --site production.company.com clear-cache
bench --site production.company.com clear-website-cache

# Build assets
bench build --app rnd_warehouse_management

# Restart all services
sudo supervisorctl restart all
sudo service nginx reload

# Verify everything is running
bench --site production.company.com doctor
```

### Post-Launch

#### 21. Monitoring

```bash
# Monitor logs in real-time
tail -f ~/frappe-bench/logs/production.company.com.log

# Monitor error logs
tail -f ~/frappe-bench/logs/production.company.com.error.log

# Monitor worker queues
bench --site production.company.com watch
```

#### 22. User Training

1. Conduct user training sessions
2. Provide documentation access
3. Set up support channels
4. Create user guides for:
   - Stock Entry creation
   - Signature workflow
   - Zone status management
   - Report generation

### Maintenance

#### Regular Maintenance Tasks

**Daily**
```bash
# Check error logs
tail -100 ~/frappe-bench/logs/*.error.log

# Verify scheduled tasks ran
grep "update_zone_status" ~/frappe-bench/logs/*.log
```

**Weekly**
```bash
# Database optimization
mysql -u [user] -p [database] -e "OPTIMIZE TABLE \`tabStock Ledger Entry\`;"

# Clear old logs
find ~/frappe-bench/logs -name "*.log" -mtime +30 -delete
```

**Monthly**
```bash
# Update dependencies
bench update --patch

# Verify backups
ls -lh ~/frappe-bench/sites/production.company.com/private/backups/

# Security audit
bench --site production.company.com console
>>> from frappe.core.doctype.user.user import get_all_users
>>> users = get_all_users()
>>> # Review user access
```

### Troubleshooting

#### Common Issues

**Issue: Signature not displaying**
```bash
# Clear cache
bench --site production.company.com clear-cache
bench build --app rnd_warehouse_management
```

**Issue: Zone status not updating**
```python
# Manual trigger
bench --site production.company.com execute rnd_warehouse_management.warehouse_management.tasks.update_zone_status
```

**Issue: Slow queries**
```sql
-- Enable slow query log
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 2;

-- Check slow queries
SELECT * FROM mysql.slow_log;
```

### Rollback Procedure

If issues arise post-deployment:

```bash
# 1. Restore from backup
bench --site production.company.com restore /path/to/backup.sql.gz --with-private-files /path/to/files.tar

# 2. Uninstall app if needed
bench --site production.company.com uninstall-app rnd_warehouse_management

# 3. Reinstall previous version
bench get-app https://github.com/minimax/rnd_warehouse_management.git --branch v0.9.0
bench --site production.company.com install-app rnd_warehouse_management

# 4. Migrate
bench --site production.company.com migrate
bench restart
```

### Support

For deployment support:
- **Documentation**: [GitHub Wiki](https://github.com/minimax/rnd_warehouse_management/wiki)
- **Issues**: [GitHub Issues](https://github.com/minimax/rnd_warehouse_management/issues)
- **Email**: support@minimax.com

---

**Deployment Checklist Complete**: ✅  
**Production Ready**: ✅  
**Support Available**: ✅
