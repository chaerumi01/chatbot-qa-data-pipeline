-- ============================================================
-- Chatbot QA Quality KPI
-- PostgreSQL / chatbot_qa.chatbot_test
-- ============================================================


-- ------------------------------------------------------------
-- 1. 배치별 판정 현황
-- 목적: 월별 PASS / FAIL / REVIEW / 미판정 건수 확인
-- ------------------------------------------------------------

SELECT
    batch_id,
    evaluation,
    COUNT(*) AS cnt
FROM chatbot_test
GROUP BY batch_id, evaluation
ORDER BY batch_id, evaluation;


-- ------------------------------------------------------------
-- 2. 배치별 FAIL 원인
-- 목적: FAIL 데이터를 failure_type별로 집계
-- ------------------------------------------------------------

SELECT
    batch_id,
    failure_type,
    COUNT(*) AS fail_count
FROM chatbot_test
WHERE evaluation = 'FAIL'
GROUP BY batch_id, failure_type
ORDER BY batch_id, fail_count DESC;


-- ------------------------------------------------------------
-- 3. DB Coverage
-- 정의:
-- 판정 완료 데이터 중 DB_GAP이 아닌 데이터의 비율
--
-- DB Coverage
-- = (판정 완료 - DB_GAP) / 판정 완료 * 100
-- ------------------------------------------------------------

SELECT
    batch_id,

    COUNT(*) FILTER (
        WHERE evaluation IS NOT NULL
    ) AS evaluated_count,

    COUNT(*) FILTER (
        WHERE failure_type = 'DB_GAP'
    ) AS db_gap_count,

    ROUND(
        100.0 * (
            COUNT(*) FILTER (WHERE evaluation IS NOT NULL)
            - COUNT(*) FILTER (WHERE failure_type = 'DB_GAP')
        )
        / NULLIF(
            COUNT(*) FILTER (WHERE evaluation IS NOT NULL),
            0
        ),
        1
    ) AS db_coverage_pct

FROM chatbot_test
GROUP BY batch_id
ORDER BY batch_id;


-- ------------------------------------------------------------
-- 4. Answer Accuracy
-- 정의:
-- DB_GAP을 제외한 답변 가능 영역에서 PASS한 비율
--
-- Answer Accuracy
-- = PASS / (판정 완료 - DB_GAP) * 100
-- ------------------------------------------------------------

SELECT
    batch_id,

    COUNT(*) FILTER (
        WHERE evaluation IS NOT NULL
          AND failure_type <> 'DB_GAP'
    ) AS answerable_count,

    COUNT(*) FILTER (
        WHERE evaluation = 'PASS'
    ) AS pass_count,

    ROUND(
        100.0
        * COUNT(*) FILTER (
            WHERE evaluation = 'PASS'
        )
        / NULLIF(
            COUNT(*) FILTER (
                WHERE evaluation IS NOT NULL
                  AND failure_type <> 'DB_GAP'
            ),
            0
        ),
        1
    ) AS answer_accuracy_pct

FROM chatbot_test
GROUP BY batch_id
ORDER BY batch_id;


-- ------------------------------------------------------------
-- 5. 월별 품질 KPI 통합 조회
-- 목적:
-- 전체 검사량 / 판정 진행률 / DB Coverage / Answer Accuracy를
-- 배치별 한 행으로 조회
-- ------------------------------------------------------------

WITH monthly AS (
    SELECT
        batch_id,

        COUNT(*) AS total_count,

        COUNT(*) FILTER (
            WHERE evaluation IS NOT NULL
        ) AS evaluated_count,

        COUNT(*) FILTER (
            WHERE evaluation = 'PASS'
        ) AS pass_count,

        COUNT(*) FILTER (
            WHERE evaluation = 'FAIL'
        ) AS fail_count,

        COUNT(*) FILTER (
            WHERE evaluation = 'REVIEW'
        ) AS review_count,

        COUNT(*) FILTER (
            WHERE evaluation IS NULL
        ) AS pending_count,

        COUNT(*) FILTER (
            WHERE failure_type = 'DB_GAP'
        ) AS db_gap_count

    FROM chatbot_test
    GROUP BY batch_id
)

SELECT
    batch_id,
    total_count,
    evaluated_count,
    pending_count,
    pass_count,
    fail_count,
    review_count,

    ROUND(
        100.0 * evaluated_count
        / NULLIF(total_count, 0),
        1
    ) AS evaluation_progress_pct,

    ROUND(
        100.0 * (evaluated_count - db_gap_count)
        / NULLIF(evaluated_count, 0),
        1
    ) AS db_coverage_pct,

    ROUND(
        100.0 * pass_count
        / NULLIF(evaluated_count - db_gap_count, 0),
        1
    ) AS answer_accuracy_pct

FROM monthly
ORDER BY batch_id;