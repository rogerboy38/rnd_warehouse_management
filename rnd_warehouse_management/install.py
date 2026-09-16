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
    """Create default movement types if they don't exist"""
    print("📋 Setting up default movement types...")
    
    movement_types = [
        {
            "doctype": "Movement Type",
            "purpose": "Material Receipt",
            "movement_code": "101",
            "movement_description": "Goods receipt from vendor",
            "add_to_transit": 0,
            "is_standard": 1
        },
        {
            "doctype": "Movement Type",
            "purpose": "Material Issue",
            "movement_code": "261",
            "movement_description": "Issue materials to production",
            "add_to_transit": 0,
            "is_standard": 1
        },
        {
            "doctype": "Movement Type",
            "purpose": "Material Transfer",
            "movement_code": "311",
            "movement_description": "Transfer between storage locations",
            "add_to_transit": 1,
            "is_standard": 1
        }
    ]
    
    created_count = 0
    try:
        for mt_data in movement_types:
            # Check if exists by purpose
            if not frappe.db.exists("Movement Type", {"purpose": mt_data["purpose"]}):
                # Add name field
                mt_data['name'] = mt_data['purpose'].replace(' ', '_').upper()
                frappe.get_doc(mt_data).insert(ignore_permissions=True)
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
