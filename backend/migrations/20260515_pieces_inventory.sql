-- Pieces stock inventory.
--
-- Adds two things:
--   1. A `pieces_in_stock` running count on each product_fabric_lines row — finished pieces
--      currently sitting in the warehouse, available to fulfill new POs without making more.
--   2. A `pieces_receipts` log table for every receipt event (mostly non-PO production runs).
--
-- Both are wrapped in transactions at the API layer so the count and the log can't drift.

BEGIN;

ALTER TABLE product_fabric_lines
  ADD COLUMN IF NOT EXISTS pieces_in_stock INTEGER NOT NULL DEFAULT 0
    CHECK (pieces_in_stock >= 0);

CREATE TABLE IF NOT EXISTS pieces_receipts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  product_fabric_line_id UUID NOT NULL REFERENCES product_fabric_lines(id) ON DELETE CASCADE,
  pieces INTEGER NOT NULL CHECK (pieces > 0),
  received_at DATE NOT NULL DEFAULT CURRENT_DATE,
  mill_name VARCHAR(150),
  notes TEXT,
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pieces_receipts_line ON pieces_receipts (product_fabric_line_id);
CREATE INDEX IF NOT EXISTS idx_pieces_receipts_date ON pieces_receipts (received_at DESC);

COMMIT;
