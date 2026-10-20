# Workflows

Workflows on **Work Order** and **Stock Entry** are shipped by this app as fixtures (`rnd_warehouse_management/fixtures/workflow.json`).
**They are edited in the repo only.** Every `bench migrate` re-imports the fixture, so a change made in a site's UI is wiped at the next migrate.

## Work Order Scheduling (since 2.2.0)

Scheduling a Work Order **is** its submit; cancelling is a workflow action for the roles below.
`Don't Override Status` is on: the list and the form keep ERPNext's own status (Not Started → In Process → Completed),
and Start / Finish / Stop / Close stay ERPNext's native buttons on a scheduled Work Order.

| State | docstatus | Who may edit |
|---|---|---|
| Draft | 0 | Manufacturing User, Planeacion, Manufacturing Manager |
| Scheduled | 1 | Planeacion, Manufacturing Manager |
| Cancelled | 2 | Planeacion |

| From | Action | To | Allowed |
|---|---|---|---|
| Draft | Schedule | Scheduled | Planeacion, System Manager |
| Scheduled | Cancel | Cancelled | Planeacion, Manufacturing Manager |

- **Amend** appears natively on a cancelled Work Order. The amended copy starts again at Draft
  (`workflow_utils.reset_workflow_state_on_amend`, `before_insert`, also on Stock Entry).
- Under an active workflow Frappe never offers the native Submit, and because a transition leads to Cancelled, the native Cancel button
  is not offered either (`can_cancel_document`); the actions above replace them.

## Roles

- **Planeacion** (custom role, shipped as a fixture; assigned to the planner's account in the UI).
  **Planeacion is granted in addition to Manufacturing User; it gates Schedule and Cancel and widens the list, it grants no document permission by itself.**
  A user holding Planeacion sees every Work Order in the list (the app's Work Order list filter).
- ERPNext grants Work Order permissions to Manufacturing User (full) and Stock User (read). A user with only Planeacion or only
  Manufacturing Manager cannot open a Work Order.

## Migration (each site)

Requires `bench migrate`. Its `sync_fixtures` installs the workflow, the states (Draft, Scheduled, Cancelled), the actions
(Schedule, Cancel) and the role; then `after_migrate` (`workflow_utils.after_migrate_work_order_workflow`, idempotent):

1. deletes the old workflow `Starting Work Order` (its states Not Started / Start and action Start are kept);
2. sets each Work Order's `workflow_state` from its docstatus (0 Draft, 1 Scheduled, 2 Cancelled) where it differs, without a save
   (no Version, no notification, `modified` unchanged);
3. closes Open Workflow Actions on Work Order whose state is not Draft / Scheduled / Cancelled, i.e. the old workflow's
   (status Completed: Workflow Action allows only Open / Completed). Pending actions of Work Order Scheduling are never touched,
   so a later migrate leaves the planner's Open Schedule actions alone.

It prints its counts in the migrate output.
