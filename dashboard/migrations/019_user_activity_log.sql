-- User activity log table
CREATE TABLE IF NOT EXISTS auth.user_activity_log (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES auth.users(id) ON DELETE SET NULL,
    action      VARCHAR(50) NOT NULL,   -- login | role_change | deactivate | activate | delete | update_profile | provision
    target_id   INTEGER,               -- affected user id for admin actions
    detail      TEXT,                  -- e.g. "role changed to admin"
    ip_address  INET,
    user_agent  TEXT,
    performed_by INTEGER REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_user_activity_log_user    ON auth.user_activity_log(user_id);
CREATE INDEX idx_user_activity_log_action  ON auth.user_activity_log(action);
CREATE INDEX idx_user_activity_log_created ON auth.user_activity_log(created_at DESC);
