# Testing Guide - RND Warehouse Management

## Overview

This guide covers all testing aspects of the RND Warehouse Management application, including unit tests, integration tests, and end-to-end testing procedures.

## Test Environment Setup

### Prerequisites

```bash
# Create test site
bench new-site test.localhost --admin-password admin

# Install ERPNext
bench --site test.localhost install-app erpnext

# Install RND Warehouse Management
bench --site test.localhost install-app rnd_warehouse_management

# Set test config
bench --site test.localhost set-config developer_mode 1
bench --site test.localhost clear-cache
```

### Test Data Setup

```python
# Run in bench console
bench --site test.localhost console

import frappe
from rnd_warehouse_management.tests.test_data import setup_test_data

setup_test_data()
frappe.db.commit()
```

## Running Tests

### All Tests

```bash
# Run all tests for the app
bench --site test.localhost run-tests --app rnd_warehouse_management

# Run with coverage
bench --site test.localhost run-tests --app rnd_warehouse_management --coverage

# Run in parallel (faster)
bench --site test.localhost run-tests --app rnd_warehouse_management --parallel
```

### Specific Test Modules

```bash
# Test stock entry functionality
bench --site test.localhost run-tests --module rnd_warehouse_management.tests.test_stock_entry

# Test work order zone status
bench --site test.localhost run-tests --module rnd_warehouse_management.tests.test_work_order

# Test warehouse management
bench --site test.localhost run-tests --module rnd_warehouse_management.tests.test_warehouse

# Test utility functions
bench --site test.localhost run-tests --module rnd_warehouse_management.tests.test_utils
```

### Specific Test Cases

```bash
# Run specific test class
bench --site test.localhost run-tests --module rnd_warehouse_management.tests.test_stock_entry --test TestStockEntrySignature

# Run specific test method
bench --site test.localhost run-tests --module rnd_warehouse_management.tests.test_stock_entry --test TestStockEntrySignature.test_warehouse_supervisor_signature
```

## Unit Tests

### Stock Entry Tests

**File**: `rnd_warehouse_management/tests/test_stock_entry.py`

```python
import frappe
import unittest
from frappe.utils import now_datetime

class TestStockEntrySignature(unittest.TestCase):
    """Test signature validation and workflow"""
    
    def setUp(self):
        self.stock_entry = create_test_stock_entry()
    
    def test_warehouse_supervisor_signature_required(self):
        """Test that warehouse supervisor signature is required for SAP 261"""
        self.stock_entry.custom_sap_movement_type = "261"
        
        # Should fail without signature
        self.assertRaises(frappe.ValidationError, self.stock_entry.submit)
        
        # Should pass with signature
        self.stock_entry.custom_warehouse_supervisor_signature = "base64_image_data"
        self.stock_entry.submit()
        self.assertEqual(self.stock_entry.docstatus, 1)
    
    def test_dual_signature_for_311(self):
        """Test that both signatures are required for SAP 311"""
        self.stock_entry.custom_sap_movement_type = "311"
        
        # Fail with only warehouse signature
        self.stock_entry.custom_warehouse_supervisor_signature = "base64_image_data"
        self.assertRaises(frappe.ValidationError, self.stock_entry.submit)
        
        # Pass with both signatures
        self.stock_entry.custom_kitting_supervisor_signature = "base64_image_data_2"
        self.stock_entry.submit()
        self.assertEqual(self.stock_entry.docstatus, 1)
```

### Work Order Zone Status Tests

**File**: `rnd_warehouse_management/tests/test_work_order.py`

```python
class TestWorkOrderZoneStatus(unittest.TestCase):
    """Test zone status calculation and updates"""
    
    def test_red_zone_insufficient_materials(self):
        """Test Red Zone status when materials are insufficient"""
        work_order = create_test_work_order()
        update_work_order_zone_status(work_order.name)
        
        work_order.reload()
        self.assertEqual(work_order.custom_current_zone_status, "Red Zone")
        self.assertLess(work_order.custom_material_completion_percentage, 100)
    
    def test_green_zone_sufficient_materials(self):
        """Test Green Zone status when all materials are available"""
        work_order = create_test_work_order_with_stock()
        update_work_order_zone_status(work_order.name)
        
        work_order.reload()
        self.assertEqual(work_order.custom_current_zone_status, "Green Zone")
        self.assertEqual(work_order.custom_material_completion_percentage, 100)
```

### Utility Functions Tests

**File**: `rnd_warehouse_management/tests/test_utils.py`

```python
class TestMaterialAssessment(unittest.TestCase):
    """Test material assessment utility functions"""
    
    def test_get_material_assessment_status(self):
        """Test material assessment status calculation"""
        from rnd_warehouse_management.warehouse_management.utils import get_material_assessment_status
        
        result = get_material_assessment_status("TEST-ITEM-001")
        
        self.assertEqual(result["status"], "success")
        self.assertIn("zone_status", result)
        self.assertIn("completion_percentage", result)
    
    def test_get_inventory_turnover(self):
        """Test inventory turnover calculation"""
        from rnd_warehouse_management.warehouse_management.utils import get_inventory_turnover
        
        result = get_inventory_turnover("Stores - TC")
        
        self.assertEqual(result["status"], "success")
        self.assertIn("average_turnover_ratio", result)
    
    def test_get_stock_aging_report(self):
        """Test stock aging report generation"""
        from rnd_warehouse_management.warehouse_management.utils import get_stock_aging_report
        
        result = get_stock_aging_report("Stores - TC", days_threshold=30)
        
        self.assertEqual(result["status"], "success")
        self.assertIn("aging_categories", result)
    
    def test_get_reorder_suggestions(self):
        """Test reorder suggestions logic"""
        from rnd_warehouse_management.warehouse_management.utils import get_reorder_suggestions
        
        result = get_reorder_suggestions("Stores - TC")
        
        self.assertEqual(result["status"], "success")
        self.assertIn("suggestions", result)
```

## Integration Tests

### End-to-End Workflow Tests

```python
class TestCompleteWorkflow(unittest.TestCase):
    """Test complete SAP movement type workflow"""
    
    def test_sap_261_complete_workflow(self):
        """Test complete workflow for SAP 261 movement"""
        # 1. Create Stock Entry
        stock_entry = create_stock_entry_261()
        stock_entry.insert()
        
        # 2. Add warehouse signature
        stock_entry.custom_warehouse_supervisor_signature = get_test_signature()
        stock_entry.save()
        
        # 3. Submit
        stock_entry.submit()
        
        # 4. Verify GI/GT slip generated
        self.assertTrue(stock_entry.custom_gi_gt_slip_number)
        
        # 5. Verify Work Order zone status updated
        if stock_entry.custom_work_order_reference:
            wo = frappe.get_doc("Work Order", stock_entry.custom_work_order_reference)
            self.assertIn(wo.custom_current_zone_status, ["Red Zone", "Green Zone"])
```

## Manual Testing Procedures

### Test Case 1: Stock Entry with SAP 261

**Objective**: Verify SAP 261 (FrontFlush) functionality

**Steps**:
1. Login as user with "Stock User" role
2. Navigate to Stock > Stock Entry > New
3. Select Purpose: "Material Issue"
4. Select SAP Movement Type: "261 (FrontFlush)"
5. Link Work Order
6. Add items from Raw Material warehouse
7. Set target warehouse as WIP
8. Save
9. Add Warehouse Supervisor signature
10. Submit

**Expected Results**:
- Stock Entry created successfully
- Zone status calculated correctly
- GI/GT slip generated
- Work Order zone status updated

### Test Case 2: Dual Signature Workflow (SAP 311)

**Objective**: Verify dual signature requirement

**Steps**:
1. Create Stock Entry with SAP 311
2. Add Warehouse Supervisor signature
3. Attempt to submit (should fail)
4. Add Kitting Supervisor signature
5. Submit

**Expected Results**:
- Submission fails without both signatures
- Submission succeeds with both signatures
- Both signatures visible in print format

### Test Case 3: Zone Status Calculation

**Objective**: Verify Red/Green zone logic

**Steps**:
1. Create Work Order with BOM
2. Check initial zone status (should be Red)
3. Create Stock Entry to add materials
4. Check zone status update
5. Add all required materials
6. Verify Green Zone status

**Expected Results**:
- Initial status: Red Zone
- Partial materials: Red Zone with completion %
- All materials: Green Zone with 100% completion

## Performance Testing

### Load Testing

```python
import time
import frappe

def test_material_assessment_performance():
    """Test performance of material assessment"""
    from rnd_warehouse_management.warehouse_management.utils import get_material_assessment_status
    
    start = time.time()
    
    for i in range(100):
        result = get_material_assessment_status(f"ITEM-{i:03d}")
    
    end = time.time()
    avg_time = (end - start) / 100
    
    print(f"Average time per assessment: {avg_time:.3f}s")
    assert avg_time < 0.5, "Material assessment too slow"
```

### Database Query Optimization

```sql
-- Monitor query performance
SET profiling = 1;

-- Run your query
SELECT * FROM `tabStock Ledger Entry` 
WHERE item_code = 'ITEM-001' AND warehouse = 'Stores - TC';

-- Check profile
SHOW PROFILES;
SHOW PROFILE FOR QUERY 1;
```

## API Testing

### Using cURL

```bash
# Test material assessment endpoint
curl -X POST "http://test.localhost:8000/api/method/rnd_warehouse_management.warehouse_management.utils.get_material_assessment_status" \
  -H "Authorization: token api_key:api_secret" \
  -d "material_code=ITEM-001"

# Test inventory turnover endpoint
curl -X POST "http://test.localhost:8000/api/method/rnd_warehouse_management.warehouse_management.utils.get_inventory_turnover" \
  -H "Authorization: token api_key:api_secret" \
  -d "warehouse=Stores - TC&period_days=365"
```

### Using Python Requests

```python
import requests
import json

api_key = "your_api_key"
api_secret = "your_api_secret"
base_url = "http://test.localhost:8000"

def test_api_endpoints():
    headers = {
        "Authorization": f"token {api_key}:{api_secret}"
    }
    
    # Test material assessment
    response = requests.post(
        f"{base_url}/api/method/rnd_warehouse_management.warehouse_management.utils.get_material_assessment_status",
        headers=headers,
        data={"material_code": "ITEM-001"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["message"]["status"] == "success"
```

## Test Coverage

### Generate Coverage Report

```bash
# Install coverage
pip install coverage

# Run tests with coverage
coverage run --source=rnd_warehouse_management -m pytest rnd_warehouse_management/tests/

# Generate report
coverage report
coverage html

# View HTML report
open htmlcov/index.html
```

### Target Coverage

- **Minimum**: 80% code coverage
- **Target**: 90% code coverage
- **Critical paths**: 100% coverage (signatures, zone status, material assessment)

## Continuous Integration

### GitHub Actions Workflow

See `.github/workflows/test.yml` for automated testing on push/PR.

## Test Data Cleanup

```python
# Clean up test data
def cleanup_test_data():
    frappe.db.sql("DELETE FROM `tabStock Entry` WHERE custom_sap_movement_type LIKE 'TEST%'")
    frappe.db.sql("DELETE FROM `tabWork Order` WHERE name LIKE 'TEST-WO%'")
    frappe.db.commit()
```

## Reporting Issues

When reporting test failures:

1. Include test name and module
2. Provide full error traceback
3. Include environment details (ERPNext version, Python version)
4. Attach relevant logs
5. Provide steps to reproduce

---

**Testing Checklist**: ✅ Complete  
**Coverage Target**: ≥90%  
**CI/CD**: Automated
