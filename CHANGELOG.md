# Changelog

All notable changes to the RND Warehouse Management app will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.3.2] - 2026-11

- `hooks.py`: removed the include of `warehouse_temperature.js` — `app_include_js` (`/assets/rnd_warehouse_management/js/warehouse_temperature.js`) and the `Warehouse` entry of `doctype_js` (`public/js/warehouse_temperature.js`). The file is in no commit of this repository (added to the hooks by `d640059`, 2026-01-25, never committed), so every Desk page requested it and got a 404. No behaviour change: nothing was ever loaded from it. No fixture, patch, DocType, Python or JS change. Tests: `tests/test_hooks_includes.py`.
- **Placeholder, not forgotten:** `warehouse_temperature.js` was the placeholder of a Warehouse temperature UI (added to the hooks by `d640059`, 2026-01-25; the file was never committed). It is intentionally NOT recreated here. It is planned for a later phase, to be built and re-registered together with the IoT bot fleet `bot_iot_l01` … `bot_iot_l34` (some of the bots are in warehouses); until then no Desk include points at it. See "Roadmap / placeholders" in the README.
- Noted, not changed: `d640059` also re-pointed `doctype_js["Warehouse"]` from the existing `public/js/warehouse.js` to the missing file, so `warehouse.js` (a "Warehouse Dashboard" button calling `rnd_warehouse_management.api.get_warehouse_dashboard`, which this repository does not define) has not loaded since 2026-01-25.

## [2.3.1] - 2026-11

- Stock Entry Approval Rule, button "View Applicable Stock Entries": the Stock Entry list is now filtered with an **equality** on the exact `custom_sap_movement_type` option (`<code> (<label>)`, read from the Stock Entry meta), not `like <code>%`. Frappe 16.17.5's filter UI lists `like` as an invalid condition for a Select field and drops it, so 2.3.0 opened an unfiltered list (measured on VPT: "20 of 373" instead of "20 of 42"). A code with no matching option (or an empty Movement Type) opens nothing and shows a message instead of an unfiltered list. JavaScript only: no fixture, hook, DocType, patch or Python change; the 2.3.0 migrate effects are unchanged. Tests: `tests/test_approval_rule_button.py` (needs `node`).

## [2.3.0] - 2026-11-03

- Stock Entry `custom_sap_movement_type` (Select) now lists all 16 codes in use, `code (description)`: 101, 102, 103, 104, 105, 106, 107, 108, 109, 261, 281, 311, 313, 501, 545, 561. 261/311 keep prod's labels; **561 is `561 (Initial Entry - Stock Balance)` — the string the 42 submitted Stock Entries on prod store** (the `… / Material Receipt` label of `0ca2d4e` would have left them un-editable: a Select value outside `options` throws on every save that is not a cancel; TASKS-272b); the rest take the Movement Type record's own description (313: its name + purpose; 108/109 read `108 (Send to Subcontractor)` and `109 (Stores Movement / Material Issue)` — the records' description text named a Stock Entry Type that contradicted their purpose and was corrected, TASKS-272d); 281 = "Goods Issue for Sampling" (prod's Movement Type Master MT-281; Hugh's ruling 2026-11-03); 501 = "Receipt without Purchase Order" (docs_TECHNICAL_SPECIFICATIONS.md MT-501).
- `fixtures/movement_type.json`: records `281` and `501` added (501 → Material Receipt; 281 → Material Issue, as 103 and 109 — Hugh's ruling 2026-11-03).
- One list, `rnd_warehouse_management/sap_movement_types.py`, now feeds `bootinfo.sap_movement_types` and the installer's Movement Type seed (which used to seed 101/261/311 only, keyed by purpose); `tests/test_sap_movement_types.py` asserts the fixture records, the Select options, boot and installer agree.
- `amb_w_spc/fixtures/custom_field.json` ships the same 25 Stock Entry Custom Fields and syncs after this app at every migrate, so it carries the identical options (its own PR); a change to this file alone is undone in the same migrate.
- In-app readers compare the leading code (`sap_code()`): the Jinja `format_sap_movement_type`, the approval dashboard's movement-type filter, the approval rule's "view applicable Stock Entries" link. Site-side readers that still compare bare `'261'`/`'311'` are reported in the PR, not changed.

## [2.2.0] - 2026-10-20

### Changed
- 2.2.0 — Work Order workflow `Work Order Scheduling` replaces `Starting Work Order`: Draft → Schedule (Planeacion) → Scheduled (docstatus 1) → Cancel (Planeacion, Manufacturing Manager) → Cancelled; Don't Override Status; new fixtures Workflow State / Workflow Action Master / Role Planeacion; `before_insert` resets `workflow_state` on amended Work Orders and Stock Entries; `after_migrate` maps existing Work Orders' states by docstatus, closes the old workflow's Open Workflow Actions (state not Draft / Scheduled / Cancelled; status Completed — Workflow Action allows only Open / Completed; pending actions of the new workflow are never touched), deletes the old workflow. Requires `bench migrate` on each site.
- Planeacion is granted in addition to Manufacturing User; it gates Schedule and Cancel and widens the Work Order list (every Work Order), it grants no document permission by itself.
- Rule: Workflows on Work Order and Stock Entry are edited in the repo only; a UI edit on a site is wiped at the next migrate.

## [2.1.1] - 2026-10-18

### Fixed
- 2.1.1 — hourly `update_zone_status` no longer re-saves Work Orders; writes the five zone fields with `db.set_value(update_modified=False)` only when they change; no Version, no notifications, no required_items re-derivation; manual endpoint uses the same path.

## [1.0.0] - 2025-08-15

### Added
- 🎆 Initial release of RND Warehouse Management
- 🏢 SAP Movement Type integration (261 FrontFlush, 311 BackFlush)
- ✍️ Dual-signature approval workflow for Stock Entry
- 🟢🔴 Red/Green zone logic for Work Order material tracking
- 📜 Professional GI/GT Slip print format with signature display
- 🏦 Advanced warehouse management with type classification
- 🔄 Transit warehouse support for material movement tracking
- 🌡️ Temperature control settings for sensitive materials
- 📊 Warehouse capacity management and utilization tracking
- 🔒 Role-based permissions (Warehouse Supervisor, Kitting Supervisor, Zone Manager)
- 🚀 Custom JavaScript enhancements for Stock Entry and Work Order forms
- 🎨 Professional CSS styling for zone status and signature fields
- 🔧 Server scripts for workflow automation and validation
- 📅 Scheduled tasks for zone status updates and maintenance
- 📧 Email integration for GI/GT Slip distribution
- 📱 Mobile-responsive design for field operations
- 🔌 Comprehensive API for integration and automation
- 📈 Dashboard enhancements with real-time zone status
- 🔍 Advanced material status tracking and shortage analysis
- 📝 Professional documentation and installation guides

### Features

#### SAP Movement Types
- **261 (FrontFlush)**: Goods Issue for Production
  - Single signature requirement (Warehouse Supervisor)
  - Validates source/target warehouse types
  - Automatic zone status calculation
- **311 (BackFlush)**: Transfer for Kitting  
  - Dual signature requirement (Warehouse + Kitting Supervisors)
  - Enhanced workflow with kitting approval
  - Complete material transfer tracking

#### Workflow Management
- Draft → Pending Warehouse Approval → Warehouse Approved → Kitting Approved
- Digital signature capture with timestamp
- Role-based state transitions
- Automatic GI/GT slip generation
- Email notifications and alerts

#### Zone Status Logic
- Real-time material availability calculation
- Automatic Red/Green zone assignment
- Work Order material completion percentage
- Missing materials tracking and reporting
- Integration with BOM requirements

#### Print Format
- Professional GI/GT Slip design
- Signature image display
- SAP movement type badges
- Zone status indicators
- Company branding support
- Mobile-optimized layout

#### Warehouse Management
- **Types**: Raw Material, Work In Progress, Finished Goods, Transit, Rejected
- Hierarchical warehouse structure
- Transit warehouse for movement tracking
- Temperature control configuration
- Capacity utilization monitoring
- Custom warehouse codes

#### Custom Fields Added

**Stock Entry**:
- `custom_sap_movement_type` - SAP Movement Type selection
- `custom_work_order_reference` - Link to Work Order
- `custom_zone_status` - Red/Green zone status
- `custom_material_completion_percentage` - Material completion %
- `custom_warehouse_supervisor_signature` - Warehouse supervisor signature
- `custom_kitting_supervisor_signature` - Kitting supervisor signature
- `custom_gi_gt_slip_number` - GI/GT slip reference number

**Work Order**:
- `custom_current_zone_status` - Current zone status
- `custom_material_completion_percentage` - Material completion %
- `custom_last_stock_entry` - Reference to last stock entry
- `custom_missing_materials_json` - JSON data of missing materials

**Warehouse**:
- `custom_temperature_control` - Temperature control flag
- `custom_target_temperature` - Target temperature setting
- `custom_warehouse_code` - Unique warehouse code
- `custom_is_zone_warehouse` - Zone warehouse flag
- `custom_max_capacity` - Maximum capacity setting

#### Server Scripts
- Stock Entry signature validation
- Work Order zone status automation
- SAP movement type validation
- Warehouse type enforcement
- Automatic field calculations

#### Scheduled Tasks
- **Hourly**: Zone status updates for active Work Orders
- **Daily**: Signature cleanup, warehouse utilization reports
- **Background**: Email notifications and alerts

#### API Endpoints
- Work Order material status checking
- Zone status updates
- Warehouse hierarchy creation
- Custom Stock Entry creation
- Dashboard data retrieval

### Technical Details

#### Dependencies
- ERPNext v15.0+
- Frappe Framework v15.0+
- Python 3.8+

#### Database Changes
- 13 custom fields across 3 DocTypes
- 5 new workflow states
- 5 workflow actions
- 7 workflow transitions
- 3 custom roles
- 1 comprehensive print format

#### File Structure
```
rnd_warehouse_management/
├── rnd_warehouse_management/
│   ├── warehouse_management/     # Core business logic
│   ├── fixtures/                  # Installation data
│   ├── patches/                   # Migration scripts
│   ├── public/                    # Client-side assets
│   └── templates/                 # Jinja templates
├── docs/                          # Documentation
└── README.md                      # Main documentation
```

### Installation

```bash
# Get the app
bench get-app https://github.com/minimax/rnd_warehouse_management.git

# Install on site
bench --site [site-name] install-app rnd_warehouse_management

# Migrate and restart
bench --site [site-name] migrate
bench restart
```

### Breaking Changes
None - This is the initial release.

### Migration Notes
- Existing Stock Entries will be updated with default SAP movement types
- New custom fields will be added to Stock Entry, Work Order, and Warehouse
- Workflow will be created for Stock Entry approval process
- Custom roles will be created for warehouse management

### Known Issues
None currently identified.

### Security
- Digital signature validation
- Role-based access control
- Warehouse type enforcement
- Workflow state validation
- Data encryption for sensitive fields

---

## Version Planning

### [1.1.0] - Planned Q1 2025
- Mobile app integration
- Barcode scanning support
- Advanced analytics dashboard
- Multi-language support

### [1.2.0] - Planned Q2 2025
- IoT sensor integration
- Machine learning forecasting
- External WMS integration
- Enhanced reporting engine

---

**Maintained by MiniMax Agent**