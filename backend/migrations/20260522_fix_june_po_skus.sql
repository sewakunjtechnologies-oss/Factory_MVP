-- Fix the June import:
--   1. Remove the 28 long-SKU fabric_lines I created (they're duplicates — the
--      size+code suffix is PO-level metadata, not a separate fabric).
--   2. For the 13 truly NEW June fabrics, create short-named lines.
--   3. Re-write the 34 June POs: po_number is now the full SKU as written on
--      the sheet; design_code_snapshot points at the short fabric_code.
--
-- Owner correction (2026-05-22): "BEIGE-DMASK-140X215-PL-TIR-10-26 its the same
-- like BEIGE-DMASK" — i.e., the long SKU is the PO identifier, not the fabric.

BEGIN;

-- ---------------------------------------------------------------------------
-- STEP 1 — wipe just the June POs (May POs are unchanged).
-- ---------------------------------------------------------------------------
-- These POs have no children yet (they were inserted as completed with no
-- mill orders / stage rows attached), so a plain DELETE is enough.
DELETE FROM purchase_orders WHERE po_number LIKE 'PO-202606-%';

-- ---------------------------------------------------------------------------
-- STEP 2 — drop the long-SKU fabric_lines (none of them are referenced now
-- that the June POs are gone).
-- ---------------------------------------------------------------------------
DELETE FROM product_fabric_lines
WHERE fabric_code IN (
  'BEIGE-DMASK-140X215-PL-TIR-10-26',
  'BLUGRN-FLORA-140X215-PL-TIR-10-26',
  'BRN-BRICK-140X215-PL-TIR-10-26',
  'FROSTED-LEAF-140X215-PL-RS7-10-26',
  'GARDEN-BLOOM-140X215-PL-TIR-10-26',
  'MINI-FERN-140X215-PL-RS7-10-26',
  'ORNG-HIBISCUS-140X215-PL-TIR-10-26',
  'RETRO-BLOCK-140X215-PL-RS7-10-26',
  'BLACK&WHITE-140X215-PL-TIR-10-25',
  'CHARCOAL-FOLK-140X215-PL-TIR-10-26',
  'KIDS-CARTOON-140X215-PL-TIR-10-26',
  'MULTI-FLORA-WPC-140X215-PL-TIR-10-26',
  'PACKEDWPC-MISTY-140X215-MC-TIR-6-25',
  'PACKEDWPC-TEAL-140X215-MC-TIR-6-25',
  'EARTHY-ABSTRACT-215X225-MC-TIR-6-26',
  'MIDNIGHT-FLORA-215X225-MC-TIR-6-26',
  'MODERN-GEO-215X225-MC-TIR-6-26',
  'SAGE-GRID-BOTANC-215X225-MC-TIR-6-26',
  'VINTAGE-PAISLEY-215X225-MC-TIR-6-26',
  'GOLD-STEM-220X230-MC-TIR-05-26',
  'JAIPURI-220X240-MC-TIR-05-26',
  'MODERN-STONE-220X230-MC-TIR-05-26',
  'FITTED-180X190-MC-TIR-5-26',
  'PREMIUM-230X270-MC-TIR-5-26',
  'SOLID-PRINT-EMB-230X265-MC-TIR-5-26',
  'WHITEBEAUTY-230X274-MC-TIR-5-26',
  'PLR-300-BLK-STP-111X213-PL-TIR-5-26',
  'PLR-300-BLU-STP-111X213-PL-TIR-5-26'
);

-- ---------------------------------------------------------------------------
-- STEP 3 — insert the 13 new short-named fabric_lines.
-- ---------------------------------------------------------------------------
WITH new_lines(category, fabric_code, per_piece) AS (VALUES
  ('99',  'PLR-300-BLU-STP',  1.42),
  ('99',  'PLR-300-BLK-STP',  1.42),
  ('109', 'BLUGRN-FLORA',     1.42),
  ('109', 'ORNG-HIBISCUS',    1.42),
  ('199', 'MULTI-FLORA-WPC',  1.75),
  ('199', 'BLACK&WHITE',      1.75),
  ('199', 'CHARCOAL-FOLK',    1.43),
  ('199', 'PACKEDWPC-MISTY',  1.75),
  ('199', 'PACKEDWPC-TEAL',   1.75),
  ('199', 'KIDS-CARTOON',     1.75),
  ('299', 'VINTAGE-PAISLEY',  2.85),
  ('299', 'MIDNIGHT-FLORA',   2.85),
  ('299', 'SAGE-GRID-BOTANC', 2.85),
  ('499', 'SOLID-PRINT-EMB',  3.35)
)
INSERT INTO product_fabric_lines (product_id, fabric_code, pieces, per_piece_meters, stock_meters, cutting, stitching, packing, dispatch)
SELECT p.id, nl.fabric_code, 0, nl.per_piece, 0, 'pending','pending','pending','pending'
FROM new_lines nl
JOIN products p ON p.product_name = nl.category
ON CONFLICT (product_id, fabric_code) DO UPDATE SET per_piece_meters = EXCLUDED.per_piece_meters;

-- ---------------------------------------------------------------------------
-- STEP 4 — re-insert June POs.
--   po_number     = full SKU as written on the dispatch sheet
--   design_code_snapshot / design_name_snapshot = short fabric name
--   Duplicates on the sheet get "-#2" / "-#3" suffix so po_number stays unique.
-- ---------------------------------------------------------------------------

WITH jun_data(seq, full_sku, category, fabric_code, pieces) AS (VALUES
  -- 99
  ( 1, '99-PLR-300-BLU-STP-111X213-PL-TIR-5-26',     '99',  'PLR-300-BLU-STP',   6000),
  ( 2, '99-PLR-300-BLK-STP-111X213-PL-TIR-5-26',     '99',  'PLR-300-BLK-STP',  12000),
  -- 109
  ( 3, '109-MINI-FERN-140X215-PL-RS7-10-26',         '109', 'MINI-FERN',         8000),
  ( 4, '109-FROSTED-LEAF-140X215-PL-RS7-10-26',      '109', 'FROSTED-LEAF',      8500),
  ( 5, '109-RETRO-BLOCK-140X215-PL-RS7-10-26',       '109', 'RETRO-BLOCK',       8500),
  ( 6, '109-GARDEN-BLOOM-140X215-PL-TIR-10-26',      '109', 'GARDEN-BLOOM',      5000),
  ( 7, '109-BEIGE-DMASK-140X215-PL-TIR-10-26',       '109', 'BEIGE-DMASK',       8000),
  ( 8, '109-BLUGRN-FLORA-140X215-PL-TIR-10-26',      '109', 'BLUGRN-FLORA',      8000),
  ( 9, '109-ORNG-HIBISCUS-140X215-PL-TIR-10-26',     '109', 'ORNG-HIBISCUS',     8500),
  (10, '109-BRN-BRICK-140X215-PL-TIR-10-26',         '109', 'BRN-BRICK',         9000),
  -- 199 (some entries appear twice on the sheet — disambiguate with -#2)
  (11, '199-MULTI-FLORA-WPC-140X215-PL-TIR-10-26',          '199', 'MULTI-FLORA-WPC',   4000),
  (12, '199-MULTI-FLORA-WPC-140X215-PL-TIR-10-26-#2',       '199', 'MULTI-FLORA-WPC',   8000),
  (13, '199-BLACK&WHITE-140X215-PL-TIR-10-25',              '199', 'BLACK&WHITE',       3000),
  (14, '199-BLACK&WHITE-140X215-PL-TIR-10-25-#2',           '199', 'BLACK&WHITE',       5000),
  (15, '199-CHARCOAL-FOLK-140X215-PL-TIR-10-26',            '199', 'CHARCOAL-FOLK',     3000),
  (16, '199-CHARCOAL-FOLK-140X215-PL-TIR-10-26-#2',         '199', 'CHARCOAL-FOLK',     4000),
  (17, '199-PACKEDWPC-MISTY-140X215-MC-TIR-6-25',           '199', 'PACKEDWPC-MISTY',   3000),
  (18, '199-PACKEDWPC-MISTY-140X215-MC-TIR-6-25-#2',        '199', 'PACKEDWPC-MISTY',   4500),
  (19, '199-PACKEDWPC-TEAL-140X215-MC-TIR-6-25',            '199', 'PACKEDWPC-TEAL',    7000),
  (20, '199-KIDS-CARTOON-140X215-PL-TIR-10-26',             '199', 'KIDS-CARTOON',     10000),
  -- 299
  (21, '299-EARTHY-ABSTRACT-215X225-MC-TIR-6-26',    '299', 'EARTHY-ABSTRACT',   4002),
  (22, '299-VINTAGE-PAISLEY-215X225-MC-TIR-6-26',    '299', 'VINTAGE-PAISLEY',   4002),
  (23, '299-MIDNIGHT-FLORA-215X225-MC-TIR-6-26',     '299', 'MIDNIGHT-FLORA',    4998),
  (24, '299-SAGE-GRID-BOTANC-215X225-MC-TIR-6-26',   '299', 'SAGE-GRID-BOTANC',  6498),
  (25, '299-MODERN-GEO-215X225-MC-TIR-6-26',         '299', 'MODERN GEO',        9498),
  -- 399
  (26, '399-MODERN-STONE-220X230-MC-TIR-05-26',      '399', 'MODERN STONE',      6000),
  (27, '399-JAIPURI-220X240-MC-TIR-05-26',           '399', 'JAIPURI',           7000),
  (28, '399-GOLD-STEM-220X230-MC-TIR-05-26',         '399', 'GOLD STEAM',        8000),
  -- 499 (duplicates → -#2)
  (29, '499-PREMIUM-230X270-MC-TIR-5-26',            '499', 'PREMIUM',           2000),
  (30, '499-FITTED-180X190-MC-TIR-5-26',             '499', 'FITTED',            3000),
  (31, '499-PREMIUM-230X270-MC-TIR-5-26-#2',         '499', 'PREMIUM',           3000),
  (32, '499-SOLID-PRINT-EMB-230X265-MC-TIR-5-26',    '499', 'SOLID-PRINT-EMB',   3500),
  (33, '499-FITTED-180X190-MC-TIR-5-26-#2',          '499', 'FITTED',            4000),
  (34, '499-WHITEBEAUTY-230X274-MC-TIR-5-26',        '499', 'WHITE BEAUTY',      6000)
)
INSERT INTO purchase_orders (
  po_number, product_id, order_quantity_pcs, mrp,
  order_date, promise_delivery_date, actual_delivery_date,
  status, design_status, design_name_snapshot, design_code_snapshot,
  notes
)
SELECT
  jd.full_sku,
  p.id,
  jd.pieces,
  jd.category::numeric,
  DATE '2026-06-01',
  DATE '2026-06-30',
  DATE '2026-06-28',
  'completed'::po_status,
  'custom_design'::po_design_status,
  jd.fabric_code,
  jd.fabric_code,
  'June 2026 dispatch'
FROM jun_data jd
JOIN products p ON p.product_name = jd.category;

COMMIT;
