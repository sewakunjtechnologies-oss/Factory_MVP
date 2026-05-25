-- Add reminder types for the three daily shortage checks:
--   mill_fabric_shortage     — mill ordered N m, received < N m
--   stitching_output_short   — stitching contractor returned fewer pcs than expected
--   fabric_stock_short       — on-hand fabric < required to meet stock production target

ALTER TYPE reminder_type ADD VALUE IF NOT EXISTS 'mill_fabric_shortage';
ALTER TYPE reminder_type ADD VALUE IF NOT EXISTS 'stitching_output_short';
ALTER TYPE reminder_type ADD VALUE IF NOT EXISTS 'fabric_stock_short';
