import frappe

def run_test():
    print('=== TEST 5.2: QI Automation ===')
    batch_name = frappe.db.get_value('Batch', {'batch_id': 'LOTE-TEST-5.2'}, 'name')
    if not batch_name:
        batch = frappe.get_doc({'doctype': 'Batch', 'batch_id': 'LOTE-TEST-5.2', 'item': '0201'})
        batch.insert(ignore_permissions=True)
        frappe.db.commit()
        batch_name = batch.name
    print(f'Test batch name={batch_name}')

    real_se = frappe.get_all('Stock Entry', filters={'docstatus': 1}, fields=['name'], limit=1, order_by='creation desc')
    ref_name = real_se[0].name if real_se else 'SE-TEST-5.2'
    print(f'Using reference SE: {ref_name}')

    class MI:
        item_code = '0201'
        item_name = 'TEST'
        qty = 10
        t_warehouse = 'AMB Wellness - Almacen General PT - AMB'
        is_finished_item = 1
    MI.batch_no = batch_name

    class MSE:
        name = ref_name
        purpose = 'Manufacture'
        stock_entry_type = 'Manufacture'
        work_order = 'MFG-WO-03426'
        items = [MI()]

    old_qis = frappe.get_all('Quality Inspection', filters={'reference_name': ref_name, 'item_code': '0201'}, fields=['name'])
    for old_qi in old_qis:
        frappe.delete_doc('Quality Inspection', old_qi.name, force=True)
    frappe.db.commit()

    from rnd_warehouse_management.rnd_warehouse_management.qi_automation import create_quality_inspection_on_manufacture
    create_quality_inspection_on_manufacture(MSE())
    frappe.db.commit()

    qis = frappe.get_all('Quality Inspection', filters={'reference_name': ref_name, 'item_code': '0201'}, fields=['name','item_code','batch_no','custom_work_order','status','quality_inspection_template'])
    if qis:
        qi = qis[0]
        print(f'[PASS] T1: QI created: {qi.name}')
        r1 = 'PASS' if qi.batch_no == batch_name else 'FAIL'
        print(f'[|r1|] T2a: Batch: {qi.batch_no}')
        r2 = 'PASS' if qi.custom_work_order == 'MFG-WO-03426' else 'FAIL'
        print(f'[{r2}] T2b: WO: {qi.custom_work_order}')
        r3 = 'PASS' if qi.quality_inspection_template else 'FAIL'
        print(f'[{r3}] T2c: Template: {qi.quality_inspection_template}')
        readings = frappe.get_all('Quality Inspection Reading', filters={'parent': qi.name}, fields=['specification','min_value','max_value'])
        r4 = 'PASS' if readings else 'FAIL'
        print(f'[{r4}] T3: Readings count: {len(readings)}')
        for r in readings:
            print(f'  - {r.specification}: min={r.min_value}, max={r.max_value}')
    else:
        print('[FAIL] No QI created')
        errors = frappe.get_all('Error Log', filters={'method': 'QI Auto-Creation Error'}, fields=['error'], limit=1, order_by='creation desc')
        if errors:
            print(f'Err: {errors[0].error[:200]}')
    print('Done')
