# Placeholder class to protect Workspace doctype from orphan deletion
# This tells Frappe that Workspace is owned by rnd_warehouse_management app
class WorkspaceProtector:
    """Dummy class to prevent Workspace from being treated as orphan during bench migrate"""
    pass
