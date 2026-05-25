DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'receipt_status') THEN
    CREATE TYPE receipt_status AS ENUM ('pending', 'approved', 'failed', 'returned');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'dispatch_cost_type') THEN
    CREATE TYPE dispatch_cost_type AS ENUM ('invoice_percent', 'cbm', 'manual');
  END IF;
END $$;

ALTER TABLE products
  ALTER COLUMN roll_length_m DROP NOT NULL;

ALTER TABLE fabric_inventory
  ADD COLUMN IF NOT EXISTS approximate_rolls integer CHECK (approximate_rolls >= 0);

ALTER TABLE fabric_plans
  ALTER COLUMN roll_length_m DROP NOT NULL,
  ALTER COLUMN rolls_required DROP NOT NULL;

ALTER TABLE contractor_allocations
  ADD COLUMN IF NOT EXISTS stage stage_name;

UPDATE contractor_allocations allocation
SET stage = summary.stage
FROM stage_summaries summary
WHERE allocation.stage_summary_id = summary.id
  AND allocation.stage IS NULL;

ALTER TABLE contractor_allocations
  ALTER COLUMN stage SET NOT NULL;

ALTER TABLE quality_failures
  ADD COLUMN IF NOT EXISTS resolution text,
  ADD COLUMN IF NOT EXISTS resolved_qty integer DEFAULT 0 CHECK (resolved_qty >= 0),
  ADD COLUMN IF NOT EXISTS pending_resolution_qty integer DEFAULT 0 CHECK (pending_resolution_qty >= 0);

CREATE TABLE IF NOT EXISTS fabric_receipts (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  purchase_order_id uuid REFERENCES purchase_orders(id),
  supplier_name varchar(150) NOT NULL,
  fabric_type varchar(120) NOT NULL,
  color varchar(80) NOT NULL,
  gsm numeric(10, 2) NOT NULL,
  width numeric(10, 2) NOT NULL,
  received_length_m numeric(14, 3) NOT NULL CHECK (received_length_m >= 0),
  approximate_rolls integer CHECK (approximate_rolls >= 0),
  status receipt_status NOT NULL,
  quality_notes text,
  received_at date NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS supplier_returns (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  fabric_receipt_id uuid NOT NULL REFERENCES fabric_receipts(id),
  supplier_name varchar(150) NOT NULL,
  returned_length_m numeric(14, 3) NOT NULL CHECK (returned_length_m >= 0),
  reason varchar(255) NOT NULL,
  returned_at date NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS debit_notes (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  fabric_receipt_id uuid NOT NULL REFERENCES fabric_receipts(id),
  supplier_name varchar(150) NOT NULL,
  amount numeric(14, 2) CHECK (amount >= 0),
  reason varchar(255) NOT NULL,
  note_date date NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE dispatch_loads
  ADD COLUMN IF NOT EXISTS cost_type dispatch_cost_type DEFAULT 'invoice_percent',
  ADD COLUMN IF NOT EXISTS cbm_value numeric(14, 3) CHECK (cbm_value > 0),
  ADD COLUMN IF NOT EXISTS cbm_rate numeric(14, 2) CHECK (cbm_rate > 0),
  ADD COLUMN IF NOT EXISTS manual_cost numeric(14, 2) CHECK (manual_cost >= 0);

UPDATE dispatch_loads
SET cost_type = 'invoice_percent'
WHERE cost_type IS NULL;

ALTER TABLE dispatch_loads
  ALTER COLUMN cost_type SET DEFAULT 'invoice_percent',
  ALTER COLUMN cost_type SET NOT NULL,
  ALTER COLUMN invoice_value DROP NOT NULL,
  ALTER COLUMN dispatch_percent DROP NOT NULL;
