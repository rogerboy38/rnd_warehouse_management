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
        
        // TASKS-384 B2: a certificate for this order, made through its lot record
        if (!frm.is_new()) {
            frm.add_custom_button(__('Certificate'), function() {
                rnd_work_order_certificate(frm);
            }, __('Create'));
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

// TASKS-384 B2. The certificate belongs to the lot record (Batch AMB), not to the Work Order: find the lot
// records of this order, let the user choose when there are several, and ask the certificates app (amb_w_tds)
// for a new certificate of that lot. The server decides the certificate type and fills it; a refusal is the
// server's own message (frappe.call shows it). Containers (level 3 and below) are not offered: a certificate
// is made for a lot or a sub-lot, and containers follow their sub-lot.
function rnd_work_order_certificate(frm) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Batch AMB',
            filters: { work_order_ref: frm.doc.name },
            fields: ['name', 'title', 'custom_batch_level', 'quality_status'],
            order_by: 'custom_batch_level asc, name asc',
            limit_page_length: 0
        },
        callback: function(r) {
            if (!r || r.exc) {
                return;
            }
            const lots = (r.message || []).filter(function(row) {
                return !['3', '4'].includes(String(row.custom_batch_level || '1'));
            });
            if (!lots.length) {
                frappe.msgprint({
                    title: __('Certificate'),
                    indicator: 'orange',
                    message: __('Work Order {0} has no lot record (Batch AMB) yet. Create the lot record first; the certificate is made for the lot.', [frm.doc.name])
                });
                return;
            }
            if (lots.length === 1) {
                rnd_make_certificate_for_lot(lots[0].name);
                return;
            }
            frappe.prompt(
                [{
                    fieldname: 'lot',
                    fieldtype: 'Select',
                    label: __('Lot record'),
                    reqd: 1,
                    options: lots.map(function(row) {
                        return {
                            value: row.name,
                            label: [
                                row.name,
                                row.title && row.title !== row.name ? row.title : null,
                                __('level {0}', [row.custom_batch_level || '1']),
                                row.quality_status ? __(row.quality_status) : null
                            ].filter(Boolean).join(' · ')
                        };
                    })
                }],
                function(values) {
                    if (values && values.lot) {
                        rnd_make_certificate_for_lot(values.lot);
                    }
                },
                __('Which lot record is the certificate for?'),
                __('Create certificate')
            );
        }
    });
}

function rnd_make_certificate_for_lot(lot) {
    frappe.call({
        method: 'amb_w_tds.api.certificate.make_certificate_for_lot',
        args: { lot: lot },
        freeze: true,
        freeze_message: __('Creating certificate...'),
        callback: function(r) {
            const made = r && !r.exc && r.message;
            if (made && made.doctype && made.name) {
                frappe.set_route('Form', made.doctype, made.name);
            }
        }
    });
}
