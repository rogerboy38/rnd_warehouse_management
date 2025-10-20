# Phase 2 Testing Guide - Quick Start

## Pre-Test Setup

### 1. Deploy the Application

**For Fresh Installation**:
```bash
bench get-app rnd_warehouse_management
bench --site your-site install-app rnd_warehouse_management
bench restart
```

**For Upgrading from Phase 1**:
```bash
cd apps/rnd_warehouse_management
git pull
bench --site your-site migrate
bench --site your-site clear-cache
bench build --app rnd_warehouse_management
bench restart
```

### 2. Create Test Users

Create the following test users with appropriate roles:

1. **Warehouse Supervisor** (Level 1 Approver)
   - Email: supervisor@test.com
   - Roles: Stock User, Warehouse Supervisor

2. **Warehouse Manager** (Level 2 Approver)
   - Email: manager@test.com
   - Roles: Stock User, Warehouse Manager

3. **Stock User** (Entry Creator)
   - Email: stockuser@test.com
   - Roles: Stock User

### 3. Configure Email (Optional but Recommended)

- Setup > Email > Email Account
- Configure SMTP settings for testing notifications

## Test Scenario 1: Basic Two-Level Approval Workflow

### Step 1: Create Approval Rules

1. Navigate to: **Stock > Stock Entry Approval Rule > New**

2. **Create Level 1 Rule**:
   - Movement Type: 261
   - Approval Level: 1
   - Approver Role: Warehouse Supervisor
   - Approval Sequence: Sequential
   - Escalation Days: 2
   - Send Notification: ✓
   - Enabled: ✓
   - **Save**

3. **Create Level 2 Rule**:
   - Movement Type: 261
   - Approval Level: 2
   - Approver Role: Warehouse Manager
   - Approval Sequence: Sequential
   - Escalation Days: 3
   - Send Notification: ✓
   - Enabled: ✓
   - **Save**

### Step 2: Create Stock Entry (as Stock User)

1. Login as: **stockuser@test.com**
2. Navigate to: **Stock > Stock Entry > New**
3. Fill in:
   - SAP Movement Type: 261
   - Purpose: Material Issue (auto-filled)
   - Posting Date: Today
   - Add items as needed
4. **Save** (Do NOT submit yet)
5. Click **"Request Approval"** button (under Approval menu)
6. Verify:
   - ✅ Approval Status changes to "Pending Level 1"
   - ✅ Success message displayed
   - ✅ Email sent to supervisor@test.com
   - ✅ Workflow timeline appears showing Level 1 pending

### Step 3: Test Approval Dashboard

1. Login as: **supervisor@test.com**
2. Navigate to: **Stock > Approval Dashboard**
3. Verify:
   - ✅ Statistics show 1 pending approval
   - ✅ Entry appears in "Pending Approvals" tab
   - ✅ Urgency badge shows "Low" (< 1 day)
   - ✅ Entry details displayed correctly

### Step 4: Approve at Level 1 (from Dashboard)

1. Still as supervisor, in Approval Dashboard:
2. Click **"Approve"** button on the entry
3. Enter comments: "Level 1 approved - all items verified"
4. Click **"Approve"**
5. Verify:
   - ✅ Success alert displayed
   - ✅ Entry disappears from pending list
   - ✅ Statistics updated
   - ✅ Email sent to manager@test.com

### Step 5: Verify Timeline Update

1. Login as: **stockuser@test.com**
2. Open the Stock Entry
3. Verify:
   - ✅ Approval Status: "Level 1 Approved"
   - ✅ Workflow timeline shows:
     - Level 1: Green checkmark, "Approved", with supervisor name and comments
     - Level 2: Orange clock icon, "Pending"

### Step 6: Approve at Level 2 (from Form)

1. Login as: **manager@test.com**
2. Open the Stock Entry
3. Verify:
   - ✅ "Approve" button visible in Approval menu
4. Click **"Approve"**
5. Enter comments: "Final approval granted"
6. Click **"Approve"**
7. Verify:
   - ✅ Approval Status: "Fully Approved"
   - ✅ Workflow timeline shows both levels green
   - ✅ Can now submit the Stock Entry

### Step 7: Verify Audit Trail

1. Navigate to: **Stock > Stock Entry Audit Log**
2. Filter by the Stock Entry name
3. Verify all events logged:
   - ✅ "Approval Requested" (Level 1)
   - ✅ "Approval Granted" (Level 1) by supervisor
   - ✅ "Approval Requested" (Level 2)
   - ✅ "Approval Granted" (Level 2) by manager
4. Click "View Approval History" in Stock Entry
5. Verify complete history displays in table format

## Test Scenario 2: Rejection Workflow

### Step 1: Create Another Stock Entry

1. Login as: **stockuser@test.com**
2. Create new Stock Entry with Movement Type 261
3. Request approval

### Step 2: Reject at Level 1

1. Login as: **supervisor@test.com**
2. Open Approval Dashboard
3. Click **"Reject"** on the entry
4. Enter rejection reason: "Incorrect warehouse selected - please update and resubmit"
5. Click **"Reject"**
6. Verify:
   - ✅ Approval Status: "Rejected"
   - ✅ Entry disappears from pending approvals
   - ✅ Email sent to stockuser@test.com

### Step 3: Verify Rejection

1. Login as: **stockuser@test.com**
2. Open the Stock Entry
3. Verify:
   - ✅ Approval Status: "Rejected"
   - ✅ Rejection Reason displayed
   - ✅ Workflow timeline shows red X on Level 1
   - ✅ Approval Comments show rejection reason

### Step 4: Resubmit After Fix

1. Still as stockuser:
2. Make necessary corrections
3. **Save**
4. Click **"Request Approval"** again
5. Verify:
   - ✅ Status resets to "Pending Level 1"
   - ✅ Workflow restarts from Level 1
   - ✅ Audit log shows new "Approval Requested" event

## Test Scenario 3: Auto-Escalation

### Step 1: Create Rule with Immediate Escalation

1. Navigate to existing Level 1 Rule for Movement Type 261
2. Edit and set: **Escalation Days = 0** (for immediate testing)
3. **Save**

### Step 2: Create Stock Entry and Request Approval

1. Login as: **stockuser@test.com**
2. Create Stock Entry with Movement Type 261
3. Request approval
4. Note the entry name (e.g., MAT-STE-2025-00003)

### Step 3: Manually Run Escalation Task

```bash
bench --site your-site execute rnd_warehouse_management.warehouse_management.stock_entry.check_and_escalate_overdue_approvals
```

### Step 4: Verify Escalation

1. Check email inbox:
   - ✅ Reminder email sent to supervisor@test.com
   - ✅ Escalation email sent to manager@test.com (next level)
   - ✅ Email subject contains "REMINDER" or "Escalation"

2. Check Audit Log:
   - ✅ "Escalated" event logged
   - ✅ Escalation reason recorded

## Test Scenario 4: Bulk Approve

### Step 1: Create Multiple Stock Entries

1. Login as: **stockuser@test.com**
2. Create 3 Stock Entries with Movement Type 261
3. Request approval for all 3

### Step 2: Bulk Approve from Dashboard

1. Login as: **supervisor@test.com**
2. Open Approval Dashboard
3. Click **"Select All"** button
4. Verify all 3 entries are checked
5. Click **"Bulk Approve"** icon in page header
6. Confirm the action
7. Verify:
   - ✅ Success message shows count (e.g., "Approved: 3, Failed: 0")
   - ✅ All entries disappear from pending list
   - ✅ All entries progress to Level 2

## Test Scenario 5: Conditional Approval

### Step 1: Create Conditional Rule

1. Navigate to: **Stock Entry Approval Rule > New**
2. Fill in:
   - Movement Type: 311
   - Approval Level: 1
   - Approver Role: Warehouse Manager
   - Conditional Logic:
     ```python
     stock_entry.total_amount > 10000
     ```
   - Enabled: ✓
3. **Save**

### Step 2: Test Low Value Entry (No Approval)

1. Create Stock Entry with Movement Type 311
2. Ensure total_amount < 10000
3. Verify:
   - ✅ No approval required (condition not met)
   - ✅ Can submit directly

### Step 3: Test High Value Entry (Approval Required)

1. Create Stock Entry with Movement Type 311
2. Ensure total_amount > 10000
3. Verify:
   - ✅ "Request Approval" button appears
   - ✅ Cannot submit without approval
4. Request approval
5. Verify:
   - ✅ Approval workflow starts (condition met)

## Test Scenario 6: Filtering in Dashboard

1. Login as: **supervisor@test.com**
2. Open Approval Dashboard
3. Test Movement Type filter:
   - Select Movement Type: 261
   - Verify: Only 261 entries displayed
4. Test Date Range filter:
   - Set From Date: Last week
   - Set To Date: Today
   - Verify: Only entries within date range displayed
5. Switch to "My History" tab
6. Verify:
   - ✅ All your past approvals/rejections displayed
   - ✅ Sortable by date
   - ✅ Shows movement type, action, status, comments

## Test Scenario 7: Mobile Responsiveness

1. Open Approval Dashboard on mobile device or resize browser to mobile width
2. Verify:
   - ✅ Statistics cards stack vertically
   - ✅ Approval cards display correctly
   - ✅ Buttons remain clickable
   - ✅ Timeline in Stock Entry form adapts to narrow screen

## Test Scenario 8: View Approval History

1. Open any Stock Entry that has gone through approval
2. Click **"View Approval History"** (under Approval menu)
3. Verify:
   - ✅ Modal dialog displays
   - ✅ Complete approval history in table format
   - ✅ Shows: Date/Time, Event, Level, User, Status, Comments
   - ✅ Color-coded status (green = approved, red = rejected)

## Quick Verification Checklist

After completing the test scenarios, verify:

### Core Functionality
- [ ] Approval rules can be created for any Movement Type
- [ ] Multi-level approvals work correctly
- [ ] Email notifications sent to approvers
- [ ] Approval status tracked accurately
- [ ] Audit trail complete for all actions

### Approval Dashboard
- [ ] Statistics display correctly
- [ ] Pending approvals list accurate
- [ ] Filters work (movement type, date range)
- [ ] Bulk approve functional
- [ ] Approval history displays correctly
- [ ] Urgency indicators accurate

### Enhanced UX
- [ ] Workflow timeline displays on Stock Entry form
- [ ] Timeline updates in real-time after actions
- [ ] Approve/Reject buttons visible to authorized users
- [ ] Dialogs work (approve, reject, history)
- [ ] Status badges color-coded correctly

### Auto-Escalation
- [ ] Escalation task runs successfully
- [ ] Escalation emails sent correctly
- [ ] Reminder emails sent to current approver
- [ ] Escalation logged in audit trail
- [ ] Overdue approvals identified correctly

### Backward Compatibility
- [ ] Phase 1 dual-signature workflow still works
- [ ] Existing Stock Entries unaffected
- [ ] Movement Type Master system functional
- [ ] No errors in console or logs

## Troubleshooting

### Issue: Approval buttons not visible
**Solution**: 
- Clear browser cache
- Run: `bench build --app rnd_warehouse_management`
- Hard refresh browser (Ctrl+Shift+R)

### Issue: Email notifications not sent
**Solution**:
- Check Email Account configuration in ERPNext
- Verify SMTP settings
- Check Email Queue for errors
- Test with: Setup > Email > Email Account > Send Test Email

### Issue: Workflow timeline not displaying
**Solution**:
- Ensure custom fields are installed
- Run: `bench --site your-site migrate`
- Clear cache and rebuild

### Issue: Escalation task not running
**Solution**:
- Check scheduler status: `bench --site your-site scheduler status`
- Enable if disabled: `bench --site your-site scheduler enable`
- Manually run task to test:
  ```bash
  bench --site your-site execute rnd_warehouse_management.warehouse_management.stock_entry.check_and_escalate_overdue_approvals
  ```

### Issue: Approval Dashboard not accessible
**Solution**:
- Verify user has required role (Stock User, Warehouse Manager, or System Manager)
- Check page permissions: Stock Entry Approval Rule list
- Run: `bench --site your-site migrate`

## Console Commands for Testing

```bash
# Run escalation task manually
bench --site your-site execute rnd_warehouse_management.warehouse_management.stock_entry.check_and_escalate_overdue_approvals

# Check scheduler status
bench --site your-site scheduler status

# Enable scheduler
bench --site your-site scheduler enable

# View error logs
bench --site your-site console
# Then in console:
frappe.log_error()

# Clear all caches
bench --site your-site clear-cache
bench --site your-site clear-website-cache

# Rebuild assets
bench build --app rnd_warehouse_management

# Restart Frappe
bench restart
```

## Test Results Template

Use this template to document your test results:

```
## Test Results - Phase 2 Complete Implementation

**Date**: [Date]
**Site**: [Site Name]
**Tester**: [Your Name]
**Version**: 2.1.0

### Scenario 1: Basic Two-Level Approval
- Status: [ ] Pass [ ] Fail
- Issues: [List any issues]

### Scenario 2: Rejection Workflow
- Status: [ ] Pass [ ] Fail
- Issues: [List any issues]

### Scenario 3: Auto-Escalation
- Status: [ ] Pass [ ] Fail
- Issues: [List any issues]

### Scenario 4: Bulk Approve
- Status: [ ] Pass [ ] Fail
- Issues: [List any issues]

### Scenario 5: Conditional Approval
- Status: [ ] Pass [ ] Fail
- Issues: [List any issues]

### Scenario 6: Dashboard Filtering
- Status: [ ] Pass [ ] Fail
- Issues: [List any issues]

### Scenario 7: Mobile Responsiveness
- Status: [ ] Pass [ ] Fail
- Issues: [List any issues]

### Scenario 8: Approval History
- Status: [ ] Pass [ ] Fail
- Issues: [List any issues]

### Overall Result
- [ ] All tests passed - Ready for production
- [ ] Some tests failed - Review required
- [ ] Major issues found - Not ready

### Notes:
[Any additional observations or comments]
```

## Next Steps After Successful Testing

1. **Document any issues found** and report for fixes
2. **Create user training materials** (if needed)
3. **Deploy to production** following deployment instructions
4. **Configure production approval rules** based on business requirements
5. **Train end users** on new workflow
6. **Monitor for first week** and gather feedback
7. **Proceed to Phase 3** (Automatic Transfer Rules Engine) when ready

## Success Criteria

Phase 2 testing is considered successful when:

✅ All 8 test scenarios pass
✅ No console errors or warnings
✅ All email notifications delivered
✅ Audit trail complete for all actions
✅ Dashboard loads within 2 seconds
✅ Timeline displays correctly on all screen sizes
✅ Bulk operations complete successfully
✅ Escalation task runs without errors
✅ No regression in Phase 1 functionality
