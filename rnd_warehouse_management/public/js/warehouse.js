// Warehouse customizations for RND Warehouse Management

frappe.ui.form.on('Warehouse', {
    
    refresh: function(frm) {
        // Add custom dashboard button
        if (!frm.is_new()) {
            frm.add_custom_button(__('Warehouse Dashboard'), function() {
                frappe.call({
                    method: 'rnd_warehouse_management.api.get_warehouse_dashboard',
                    args: { warehouse: frm.doc.name },
                    callback: function(r) {
                        if (r.message) {
                            const data = r.message;
                            const html = `
                                <div style="padding: 15px;">
                                    <h4>Warehouse Statistics</h4>
                                    <table class="table table-bordered">
                                        <tr>
                                            <td><strong>Total Items:</strong></td>
                                            <td>${data.total_items || 0}</td>
                                        </tr>
                                        <tr>
                                            <td><strong>Stock Value:</strong></td>
                                            <td>${format_currency(data.stock_value || 0)}</td>
                                        </tr>
                                        <tr>
                                            <td><strong>Capacity Used:</strong></td>
                                            <td>${data.capacity_used || 0}%</td>
                                        </tr>
                                    </table>
                                </div>
                            `;
                            frappe.msgprint({
                                title: __('Warehouse Dashboard: ') + frm.doc.name,
                                message: html,
                                wide: true
                            });
                        }
                    }
                });
            });
        }
    },
    
    warehouse_type: function(frm) {
        // Set default capacity based on type
        if (frm.doc.warehouse_type && !frm.doc.capacity) {
            const default_capacities = {
                'Raw Material': 10000,
                'Work In Progress': 5000,
                'Finished Goods': 15000,
                'Transit': 2000,
                'Rejected': 1000
            };
            frm.set_value('capacity', default_capacities[frm.doc.warehouse_type] || 5000);
        }
    }
});
