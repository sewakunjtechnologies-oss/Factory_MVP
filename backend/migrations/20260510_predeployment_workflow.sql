DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
    ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'admin';
    ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'fabric_verifier';
    ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'fabric_allocator';
    ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'cutting_verifier';
    ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'stitching_allocator';
    ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'stitching_verifier';
    ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'packing_allocator';
    ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'packer';
    ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'mill_followup_user';
    ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'qc_manager';
    ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'dispatch_document_user';
  END IF;
END $$;

-- bootstrap missing dependencies for environments that were initialized before
-- mill requirement / fabric mill order tables were introduced.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'mill_order_requirement_status') THEN
    CREATE TYPE mill_order_requirement_status AS ENUM ('pending_mill_selection', 'mill_order_created', 'closed');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS mill_order_requirements (
  id UUID PRIMARY KEY,
  purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id),
  required_meters NUMERIC(14,3) NOT NULL,
  available_meters NUMERIC(14,3) NOT NULL,
  shortage_meters NUMERIC(14,3) NOT NULL,
  gsm NUMERIC(10,2) NULL,
  fabric_type VARCHAR(120) NULL,
  design VARCHAR(120) NULL,
  color VARCHAR(80) NULL,
  suggested_order_meters NUMERIC(14,3) NOT NULL,
  status mill_order_requirement_status NOT NULL DEFAULT 'pending_mill_selection',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'fabric_mill_order_status') THEN
    CREATE TYPE fabric_mill_order_status AS ENUM ('not_ordered', 'ordered', 'in_followup', 'partially_received', 'received', 'delayed', 'cancelled');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS fabric_mill_orders (
  id UUID PRIMARY KEY,
  purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id),
  mill_name VARCHAR(150) NOT NULL,
  ordered_meters NUMERIC(14,3) NOT NULL,
  ordered_width NUMERIC(10,2) NULL,
  ordered_gsm NUMERIC(10,2) NULL,
  ordered_rate_per_meter NUMERIC(14,2) NULL,
  expected_quality_notes TEXT NULL,
  committed_delivery_date DATE NOT NULL,
  actual_delivery_date DATE NULL,
  status fabric_mill_order_status NOT NULL DEFAULT 'ordered',
  responsible_user_id UUID NULL REFERENCES users(id),
  assigned_to UUID NULL REFERENCES users(id),
  responsible_role VARCHAR(80) NULL,
  completed_by UUID NULL REFERENCES users(id),
  completed_at TIMESTAMPTZ NULL,
  remarks TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'po_status') THEN
    ALTER TYPE po_status ADD VALUE IF NOT EXISTS 'dispatched_with_exception';
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'reminder_type') THEN
    ALTER TYPE reminder_type ADD VALUE IF NOT EXISTS 'mill_delivery_due_today';
    ALTER TYPE reminder_type ADD VALUE IF NOT EXISTS 'mill_delivery_due_tomorrow';
    ALTER TYPE reminder_type ADD VALUE IF NOT EXISTS 'partial_delivery_pending';
    ALTER TYPE reminder_type ADD VALUE IF NOT EXISTS 'replacement_fabric_pending';
  END IF;
END $$;

ALTER TABLE IF EXISTS reminders
  ADD COLUMN IF NOT EXISTS escalation_level INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS escalated_to UUID NULL REFERENCES users(id),
  ADD COLUMN IF NOT EXISTS escalated_at TIMESTAMPTZ NULL,
  ADD COLUMN IF NOT EXISTS escalation_reason TEXT NULL;

ALTER TABLE IF EXISTS purchase_orders
  ADD COLUMN IF NOT EXISTS priority_level VARCHAR(30) NULL DEFAULT 'normal',
  ADD COLUMN IF NOT EXISTS priority_reason TEXT NULL,
  ADD COLUMN IF NOT EXISTS priority_updated_by UUID NULL REFERENCES users(id),
  ADD COLUMN IF NOT EXISTS priority_updated_at TIMESTAMPTZ NULL;

ALTER TABLE IF EXISTS fabric_issue_to_cutting
  ADD COLUMN IF NOT EXISTS contractor_id UUID NULL REFERENCES contractors(id),
  ADD COLUMN IF NOT EXISTS expected_return_date DATE NULL,
  ADD COLUMN IF NOT EXISTS status VARCHAR(60) NULL DEFAULT 'issued';

ALTER TABLE IF EXISTS dispatch_loads
  ADD COLUMN IF NOT EXISTS document_status VARCHAR(50) NULL,
  ADD COLUMN IF NOT EXISTS invoice_uploaded BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS packing_list_uploaded BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS eway_bill_uploaded BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS transporter_confirmation BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS buyer_dispatch_approval BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS shortfall_qty INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS shortfall_reason VARCHAR(255) NULL,
  ADD COLUMN IF NOT EXISTS linked_repair_qty INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS linked_alteration_qty INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS audit_logs (
  id UUID PRIMARY KEY,
  action_type VARCHAR(120) NOT NULL,
  purchase_order_id UUID NULL REFERENCES purchase_orders(id),
  entity_type VARCHAR(120) NOT NULL,
  entity_id VARCHAR(120) NOT NULL,
  performed_by UUID NULL REFERENCES users(id),
  role VARCHAR(80) NULL,
  old_value_json JSONB NULL,
  new_value_json JSONB NULL,
  remarks TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_audit_logs_action_type ON audit_logs(action_type);
CREATE INDEX IF NOT EXISTS ix_audit_logs_purchase_order_id ON audit_logs(purchase_order_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_performed_by ON audit_logs(performed_by);

CREATE TABLE IF NOT EXISTS notifications (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  purchase_order_id UUID NULL REFERENCES purchase_orders(id),
  notification_type VARCHAR(120) NOT NULL,
  title VARCHAR(180) NOT NULL,
  message TEXT NOT NULL,
  is_read BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  read_at TIMESTAMPTZ NULL
);
CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS ix_notifications_purchase_order_id ON notifications(purchase_order_id);
CREATE INDEX IF NOT EXISTS ix_notifications_notification_type ON notifications(notification_type);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'mill_order_split_status') THEN
    CREATE TYPE mill_order_split_status AS ENUM ('not_ordered', 'ordered', 'in_followup', 'partially_received', 'received', 'delayed', 'cancelled');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'mill_delivery_lot_status') THEN
    CREATE TYPE mill_delivery_lot_status AS ENUM ('not_ordered', 'ordered', 'in_followup', 'partially_received', 'received', 'delayed', 'cancelled');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'mill_order_prev_status') THEN
    CREATE TYPE mill_order_prev_status AS ENUM ('not_ordered', 'ordered', 'in_followup', 'partially_received', 'received', 'delayed', 'cancelled');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'mill_order_new_status') THEN
    CREATE TYPE mill_order_new_status AS ENUM ('not_ordered', 'ordered', 'in_followup', 'partially_received', 'received', 'delayed', 'cancelled');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS mill_order_splits (
  id UUID PRIMARY KEY,
  purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id),
  mill_order_requirement_id UUID NULL REFERENCES mill_order_requirements(id),
  mill_name VARCHAR(150) NOT NULL,
  split_percent NUMERIC(6,3) NOT NULL,
  ordered_meters NUMERIC(14,3) NOT NULL,
  committed_delivery_date DATE NOT NULL,
  status mill_order_split_status NOT NULL DEFAULT 'ordered',
  responsible_user_id UUID NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_mill_order_splits_purchase_order_id ON mill_order_splits(purchase_order_id);
CREATE INDEX IF NOT EXISTS ix_mill_order_splits_mill_order_requirement_id ON mill_order_splits(mill_order_requirement_id);

CREATE TABLE IF NOT EXISTS mill_delivery_lots (
  id UUID PRIMARY KEY,
  fabric_mill_order_id UUID NOT NULL REFERENCES fabric_mill_orders(id),
  lot_number VARCHAR(80) NOT NULL,
  delivered_meters NUMERIC(14,3) NOT NULL,
  received_date DATE NOT NULL,
  quality_notes TEXT NULL,
  status mill_delivery_lot_status NOT NULL DEFAULT 'partially_received',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_mill_delivery_lots_fabric_mill_order_id ON mill_delivery_lots(fabric_mill_order_id);

CREATE TABLE IF NOT EXISTS mill_order_status_history (
  id UUID PRIMARY KEY,
  fabric_mill_order_id UUID NOT NULL REFERENCES fabric_mill_orders(id),
  previous_status mill_order_prev_status NULL,
  new_status mill_order_new_status NOT NULL,
  reason TEXT NULL,
  changed_by UUID NULL REFERENCES users(id),
  changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_mill_order_status_history_fabric_mill_order_id ON mill_order_status_history(fabric_mill_order_id);
