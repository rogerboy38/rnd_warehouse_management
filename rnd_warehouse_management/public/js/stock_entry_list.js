// Stock Entry List customizations

frappe.listview_settings['Stock Entry'] = {
    
    add_fields: ['sap_movement_type', 'zone_status', 'approval_status'],
    
    get_indicator: function(doc) {
        // Custom indicators based on approval status
        if (doc.approval_status === 'Approved') {
            return [__("Approved"), "green", "approval_status,=,Approved"];
        } else if (doc.approval_status === 'Rejected') {
            return [__("Rejected"), "red", "approval_status,=,Rejected"];
        } else if (doc.approval_status === 'Pending') {
            return [__("Pending Approval"), "orange", "approval_status,=,Pending"];
        } else if (doc.docstatus === 1) {
            return [__("Submitted"), "blue", "docstatus,=,1"];
        }
    },
    
    formatters: {
        sap_movement_type: function(value) {
            return value ? `<span class="sap-movement-type">${value}</span>` : '';
        },
        zone_status: function(value) {
            return rnd_warehouse_management.utils.get_zone_badge(value);
        }
    }
};
