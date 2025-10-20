# Usage Guide

This comprehensive guide covers all aspects of using the RND Warehouse Management system in ERPNext.

## Table of Contents

1. [Getting Started](#getting-started)
2. [SAP Movement Types](#sap-movement-types)
3. [Dual-Signature Workflow](#dual-signature-workflow)
4. [Zone Status Management](#zone-status-management)
5. [GI/GT Slip Operations](#gigt-slip-operations)
6. [Warehouse Management](#warehouse-management)
7. [Reporting & Analytics](#reporting--analytics)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

## Getting Started

### Dashboard Overview

After installation, you'll see enhanced dashboards with:
- **Zone Status Indicators**: Red/Green zone work orders
- **Pending Approvals**: Stock entries awaiting signatures
- **Material Shortages**: Items requiring attention
- **Warehouse Utilization**: Capacity and usage metrics

### User Roles

**Warehouse Supervisor**
- Create and approve Stock Entries
- Provide first-level signatures
- Manage warehouse operations
- View zone status reports

**Kitting Supervisor**
- Provide second-level signatures for SAP 311 movements
- Approve material transfers to kitting
- Manage kitting area operations
- Monitor green zone transitions

**Zone Manager**
- Monitor Work Order zone status
- Analyze material completion rates
- Generate shortage reports
- Plan production based on green zone availability

**Stock User**
- Create Stock Entries
- Submit for supervisor approval
- Update material movements
- View assigned warehouse data

## SAP Movement Types

### 261 (FrontFlush) - Goods Issue for Production

**Purpose**: Issue materials from storage to production

**Workflow**:
1. Create Stock Entry with Purpose: "Material Issue"
2. Select SAP Movement Type: "261 (FrontFlush)"
3. Link to Work Order (optional but recommended)
4. Add items from Raw Material warehouses to WIP warehouses
5. Submit for warehouse supervisor approval
6. Warehouse supervisor provides digital signature
7. System automatically submits and generates GI/GT slip

**Example Scenario**:
```
Scenario: Issue steel plates for manufacturing
Source: Raw Material Main - AMB-W
Target: Production WIP - AMB-W
Work Order: WO-2024-001
Required Signature: Warehouse Supervisor only
```

**Validation Rules**:
- Source warehouse must be "Raw Material" or "Work In Progress" type
- Target warehouse must be "Work In Progress" type
- Warehouse supervisor signature required
- Purpose must be "Material Issue"

### 311 (BackFlush) - Transfer for Kitting

**Purpose**: Transfer materials from production to kitting area

**Workflow**:
1. Create Stock Entry with Purpose: "Material Transfer"
2. Select SAP Movement Type: "311 (BackFlush)"
3. Link to Work Order for zone tracking
4. Add items from WIP warehouses to Kitting warehouses
5. Submit for warehouse supervisor approval
6. Warehouse supervisor provides digital signature
7. Submit for kitting supervisor approval
8. Kitting supervisor provides digital signature
9. System submits and generates GI/GT slip

**Example Scenario**:
```
Scenario: Transfer assembled components for final kitting
Source: Production WIP - AMB-W
Target: Kitting Area - AMB-W
Work Order: WO-2024-001
Required Signatures: Warehouse Supervisor + Kitting Supervisor
```

**Validation Rules**:
- Source warehouse must be "Work In Progress" type
- Target warehouse must be "Work In Progress" or "Kitting" type
- Both warehouse and kitting supervisor signatures required
- Purpose must be "Material Transfer"

## Dual-Signature Workflow

### Workflow States

1. **Draft**: Initial creation by user
2. **Pending Warehouse Approval**: Awaiting warehouse supervisor signature
3. **Warehouse Approved**: First signature obtained
4. **Kitting Approved**: Final approval (SAP 311 only)
5. **Rejected**: Returned for revision

### Signature Process

**For Warehouse Supervisors**:
1. Navigate to Stock Entry list
2. Filter by "Pending Warehouse Approval"
3. Open Stock Entry
4. Review items and warehouses
5. Scroll to "Dual Signature Approval" section
6. Click in "Warehouse Supervisor Signature" field
7. Provide digital signature using stylus or finger
8. Click "Warehouse Approve" action
9. Confirm approval

**For Kitting Supervisors** (SAP 311 only):
1. Filter Stock Entries by "Warehouse Approved"
2. Open Stock Entry
3. Verify warehouse supervisor signature
4. Review kitting requirements
5. Provide signature in "Kitting Supervisor Signature" field
6. Click "Kitting Approve" action
7. Confirm final approval

### Signature Validation

- Signatures are timestamped automatically
- Empty signatures are rejected
- Role validation ensures proper authority
- Audit trail maintained for compliance

## Zone Status Management

### Understanding Zone Status

**Red Zone** 🔴
- Incomplete material availability
- Work Order cannot proceed with production
- Material shortages require attention
- Displayed with red color coding

**Green Zone** 🟢
- All materials available for production
- Work Order ready to begin
- 100% material completion achieved
- Displayed with green color coding

### Zone Status Calculation

**Automatic Calculation**:
1. System reads Work Order BOM requirements
2. Checks actual stock in specified warehouses
3. Calculates availability percentage
4. Updates zone status based on threshold:
   - 100% availability = Green Zone
   - < 100% availability = Red Zone

**Manual Updates**:
```python
# Via API call
frappe.call({
    method: 'rnd_warehouse_management.warehouse_management.work_order.update_work_order_zone_status',
    args: { work_order_name: 'WO-2024-001' }
})
```

### Zone Status Monitoring

**Dashboard Indicators**:
- Work Order list shows zone status column
- Color-coded badges for quick identification
- Completion percentage displayed
- Last update timestamp

**Material Status Details**:
1. Open Work Order
2. Click "Check Material Status" button
3. Review detailed material availability
4. Identify specific shortages
5. Plan procurement or production accordingly

### Zone Transitions

**Red to Green Transition**:
- Triggered by stock replenishment
- Automatic when all materials available
- Email notifications to production team
- Work Order becomes production-ready

**Green to Red Transition**:
- Occurs when materials consumed
- Stock falls below BOM requirements
- Immediate notification to procurement
- Production planning adjustment needed

## GI/GT Slip Operations

### Automatic Generation

**When Generated**:
- Upon final workflow approval
- Unique slip number assigned (GI-GT-XXXXX)
- Timestamp recorded
- Available for printing and email

**Slip Contents**:
- Document information (ID, date, time)
- SAP movement type with description
- Work Order reference and zone status
- Complete item details with quantities
- Source and target warehouse information
- Digital signatures with timestamps
- Company branding and footer

### Printing Options

**Standard Print**:
1. Open approved Stock Entry
2. Click "Print" dropdown
3. Select "GI/GT Slip with Signatures"
4. Choose print or PDF download

**Bulk Printing**:
1. Go to Stock Entry list
2. Select multiple approved entries
3. Use "Actions" > "Print" > "GI/GT Slip with Signatures"
4. Generate batch PDF

### Email Distribution

**Single Email**:
1. Open Stock Entry
2. Click "Email GI/GT Slip" button
3. Select recipients
4. Add custom message
5. Send with PDF attachment

**Automated Email**:
- Configure email templates
- Set up automatic distribution lists
- Schedule daily/weekly slip summaries

### Mobile Access

**Responsive Design**:
- Optimized for tablet and phone viewing
- Touch-friendly signature capture
- Readable on small screens
- Offline PDF generation

## Warehouse Management

### Warehouse Types

**Raw Material**
- Stores incoming materials and components
- Source for SAP 261 movements
- Requires temperature control for sensitive items
- Links to purchase orders and receipts

**Work In Progress**
- Items currently being manufactured
- Intermediate storage during production
- Source and target for various movements
- Includes kitting and assembly areas

**Finished Goods**
- Completed products ready for sale
- Target for production completion
- Source for sales and delivery
- Quality inspection integration

**Transit**
- Virtual warehouses for movement tracking
- Ensures no inventory "disappears" during transfers
- Temporary holding during approvals
- Audit trail for material movements

**Rejected**
- Defective or non-conforming materials
- Requires quality review before disposal
- Separate tracking for compliance
- Integration with quality management

### Warehouse Configuration

**Basic Setup**:
1. Go to Stock > Warehouse
2. Create new warehouse
3. Set warehouse type from dropdown
4. Configure parent warehouse if hierarchical
5. Set company association
6. Save configuration

**Advanced Settings**:

**Temperature Control**:
```
☑️ Temperature Control
Target Temperature: 20°C
```

**Capacity Management**:
```
Maximum Capacity: 10000 (units/value)
Current Utilization: Auto-calculated
```

**Zone Configuration**:
```
☑️ Is Zone Warehouse
Zone Type: Red Zone / Green Zone
```

### Transit Warehouse Setup

**Purpose**: Track materials during movement between physical locations

**Configuration**:
1. Create warehouse with "Transit" type
2. Name format: "[Source] Transit - [Location]"
3. Set parent as source warehouse
4. Configure in source warehouse's "Default In-Transit Warehouse"
5. Do not set as group warehouse

**Example Setup**:
```
Raw Material Main - AMB-W
└── Default In-Transit: Raw Material Transit - AMB-W

Production WIP - AMB-W
└── Default In-Transit: Production Transit - AMB-W
```

## Reporting & Analytics

### Standard Reports

**Zone Status Report**:
- Current zone distribution (Red vs Green)
- Work Order completion rates
- Material shortage analysis
- Trend analysis over time

**Signature Audit Report**:
- Approval timeline tracking
- Supervisor activity monitoring
- Workflow bottleneck identification
- Compliance documentation

**Warehouse Utilization**:
- Capacity vs current usage
- Temperature compliance tracking
- Movement frequency analysis
- Storage efficiency metrics

### Custom Dashboards

**Production Planning Dashboard**:
```python
# Create custom dashboard
from frappe.desk.page.setup_wizard.setup_wizard import make_records

dashboard_data = {
    "doctype": "Dashboard",
    "dashboard_name": "Warehouse Management",
    "charts": [
        {
            "chart_name": "Zone Status Distribution",
            "chart_type": "Donut",
            "source": "Work Order",
            "filters": {"custom_current_zone_status": ["in", ["Red Zone", "Green Zone"]]}
        }
    ]
}
```

### Automated Reports

**Daily Summary Email**:
- Pending approvals count
- Zone status changes
- Material shortages
- Warehouse utilization alerts

**Weekly Analysis**:
- Approval workflow performance
- Zone transition trends
- Signature compliance rates
- Warehouse efficiency metrics

## Best Practices

### Workflow Efficiency

1. **Batch Processing**:
   - Group similar movements together
   - Process multiple Stock Entries simultaneously
   - Schedule regular approval sessions

2. **Signature Management**:
   - Use consistent signature styles
   - Provide signatures promptly
   - Maintain signature quality for readability

3. **Zone Status Monitoring**:
   - Check zone status before production planning
   - Address red zones immediately
   - Maintain buffer stock for critical items

### Data Accuracy

1. **Stock Entry Creation**:
   - Always link to Work Orders when applicable
   - Use correct SAP movement types
   - Verify warehouse types before submission

2. **Material Management**:
   - Keep BOM data updated
   - Maintain accurate stock levels
   - Regular cycle counting

3. **Quality Control**:
   - Review all entries before approval
   - Verify item quantities and warehouses
   - Check for data consistency

### Performance Optimization

1. **System Maintenance**:
   - Regular cache clearing
   - Database index optimization
   - Periodic signature cleanup

2. **User Training**:
   - Comprehensive role-based training
   - Regular refresher sessions
   - Best practice documentation

## Troubleshooting

### Common Issues

**Signature Not Capturing**:
```javascript
// Check browser compatibility
if (!('PointerEvent' in window)) {
    alert('Your browser may not support signature capture');
}

// Clear browser cache
// Update browser to latest version
// Try different device if persistent
```

**Zone Status Not Updating**:
```python
# Manual zone status refresh
frappe.call({
    method: 'rnd_warehouse_management.warehouse_management.work_order.update_work_order_zone_status',
    args: { work_order_name: 'WO-XXXX' }
})
```

**Workflow Stuck**:
```bash
# Check workflow state
bench --site [site] console
>>> doc = frappe.get_doc("Stock Entry", "SE-XXXX")
>>> print(doc.workflow_state)
>>> print(doc.docstatus)

# Reset if needed
>>> doc.workflow_state = "Draft"
>>> doc.save()
```

**Print Format Issues**:
```bash
# Reload print format
bench --site [site] console
>>> frappe.reload_doctype("Print Format")
>>> frappe.clear_cache()
```

### Error Resolution

**Permission Denied**:
1. Check user roles
2. Verify role permissions
3. Clear cache and re-login
4. Contact system administrator

**Missing Custom Fields**:
1. Check app installation
2. Run migration if needed
3. Reload DocTypes
4. Restart services

**Workflow Errors**:
1. Verify workflow configuration
2. Check role assignments
3. Review transition conditions
4. Test with admin user

### Getting Help

**Documentation**:
- [Installation Guide](INSTALLATION.md)
- [API Reference](API.md)
- [Configuration Guide](CONFIGURATION.md)

**Support Channels**:
- Email: support@minimax.com
- GitHub: [Issues](https://github.com/minimax/rnd_warehouse_management/issues)
- Community: [ERPNext Forum](https://discuss.erpnext.com)

**Training Resources**:
- Video tutorials (coming soon)
- Webinar sessions
- User manual downloads
- Best practice guides

---

**Need more help? Check our [FAQ](FAQ.md) or contact support!**