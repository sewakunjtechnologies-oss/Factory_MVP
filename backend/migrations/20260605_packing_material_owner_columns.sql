ALTER TABLE packing_material_inventory
    ADD COLUMN IF NOT EXISTS printed_consumption_qty NUMERIC(14, 3) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS actual_consumption_qty NUMERIC(14, 3) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS printed_stock_qty NUMERIC(14, 3) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS actual_stock_qty NUMERIC(14, 3) NOT NULL DEFAULT 0;

UPDATE packing_material_inventory
SET
    printed_consumption_qty = CASE WHEN printed_consumption_qty = 0 THEN required_qty ELSE printed_consumption_qty END,
    actual_consumption_qty = CASE WHEN actual_consumption_qty = 0 THEN consumed_qty ELSE actual_consumption_qty END,
    printed_stock_qty = CASE WHEN printed_stock_qty = 0 THEN in_stock_qty ELSE printed_stock_qty END,
    actual_stock_qty = CASE WHEN actual_stock_qty = 0 THEN in_stock_qty ELSE actual_stock_qty END;
