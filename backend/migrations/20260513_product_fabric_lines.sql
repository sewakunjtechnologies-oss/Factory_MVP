-- Product fabric lines: in-house production-to-stock tracking.
-- One product (e.g. "109 MRP Single Bed Sheet") has many fabric variants;
-- each variant has a piece target, current fabric inventory, and stage progress
-- through cutting / stitching / packing / dispatch.

CREATE TABLE IF NOT EXISTS product_fabric_lines (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  fabric_code VARCHAR(80) NOT NULL,
  pieces INTEGER NOT NULL DEFAULT 0 CHECK (pieces >= 0),
  per_piece_meters NUMERIC(8, 3) NOT NULL DEFAULT 0 CHECK (per_piece_meters >= 0),
  stock_meters NUMERIC(14, 3) NOT NULL DEFAULT 0 CHECK (stock_meters >= 0),
  cutting VARCHAR(16) NOT NULL DEFAULT 'pending'
    CHECK (cutting IN ('pending', 'in_progress', 'done')),
  stitching VARCHAR(16) NOT NULL DEFAULT 'pending'
    CHECK (stitching IN ('pending', 'in_progress', 'done')),
  packing VARCHAR(16) NOT NULL DEFAULT 'pending'
    CHECK (packing IN ('pending', 'in_progress', 'done')),
  dispatch VARCHAR(16) NOT NULL DEFAULT 'pending'
    CHECK (dispatch IN ('pending', 'in_progress', 'done')),
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT product_fabric_lines_unique UNIQUE (product_id, fabric_code)
);

CREATE INDEX IF NOT EXISTS idx_product_fabric_lines_product ON product_fabric_lines (product_id);
CREATE INDEX IF NOT EXISTS idx_product_fabric_lines_fabric_code ON product_fabric_lines (fabric_code);

CREATE OR REPLACE FUNCTION set_product_fabric_lines_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS product_fabric_lines_updated_at ON product_fabric_lines;
CREATE TRIGGER product_fabric_lines_updated_at
BEFORE UPDATE ON product_fabric_lines
FOR EACH ROW EXECUTE FUNCTION set_product_fabric_lines_updated_at();
