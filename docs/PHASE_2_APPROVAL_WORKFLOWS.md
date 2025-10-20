# Phase 2: Enhanced Stock Entry Workflows - Implementation Documentation

## Overview

Phase 2 introduces a comprehensive, multi-level approval workflow system with full audit trails and intelligent notifications for Stock Entry management.

## What's New in Phase 2

### 1. Stock Entry Approval Rule DocType

**Purpose**: Configurable approval routing based on movement types and conditions

**Key Features**:
- **Multi-Level Approvals**: Support for up to 5 approval levels
- **Role-Based Authorization**: Assign approvals by role or specific user
- **Conditional Logic**: Python expressions for dynamic approval requirements
- **Escalation Management**: Configurable escalation timeframes
- **Sequential/Parallel**: Flexible approval sequencing

**Location**:
```
rnd_warehouse_management/warehouse_management/doctype/stock_entry_approval_rule/
├── stock_entry_approval_rule.json      # DocType definition
├── stock_entry_approval_rule.py        # Server-side logic
├── stock_entry_approval_rule.js        # Client-side logic
└── test_stock_entry_approval_rule.py   # Unit tests
```

**Key Fields**:
- `movement_type` (Link): Movement Type Master reference
- `approval_level` (Int): 1-5 approval level
- `approver_role` (Link): Required role for approval
- `approver_user` (Link): Specific user (optional)
- `approval_sequence` (Select): Sequential or Parallel
- `escalation_days` (Int): Days before escalation
- `conditional_logic` (Code): Python expression for conditional approval
- `enabled` (Check): Active status

**API Functions**:
```python
get_approval_rules_for_movement_type(movement_type, stock_entry_data=None)
get_next_approvers(movement_type, current_level=0, stock_entry_data=None)
evaluate_conditional_logic(conditional_logic, stock_entry_data)
```

### 2. Stock Entry Audit Log DocType

**Purpose**: Comprehensive, read-only audit trail for all Stock Entry events

**Key Features**:
- **Complete Event Tracking**: All changes, approvals, signatures logged
- **User Context**: User, role, IP address captured
- **Field-Level Changes**: Before/after values for modifications
- **Approval History**: Complete approval chain with timestamps
- **Signature Storage**: Digital signature data retention
- **Additional Context**: JSON data for extended information

**Location**:
```
rnd_warehouse_management/warehouse_management/doctype/stock_entry_audit_log/
├── stock_entry_audit_log.json      # DocType definition
├── stock_entry_audit_log.py        # Server-side logic
├── stock_entry_audit_log.js        # Client-side logic
└── test_stock_entry_audit_log.py   # Unit tests
```

**Event Types**:
- Created
- Modified
- Submitted
- Cancelled
- Approval Requested
- Approval Granted
- Approval Rejected
- Signature Added
- Escalated
- Comment Added

**API Functions**:
```python
create_audit_log(stock_entry, event_type, **kwargs)
get_audit_trail(stock_entry, event_type=None)
get_approval_history(stock_entry)
get_field_change_history(stock_entry, field_name=None)
log_stock_entry_event(stock_entry, event_type, **kwargs)
```

### 3. Enhanced Stock Entry Custom Fields

**New Fields Added**:

**Approval Workflow Status Section**:
- `custom_approval_status` (Select): Current approval state
  - Draft
  - Pending Level 1-5
  - Level 1-5 Approved
  - Fully Approved
  - Rejected
- `custom_current_approval_level` (Int): Current approval level (0-5)
- `custom_pending_approver` (Link): User awaiting action
- `custom_approval_requested_on` (Datetime): When approval was requested

**Comments & Rejection**:
- `custom_approval_comments` (Text Editor): Approval comment history
- `custom_rejection_reason` (Long Text): Rejection details

### 4. Approval Workflow API

**New Whitelisted Functions** in `stock_entry.py`:

#### Request Approval
```python
@frappe.whitelist()
def request_approval(stock_entry_name)
```
- Initiates approval workflow
- Validates movement type requires approval
- Determines first-level approvers
- Sends notifications
- Creates audit log entry

**Returns**:
```json
{
  "success": true,
  "message": "Approval request sent to 2 approvers",
  "approvers": [{"user": "user@example.com", "role": "Warehouse Manager", ...}]
}
```

#### Approve Stock Entry
```python
@frappe.whitelist()
def approve_stock_entry(stock_entry_name, comments=None, signature_data=None)
```
- Approves at current level
- Validates approver permissions
- Progresses to next level or marks fully approved
- Sends notifications to next approvers
- Creates audit log entries

**Returns**:
```json
{
  "success": true,
  "message": "Stock Entry approved at Level 2",
  "approval_status": "Level 2 Approved",
  "next_approvers": [...]
}
```

#### Reject Stock Entry
```python
@frappe.whitelist()
def reject_stock_entry(stock_entry_name, rejection_reason)
```
- Rejects stock entry
- Validates approver permissions
- Records rejection reason
- Notifies creator
- Creates audit log entry

#### Get Pending Approvals
```python
@frappe.whitelist()
def get_pending_approvals(user=None)
```
- Returns all pending approvals for a user
- Filters by user's approval permissions
- Used for approval dashboard

**Returns**:
```json
[
  {
    "name": "MAT-STE-2025-00001",
    "posting_date": "2025-10-20",
    "custom_sap_movement_type": "261",
    "custom_approval_status": "Pending Level 1",
    "custom_current_approval_level": 0,
    "custom_pending_approver": "approver@example.com"
  }
]
```

#### Get Approval Summary
```python
@frappe.whitelist()
def get_approval_summary(stock_entry_name)
```
- Complete approval status and history
- Configured approval rules
- User's approval permission

**Returns**:
```json
{
  "current_status": "Level 1 Approved",
  "current_level": 1,
  "pending_approver": "manager@example.com",
  "total_levels": 2,
  "approval_rules": [...],
  "approval_history": [...],
  "can_approve": false
}
```

## Installation & Migration

### For Fresh Installation:

```bash
# Get the app
bench get-app rnd_warehouse_management

# Install on site
bench --site your-site install-app rnd_warehouse_management
```

Phase 2 features will be automatically available.

### For Upgrading from v2.0.0 (Phase 1):

```bash
# Pull latest code
cd apps/rnd_warehouse_management
git pull

# Run migrations
bench --site your-site migrate

# Install new fixtures
bench --site your-site install-app rnd_warehouse_management

# Clear cache
bench --site your-site clear-cache
bench --site your-site clear-website-cache

# Rebuild assets
bench build --app rnd_warehouse_management

# Restart
bench restart
```

### Data Migration Notes:

**Backward Compatibility**: All Phase 1 functionality remains intact. Existing Stock Entries will:
- Have `custom_approval_status` default to "Draft"
- Continue to use Phase 1 dual-signature workflow
- Not require Phase 2 approval unless explicitly configured

## Configuration Guide

### Setting Up Approval Rules

#### Example 1: Simple Two-Level Approval

**Requirement**: Movement Type 261 requires Warehouse Supervisor (Level 1) and Warehouse Manager (Level 2) approval.

**Setup**:

1. **Create Level 1 Rule**:
   - Navigate to: **Stock > Stock Entry Approval Rule > New**
   - Movement Type: 261
   - Approval Level: 1
   - Approver Role: Warehouse Supervisor
   - Approval Sequence: Sequential
   - Escalation Days: 2
   - Enabled: Yes

2. **Create Level 2 Rule**:
   - Movement Type: 261
   - Approval Level: 2
   - Approver Role: Warehouse Manager
   - Approval Sequence: Sequential
   - Escalation Days: 3
   - Enabled: Yes

#### Example 2: Conditional Approval Based on Value

**Requirement**: Movement Type 311 requires manager approval only if total value > $10,000.

**Setup**:

1. **Create Conditional Rule**:
   - Movement Type: 311
   - Approval Level: 1
   - Approver Role: Warehouse Manager
   - Conditional Logic:
     ```python
     stock_entry.total_value > 10000
     ```
   - Enabled: Yes

#### Example 3: Specific User Assignment

**Requirement**: High-value adjustments require approval from CFO (specific user).

**Setup**:

1. **Create User-Specific Rule**:
   - Movement Type: 701
   - Approval Level: 1
   - Approver Role: Director
   - Approver User: cfo@company.com
   - Conditional Logic:
     ```python
     stock_entry.total_value > 50000
     ```
   - Enabled: Yes

### Conditional Logic Examples

**Based on Total Value**:
```python
stock_entry.total_value > 25000
```

**Based on Warehouse**:
```python
'Finished Goods' in str(stock_entry.to_warehouse)
```

**Based on Item Quantity**:
```python
any(item.qty > 1000 for item in stock_entry.items)
```

**Based on Purpose**:
```python
stock_entry.purpose == 'Material Issue'
```

**Multiple Conditions**:
```python
stock_entry.total_value > 10000 and stock_entry.purpose == 'Material Transfer'
```

## Workflow Examples

### Scenario 1: Standard Multi-Level Approval

**Setup**: Movement Type 261 requires 2 levels of approval.

**Workflow**:

1. **User Creates Stock Entry**:
   - Selects Movement Type 261
   - Fills in details
   - Clicks "Request Approval" button

2. **System Actions**:
   - Sets status to "Pending Level 1"
   - Identifies Level 1 approvers (Warehouse Supervisors)
   - Sends email notifications
   - Creates audit log entry

3. **Level 1 Approver**:
   - Receives email notification
   - Opens Stock Entry
   - Reviews details
   - Clicks "Approve" and adds comments

4. **System Actions**:
   - Sets status to "Level 1 Approved"
   - Sets status to "Pending Level 2"
   - Identifies Level 2 approvers (Warehouse Managers)
   - Sends notifications
   - Creates audit log entries

5. **Level 2 Approver**:
   - Receives notification
   - Reviews and approves

6. **System Actions**:
   - Sets status to "Fully Approved"
   - User can now submit the Stock Entry
   - Final audit log created

### Scenario 2: Rejection and Rework

**Workflow**:

1. User creates and requests approval
2. Level 1 approver reviews
3. Approver finds issue and clicks "Reject"
4. Enters rejection reason
5. System:
   - Sets status to "Rejected"
   - Notifies creator
   - Creates audit log
6. Creator:
   - Receives rejection notification
   - Reviews reason
   - Modifies Stock Entry
   - Re-requests approval
7. Workflow starts again from Level 1

## Testing Guide

### Unit Tests

Run the test suite:
```bash
# Test Approval Rule DocType
bench --site your-site run-tests --app rnd_warehouse_management --doctype "Stock Entry Approval Rule"

# Test Audit Log DocType
bench --site your-site run-tests --app rnd_warehouse_management --doctype "Stock Entry Audit Log"
```

### Manual Testing Checklist

**Test 1: Create Approval Rules**
- [ ] Create approval rule for Movement Type 261, Level 1
- [ ] Create approval rule for Movement Type 261, Level 2
- [ ] Verify rules are active
- [ ] Verify duplicate rule validation works

**Test 2: Request Approval**
- [ ] Create Stock Entry with Movement Type 261
- [ ] Click "Request Approval"
- [ ] Verify status changes to "Pending Level 1"
- [ ] Verify notification sent to approver
- [ ] Verify audit log created

**Test 3: Approve at Level 1**
- [ ] Login as Level 1 approver
- [ ] Open pending Stock Entry
- [ ] Click "Approve" with comments
- [ ] Verify status changes to "Level 1 Approved"
- [ ] Verify status changes to "Pending Level 2"
- [ ] Verify notification sent to Level 2 approver
- [ ] Verify audit logs created

**Test 4: Approve at Level 2 (Final)**
- [ ] Login as Level 2 approver
- [ ] Approve Stock Entry
- [ ] Verify status changes to "Fully Approved"
- [ ] Verify Stock Entry can now be submitted
- [ ] Verify audit trail is complete

**Test 5: Rejection Workflow**
- [ ] Create and request approval
- [ ] Login as approver
- [ ] Click "Reject" with reason
- [ ] Verify status changes to "Rejected"
- [ ] Verify rejection reason is saved
- [ ] Verify creator receives notification
- [ ] Verify audit log created

**Test 6: Conditional Approval**
- [ ] Create approval rule with conditional logic
- [ ] Create Stock Entry that meets condition
- [ ] Verify approval is required
- [ ] Create Stock Entry that doesn't meet condition
- [ ] Verify approval is not required

**Test 7: Audit Trail**
- [ ] Create Stock Entry and go through approval workflow
- [ ] View Audit Log list for the Stock Entry
- [ ] Verify all events are logged
- [ ] Verify timestamps are correct
- [ ] Verify user/role information is captured
- [ ] Verify signature data is stored (if applicable)

**Test 8: Get Pending Approvals**
- [ ] Create multiple Stock Entries with approvals pending
- [ ] Call `get_pending_approvals()` API
- [ ] Verify only entries where user can approve are returned
- [ ] Verify filtering by role works correctly

**Test 9: Backward Compatibility**
- [ ] Create Stock Entry with Movement Type 261 (from Phase 1)
- [ ] Verify Phase 1 dual-signature workflow still works
- [ ] Verify no conflicts with Phase 2 approval workflow
- [ ] Verify existing Stock Entries are not affected

## Performance Considerations

**Database Indexing**:
- `Stock Entry`: Indexed on `custom_approval_status`, `custom_pending_approver`
- `Stock Entry Audit Log`: Indexed on `stock_entry`, `event_type`, `event_timestamp`
- `Stock Entry Approval Rule`: Indexed on `movement_type`, `approval_level`

**Caching**:
- Approval rules are cached per movement type
- Cache invalidation on rule update
- User role cache for permission checks

**Best Practices**:
1. **Limit Approval Levels**: Keep approval levels to 3 or fewer for optimal performance
2. **Conditional Logic**: Keep conditional logic simple to avoid execution delays
3. **Audit Log Cleanup**: Implement periodic cleanup for old audit logs (>2 years)
4. **Notification Batching**: For high-volume scenarios, batch notifications

## Security & Permissions

**Role-Based Access**:
- **System Manager**: Full access to all approval rules and audit logs
- **Warehouse Manager**: Create/modify approval rules, view audit logs
- **Stock User**: View approval rules, view own audit logs
- **Auditor**: Read-only access to all audit logs

**Data Security**:
- Audit logs are immutable (no edit/delete permissions)
- Signature data is encrypted before storage
- IP addresses logged for compliance
- All approval actions require valid user session

## Troubleshooting

### Issue: Approval request fails

**Symptoms**: Error when clicking "Request Approval"

**Possible Causes**:
1. No approval rules configured
2. Movement Type doesn't require approval
3. Conditional logic evaluation error

**Solution**:
1. Check approval rules exist: Stock Entry Approval Rule list
2. Verify Movement Type Master `requires_approval` is checked
3. Review conditional logic syntax
4. Check error logs: `bench --site your-site console`

### Issue: Approver not receiving notifications

**Symptoms**: Email notifications not delivered

**Possible Causes**:
1. Email settings not configured
2. `send_notification` unchecked in approval rule
3. User email address not set

**Solution**:
1. Configure email settings in ERPNext
2. Verify approval rule has `send_notification` checked
3. Verify user has valid email address
4. Check email queue: Email Queue list

### Issue: Audit log not created

**Symptoms**: Events not appearing in audit trail

**Possible Causes**:
1. Permission issue
2. Database error

**Solution**:
1. Check error logs
2. Verify Stock Entry Audit Log DocType exists
3. Verify user has create permission (should use `ignore_permissions=True`)

## API Reference

### Python API

#### Request Approval
```python
import frappe

result = frappe.call(
    'rnd_warehouse_management.warehouse_management.stock_entry.request_approval',
    stock_entry_name='MAT-STE-2025-00001'
)
```

#### Approve Stock Entry
```python
result = frappe.call(
    'rnd_warehouse_management.warehouse_management.stock_entry.approve_stock_entry',
    stock_entry_name='MAT-STE-2025-00001',
    comments='Approved - all items verified',
    signature_data='data:image/png;base64,...'
)
```

#### Reject Stock Entry
```python
result = frappe.call(
    'rnd_warehouse_management.warehouse_management.stock_entry.reject_stock_entry',
    stock_entry_name='MAT-STE-2025-00001',
    rejection_reason='Incorrect warehouse selected'
)
```

#### Get Pending Approvals
```python
pending = frappe.call(
    'rnd_warehouse_management.warehouse_management.stock_entry.get_pending_approvals',
    user='approver@company.com'
)
```

### JavaScript API

#### Request Approval
```javascript
frappe.call({
    method: 'rnd_warehouse_management.warehouse_management.stock_entry.request_approval',
    args: {
        stock_entry_name: frm.doc.name
    },
    callback: function(r) {
        if (r.message.success) {
            frappe.msgprint(r.message.message);
            frm.reload_doc();
        }
    }
});
```

#### Approve
```javascript
frappe.call({
    method: 'rnd_warehouse_management.warehouse_management.stock_entry.approve_stock_entry',
    args: {
        stock_entry_name: frm.doc.name,
        comments: 'Approved',
        signature_data: signature_image_data
    },
    callback: function(r) {
        if (r.message.success) {
            frappe.msgprint(r.message.message);
            frm.reload_doc();
        }
    }
});
```

## Next Steps

**Phase 2 Completed Features**:
- ✅ Multi-level approval workflow system
- ✅ Comprehensive audit trail
- ✅ Conditional approval logic
- ✅ Email notifications
- ✅ Backward compatibility with Phase 1

**Remaining Phase 2 Tasks** (Optional Enhancements):
- [ ] Task 5: Approval Dashboard (Custom Page)
- [ ] Task 6: Enhanced Client-Side UX (workflow visualization)
- [ ] Task 7: Escalation Logic (scheduled task)

**Future Phases**:
- Phase 3: Automatic Transfer Rules Engine
- Phase 4: Barcode/QR Scanning System
- Phase 5: Mobile PWA Development
- Phase 6: Red/Green Zone Management System
- Phase 7: Enhanced Reporting & Analytics

## Version History

**v2.1.0 (Phase 2) - 2025-10-20**
- Introduced Stock Entry Approval Rule DocType
- Introduced Stock Entry Audit Log DocType
- Added multi-level approval workflow
- Added comprehensive audit trail
- Added email notifications
- Added conditional approval logic
- Added 9 new custom fields to Stock Entry
- Added 10 new whitelisted API functions
- 100% backward compatible with Phase 1

**v2.0.0 (Phase 1) - 2025-10-20**
- Movement Type Master system
- 46 pre-loaded SAP movement types
- Dynamic validation and signatures

**v1.0.0 - Previous**
- Hardcoded movement types 261/311
- Basic dual-signature workflow

## Support & Documentation

For additional support:
- Review the main README.md
- Check docs/API.md for API reference
- Check docs/PHASE_1_MOVEMENT_TYPE_MASTER_IMPLEMENTATION.md for Phase 1 details
- Consult the Frappe Framework documentation: https://docs.frappe.io
- ERPNext Stock Module documentation: https://docs.erpnext.com/docs/user/manual/en/stock
