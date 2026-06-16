BEGIN;

CREATE TABLE IF NOT EXISTS packing_material_inventory (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  purchase_order_id UUID NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
  po_number VARCHAR(100),
  category_name VARCHAR(180) NOT NULL,
  material_name VARCHAR(120) NOT NULL,
  material_type VARCHAR(60) NOT NULL DEFAULT 'other',
  unit VARCHAR(30) NOT NULL DEFAULT 'pcs',
  required_qty NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (required_qty >= 0),
  in_stock_qty NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (in_stock_qty >= 0),
  ordered_qty NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (ordered_qty >= 0),
  received_qty NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (received_qty >= 0),
  consumed_qty NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (consumed_qty >= 0),
  shortage_qty NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (shortage_qty >= 0),
  status VARCHAR(40) NOT NULL DEFAULT 'unknown',
  supplier_name VARCHAR(150),
  expected_delivery_date DATE,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_packing_material_po_material UNIQUE (purchase_order_id, material_name)
);

CREATE INDEX IF NOT EXISTS idx_packing_material_po ON packing_material_inventory (purchase_order_id);
CREATE INDEX IF NOT EXISTS idx_packing_material_po_number ON packing_material_inventory (po_number);
CREATE INDEX IF NOT EXISTS idx_packing_material_category ON packing_material_inventory (category_name);
CREATE INDEX IF NOT EXISTS idx_packing_material_status ON packing_material_inventory (status);

COMMIT;
