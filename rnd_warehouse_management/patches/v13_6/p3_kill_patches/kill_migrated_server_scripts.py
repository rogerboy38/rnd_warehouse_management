# -*- coding: utf-8 -*-
# ==========================================================
# rnd_warehouse_management.patches.v13_6.p3_kill_patches.kill_migrated_server_scripts
# ==========================================================
# V13.6.0 P3 — Server Script migration kill-patch.
# Deletes Server Script DB rows whose logic has been migrated
# into in-code hooks (doctype_events / api / override_whitelisted_methods)
# OR archived verbatim under docs/legacy/.
#
# Runs automatically on `bench migrate` (listed in patches.txt).
# Pre-kill backups live under /tmp/p3-artifacts/ (full Frappe
# backup + server_scripts_full_dump.json + per-row body files).
# ==========================================================
import frappe


def execute():
    scripts_to_delete = [
        "SAP Movement Type Validation",
        "Stock Entry Signature Validation",
        "Work Order Zone Status Update",
        "Work Order Zone Assignment",
        "Stock Entry Zone Validation",
        "Work Order List Show Drafts",
    ]

    deleted = 0
    missing = 0
    failed  = 0
    for script_name in scripts_to_delete:
        try:
            frappe.delete_doc("Server Script", script_name, force=True)
            frappe.db.commit()
            print(f"OK     deleted  : {script_name}")
            deleted += 1
        except frappe.DoesNotExistError:
            print(f"SKIP   not found : {script_name}")
            missing += 1
        except Exception as e:
            print(f"FAIL             : {script_name} -> {e}")
            failed += 1

    total = len(scripts_to_delete)
    print(f"P3 kill-patch (rnd_warehouse_management): total={total} deleted={deleted} missing={missing} failed={failed}")
