-- Dashboard chat conversation history
CREATE TABLE IF NOT EXISTS dna_app.conversations (
    id BIGSERIAL PRIMARY KEY,
    conversation_id UUID NOT NULL,
    user_id INTEGER NOT NULL,
    message_role VARCHAR(20) NOT NULL,
    message_content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_conversations_conv_id ON dna_app.conversations(conversation_id, created_at);
GRANT SELECT, INSERT ON dna_app.conversations TO dna_user;
