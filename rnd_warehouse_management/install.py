"""
Installation script for RND Warehouse Management
"""

import frappe

def after_install():
    """Post-installation setup"""
    print("🚀 Starting RND Warehouse Management installation...")
    
    # Create Kitting Supervisor role if not exists
    if not frappe.db.exists("Role", "Kitting Supervisor"):
        role = frappe.get_doc({
            "doctype": "Role",
            "role_name": "Kitting Supervisor",
            "desk_access": 1
        })
        role.insert(ignore_permissions=True)
        print("✅ Created role: Kitting Supervisor")
    
    # Create default movement types
    create_default_movement_types()
    
    # Create default workflows
    create_default_workflows()
    
    # Apply any patches
    apply_patches()
    
    print("✅ RND Warehouse Management installation completed successfully!")

def create_default_movement_types():
    """Seed one Movement Type per SAP code of the one list (TASKS-272: was 101/261/311, keyed by purpose,
    so at most one code per purpose could ever be seeded). Idempotent: a code that exists is left alone."""
    from rnd_warehouse_management.sap_movement_types import SAP_MOVEMENT_TYPES
    print("📋 Setting up default movement types...")
    created_count = 0
    try:
        for m in SAP_MOVEMENT_TYPES:
            if frappe.db.exists("Movement Type", {"movement_code": m["code"]}):
                continue
            frappe.get_doc({
                "doctype": "Movement Type",
                "name": m["code"],
                "movement_code": m["code"],
                "sap_equivalent": m["code"],
                "purpose": m["purpose"],
                "default_stock_entry_type": m["default_stock_entry_type"],
                "movement_description": m["label"],
                "add_to_transit": 0,
                "is_standard": 0,
            }).insert(ignore_permissions=True)
            created_count += 1
        if created_count > 0:
            print(f"   ✅ Created {created_count} movement types")
        else:
            print("   ✅ Movement types already exist")
    except Exception as e:
        # Movement Type doctype not yet resolvable during fresh install
        # (Frappe tries to import frappe.core.doctype.movement_type before sync).
        # Records will be created on first bench migrate via fixtures.
        frappe.db.rollback()
        print(f"   ⚠️  Movement Type creation deferred: {type(e).__name__}: {e}")

def create_default_workflows():
    """Create default approval workflows"""
    print("⚙️  Setting up default workflows...")
    
    # This would create workflow states and transitions
    # For now, just log that we would do this
    print("   ✅ Workflow setup placeholder - customize as needed")

def apply_patches():
    """Apply any necessary patches"""
    print("🔧 Applying patches...")
    
    try:
        # Apply permission query fix if needed
        from .patches.fix_permission_query import execute as fix_permission_query
        fix_permission_query()
        print("   ✅ Applied permission query fix")
    except ImportError as e:
        print(f"   ⚠️  Permission query patch not found: {e}")
    except Exception as e:
        print(f"   ⚠️  Could not apply permission query patch: {e}")
    
    print("   ✅ Patch application complete")
