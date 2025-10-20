# RND Warehouse Management

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![ERPNext](https://img.shields.io/badge/ERPNext-v15+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)

A professional warehouse management system for ERPNext with SAP-style movement types, dual-signature workflows, and comprehensive Red/Green zone logic for efficient material handling and production planning.

## 🎆 Features

### 🏢 SAP Movement Type Integration
- **261 (FrontFlush)**: Goods Issue for Production with warehouse supervisor approval
- **311 (BackFlush)**: Transfer for Kitting with dual-signature approval workflow
- Automated warehouse type validation and material flow control

### ✍️ Dual-Signature Approval Workflow
- **Warehouse Supervisor**: First-level approval for all material movements
- **Kitting Supervisor**: Second-level approval for SAP 311 movements
- Digital signature capture with timestamp tracking
- Role-based permissions and workflow state management

### 🟢🔴 Red/Green Zone Logic
- **Red Zone**: Incomplete material availability - Work Orders cannot proceed
- **Green Zone**: All materials available - Work Orders ready for production
- Real-time material completion percentage calculation
- Automated zone status updates based on stock availability

### 📜 GI/GT Slip Generation
- Professional print format with signature display
- Automated slip numbering and generation
- Email integration for slip distribution
- Mobile-responsive design for field operations

### 🏦 Advanced Warehouse Management
- **Warehouse Types**: Raw Material, Work In Progress, Finished Goods, Transit, Rejected
- **Transit Warehouses**: Virtual tracking for materials in movement
- **Temperature Control**: Optional temperature monitoring for sensitive materials
- **Capacity Management**: Warehouse utilization tracking and alerts

### 📊 Reporting & Analytics
- Daily warehouse utilization reports
- Material shortage analysis
- Zone status trending
- Approval workflow metrics

## 🚀 Quick Start

### Prerequisites

- ERPNext v15.0 or higher
- Frappe Framework v15.0 or higher
- Python 3.8 or higher
- Active ERPNext instance with administrator access

### Installation

1. **Get the app from GitHub**
   ```bash
   cd ~/frappe-bench
   bench get-app https://github.com/minimax/rnd_warehouse_management.git
   ```

2. **Install on your site**
   ```bash
   bench --site [your-site-name] install-app rnd_warehouse_management
   ```

3. **Restart and migrate**
   ```bash
   bench restart
   bench --site [your-site-name] migrate
   ```

4. **Clear cache and build assets**
   ```bash
   bench --site [your-site-name] clear-cache
   bench build
   ```

### Quick Configuration

1. **Assign Roles**
   - Go to User Management → Role Assignment
   - Assign "Warehouse Supervisor" role to warehouse staff
   - Assign "Kitting Supervisor" role to kitting staff
   - Assign "Zone Manager" role to production planners

2. **Configure Warehouses**
   - Set warehouse types (Raw Material, Work In Progress, Finished Goods, etc.)
   - Configure transit warehouses for material movement tracking
   - Set up temperature control settings if required

3. **Test Workflow**
   - Create a test Stock Entry with SAP Movement Type
   - Verify signature capture and approval workflow
   - Generate and review GI/GT Slip output

## 📋 Usage Guide

### Creating SAP-Style Stock Entries

1. **Navigate to Stock → Stock Entry**
2. **Select Purpose**: Material Issue (261) or Material Transfer (311)
3. **Choose SAP Movement Type**: 
   - Select "261 (FrontFlush)" for goods issue to production
   - Select "311 (BackFlush)" for kitting transfers
4. **Link Work Order**: Associate with relevant Work Order for zone tracking
5. **Add Items**: Select items and specify source/target warehouses
6. **Save and Submit**: Follow the dual-signature approval workflow

### Approval Workflow Process

1. **Draft State**: Initial creation by Stock User or Warehouse Supervisor
2. **Warehouse Approval**: Warehouse Supervisor provides digital signature
3. **Kitting Approval** (SAP 311 only): Kitting Supervisor provides second signature
4. **Final Submission**: System automatically submits and generates GI/GT Slip

### Zone Status Management

1. **Work Order Creation**: System automatically sets to Red Zone
2. **Material Assessment**: Real-time calculation of material availability
3. **Zone Transition**: Automatic Red → Green when all materials available
4. **Production Planning**: Use Green Zone status to prioritize Work Orders

### GI/GT Slip Generation

1. **Automatic Generation**: Created upon final approval
2. **Print Options**: Use "Print GI/GT Slip" button for formatted output
3. **Email Distribution**: Send via email to relevant stakeholders
4. **Mobile Access**: Responsive design for field operations

## 🔧 Configuration

### Warehouse Setup

```python
# Recommended warehouse hierarchy
Company
├── Raw Materials Division
│   ├── Raw Material Main (Type: Raw Material)
│   ├── Raw Material Transit (Type: Transit)
│   └── Raw Material Rejected (Type: Rejected)
├── Production Division
│   ├── Production WIP (Type: Work In Progress)
│   ├── Kitting Area (Type: Work In Progress)
│   ├── Production Transit (Type: Transit)
│   └── Production Rejected (Type: Rejected)
└── Finished Goods Division
    ├── FG Main (Type: Finished Goods)
    ├── FG to Sell (Type: Finished Goods)
    ├── FG Transit (Type: Transit)
    └── FG Rejected (Type: Rejected)
```

### Role Permissions

| Role | Stock Entry | Work Order | Warehouse | Workflow Actions |
|------|-------------|------------|-----------|------------------|
| Warehouse Supervisor | Create, Read, Write, Submit | Read | Read, Write | Warehouse Approve |
| Kitting Supervisor | Read, Write, Submit | Read | Read | Kitting Approve |
| Zone Manager | Read | Read, Write | Read | View Reports |
| Stock User | Create, Read, Write | Read | Read | Submit for Approval |

### SAP Movement Type Configuration

```json
{
  "261": {
    "name": "FrontFlush - Goods Issue for Production",
    "purpose": "Material Issue",
    "required_signatures": ["warehouse_supervisor"],
    "allowed_source_types": ["Raw Material", "Work In Progress"],
    "allowed_target_types": ["Work In Progress", "Production WIP"]
  },
  "311": {
    "name": "BackFlush - Transfer for Kitting",
    "purpose": "Material Transfer",
    "required_signatures": ["warehouse_supervisor", "kitting_supervisor"],
    "allowed_source_types": ["Work In Progress"],
    "allowed_target_types": ["Work In Progress", "Kitting Area"]
  }
}
```

## 🔌 API Reference

### Server-Side Methods

#### Work Order Zone Status
```python
# Update Work Order zone status
frappe.call({
    method: 'rnd_warehouse_management.warehouse_management.work_order.update_work_order_zone_status',
    args: { work_order_name: 'WO-001' }
})

# Get material status
frappe.call({
    method: 'rnd_warehouse_management.warehouse_management.work_order.get_work_order_material_status',
    args: { work_order_name: 'WO-001' }
})
```

#### Warehouse Management
```python
# Create warehouse hierarchy
frappe.call({
    method: 'rnd_warehouse_management.warehouse_management.warehouse.create_warehouse_hierarchy',
    args: { company: 'Your Company', locations: ['AMB-W'] }
})

# Get warehouse dashboard data
frappe.call({
    method: 'rnd_warehouse_management.warehouse_management.warehouse.get_warehouse_dashboard_data',
    args: { warehouse: 'Warehouse Name' }
})
```

#### Custom Stock Entry
```python
# Create custom stock entry with SAP movement type
frappe.call({
    method: 'rnd_warehouse_management.warehouse_management.stock_entry.make_custom_stock_entry',
    args: { work_order: 'WO-001', purpose: 'Material Issue', qty: 10 }
})
```

### Client-Side Hooks

#### Stock Entry Form Events
```javascript
// SAP Movement Type change
frappe.ui.form.on('Stock Entry', {
    custom_sap_movement_type: function(frm) {
        // Validates movement type and updates UI
    }
});

// Signature capture
frappe.ui.form.on('Stock Entry', {
    custom_warehouse_supervisor_signature: function(frm) {
        // Handles signature timestamp and validation
    }
});
```

## 📈 Monitoring & Maintenance

### Scheduled Tasks

- **Hourly**: Update Work Order zone status
- **Daily**: Clean up expired signatures, generate warehouse reports
- **Weekly**: Send warehouse utilization summaries

### Log Monitoring

```bash
# Check app-specific logs
bench --site [site-name] logs

# Monitor zone status updates
grep "Zone status" ~/frappe-bench/logs/[site-name].log

# Track signature workflow
grep "Signature" ~/frappe-bench/logs/[site-name].log
```

### Performance Optimization

1. **Database Indexing**: Ensure proper indexes on custom fields
2. **Cache Management**: Clear cache after configuration changes
3. **Background Jobs**: Monitor queue for scheduled tasks
4. **Image Storage**: Optimize signature image compression

## 🔄 Migration & Updates

### Version Updates

```bash
# Update from GitHub
cd ~/frappe-bench/apps/rnd_warehouse_management
git pull origin main

# Update site
cd ~/frappe-bench
bench --site [site-name] migrate
bench restart
```

### Data Migration

The app includes automatic migration patches:
- **v1.0.0**: Setup warehouse types, create workflows, update existing data
- Custom fields are automatically added via fixtures
- Existing Stock Entries are updated with default SAP movement types

## 🐛 Troubleshooting

### Common Issues

#### Signature Fields Not Showing
```bash
# Clear cache and reload
bench --site [site-name] clear-cache
bench --site [site-name] reload-doctype "Stock Entry"
```

#### Workflow Not Working
```bash
# Check workflow status
bench --site [site-name] console
>>> frappe.get_doc("Workflow", "Stock Entry Dual Signature Approval")
```

#### Zone Status Not Updating
```bash
# Manually trigger zone status update
bench --site [site-name] execute rnd_warehouse_management.warehouse_management.tasks.update_zone_status
```

#### Permission Issues
```bash
# Reset permissions
bench --site [site-name] console
>>> frappe.clear_cache()
>>> frappe.db.commit()
```

### Debug Mode

```python
# Enable debug logging in hooks.py
logger = frappe.logger("rnd_warehouse_management", file_count=5)
logger.setLevel(frappe.logging.DEBUG)
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Fork and clone
git clone https://github.com/your-username/rnd_warehouse_management.git
cd rnd_warehouse_management

# Create development branch
git checkout -b feature/your-feature-name

# Install in development mode
cd ~/frappe-bench
bench get-app ~/path/to/rnd_warehouse_management
bench --site development.localhost install-app rnd_warehouse_management
```

### Testing

```bash
# Run tests
bench --site [site-name] run-tests --app rnd_warehouse_management

# Test specific module
bench --site [site-name] run-tests --app rnd_warehouse_management --module rnd_warehouse_management.tests.test_stock_entry
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📧 Support

For support, please contact:
- **Email**: support@minimax.com
- **GitHub Issues**: [Create an issue](https://github.com/minimax/rnd_warehouse_management/issues)
- **Documentation**: [Wiki](https://github.com/minimax/rnd_warehouse_management/wiki)

## 🚀 Roadmap

### Version 1.1.0 (Planned)
- [ ] Mobile app integration
- [ ] Barcode scanning support
- [ ] Advanced analytics dashboard
- [ ] Multi-language support
- [ ] API rate limiting

### Version 1.2.0 (Planned)
- [ ] IoT sensor integration
- [ ] Machine learning for demand forecasting
- [ ] Advanced reporting engine
- [ ] Integration with external WMS systems

## 🔗 Related Projects

- [ERPNext](https://github.com/frappe/erpnext) - The main ERP system
- [Frappe Framework](https://github.com/frappe/frappe) - The underlying framework

## 📊 Statistics

![GitHub stars](https://img.shields.io/github/stars/minimax/rnd_warehouse_management)
![GitHub forks](https://img.shields.io/github/forks/minimax/rnd_warehouse_management)
![GitHub issues](https://img.shields.io/github/issues/minimax/rnd_warehouse_management)
![GitHub pull requests](https://img.shields.io/github/issues-pr/minimax/rnd_warehouse_management)

---

**Built with ❤️ by MiniMax Agent for the ERPNext Community**