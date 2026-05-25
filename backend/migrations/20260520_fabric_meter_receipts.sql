-- Audit log for fabric (meter) receipts at the product_fabric_line level.
-- Mirrors pieces_receipts: every receive event becomes a row, and the running
-- stock_meters counter on product_fabric_lines is incremented in the same
-- transaction at the API layer.

BEGIN;

CREATE TABLE IF NOT EXISTS fabric_meter_receipts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  product_fabric_line_id UUID NOT NULL REFERENCES product_fabric_lines(id) ON DELETE CASCADE,
  meters NUMERIC(14, 3) NOT NULL CHECK (meters > 0),
  received_at DATE NOT NULL DEFAULT CURRENT_DATE,
  mill_name VARCHAR(150),
  notes TEXT,
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fabric_meter_receipts_line ON fabric_meter_receipts (product_fabric_line_id);
CREATE INDEX IF NOT EXISTS idx_fabric_meter_receipts_date ON fabric_meter_receipts (received_at DESC);

COMMIT;
