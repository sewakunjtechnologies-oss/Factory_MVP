# Seed Sample POs (2026)

This seed flow resets previous sample/demo factory data and creates a fresh, workflow-rich dataset for dashboard and end-to-end testing.

## What this script creates

- Exactly **15 Purchase Orders**:
  - `DBL-2026-001..003`
  - `SGL-2026-001..003`
  - `FIT-2026-001..003`
  - `KNG-2026-001..003`
  - `PIL-2026-001..003`
- 15 product snapshots (`product_category=seed_sample_po`)
- Seed fabric inventory with mixed readiness and shortages
- PO drafts (`confirmed` + `needs_review`)
- Fabric plans (auto-calculated via service)
- Mill order requirements for shortage POs
- Fabric mill orders + followups (on-time, overdue, partially received)
- Fabric receipts (pending verification + failed/rejected with supplier return + debit note)
- Contractors (cutting/stitching/packing/transport)
- Stage allocations and daily production ledger entries
- Partial movement between stages
- Quality failures and QC inspections
- Packing output/risk signals
- Dispatch loads with mixed costing:
  - `invoice_percent`
  - `cbm`
  - `manual`
  - `vehicle_capacity`
- Alerts + reminders
- Capacity profiles and underutilization signals

## Seeded PO list

1. DBL-2026-001  
2. DBL-2026-002  
3. DBL-2026-003  
4. SGL-2026-001  
5. SGL-2026-002  
6. SGL-2026-003  
7. FIT-2026-001  
8. FIT-2026-002  
9. FIT-2026-003  
10. KNG-2026-001  
11. KNG-2026-002  
12. KNG-2026-003  
13. PIL-2026-001  
14. PIL-2026-002  
15. PIL-2026-003

## Idempotency / reset behavior

The script now performs a **full operational reset** before reseeding.

It clears existing workflow data from:

- alerts
- reminders
- dispatch loads
- packing outputs
- qc inspections
- quality failures
- stage progress entries
- contractor allocations
- stage summaries
- stage cost entries
- cutting analysis
- fabric issue to cutting
- mill followups
- fabric mill orders
- supplier returns
- debit notes
- fabric receipts
- mill order requirements
- fabric plans
- po drafts
- purchase orders
- fabric inventory
- capacity profiles
- contractors
- products

Admin/user accounts are preserved. A manager user is created only if no user exists.

## Run commands

From repo root:

```bash
python3 -m compileall backend/app
python3 -m compileall backend/seed
python3 backend/seed/seed_sample_pos.py
```

Alternative module mode:

```bash
PYTHONPATH=backend python3 -m seed.seed_sample_pos
```

## Dashboard verification checklist

After seed:

- 15 active/sample POs visible
- mix of fabric-ready and fabric-shortage POs
- mill order requirements present
- reminders due (fabric, followup, QC, packing, dispatch)
- contractor allocations and delayed work visible
- QC pass/failure examples present
- packing risk and shipment risk present
- partial dispatch and mixed dispatch costing visible

## Known assumptions

- Alert enum in codebase does not include explicit `mill_delivery_overdue` / `fabric_verification_pending` / `dispatch_pending` types; these are represented through existing alert types and title/message text.
- Script ensures schema with `Base.metadata.create_all()` to avoid missing table issues in local environments.
