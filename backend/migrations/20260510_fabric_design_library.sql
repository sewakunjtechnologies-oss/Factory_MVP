DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'fabric_design_category') THEN
    CREATE TYPE fabric_design_category AS ENUM (
      'double_bed_sheet',
      'single_bed_sheet',
      'fitted_bed_sheet',
      'king_bed_sheet',
      'pillow',
      'other'
    );
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'po_design_status') THEN
    CREATE TYPE po_design_status AS ENUM (
      'selected_from_library',
      'custom_design',
      'not_provided'
    );
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS fabric_designs (
  id UUID PRIMARY KEY,
  category fabric_design_category NOT NULL,
  design_name VARCHAR(180) NOT NULL,
  design_code VARCHAR(30) NOT NULL UNIQUE,
  image_url VARCHAR(500) NULL,
  color_tags JSONB NULL,
  description TEXT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_by UUID NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_fabric_designs_design_code ON fabric_designs(design_code);
CREATE INDEX IF NOT EXISTS ix_fabric_designs_category ON fabric_designs(category);
CREATE INDEX IF NOT EXISTS ix_fabric_designs_is_active ON fabric_designs(is_active);

ALTER TABLE IF EXISTS purchase_orders
  ADD COLUMN IF NOT EXISTS fabric_design_id UUID NULL REFERENCES fabric_designs(id),
  ADD COLUMN IF NOT EXISTS design_name_snapshot VARCHAR(180) NULL,
  ADD COLUMN IF NOT EXISTS design_code_snapshot VARCHAR(30) NULL,
  ADD COLUMN IF NOT EXISTS design_image_url_snapshot VARCHAR(500) NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'purchase_orders' AND column_name = 'design_status'
  ) THEN
    ALTER TABLE purchase_orders ADD COLUMN design_status po_design_status NOT NULL DEFAULT 'not_provided';
  END IF;
END $$;
