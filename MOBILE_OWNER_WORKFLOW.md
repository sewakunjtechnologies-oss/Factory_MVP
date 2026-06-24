# Mobile Owner Workflow

## Mobile-Only Architecture

The desktop web application remains unchanged. The new phone workflow is mounted under `/mobile` and uses the same backend database, authentication, PO records, fabric planning, alerts, reminders, dispatch records, PDF reports, and AI assistant.

Capacitor/native Android users are routed to `/mobile/home`. Desktop browser users continue to land on the existing dashboard.

## Simplified PO Creation

Mobile PO creation asks only:

1. Product / Fabric Category
2. Quantity
3. Delivery month or exact delivery date

The selected category comes from existing product/fabric-line master data. The backend generates the PO number, creation date, initial fabric plan, fabric shortage/ready status, and audit entry.

If only a delivery month is selected, the app stores the last day of that month as the planning date and marks it as an estimated planning date in the PO notes.

## Stage Flow

The mobile owner stage flow is:

1. `PO_CREATED`
2. `FABRIC_CHECK`
3. `FABRIC_SHORTAGE` or `FABRIC_READY`
4. `FABRIC_ORDERED`
5. `FABRIC_RECEIVED`
6. `FABRIC_VERIFIED`
7. `CUTTING`
8. `CUTTING_COMPLETED`
9. `STITCHING`
10. `STITCHING_COMPLETED`
11. `PACKING`
12. `PACKING_COMPLETED`
13. `READY_FOR_DISPATCH`
14. `PARTIALLY_DISPATCHED`
15. `DISPATCHED`
16. `COMPLETED`

The first implementation maps this flow onto existing PO statuses and stage-progress records. Fabric-receipt and fabric-verification sub-stages are still represented by the existing backend modules and can be expanded in the mobile bottom sheet later.

## Required Questions Per Stage

The mobile detail page shows one main button. When tapped, a bottom sheet asks only required fields for the next transition:

- Fabric shortage: mill, meters, expected delivery date, optional rate
- Cutting completion: completed pieces, rejected pieces, repair pieces
- Stitching completion: returned, approved, repair, alteration, rejected
- Packing completion: packed pieces, damaged or pending pieces
- Dispatch: dispatched pieces, optional date/transporter/remarks
- Completion: no fields, but backend blocks completion if dispatch is pending

## Reminder Behavior

Mobile reminders use the existing reminders table. The mobile app:

- shows open reminder cards
- refreshes every 4 hours while active
- allows snooze for 4 hours
- allows snooze until tomorrow
- allows mark as handled
- keeps reminders database-backed so notifications are not the source of truth

Native Android push notifications are not yet device-verified in this change. In-app reminder cards are the reliable fallback.

## AI Workflow

The mobile assistant route reuses the existing assistant page and backend AI route. AI text/voice can continue to answer questions, generate reports, and execute supported write actions through the existing confirmation flow.

The stage-transition service is intentionally backend-owned so the button workflow and AI workflow can share the same validation path as AI stage-write coverage is expanded.

## Historical Import Behavior

`backend/seed/import_owner_may_june_historical_pos.py` imports owner May and June data as historical dispatched POs only when run with `--apply`.

Rules:

- no database reset
- no current stock deduction
- no fabric shortages
- no active mill orders
- editable PO records
- one full dispatch record per historical PO
- batch rollback affects only the selected import batch

Preview before applying:

```bash
backend/.venv/bin/python backend/seed/import_owner_may_june_historical_pos.py --preview
```

## Web Compatibility

Existing desktop routes and forms remain mounted outside `/mobile`. The desktop Create PO form retains separate Category and Fabric fields. The mobile Create PO form has one unified Product / Fabric Category selector.

## Known Limitations

- Native Android notifications require device permission testing.
- AI stage actions should be expanded to call the new mobile transition endpoint for every stage command.
- The mobile report/settings routes currently reuse existing pages or placeholders.
- Android readiness still needs physical-device testing after `npm run android:sync`.

## Testing Instructions

Backend:

```bash
python3 -m compileall backend/app
python3 -m compileall backend/tests
backend/.venv/bin/python -m pytest backend/tests -q
backend/.venv/bin/python backend/seed/import_owner_may_june_historical_pos.py --preview
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
npm run android:sync
```
