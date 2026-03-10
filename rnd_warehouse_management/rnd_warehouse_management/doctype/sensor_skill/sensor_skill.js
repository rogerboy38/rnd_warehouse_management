// Copyright (c) 2026, Prosolmex and contributors
// For license information, please see license.txt

frappe.ui.form.on('Sensor Skill', {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Build Skill Package'), function() {
                frappe.call({
                    method: 'rnd_warehouse_management.rnd_warehouse_management.doctype.sensor_skill.sensor_skill.get_skill_package',
                    args: { sensor_type: frm.doc.sensor_type },
                    callback: function(r) {
                        if (r.message) {
                            frappe.msgprint({
                                title: __('Skill Package'),
                                message: '<pre>' + JSON.stringify(r.message, null, 2) + '</pre>',
                                indicator: 'green'
                            });
                        }
                    }
                });
            });
        }
    }
});
