-- Workflow simplification — align DB to the 9-step factory workflow.
--
-- 1. Single cutting contractor (deactivate the 2nd; keep history)
-- 2. Remove packing contractors (packing is in-house workers; deactivate, drop enum value later)
-- 3. Drop Quality Check inspections + Capacity profiles (not part of the new workflow)
-- 4. Remove size_inspection stage rows from stage_summaries (workflow has no size_inspection step)

BEGIN;

-- Deactivate the second cutting contractor; first stays as the canonical single contractor.
UPDATE contractors
SET is_active = FALSE
WHERE contractor_type = 'cutting' AND name = 'Cutting Contractor B';

-- Packing is in-house — deactivate any "packing" contractor rows. Don't delete to preserve
-- any historical stage_cost_entries or contractor_allocations references.
UPDATE contractors SET is_active = FALSE WHERE contractor_type = 'packing';

-- Drop tables that no longer fit the workflow.
DROP TABLE IF EXISTS qc_inspections CASCADE;
DROP TABLE IF EXISTS capacity_profiles CASCADE;

-- Clean up alert types that depended on the dropped concepts. (alerts table has a varchar column,
-- so we just delete rows; no enum change needed.)
DELETE FROM alerts
WHERE alert_type IN (
  'capacity_risk',
  'cutting_underutilization',
  'stitching_underutilization',
  'packing_underutilization',
  'high_rejection'
);

COMMIT;
