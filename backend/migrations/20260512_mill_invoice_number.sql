-- Step 1: each fabric mill order acts as an invoice to the mill.
-- Add a stable, owner-readable invoice_number column. Existing rows get backfilled.

ALTER TABLE fabric_mill_orders
  ADD COLUMN IF NOT EXISTS invoice_number VARCHAR(40);

-- Backfill any existing rows with a sequential number per creation date.
WITH numbered AS (
  SELECT
    id,
    'MILL-INV-' || to_char(created_at, 'YYYY') || '-' ||
    lpad(ROW_NUMBER() OVER (
      PARTITION BY to_char(created_at, 'YYYY')
      ORDER BY created_at, id
    )::text, 4, '0') AS new_invoice_number
  FROM fabric_mill_orders
  WHERE invoice_number IS NULL
)
UPDATE fabric_mill_orders fmo
SET invoice_number = n.new_invoice_number
FROM numbered n
WHERE fmo.id = n.id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_fabric_mill_orders_invoice_number
  ON fabric_mill_orders (invoice_number);
