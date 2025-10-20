// Work Order customizations for RND Warehouse Management

frappe.ui.form.on('Work Order', {
    
    refresh: function(frm) {
        // Add button to check material availability
        if (frm.doc.docstatus === 0 || frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Check Material Availability'), function() {
                frappe.call({
                    method: 'rnd_warehouse_management.api.get_material_status',
                    args: { work_order: frm.doc.name },
                    callback: function(r) {
                        if (r.message) {
                            frm.set_value('zone_status', r.message.zone_status);
                            frm.set_value('material_completion_percentage', r.message.completion_percentage);
                            frm.refresh();
                            
                            frappe.msgprint({
                                title: __('Material Status'),
                                indicator: r.message.zone_status === 'Green' ? 'green' : 'red',
                                message: `Zone Status: ${r.message.zone_status}<br>
                                         Completion: ${r.message.completion_percentage}%`
                            });
                        }
                    }
                });
            });
        }
        
        // Show zone status badge
        if (frm.doc.zone_status) {
            frm.set_intro(
                rnd_warehouse_management.utils.get_zone_badge(frm.doc.zone_status),
                frm.doc.zone_status === 'Green' ? 'green' : 'orange'
            );
        }
    },
    
    onload: function(frm) {
        // Auto-check material status on load
        if (frm.doc.name && !frm.is_new()) {
            setTimeout(function() {
                frm.trigger('refresh');
            }, 1000);
        }
    }
});
