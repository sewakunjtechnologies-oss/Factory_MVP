# AI Owner Operations Update

## Overview

The Factory Assistant now supports short owner commands for common operational updates through text or manual voice input. Read-only questions still use deterministic database-backed answers first, and write actions are parsed into a structured pending action before anything is changed.

## Supported Owner Commands

- Fabric ordered or received: "Fabric for JUNE-010 has arrived", "We received 12000 meters from Krishna Mill".
- Cutting and packing completion: "JUNE-005 cutting complete", "Packing completed for 2500 pieces".
- Stitching assignment: "Send 5000 pieces of JUNE-003 to Kumar stitching contractor".
- Quality buckets: "300 pieces repair and 100 alteration for JUNE-006".
- Dispatch: "Dispatch 3000 pieces for JUNE-004", "JUNE-004 went for dispatch".
- PO updates: "Update shipment date of JUNE-006 to 30 June", "Mark PO JUNE-008 as completed".
- Existing read/report questions and PDF report generation remain supported.

## Supported Intents

Write intents implemented in the current deterministic flow include fabric ordered, fabric received, dispatch pieces, stage movement, cutting/packing completion, stitching assignment, repair/alter/rejected quantities, delivery date update, PO status update, PO completion, bulk field updates, and packing material updates.

Read intents continue to cover PO status, shortages, attention today, mill orders, late mills, dispatch readiness, contractor delays, packing risk, alerts, reminders, and PDF reports.

## Required Fields

- Fabric receipt/order: PO number, meters, mill name.
- Dispatch: PO number, pieces. If the owner says a PO went for dispatch and one dispatch-ready quantity is available, the assistant proposes that quantity.
- Stage completion: PO number, stage, pieces. Missing pieces default to the current pending quantity for that stage where available.
- Stitching assignment: PO number, pieces, contractor.
- Delivery date update: PO number and date.

Optional notes, vehicle details, and remarks do not block simple owner updates.

## Confirmation Behavior

Every write operation creates a pending action and asks for confirmation. The assistant accepts "confirm", "yes", "okay", "do it", and "haan". It accepts "cancel", "no", "stop", and similar cancellation phrases. Confirming twice does not execute twice because the pending action is cleared after execution.

## Audit Behavior

Write handlers call existing services where possible. Fabric, dispatch, stage, PO status/date, and bulk updates create audit entries through the existing audit service or the underlying domain service.

## Token-Saving Strategy

The route uses deterministic parsing before Gemini. Gemini fallback receives only a compact context: mentioned PO records when present, otherwise a small active PO snapshot plus limited fabric, mill, dispatch, and vehicle context. It no longer sends broad database snapshots or long conversation history.

## Gemini Fallback

Gemini is used only when deterministic logic cannot answer or parse the request. It is instructed not to invent records and not to claim writes happened unless a tool confirms it.

## Mobile UI Flow

The Assistant page now shows a clear status, large hold-to-speak button, stop button while listening/speaking, sticky bottom input, and a confirmation card with Confirm, Edit, and Cancel. The confirmation card shows the affected PO.

## Unified Category Field

The Create PO form now shows one "Product / Fabric Category" dropdown. It maps internally to the existing product category and fabric line fields so existing calculations, reports, filters, and records continue working. The edit PO dialog also exposes one Product / Fabric Category field while preserving legacy snapshot values.

## Known Limitations

- Pending action context is currently process-local and single-slot. It is reliable for one owner demo session but should move to a per-user persisted store for multi-user production.
- Gemini fallback is compact by design; very broad analytical questions may need a PDF/report or explicit filter.
- Some complex write actions such as owner override for mismatched fabric still need dedicated service-level UI/route support before voice execution.

## Test Commands

```bash
python3 -m compileall backend/app
python3 -m compileall backend/tests
backend/.venv/bin/python -m pytest backend/tests -q
cd frontend && npm run lint
cd frontend && npm run build
cd frontend && npm run android:sync
```
