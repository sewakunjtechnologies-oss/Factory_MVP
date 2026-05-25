-- CBM-based dispatch planning.
--
-- 1. Add bale-spec columns to product_fabric_lines so the owner can record
--    pieces_per_bale + bale_size_cbm + bale_weight_kg for each fabric.
-- 2. New `vehicles` master table (truck name + CBM capacity + max weight).
-- 3. New `dispatch_load_items` linking a dispatch load to multiple
--    fabric_line bales — so a single truck can carry mixed categories.

BEGIN;

ALTER TABLE product_fabric_lines
  ADD COLUMN IF NOT EXISTS pieces_per_bale INTEGER NOT NULL DEFAULT 0
    CHECK (pieces_per_bale >= 0),
  ADD COLUMN IF NOT EXISTS bale_size_cbm NUMERIC(8, 4) NOT NULL DEFAULT 0
    CHECK (bale_size_cbm >= 0),
  ADD COLUMN IF NOT EXISTS bale_weight_kg NUMERIC(8, 2) NOT NULL DEFAULT 0
    CHECK (bale_weight_kg >= 0);

CREATE TABLE IF NOT EXISTS vehicles (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name VARCHAR(120) NOT NULL UNIQUE,
  registration_number VARCHAR(40),
  cbm_capacity NUMERIC(10, 3) NOT NULL CHECK (cbm_capacity > 0),
  max_weight_kg NUMERIC(10, 2) NOT NULL CHECK (max_weight_kg > 0),
  notes TEXT,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_vehicles_active ON vehicles (is_active);

-- Seed a couple of common truck sizes so the owner has examples to pick from.
INSERT INTO vehicles (name, registration_number, cbm_capacity, max_weight_kg, notes)
VALUES
  ('Tata 407 (small)',     NULL, 11.0,  2500.0, 'Light commercial — short hauls'),
  ('Eicher Pro 1110 (medium)', NULL, 32.0,  6500.0, 'Mid-size, common for inter-city'),
  ('Ashok Leyland 16-tonne (large)', NULL, 50.0, 14500.0, 'Long-haul / full truck load')
ON CONFLICT (name) DO NOTHING;

CREATE TABLE IF NOT EXISTS dispatch_load_items (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  dispatch_load_id UUID NOT NULL REFERENCES dispatch_loads(id) ON DELETE CASCADE,
  product_fabric_line_id UUID NOT NULL REFERENCES product_fabric_lines(id) ON DELETE RESTRICT,
  bales INTEGER NOT NULL CHECK (bales > 0),
  pieces INTEGER NOT NULL CHECK (pieces > 0),
  cbm NUMERIC(10, 4) NOT NULL CHECK (cbm >= 0),
  weight_kg NUMERIC(10, 2) NOT NULL CHECK (weight_kg >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dispatch_load_items_load ON dispatch_load_items (dispatch_load_id);
CREATE INDEX IF NOT EXISTS idx_dispatch_load_items_line ON dispatch_load_items (product_fabric_line_id);

COMMIT;
