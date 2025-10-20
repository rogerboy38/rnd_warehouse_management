// RND Warehouse Management - Global JavaScript

frappe.provide('rnd_warehouse_management');

// Global configuration
rnd_warehouse_management.config = {
    app_name: 'RND Warehouse Management',
    version: '2.1.0'
};

// Utility functions
rnd_warehouse_management.utils = {
    
    // Format SAP movement type display
    format_movement_type: function(code, description) {
        return `<span class="sap-movement-type">${code}</span> - ${description}`;
    },
    
    // Show zone status badge
    get_zone_badge: function(status) {
        const badges = {
            'Green': '<span class="zone-status-badge zone-status-green">Green Zone</span>',
            'Red': '<span class="zone-status-badge zone-status-red">Red Zone</span>',
            'Yellow': '<span class="zone-status-badge zone-status-yellow">Yellow Zone</span>'
        };
        return badges[status] || status;
    },
    
    // Refresh movement type data
    refresh_movement_types: function(frm) {
        if (frm.doc.sap_movement_type) {
            frappe.call({
                method: 'rnd_warehouse_management.api.get_movement_type_details',
                args: { movement_type: frm.doc.sap_movement_type },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('requires_kitting_signature', r.message.requires_kitting_signature);
                        frm.refresh_field('requires_kitting_signature');
                    }
                }
            });
        }
    }
};

// Initialize on page load
$(document).ready(function() {
    console.log('RND Warehouse Management loaded - Version ' + rnd_warehouse_management.config.version);
});
