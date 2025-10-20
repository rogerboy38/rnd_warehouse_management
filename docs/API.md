# API Reference

Complete API documentation for RND Warehouse Management system.

## Table of Contents

1. [Authentication](#authentication)
2. [Work Order APIs](#work-order-apis)
3. [Stock Entry APIs](#stock-entry-apis)
4. [Warehouse APIs](#warehouse-apis)
5. [Zone Status APIs](#zone-status-apis)
6. [Signature APIs](#signature-apis)
7. [Report APIs](#report-apis)
8. [Webhook Events](#webhook-events)
9. [Error Handling](#error-handling)

## Authentication

All API endpoints require ERPNext authentication. You can authenticate using:

- **Session Authentication**: Login via web interface
- **API Key/Secret**: Generate from ERPNext User settings
- **Token Authentication**: OAuth2 or JWT tokens

```python
# Using API Key/Secret
headers = {
    'Authorization': 'token api_key:api_secret',
    'Content-Type': 'application/json'
}

# Using session (browser)
# Automatically handled by frappe.call()
```

## Work Order APIs

### Update Zone Status

Recalculate and update Work Order zone status based on current material availability.

**Endpoint**: `POST /api/method/rnd_warehouse_management.warehouse_management.work_order.update_work_order_zone_status`

**Parameters**:
```json
{
    "work_order_name": "WO-2024-001"
}
```

**Response**:
```json
{
    "status": "success",
    "zone_status": "Green Zone",
    "completion_percentage": 100.0,
    "last_updated": "2024-01-15 10:30:00"
}
```

**Error Response**:
```json
{
    "status": "error",
    "message": "Work Order not found"
}
```

**Example Usage**:
```python
# Python
import requests

response = requests.post(
    'https://your-site.com/api/method/rnd_warehouse_management.warehouse_management.work_order.update_work_order_zone_status',
    json={'work_order_name': 'WO-2024-001'},
    headers=headers
)
data = response.json()
```

```javascript
// JavaScript (ERPNext client-side)
frappe.call({
    method: 'rnd_warehouse_management.warehouse_management.work_order.update_work_order_zone_status',
    args: {
        work_order_name: 'WO-2024-001'
    },
    callback: function(r) {
        if (r.message.status === 'success') {
            console.log('Zone status:', r.message.zone_status);
        }
    }
});
```

### Get Material Status

Get detailed material availability status for a Work Order.

**Endpoint**: `GET /api/method/rnd_warehouse_management.warehouse_management.work_order.get_work_order_material_status`

**Parameters**:
```json
{
    "work_order_name": "WO-2024-001"
}
```

**Response**:
```json
{
    "status": "success",
    "work_order": "WO-2024-001",
    "zone_status": "Red Zone",
    "completion_percentage": 75.5,
    "material_status": [
        {
            "item_code": "STEEL-PLATE-001",
            "item_name": "Steel Plate 10mm",
            "description": "High-grade steel plate",
            "required_qty": 100.0,
            "available_qty": 100.0,
            "shortage": 0.0,
            "warehouse": "Raw Material Main - AMB-W",
            "status": "Available"
        },
        {
            "item_code": "BOLT-M10",
            "item_name": "Bolt M10x50",
            "description": "Stainless steel bolt",
            "required_qty": 50.0,
            "available_qty": 30.0,
            "shortage": 20.0,
            "warehouse": "Raw Material Main - AMB-W",
            "status": "Shortage"
        }
    ]
}
```

## Stock Entry APIs

### Create Custom Stock Entry

Create a new Stock Entry with SAP movement type and Work Order reference.

**Endpoint**: `POST /api/method/rnd_warehouse_management.warehouse_management.stock_entry.make_custom_stock_entry`

**Parameters**:
```json
{
    "work_order": "WO-2024-001",
    "purpose": "Material Issue",
    "qty": 10.0
}
```

**Response**:
```json
{
    "doctype": "Stock Entry",
    "name": "SE-2024-001",
    "purpose": "Material Issue",
    "custom_sap_movement_type": "261",
    "custom_work_order_reference": "WO-2024-001",
    "items": [...],
    "workflow_state": "Draft"
}
```

### Validate SAP Requirements

Validate Stock Entry against SAP movement type requirements.

**Endpoint**: `POST /api/method/rnd_warehouse_management.warehouse_management.stock_entry.validate_sap_requirements`

**Parameters**:
```json
{
    "doc": {
        "name": "SE-2024-001",
        "custom_sap_movement_type": "261",
        "purpose": "Material Issue",
        "items": [...]
    }
}
```

**Response**:
```json
{
    "status": "success",
    "message": "All SAP movement requirements satisfied",
    "validations": {
        "purpose_valid": true,
        "warehouse_types_valid": true,
        "signatures_valid": true
    }
}
```

## Warehouse APIs

### Create Warehouse Hierarchy

Create a complete warehouse hierarchy for specified locations.

**Endpoint**: `POST /api/method/rnd_warehouse_management.warehouse_management.warehouse.create_warehouse_hierarchy`

**Parameters**:
```json
{
    "company": "AMB-Wellness",
    "locations": ["AMB-W", "AMB-E"]
}
```

**Response**:
```json
{
    "status": "success",
    "message": "Created 32 warehouses",
    "created_warehouses": [
        "Raw Material Main - AMB-W",
        "Raw Material Transit - AMB-W",
        "Production WIP - AMB-W",
        ...
    ]
}
```

### Get Warehouse Dashboard Data

Retrieve comprehensive warehouse utilization and status data.

**Endpoint**: `GET /api/method/rnd_warehouse_management.warehouse_management.warehouse.get_warehouse_dashboard_data`

**Parameters**:
```json
{
    "warehouse": "Raw Material Main - AMB-W"  // Optional - omit for all warehouses
}
```

**Response**:
```json
{
    "status": "success",
    "warehouses": [
        {
            "name": "Raw Material Main - AMB-W",
            "warehouse_type": "Raw Material",
            "is_group": 0,
            "parent_warehouse": null,
            "company": "AMB-Wellness",
            "custom_temperature_control": 1,
            "custom_target_temperature": 20.0,
            "item_count": 156,
            "total_qty": 2500.0,
            "total_value": 125000.0,
            "custom_current_utilization": 75.5,
            "custom_last_capacity_update": "2024-01-15 09:00:00"
        }
    ]
}
```

## Zone Status APIs

### Batch Zone Status Update

Update zone status for multiple Work Orders simultaneously.

**Endpoint**: `POST /api/method/rnd_warehouse_management.warehouse_management.tasks.update_zone_status`

**Parameters**: None (processes all active Work Orders)

**Response**:
```json
{
    "status": "success",
    "message": "Updated zone status for 25 Work Orders",
    "updated_work_orders": [
        {
            "work_order": "WO-2024-001",
            "old_status": "Red Zone",
            "new_status": "Green Zone",
            "completion_percentage": 100.0
        },
        {
            "work_order": "WO-2024-002",
            "old_status": "Green Zone",
            "new_status": "Red Zone",
            "completion_percentage": 85.0
        }
    ]
}
```

### Zone Status History

Get historical zone status changes for analysis.

**Endpoint**: `GET /api/method/rnd_warehouse_management.warehouse_management.reports.get_zone_status_history`

**Parameters**:
```json
{
    "work_order": "WO-2024-001",  // Optional - omit for all Work Orders
    "from_date": "2024-01-01",
    "to_date": "2024-01-31"
}
```

**Response**:
```json
{
    "status": "success",
    "history": [
        {
            "work_order": "WO-2024-001",
            "date": "2024-01-15",
            "time": "10:30:00",
            "zone_status": "Green Zone",
            "completion_percentage": 100.0,
            "changed_by": "Material Receipt",
            "stock_entry": "SE-2024-005"
        }
    ]
}
```

## Signature APIs

### Validate Signature

Validate digital signature data and metadata.

**Endpoint**: `POST /api/method/rnd_warehouse_management.warehouse_management.signatures.validate_signature`

**Parameters**:
```json
{
    "signature_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgA...",
    "document_type": "Stock Entry",
    "document_name": "SE-2024-001",
    "signature_type": "warehouse_supervisor"
}
```

**Response**:
```json
{
    "status": "success",
    "valid": true,
    "signature_info": {
        "format": "PNG",
        "size_bytes": 15680,
        "dimensions": "300x150",
        "quality_score": 0.85
    }
}
```

### Get Signature Audit Trail

Retrieve signature history for compliance and auditing.

**Endpoint**: `GET /api/method/rnd_warehouse_management.warehouse_management.signatures.get_signature_audit_trail`

**Parameters**:
```json
{
    "document_name": "SE-2024-001",
    "from_date": "2024-01-01",
    "to_date": "2024-01-31"
}
```

**Response**:
```json
{
    "status": "success",
    "audit_trail": [
        {
            "document": "SE-2024-001",
            "signature_type": "warehouse_supervisor",
            "signed_by": "john.supervisor@company.com",
            "signed_date": "2024-01-15 10:30:00",
            "ip_address": "192.168.1.100",
            "user_agent": "Mozilla/5.0...",
            "workflow_state": "Warehouse Approved"
        }
    ]
}
```

## Report APIs

### Generate Warehouse Report

Generate comprehensive warehouse utilization and performance reports.

**Endpoint**: `POST /api/method/rnd_warehouse_management.warehouse_management.reports.generate_warehouse_report`

**Parameters**:
```json
{
    "report_type": "utilization",  // Options: utilization, performance, compliance
    "warehouse_type": "Raw Material",  // Optional filter
    "from_date": "2024-01-01",
    "to_date": "2024-01-31",
    "format": "json"  // Options: json, pdf, excel
}
```

**Response**:
```json
{
    "status": "success",
    "report_data": {
        "summary": {
            "total_warehouses": 16,
            "average_utilization": 67.5,
            "total_movements": 245,
            "approval_rate": 98.5
        },
        "warehouses": [
            {
                "name": "Raw Material Main - AMB-W",
                "utilization": 75.5,
                "movements": 45,
                "last_updated": "2024-01-15 09:00:00"
            }
        ]
    },
    "generated_at": "2024-01-15 15:30:00",
    "report_id": "RPT-2024-001"
}
```

### Export Data

Export warehouse management data in various formats.

**Endpoint**: `POST /api/method/rnd_warehouse_management.warehouse_management.exports.export_data`

**Parameters**:
```json
{
    "data_type": "stock_entries",  // Options: stock_entries, work_orders, signatures
    "filters": {
        "custom_sap_movement_type": "261",
        "from_date": "2024-01-01",
        "to_date": "2024-01-31"
    },
    "format": "excel",  // Options: excel, csv, json
    "include_signatures": false
}
```

**Response**:
```json
{
    "status": "success",
    "download_url": "/api/method/download_file?file_url=/private/files/export_2024_01_15.xlsx",
    "file_size": "2.5 MB",
    "record_count": 1250,
    "expires_at": "2024-01-16 15:30:00"
}
```

## Webhook Events

The system sends webhook notifications for key events.

### Zone Status Changed

**Event**: `zone_status_changed`

**Payload**:
```json
{
    "event": "zone_status_changed",
    "timestamp": "2024-01-15T10:30:00Z",
    "data": {
        "work_order": "WO-2024-001",
        "old_status": "Red Zone",
        "new_status": "Green Zone",
        "completion_percentage": 100.0,
        "triggered_by": "SE-2024-005"
    }
}
```

### Signature Captured

**Event**: `signature_captured`

**Payload**:
```json
{
    "event": "signature_captured",
    "timestamp": "2024-01-15T10:30:00Z",
    "data": {
        "document": "SE-2024-001",
        "signature_type": "warehouse_supervisor",
        "signed_by": "john.supervisor@company.com",
        "workflow_state": "Warehouse Approved"
    }
}
```

### Approval Completed

**Event**: `approval_completed`

**Payload**:
```json
{
    "event": "approval_completed",
    "timestamp": "2024-01-15T10:30:00Z",
    "data": {
        "document": "SE-2024-001",
        "sap_movement_type": "311",
        "final_approver": "jane.kitting@company.com",
        "gi_gt_slip_number": "GI-GT-SE-2024-001",
        "total_approval_time": "02:30:00"
    }
}
```

## Error Handling

### Standard Error Response

```json
{
    "status": "error",
    "error_code": "VALIDATION_ERROR",
    "message": "Warehouse Supervisor signature is required",
    "details": {
        "field": "custom_warehouse_supervisor_signature",
        "doctype": "Stock Entry",
        "docname": "SE-2024-001"
    },
    "timestamp": "2024-01-15T10:30:00Z"
}
```

### Error Codes

| Code | Description |
|------|-------------|
| `VALIDATION_ERROR` | Data validation failed |
| `PERMISSION_DENIED` | User lacks required permissions |
| `WORKFLOW_ERROR` | Workflow state transition invalid |
| `SAP_MOVEMENT_ERROR` | SAP movement type validation failed |
| `SIGNATURE_ERROR` | Digital signature validation failed |
| `ZONE_STATUS_ERROR` | Zone status calculation failed |
| `NOT_FOUND` | Requested resource not found |
| `RATE_LIMITED` | API rate limit exceeded |
| `INTERNAL_ERROR` | Unexpected server error |

### Rate Limiting

API endpoints are rate limited:

- **Standard endpoints**: 100 requests per minute
- **Bulk operations**: 10 requests per minute
- **Report generation**: 5 requests per minute

**Rate limit headers**:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642248600
```

### Authentication Errors

```json
{
    "status": "error",
    "error_code": "AUTHENTICATION_REQUIRED",
    "message": "Valid authentication credentials required",
    "details": {
        "auth_methods": ["API Key", "Session", "Token"]
    }
}
```

## SDK Examples

### Python SDK

```python
import requests
import json

class RNDWarehouseAPI:
    def __init__(self, base_url, api_key, api_secret):
        self.base_url = base_url
        self.headers = {
            'Authorization': f'token {api_key}:{api_secret}',
            'Content-Type': 'application/json'
        }
    
    def update_zone_status(self, work_order_name):
        endpoint = f'{self.base_url}/api/method/rnd_warehouse_management.warehouse_management.work_order.update_work_order_zone_status'
        response = requests.post(
            endpoint,
            json={'work_order_name': work_order_name},
            headers=self.headers
        )
        return response.json()
    
    def get_material_status(self, work_order_name):
        endpoint = f'{self.base_url}/api/method/rnd_warehouse_management.warehouse_management.work_order.get_work_order_material_status'
        response = requests.get(
            endpoint,
            params={'work_order_name': work_order_name},
            headers=self.headers
        )
        return response.json()

# Usage
api = RNDWarehouseAPI(
    'https://your-site.com',
    'your_api_key',
    'your_api_secret'
)

result = api.update_zone_status('WO-2024-001')
print(f"Zone status: {result['zone_status']}")
```

### JavaScript SDK

```javascript
class RNDWarehouseAPI {
    constructor(baseUrl, apiKey, apiSecret) {
        this.baseUrl = baseUrl;
        this.headers = {
            'Authorization': `token ${apiKey}:${apiSecret}`,
            'Content-Type': 'application/json'
        };
    }
    
    async updateZoneStatus(workOrderName) {
        const response = await fetch(
            `${this.baseUrl}/api/method/rnd_warehouse_management.warehouse_management.work_order.update_work_order_zone_status`,
            {
                method: 'POST',
                headers: this.headers,
                body: JSON.stringify({ work_order_name: workOrderName })
            }
        );
        return response.json();
    }
    
    async getMaterialStatus(workOrderName) {
        const params = new URLSearchParams({ work_order_name: workOrderName });
        const response = await fetch(
            `${this.baseUrl}/api/method/rnd_warehouse_management.warehouse_management.work_order.get_work_order_material_status?${params}`,
            {
                method: 'GET',
                headers: this.headers
            }
        );
        return response.json();
    }
}

// Usage
const api = new RNDWarehouseAPI(
    'https://your-site.com',
    'your_api_key',
    'your_api_secret'
);

api.updateZoneStatus('WO-2024-001')
    .then(result => console.log('Zone status:', result.zone_status))
    .catch(error => console.error('Error:', error));
```

---

**For more examples and advanced usage, see our [GitHub repository](https://github.com/minimax/rnd_warehouse_management).**