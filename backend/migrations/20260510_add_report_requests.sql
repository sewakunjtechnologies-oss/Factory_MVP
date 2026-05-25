DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'report_request_status') THEN
    CREATE TYPE report_request_status AS ENUM ('pending', 'generating', 'completed', 'failed');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS report_requests (
  id UUID PRIMARY KEY,
  report_type VARCHAR(120) NOT NULL,
  requested_by UUID NULL REFERENCES users(id),
  filters_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  title VARCHAR(255) NOT NULL,
  status report_request_status NOT NULL DEFAULT 'pending',
  file_path VARCHAR(500) NULL,
  download_url VARCHAR(500) NULL,
  error_message TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS ix_report_requests_report_type ON report_requests(report_type);
CREATE INDEX IF NOT EXISTS ix_report_requests_requested_by ON report_requests(requested_by);
