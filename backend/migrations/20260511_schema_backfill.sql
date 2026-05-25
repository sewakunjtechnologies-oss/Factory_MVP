-- Backfill schema objects that may be missing in partially-migrated local DBs.
-- Safe to run multiple times.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'reminder_priority') THEN
    CREATE TYPE reminder_priority AS ENUM ('low', 'medium', 'high', 'critical');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'reminder_status') THEN
    CREATE TYPE reminder_status AS ENUM ('open', 'completed', 'cancelled');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'reminder_type') THEN
    CREATE TYPE reminder_type AS ENUM (
      'fabric_not_ordered',
      'fabric_order_pending',
      'mill_delivery_due',
      'mill_delivery_due_today',
      'mill_delivery_due_tomorrow',
      'mill_delivery_overdue',
      'fabric_verification_pending',
      'cutting_due',
      'stitching_due',
      'qc_pending',
      'packing_due',
      'dispatch_due',
      'followup_due',
      'partial_delivery_pending',
      'replacement_fabric_pending'
    );
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS reminders (
  id UUID PRIMARY KEY,
  purchase_order_id UUID NULL REFERENCES purchase_orders(id),
  reminder_type reminder_type NOT NULL,
  title VARCHAR(150) NOT NULL,
  message TEXT NOT NULL,
  due_date DATE NOT NULL,
  assigned_to UUID NULL REFERENCES users(id),
  priority reminder_priority NOT NULL,
  status reminder_status NOT NULL DEFAULT 'open',
  escalation_level INTEGER NOT NULL DEFAULT 0,
  escalated_to UUID NULL REFERENCES users(id),
  escalated_at TIMESTAMPTZ NULL,
  escalation_reason TEXT NULL,
  completed_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_reminders_due_date ON reminders(due_date);
CREATE INDEX IF NOT EXISTS ix_reminders_purchase_order_id ON reminders(purchase_order_id);
CREATE INDEX IF NOT EXISTS ix_reminders_assigned_to ON reminders(assigned_to);
CREATE INDEX IF NOT EXISTS ix_reminders_status ON reminders(status);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'po_draft_status') THEN
    CREATE TYPE po_draft_status AS ENUM ('draft', 'needs_review', 'confirmed', 'rejected');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS po_drafts (
  id UUID PRIMARY KEY,
  raw_input_text TEXT NOT NULL,
  po_number VARCHAR(100) NULL,
  quantity_pieces INTEGER NULL,
  order_date DATE NULL,
  shipment_date DATE NULL,
  mrp_on_package NUMERIC(12,2) NULL,
  selling_price NUMERIC(12,2) NULL,
  product_name VARCHAR(150) NULL,
  design VARCHAR(120) NULL,
  color VARCHAR(80) NULL,
  product_size VARCHAR(100) NULL,
  gsm NUMERIC(10,2) NULL,
  meter_per_piece NUMERIC(12,3) NULL,
  wastage_percent NUMERIC(7,4) NULL,
  product_photo_url VARCHAR(500) NULL,
  extracted_fields_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  missing_fields_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  confidence_score DOUBLE PRECISION NOT NULL DEFAULT 0,
  status po_draft_status NOT NULL DEFAULT 'draft',
  created_by UUID NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_po_drafts_po_number ON po_drafts(po_number);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'capacity_product_type') THEN
    CREATE TYPE capacity_product_type AS ENUM (
      'single_bedsheet',
      'double_bedsheet',
      'king_bedsheet',
      'pillow',
      'fitted_sheet',
      'other'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'capacity_stage') THEN
    CREATE TYPE capacity_stage AS ENUM ('cutting', 'stitching', 'packing');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS capacity_profiles (
  id UUID PRIMARY KEY,
  product_type capacity_product_type NOT NULL,
  stage capacity_stage NOT NULL,
  daily_capacity_qty INTEGER NOT NULL,
  worker_count INTEGER NOT NULL DEFAULT 0,
  overtime_allowed BOOLEAN NOT NULL DEFAULT FALSE,
  include_sunday BOOLEAN NOT NULL DEFAULT FALSE,
  effective_from DATE NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  assigned_to UUID NULL,
  responsible_role VARCHAR(80) NULL,
  completed_by UUID NULL,
  completed_at TIMESTAMPTZ NULL,
  remarks VARCHAR(500) NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_capacity_profiles_stage ON capacity_profiles(stage);
CREATE INDEX IF NOT EXISTS ix_capacity_profiles_product_type ON capacity_profiles(product_type);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'mill_followup_status') THEN
    CREATE TYPE mill_followup_status AS ENUM (
      'not_ordered',
      'ordered',
      'in_followup',
      'partially_received',
      'received',
      'delayed',
      'cancelled'
    );
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS mill_followups (
  id UUID PRIMARY KEY,
  mill_order_id UUID NOT NULL REFERENCES fabric_mill_orders(id),
  followup_date DATE NOT NULL,
  followup_by UUID NULL REFERENCES users(id),
  response_notes TEXT NULL,
  next_followup_date DATE NULL,
  status mill_followup_status NOT NULL DEFAULT 'in_followup',
  assigned_to UUID NULL REFERENCES users(id),
  responsible_role VARCHAR(80) NULL,
  completed_by UUID NULL REFERENCES users(id),
  completed_at TIMESTAMPTZ NULL,
  remarks TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_mill_followups_mill_order_id ON mill_followups(mill_order_id);

CREATE TABLE IF NOT EXISTS fabric_issue_to_cutting (
  id UUID PRIMARY KEY,
  purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id),
  fabric_inventory_id UUID NULL REFERENCES fabric_inventory(id),
  fabric_receipt_id UUID NULL REFERENCES fabric_receipts(id),
  contractor_id UUID NULL REFERENCES contractors(id),
  issued_meters NUMERIC(14,3) NOT NULL,
  issued_rolls INTEGER NULL,
  issued_by UUID NULL REFERENCES users(id),
  received_by UUID NULL REFERENCES users(id),
  issue_date DATE NOT NULL,
  expected_return_date DATE NULL,
  status VARCHAR(60) NULL DEFAULT 'issued',
  remarks TEXT NULL,
  assigned_to UUID NULL REFERENCES users(id),
  responsible_role VARCHAR(80) NULL,
  completed_by UUID NULL REFERENCES users(id),
  completed_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_fabric_issue_to_cutting_purchase_order_id ON fabric_issue_to_cutting(purchase_order_id);

CREATE TABLE IF NOT EXISTS cutting_analysis (
  id UUID PRIMARY KEY,
  purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id),
  planned_cut_size VARCHAR(120) NULL,
  actual_cut_size VARCHAR(120) NULL,
  planned_consumption_m NUMERIC(14,3) NOT NULL DEFAULT 0,
  actual_consumption_m NUMERIC(14,3) NOT NULL DEFAULT 0,
  planned_wastage_m NUMERIC(14,3) NOT NULL DEFAULT 0,
  actual_wastage_m NUMERIC(14,3) NOT NULL DEFAULT 0,
  wastage_difference_m NUMERIC(14,3) NOT NULL DEFAULT 0,
  reason_for_difference TEXT NULL,
  cutting_supervisor_id UUID NULL REFERENCES users(id),
  assigned_to UUID NULL REFERENCES users(id),
  responsible_role VARCHAR(80) NULL,
  completed_by UUID NULL REFERENCES users(id),
  completed_at TIMESTAMPTZ NULL,
  remarks TEXT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_cutting_analysis_purchase_order_id ON cutting_analysis(purchase_order_id);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'qc_stage_name') THEN
    CREATE TYPE qc_stage_name AS ENUM ('fabric_ready', 'cutting', 'stitching', 'size_inspection', 'quality_check', 'packing', 'dispatch');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'qc_status') THEN
    CREATE TYPE qc_status AS ENUM ('not_started', 'in_progress', 'completed', 'delayed', 'blocked');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS qc_inspections (
  id UUID PRIMARY KEY,
  purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id),
  stage qc_stage_name NOT NULL,
  inspected_qty INTEGER NOT NULL,
  size_ok BOOLEAN NOT NULL DEFAULT TRUE,
  stitching_ok BOOLEAN NOT NULL DEFAULT TRUE,
  shape_ok BOOLEAN NOT NULL DEFAULT TRUE,
  fabric_defect_found BOOLEAN NOT NULL DEFAULT FALSE,
  defect_notes TEXT NULL,
  passed_qty INTEGER NOT NULL DEFAULT 0,
  failed_qty INTEGER NOT NULL DEFAULT 0,
  repair_qty INTEGER NOT NULL DEFAULT 0,
  alteration_qty INTEGER NOT NULL DEFAULT 0,
  rejected_qty INTEGER NOT NULL DEFAULT 0,
  inspected_by UUID NULL REFERENCES users(id),
  inspection_date DATE NOT NULL,
  status qc_status NOT NULL DEFAULT 'in_progress',
  assigned_to UUID NULL REFERENCES users(id),
  responsible_role VARCHAR(80) NULL,
  completed_by UUID NULL REFERENCES users(id),
  completed_at TIMESTAMPTZ NULL,
  remarks TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_qc_inspections_purchase_order_id ON qc_inspections(purchase_order_id);

CREATE TABLE IF NOT EXISTS packing_outputs (
  id UUID PRIMARY KEY,
  purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id),
  output_date DATE NOT NULL,
  worker_count INTEGER NOT NULL DEFAULT 0,
  packed_qty INTEGER NOT NULL DEFAULT 0,
  pending_qty INTEGER NOT NULL DEFAULT 0,
  daily_target NUMERIC(12,2) NOT NULL DEFAULT 0,
  required_workers NUMERIC(12,2) NOT NULL DEFAULT 0,
  blocker_reason TEXT NULL,
  updated_by UUID NULL REFERENCES users(id),
  assigned_to UUID NULL REFERENCES users(id),
  responsible_role VARCHAR(80) NULL,
  completed_by UUID NULL REFERENCES users(id),
  completed_at TIMESTAMPTZ NULL,
  remarks TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_packing_outputs_purchase_order_id ON packing_outputs(purchase_order_id);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'stage_cost_stage_name') THEN
    CREATE TYPE stage_cost_stage_name AS ENUM ('fabric_ready', 'cutting', 'stitching', 'size_inspection', 'quality_check', 'packing', 'dispatch');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS stage_cost_entries (
  id UUID PRIMARY KEY,
  purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id),
  stage stage_cost_stage_name NOT NULL,
  contractor_id UUID NULL REFERENCES contractors(id),
  qty INTEGER NOT NULL DEFAULT 0,
  rate_per_piece NUMERIC(12,4) NULL,
  manual_cost NUMERIC(14,2) NULL,
  total_stage_cost NUMERIC(14,2) NOT NULL DEFAULT 0,
  cost_per_piece NUMERIC(12,4) NOT NULL DEFAULT 0,
  assigned_to UUID NULL REFERENCES users(id),
  responsible_role VARCHAR(80) NULL,
  completed_by UUID NULL REFERENCES users(id),
  completed_at TIMESTAMPTZ NULL,
  remarks TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_stage_cost_entries_purchase_order_id ON stage_cost_entries(purchase_order_id);
