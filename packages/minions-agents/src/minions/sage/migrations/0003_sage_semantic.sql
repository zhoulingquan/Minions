BEGIN;

ALTER TABLE sage.knowledge_item
    ADD COLUMN IF NOT EXISTS embedding_model text NOT NULL DEFAULT '';
ALTER TABLE sage.knowledge_item
    ADD COLUMN IF NOT EXISTS embedding_item_version integer NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS ix_sage_item_embedding_model
    ON sage.knowledge_item (tenant_id, embedding_model, state)
    WHERE embedding IS NOT NULL;

COMMIT;
