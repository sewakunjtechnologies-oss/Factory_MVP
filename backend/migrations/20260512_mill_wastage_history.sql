-- Step 5: per-mill wastage memory.
-- Records each cutting verification event with the mill whose fabric was cut,
-- so the owner can query historical wastage per mill across all POs.

CREATE TABLE IF NOT EXISTS mill_wastage_records (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id),
  mill_name VARCHAR(150) NOT NULL,
  cutting_analysis_id UUID REFERENCES cutting_analysis(id),
  planned_wastage_m NUMERIC(14,3) NOT NULL DEFAULT 0,
  actual_wastage_m NUMERIC(14,3) NOT NULL DEFAULT 0,
  wastage_difference_m NUMERIC(14,3) NOT NULL DEFAULT 0,
  flag VARCHAR(16) NOT NULL DEFAULT 'normal',
  recorded_by UUID REFERENCES users(id),
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mill_wastage_records_mill_name ON mill_wastage_records (mill_name);
CREATE INDEX IF NOT EXISTS idx_mill_wastage_records_po ON mill_wastage_records (purchase_order_id);
