-- Add the qualitative stock status the owner writes on the daily sheet
-- ("Short", "Extra", "In stock", "OK", "Nil") plus a separate counter
-- for shortfall pieces (so we can store a deficit without violating the
-- pieces_in_stock >= 0 check).

BEGIN;

ALTER TABLE product_fabric_lines
  ADD COLUMN IF NOT EXISTS stock_status VARCHAR(16) NOT NULL DEFAULT 'unknown'
    CHECK (stock_status IN ('extra', 'in_stock', 'ok', 'nil', 'short', 'unknown')),
  ADD COLUMN IF NOT EXISTS pieces_short INTEGER NOT NULL DEFAULT 0
    CHECK (pieces_short >= 0);

-- Seed values from the 2026-05-20 stock sheet.
-- 109 category already had real data from earlier; leave it as-is.

-- 199-PKD
UPDATE product_fabric_lines l SET pieces_in_stock = 0,    pieces_short = 500,  stock_status = 'short'
  FROM products p WHERE l.product_id = p.id AND p.product_name = '199-PKD' AND l.fabric_code = 'MISTY';
UPDATE product_fabric_lines l SET pieces_in_stock = 2500, pieces_short = 0,    stock_status = 'extra'
  FROM products p WHERE l.product_id = p.id AND p.product_name = '199-PKD' AND l.fabric_code = 'TEAL';
UPDATE product_fabric_lines l SET pieces_in_stock = 2200, pieces_short = 0,    stock_status = 'extra'
  FROM products p WHERE l.product_id = p.id AND p.product_name = '199-PKD' AND l.fabric_code = 'CHARCOAL';

-- 299
UPDATE product_fabric_lines l SET pieces_in_stock = 2000, pieces_short = 0,    stock_status = 'extra'
  FROM products p WHERE l.product_id = p.id AND p.product_name = '299' AND l.fabric_code = 'SAGE-GRID';
UPDATE product_fabric_lines l SET pieces_in_stock = 500,  pieces_short = 0,    stock_status = 'in_stock'
  FROM products p WHERE l.product_id = p.id AND p.product_name = '299' AND l.fabric_code = 'EARTHY-ABSTRACT';
UPDATE product_fabric_lines l SET pieces_in_stock = 0,    pieces_short = 0,    stock_status = 'nil'
  FROM products p WHERE l.product_id = p.id AND p.product_name = '299' AND l.fabric_code = 'MODERN GEO';

-- 399
UPDATE product_fabric_lines l SET pieces_in_stock = 3000, pieces_short = 0,    stock_status = 'in_stock'
  FROM products p WHERE l.product_id = p.id AND p.product_name = '399' AND l.fabric_code = 'JAIPURI';
UPDATE product_fabric_lines l SET pieces_in_stock = 300,  pieces_short = 0,    stock_status = 'extra'
  FROM products p WHERE l.product_id = p.id AND p.product_name = '399' AND l.fabric_code = 'GOLD STEAM';
UPDATE product_fabric_lines l SET pieces_in_stock = 4000, pieces_short = 0,    stock_status = 'extra'
  FROM products p WHERE l.product_id = p.id AND p.product_name = '399' AND l.fabric_code = 'MODERN STONE';

-- 499 — all "OK" on the sheet (no number written).
UPDATE product_fabric_lines l SET stock_status = 'ok'
  FROM products p WHERE l.product_id = p.id AND p.product_name = '499' AND l.fabric_code IN ('FITTED', 'PREMIUM', 'WHITE BEAUTY');

COMMIT;
