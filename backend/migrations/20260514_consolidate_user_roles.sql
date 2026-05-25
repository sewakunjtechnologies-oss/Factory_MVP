-- Consolidate user roles to only `owner` and `manager`.
-- All previous per-stage roles (allocator, verifier, dispatcher, fabric_*, stitching_*, etc.)
-- are migrated to `manager` since their access surface becomes manager-level.

BEGIN;

-- 1. Migrate user rows out of all soon-to-be-removed roles.
UPDATE users
SET role = 'manager'
WHERE role NOT IN ('owner', 'manager');

-- 2. Create a new restricted enum, swap the column over, drop the old enum.
CREATE TYPE user_role_new AS ENUM ('owner', 'manager');

ALTER TABLE users
  ALTER COLUMN role DROP DEFAULT,
  ALTER COLUMN role TYPE user_role_new USING role::text::user_role_new;

DROP TYPE user_role;
ALTER TYPE user_role_new RENAME TO user_role;

COMMIT;
