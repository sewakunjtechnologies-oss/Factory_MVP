CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TYPE user_role AS ENUM ('owner', 'manager', 'supervisor');
CREATE TYPE po_status AS ENUM (
  'draft', 'fabric_check_pending', 'fabric_ready', 'shortage',
  'cutting', 'stitching', 'size_inspection', 'quality_check',
  'packing', 'dispatch', 'partially_dispatched', 'completed',
  'delayed', 'cancelled'
);
CREATE TYPE contractor_type AS ENUM (
  'mill', 'cutting', 'stitching', 'size_inspection',
  'quality_check', 'packing', 'transport'
);
CREATE TYPE stage_name AS ENUM (
  'fabric_ready', 'cutting', 'stitching',
  'size_inspection', 'quality_check', 'packing', 'dispatch'
);
CREATE TYPE stage_status AS ENUM ('not_started', 'in_progress', 'completed', 'delayed', 'blocked');
CREATE TYPE receipt_status AS ENUM ('pending', 'approved', 'failed', 'returned');
CREATE TYPE shortage_status AS ENUM ('open', 'action_taken', 'closed');
CREATE TYPE fabric_plan_status AS ENUM ('fabric_ready', 'shortage');
CREATE TYPE dispatch_cost_type AS ENUM ('invoice_percent', 'cbm', 'manual');
CREATE TYPE alert_type AS ENUM (
  'stock_shortage', 'stage_delay', 'contractor_delay',
  'shipment_risk', 'packing_risk', 'high_rejection'
);
CREATE TYPE alert_priority AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE quality_action AS ENUM ('repair_in_factory', 'return_to_contractor', 'reject');

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  full_name varchar(120) NOT NULL,
  email varchar(255) NOT NULL UNIQUE,
  password_hash varchar NOT NULL,
  role user_role NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE products (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  product_name varchar(150) NOT NULL,
  product_category varchar(100) NOT NULL DEFAULT 'bedsheet',
  size varchar(100) NOT NULL,
  design varchar(120) NOT NULL,
  color varchar(80) NOT NULL,
  fabric_type varchar(120) NOT NULL,
  gsm numeric(10, 2) NOT NULL CHECK (gsm > 0),
  width numeric(10, 2) NOT NULL CHECK (width > 0),
  per_piece_fabric_usage_m numeric(12, 3) NOT NULL CHECK (per_piece_fabric_usage_m > 0),
  wastage_percent numeric(5, 2) NOT NULL DEFAULT 0 CHECK (wastage_percent >= 0),
  roll_length_m numeric(12, 3) CHECK (roll_length_m > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE purchase_orders (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  po_number varchar(100) NOT NULL UNIQUE,
  product_id uuid NOT NULL REFERENCES products(id),
  order_quantity_pcs integer NOT NULL CHECK (order_quantity_pcs > 0),
  mrp numeric(12, 2) CHECK (mrp >= 0),
  selling_price numeric(12, 2) CHECK (selling_price >= 0),
  order_date date NOT NULL,
  promise_delivery_date date NOT NULL,
  actual_delivery_date date,
  status po_status NOT NULL DEFAULT 'fabric_check_pending',
  notes text,
  created_by uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (promise_delivery_date >= order_date)
);

CREATE TABLE fabric_inventory (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  fabric_type varchar(120) NOT NULL,
  color varchar(80) NOT NULL,
  gsm numeric(10, 2) NOT NULL CHECK (gsm > 0),
  width numeric(10, 2) NOT NULL CHECK (width > 0),
  available_length_m numeric(14, 3) NOT NULL DEFAULT 0 CHECK (available_length_m >= 0),
  approximate_rolls integer CHECK (approximate_rolls >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_fabric_inventory_spec UNIQUE (fabric_type, color, gsm, width)
);

CREATE TABLE fabric_plans (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  purchase_order_id uuid NOT NULL UNIQUE REFERENCES purchase_orders(id) ON DELETE CASCADE,
  required_m numeric(14, 3) NOT NULL CHECK (required_m >= 0),
  wastage_m numeric(14, 3) NOT NULL CHECK (wastage_m >= 0),
  total_required_m numeric(14, 3) NOT NULL CHECK (total_required_m >= 0),
  roll_length_m numeric(12, 3) CHECK (roll_length_m > 0),
  rolls_required integer CHECK (rolls_required >= 0),
  available_m numeric(14, 3) NOT NULL CHECK (available_m >= 0),
  shortage_m numeric(14, 3) NOT NULL CHECK (shortage_m >= 0),
  status fabric_plan_status NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE contractors (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  name varchar(150) NOT NULL,
  contractor_type contractor_type NOT NULL,
  phone varchar(40),
  email varchar(255),
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE stage_summaries (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  purchase_order_id uuid NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
  stage stage_name NOT NULL,
  sequence integer NOT NULL,
  input_qty integer NOT NULL DEFAULT 0 CHECK (input_qty >= 0),
  completed_qty integer NOT NULL DEFAULT 0 CHECK (completed_qty >= 0),
  approved_qty integer NOT NULL DEFAULT 0 CHECK (approved_qty >= 0),
  rejected_qty integer NOT NULL DEFAULT 0 CHECK (rejected_qty >= 0),
  repair_qty integer NOT NULL DEFAULT 0 CHECK (repair_qty >= 0),
  alter_qty integer NOT NULL DEFAULT 0 CHECK (alter_qty >= 0),
  moved_to_next_qty integer NOT NULL DEFAULT 0 CHECK (moved_to_next_qty >= 0),
  pending_qty integer NOT NULL DEFAULT 0 CHECK (pending_qty >= 0),
  status stage_status NOT NULL DEFAULT 'not_started',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_stage_summary_po_stage UNIQUE (purchase_order_id, stage)
);

CREATE TABLE contractor_allocations (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  stage_summary_id uuid NOT NULL REFERENCES stage_summaries(id) ON DELETE CASCADE,
  stage stage_name NOT NULL,
  contractor_id uuid NOT NULL REFERENCES contractors(id),
  issued_qty integer NOT NULL CHECK (issued_qty > 0),
  completed_qty integer NOT NULL DEFAULT 0 CHECK (completed_qty >= 0),
  rejected_qty integer NOT NULL DEFAULT 0 CHECK (rejected_qty >= 0),
  repair_qty integer NOT NULL DEFAULT 0 CHECK (repair_qty >= 0),
  alter_qty integer NOT NULL DEFAULT 0 CHECK (alter_qty >= 0),
  delay_days integer NOT NULL DEFAULT 0 CHECK (delay_days >= 0),
  expected_completion_date date,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE stage_progress_entries (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  stage_summary_id uuid NOT NULL REFERENCES stage_summaries(id) ON DELETE CASCADE,
  allocation_id uuid REFERENCES contractor_allocations(id) ON DELETE SET NULL,
  entry_date date NOT NULL,
  completed_today integer NOT NULL DEFAULT 0 CHECK (completed_today >= 0),
  approved_today integer NOT NULL DEFAULT 0 CHECK (approved_today >= 0),
  rejected_today integer NOT NULL DEFAULT 0 CHECK (rejected_today >= 0),
  repair_today integer NOT NULL DEFAULT 0 CHECK (repair_today >= 0),
  alter_today integer NOT NULL DEFAULT 0 CHECK (alter_today >= 0),
  moved_to_next_stage_today integer NOT NULL DEFAULT 0 CHECK (moved_to_next_stage_today >= 0),
  delay_days integer NOT NULL DEFAULT 0 CHECK (delay_days >= 0),
  remarks text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE quality_failures (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  stage_summary_id uuid NOT NULL REFERENCES stage_summaries(id) ON DELETE CASCADE,
  allocation_id uuid REFERENCES contractor_allocations(id) ON DELETE SET NULL,
  failed_qty integer NOT NULL CHECK (failed_qty > 0),
  resolved_qty integer NOT NULL DEFAULT 0 CHECK (resolved_qty >= 0),
  pending_resolution_qty integer NOT NULL DEFAULT 0 CHECK (pending_resolution_qty >= 0),
  action quality_action NOT NULL,
  reason varchar(255) NOT NULL,
  resolution text,
  action_date date NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fabric_receipts (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  purchase_order_id uuid REFERENCES purchase_orders(id),
  supplier_name varchar(150) NOT NULL,
  fabric_type varchar(120) NOT NULL,
  color varchar(80) NOT NULL,
  gsm numeric(10, 2) NOT NULL CHECK (gsm > 0),
  width numeric(10, 2) NOT NULL CHECK (width > 0),
  received_length_m numeric(14, 3) NOT NULL CHECK (received_length_m >= 0),
  approximate_rolls integer CHECK (approximate_rolls >= 0),
  status receipt_status NOT NULL,
  quality_notes text,
  received_at date NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE supplier_returns (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  fabric_receipt_id uuid NOT NULL REFERENCES fabric_receipts(id),
  supplier_name varchar(150) NOT NULL,
  returned_length_m numeric(14, 3) NOT NULL CHECK (returned_length_m >= 0),
  reason varchar(255) NOT NULL,
  returned_at date NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE debit_notes (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  fabric_receipt_id uuid NOT NULL REFERENCES fabric_receipts(id),
  supplier_name varchar(150) NOT NULL,
  amount numeric(14, 2) CHECK (amount >= 0),
  reason varchar(255) NOT NULL,
  note_date date NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE dispatch_loads (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  purchase_order_id uuid NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
  load_number varchar(100) NOT NULL,
  shipped_qty integer NOT NULL CHECK (shipped_qty > 0),
  cost_type dispatch_cost_type NOT NULL DEFAULT 'invoice_percent',
  invoice_value numeric(14, 2) CHECK (invoice_value > 0),
  dispatch_percent numeric(5, 2) CHECK (dispatch_percent >= 0),
  cbm_value numeric(14, 3) CHECK (cbm_value > 0),
  cbm_rate numeric(14, 2) CHECK (cbm_rate > 0),
  manual_cost numeric(14, 2) CHECK (manual_cost >= 0),
  dispatch_cost numeric(14, 2) NOT NULL CHECK (dispatch_cost >= 0),
  cost_per_piece numeric(14, 4) NOT NULL CHECK (cost_per_piece >= 0),
  shipped_at date NOT NULL,
  transporter_name varchar(150),
  destination varchar(255),
  tracking_reference varchar(150),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE alerts (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  purchase_order_id uuid REFERENCES purchase_orders(id) ON DELETE CASCADE,
  alert_type alert_type NOT NULL,
  priority alert_priority NOT NULL,
  title varchar(150) NOT NULL,
  message text NOT NULL,
  is_resolved boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz
);
