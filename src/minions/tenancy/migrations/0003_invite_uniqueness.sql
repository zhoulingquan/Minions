-- A tenant may have only one live invitation for the same login name.
WITH duplicates AS (
    SELECT invite_id,
           row_number() OVER (
               PARTITION BY tenant_id, lower(username)
               ORDER BY created_at DESC, invite_id DESC
           ) AS duplicate_rank
    FROM tenant_invites
    WHERE status='pending'
)
UPDATE tenant_invites AS invite
SET status='revoked'
FROM duplicates
WHERE invite.invite_id=duplicates.invite_id
  AND duplicates.duplicate_rank > 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_pending_invite_username
    ON tenant_invites (tenant_id, lower(username))
    WHERE status='pending';

INSERT INTO tenancy_schema_version(version) VALUES (3)
ON CONFLICT (version) DO NOTHING;
