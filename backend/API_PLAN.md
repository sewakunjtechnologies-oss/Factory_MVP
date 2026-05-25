# API Plan

Base path: `/api/v1`

## Auth
- POST `/auth/login`
- GET `/auth/me`

## Products
- POST `/products`
- GET `/products`
- GET `/products/{product_id}`
- PATCH `/products/{product_id}`

## Purchase Orders
- POST `/purchase-orders`
- GET `/purchase-orders`
- GET `/purchase-orders/{po_id}`
- PATCH `/purchase-orders/{po_id}`
- GET `/purchase-orders/{po_id}/dashboard`

## Fabric
- POST `/purchase-orders/{po_id}/fabric-plan/recalculate`
- GET `/purchase-orders/{po_id}/fabric-plan`
- PATCH `/purchase-orders/{po_id}/fabric-plan`
- POST `/purchase-orders/{po_id}/fabric-receipts`
- PATCH `/fabric-receipts/{receipt_id}/confirm`
- GET `/fabric-shortages`

## Contractors / Stages
- POST `/contractors`
- GET `/contractors`
- POST `/purchase-orders/{po_id}/stage-allocations`
- GET `/purchase-orders/{po_id}/stage-allocations`
- POST `/purchase-orders/{po_id}/stage-progress`
- GET `/purchase-orders/{po_id}/stage-progress`
- GET `/purchase-orders/{po_id}/stage-summaries`

## Dispatch / Alerts / Dashboard
- POST `/purchase-orders/{po_id}/dispatch-loads`
- GET `/purchase-orders/{po_id}/dispatch-loads`
- GET `/alerts`
- PATCH `/alerts/{alert_id}/resolve`
- GET `/dashboard/owner`
