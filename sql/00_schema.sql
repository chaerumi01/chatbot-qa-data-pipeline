-- ============================================================
-- Chatbot QA Database Schema
-- PostgreSQL / chatbot_test
-- ============================================================

CREATE TABLE chatbot_test (
    test_id             VARCHAR(20) PRIMARY KEY,
    batch_id            VARCHAR(20),
    tested_at           TIMESTAMP,
    source_type         VARCHAR(30),
    category            VARCHAR(50),
    question            TEXT NOT NULL,
    answer_raw          TEXT,
    chatbot_result      VARCHAR(30),
    evaluation          VARCHAR(20),
    failure_type        VARCHAR(30),
    action_required     VARCHAR(30),
    note                TEXT,
    collection_status   VARCHAR(20) DEFAULT 'SUCCESS',
    retest_of_test_id   VARCHAR(20),

    CONSTRAINT uq_batch_question
        UNIQUE (batch_id, question),

    CONSTRAINT chk_evaluation
        CHECK (
            evaluation IS NULL
            OR evaluation IN ('PASS', 'PARTIAL', 'FAIL', 'REVIEW')
        ),

    CONSTRAINT fk_retest
        FOREIGN KEY (retest_of_test_id)
        REFERENCES chatbot_test(test_id)
);

CREATE INDEX idx_batch_eval
    ON chatbot_test (batch_id, evaluation);

CREATE INDEX idx_category
    ON chatbot_test (category);
