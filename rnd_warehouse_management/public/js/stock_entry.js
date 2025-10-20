// Stock Entry customizations for RND Warehouse Management

frappe.ui.form.on('Stock Entry', {
    
    refresh: function(frm) {
        // Add custom buttons for SAP workflows
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Load Movement Type'), function() {
                rnd_warehouse_management.utils.refresh_movement_types(frm);
            });
        }
        
        // Show zone status if available
        if (frm.doc.zone_status) {
            frm.set_intro(
                rnd_warehouse_management.utils.get_zone_badge(frm.doc.zone_status),
                'blue'
            );
        }
        
        // Display approval status
        if (frm.doc.approval_status) {
            frm.trigger('show_approval_timeline');
        }
    },
    
    sap_movement_type: function(frm) {
        // Auto-load movement type requirements
        rnd_warehouse_management.utils.refresh_movement_types(frm);
    },
    
    show_approval_timeline: function(frm) {
        // Display approval workflow timeline
        if (frm.doc.approval_status && frm.doc.approval_status !== 'Not Required') {
            const html = `
                <div class="approval-timeline">
                    <h6>Approval Workflow</h6>
                    <div class="approval-step ${frm.doc.approval_status.toLowerCase()}">
                        <div class="approval-step-icon"></div>
                        <strong>Status:</strong> ${frm.doc.approval_status}
                    </div>
                </div>
            `;
            frm.set_df_property('approval_status', 'description', html);
        }
    }
});
