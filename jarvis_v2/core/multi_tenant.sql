-- multi_tenant.sql - Schema multi-tenant para aislamiento empresarial.
--
-- Estrategia: PRIMARY KEY compuesta (tenant_id, ...) + indexes en tenant_id
-- + Row-level isolation enforced en application layer via WHERE tenant_id=?.
--
-- Diseno para SQLite (cada tenant tiene su propio .db en data/tenants/{id}/
-- memory.db). Para producción enterprise: migrar a PostgreSQL + RLS nativo.
--
-- Conexion model:
--   tenant_db_path = data/tenants/{tenant_id}/memory.db
--   secrets viven encriptados en data/tenants/{tenant_id}/secrets.enc (age)
--   logs structurados a data/tenants/{tenant_id}/logs/*.log (rotated daily)
--
-- Apply: sqlite3 data/tenants/{tenant_id}/memory.db < multi_tenant.sql

-- =====================================================================
-- TABLA 1: tenant_meta - identidad del tenant
-- =====================================================================
CREATE TABLE IF NOT EXISTS tenant_meta (
    tenant_id TEXT PRIMARY KEY,
    legal_name TEXT NOT NULL,
    industry TEXT NOT NULL,
    plan TEXT DEFAULT 'standard',  -- standard | pro | enterprise
    created_at TEXT DEFAULT (datetime('now')),
    last_seen TEXT,
    contact_email TEXT,
    region TEXT DEFAULT 'mx',
    settings_json TEXT,  -- JSON de overrides especificos
    CHECK (industry IN (
        'ecommerce', 'agri_logistics', 'marketing', 'dev',
        'video_pipeline', 'trading', 'generic'
    ))
);

-- =====================================================================
-- TABLA 2: memory_lessons - knowledge persistente del agente PER TENANT
-- (equivalente a memory_manager.recall_lessons pero aislado)
-- =====================================================================
CREATE TABLE IF NOT EXISTS memory_lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    industry TEXT NOT NULL,
    insight TEXT NOT NULL,
    tags TEXT,  -- JSON array
    severity TEXT DEFAULT 'info',  -- info | warning | critical
    confidence REAL DEFAULT 0.5,
    helpful_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (tenant_id) REFERENCES tenant_meta(tenant_id)
);
CREATE INDEX IF NOT EXISTS idx_lessons_tenant ON memory_lessons(tenant_id);
CREATE INDEX IF NOT EXISTS idx_lessons_industry ON memory_lessons(industry);
CREATE INDEX IF NOT EXISTS idx_lessons_tenant_helpful
    ON memory_lessons(tenant_id, helpful_count DESC);

-- =====================================================================
-- TABLA 3: api_credentials - tokens externos PER TENANT (encriptados)
-- Valores guardados como ciphertext con SOPS+age. El plaintext jamas vive
-- en SQL. Esta tabla solo guarda metadata + handle al secret store.
-- =====================================================================
CREATE TABLE IF NOT EXISTS api_credentials (
    tenant_id TEXT NOT NULL,
    provider TEXT NOT NULL,   -- shopify | meta_ads | binance | telegram | ...
    handle TEXT NOT NULL,     -- identifier (e.g. store domain, account id)
    secret_ref TEXT NOT NULL, -- path en secret store (vault key, file path enc)
    scopes TEXT,              -- JSON array
    created_at TEXT DEFAULT (datetime('now')),
    last_used TEXT,
    rotated_at TEXT,
    expires_at TEXT,
    is_active INTEGER DEFAULT 1,
    PRIMARY KEY (tenant_id, provider, handle),
    FOREIGN KEY (tenant_id) REFERENCES tenant_meta(tenant_id)
);

-- =====================================================================
-- TABLA 4: action_log - auditoria completa PER TENANT
-- Cada accion ejecutada por el agente queda registrada para compliance
-- (SOC 2, GDPR right-to-explanation).
-- =====================================================================
CREATE TABLE IF NOT EXISTS action_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    ts TEXT DEFAULT (datetime('now')),
    industry TEXT,
    action_type TEXT,         -- shell | api | click | file_write | ...
    objective_summary TEXT,
    target_or_command TEXT,
    cost_usd REAL DEFAULT 0,
    success INTEGER,
    elapsed_ms INTEGER,
    error TEXT,
    initiated_by TEXT DEFAULT 'agent',  -- agent | user | scheduler
    FOREIGN KEY (tenant_id) REFERENCES tenant_meta(tenant_id)
);
CREATE INDEX IF NOT EXISTS idx_action_tenant_ts
    ON action_log(tenant_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_action_tenant_success
    ON action_log(tenant_id, success);

-- =====================================================================
-- TABLA 5: spend_ledger - billing PER TENANT por modelo LLM usado
-- Para facturar el plan que use cada empresa al final del mes.
-- =====================================================================
CREATE TABLE IF NOT EXISTS spend_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    ts TEXT DEFAULT (datetime('now')),
    provider TEXT,              -- anthropic_proxy | openrouter | gemini_api | ollama
    model TEXT,                 -- claude-haiku-4-5 | claude-sonnet-4-6 | ...
    tokens_in INTEGER,
    tokens_out INTEGER,
    cost_usd REAL,
    objective_id TEXT,
    FOREIGN KEY (tenant_id) REFERENCES tenant_meta(tenant_id)
);
CREATE INDEX IF NOT EXISTS idx_spend_tenant_ts
    ON spend_ledger(tenant_id, ts DESC);

-- =====================================================================
-- TABLA 6: artifacts - archivos generados por el agente PER TENANT
-- (reports, roadmaps, exports). Solo metadata: paths a archivos en
-- data/tenants/{tenant_id}/artifacts/.
-- =====================================================================
CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    ts TEXT DEFAULT (datetime('now')),
    kind TEXT,                  -- report | roadmap | video | csv | code
    relative_path TEXT NOT NULL,
    size_bytes INTEGER,
    metadata_json TEXT,
    FOREIGN KEY (tenant_id) REFERENCES tenant_meta(tenant_id)
);
CREATE INDEX IF NOT EXISTS idx_artifacts_tenant_kind
    ON artifacts(tenant_id, kind);

-- =====================================================================
-- VIEWS de conveniencia (read-only, NO atraviesan tenants)
-- =====================================================================
CREATE VIEW IF NOT EXISTS v_tenant_summary AS
SELECT
    t.tenant_id,
    t.legal_name,
    t.industry,
    t.plan,
    (SELECT COUNT(*) FROM action_log WHERE tenant_id = t.tenant_id) AS total_actions,
    (SELECT COUNT(*) FROM action_log WHERE tenant_id = t.tenant_id AND success = 1) AS ok_actions,
    (SELECT ROUND(SUM(cost_usd), 4) FROM spend_ledger WHERE tenant_id = t.tenant_id) AS total_spend_usd,
    (SELECT COUNT(*) FROM memory_lessons WHERE tenant_id = t.tenant_id) AS lessons_learned,
    (SELECT COUNT(*) FROM api_credentials WHERE tenant_id = t.tenant_id AND is_active = 1) AS active_integrations
FROM tenant_meta t;

-- =====================================================================
-- SEED del tenant default (Emmanuel - dueno del setup)
-- =====================================================================
INSERT OR IGNORE INTO tenant_meta (
    tenant_id, legal_name, industry, plan, contact_email
) VALUES (
    'default', 'Emmanuel Pedraza (Owner)', 'generic', 'enterprise',
    'emmanuelpedrazavega8@gmail.com'
);
