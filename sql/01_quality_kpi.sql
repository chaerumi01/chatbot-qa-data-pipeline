-- ============================================================
-- Chatbot QA Quality KPI
-- PostgreSQL / chatbot_qa.chatbot_test
--
-- KPI Definitions
-- 1. Collection Success Rate
--    = 정상 수집 건수 / 전체 테스트 건수
--
-- 2. DB Coverage Rate
--    = ANSWERED / (ANSWERED + NO_MATCH)
--
-- 3. Answer Accuracy
--    = PASS / (ANSWERED 상태이면서 PASS 또는 FAIL로 판정 완료된 건수)
--
-- 4. Evaluation Progress Rate
--    = (PASS + FAIL) / (PASS + FAIL + REVIEW)
--
-- REVIEW = 판정 보류 상태이므로 Answer Accuracy에서 제외
-- NO_MATCH = 수집 실패가 아닌 챗봇의 DB Coverage 문제
-- ============================================================


-- ------------------------------------------------------------
-- 1. 배치별 판정 현황
-- 목적: PASS / FAIL / REVIEW / 미판정 건수 확인
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
-- 3. Collection Success Rate
-- 정의:
-- 정상적으로 수집된 테스트 / 전체 테스트
--
-- 수집 실패와 NO_MATCH를 분리하기 위한 파이프라인 KPI
-- ------------------------------------------------------------

SELECT
    batch_id,

    COUNT(*) AS total_count,

    COUNT(*) FILTER (
        WHERE collection_status = 'SUCCESS'
    ) AS collection_success_count,

    ROUND(
        100.0
        * COUNT(*) FILTER (
            WHERE collection_status = 'SUCCESS'
        )
        / NULLIF(COUNT(*), 0),
        2
    ) AS collection_success_rate

FROM chatbot_test
GROUP BY batch_id
ORDER BY batch_id;


-- ------------------------------------------------------------
-- 4. DB Coverage Rate
-- 정의:
-- 정상 수집된 테스트 중 챗봇이 실제 답변을 반환한 비율
--
-- DB Coverage
-- = ANSWERED / (ANSWERED + NO_MATCH)
-- ------------------------------------------------------------

SELECT
    batch_id,

    COUNT(*) FILTER (
        WHERE collection_status = 'SUCCESS'
          AND chatbot_result = 'ANSWERED'
    ) AS answered_count,

    COUNT(*) FILTER (
        WHERE collection_status = 'SUCCESS'
          AND chatbot_result = 'NO_MATCH'
    ) AS no_match_count,

    ROUND(
        100.0
        * COUNT(*) FILTER (
            WHERE collection_status = 'SUCCESS'
              AND chatbot_result = 'ANSWERED'
        )
        /
        NULLIF(
            COUNT(*) FILTER (
                WHERE collection_status = 'SUCCESS'
                  AND chatbot_result IN ('ANSWERED', 'NO_MATCH')
            ),
            0
        ),
        2
    ) AS db_coverage_rate

FROM chatbot_test
GROUP BY batch_id
ORDER BY batch_id;


-- ------------------------------------------------------------
-- 5. Answer Accuracy
-- 정의:
-- ANSWERED 상태이며 PASS / FAIL 판정이 완료된 답변 중
-- PASS 비율
--
-- REVIEW는 판정 보류이므로 분모에서 제외
-- NO_MATCH는 DB Coverage 문제이므로 Accuracy에서 제외
-- ------------------------------------------------------------

SELECT
    batch_id,

    COUNT(*) FILTER (
        WHERE collection_status = 'SUCCESS'
          AND chatbot_result = 'ANSWERED'
          AND evaluation = 'PASS'
    ) AS pass_count,

    COUNT(*) FILTER (
        WHERE collection_status = 'SUCCESS'
          AND chatbot_result = 'ANSWERED'
          AND evaluation = 'FAIL'
    ) AS answered_fail_count,

    COUNT(*) FILTER (
        WHERE collection_status = 'SUCCESS'
          AND chatbot_result = 'ANSWERED'
          AND evaluation = 'REVIEW'
    ) AS review_count,

    ROUND(
        100.0
        * COUNT(*) FILTER (
            WHERE collection_status = 'SUCCESS'
              AND chatbot_result = 'ANSWERED'
              AND evaluation = 'PASS'
        )
        /
        NULLIF(
            COUNT(*) FILTER (
                WHERE collection_status = 'SUCCESS'
                  AND chatbot_result = 'ANSWERED'
                  AND evaluation IN ('PASS', 'FAIL')
            ),
            0
        ),
        2
    ) AS answer_accuracy

FROM chatbot_test
GROUP BY batch_id
ORDER BY batch_id;


-- ------------------------------------------------------------
-- 6. Evaluation Progress Rate
-- 정의:
-- ANSWERED된 테스트 중 PASS / FAIL 판정이 완료된 비율
--
-- NO_MATCH는 평가 대상 답변이 없으므로 제외
-- REVIEW 및 NULL은 아직 판정이 완료되지 않은 상태
-- ------------------------------------------------------------

SELECT
    batch_id,

    COUNT(*) FILTER (
        WHERE chatbot_result = 'ANSWERED'
          AND evaluation = 'PASS'
    ) AS evaluated_pass_count,

    COUNT(*) FILTER (
        WHERE chatbot_result = 'ANSWERED'
          AND evaluation = 'FAIL'
    ) AS evaluated_fail_count,

    COUNT(*) FILTER (
        WHERE chatbot_result = 'ANSWERED'
    ) AS answer_evaluation_target_count,

    ROUND(
        100.0
        * COUNT(*) FILTER (
            WHERE chatbot_result = 'ANSWERED'
              AND evaluation IN ('PASS', 'FAIL')
        )
        /
        NULLIF(
            COUNT(*) FILTER (
                WHERE chatbot_result = 'ANSWERED'
            ),
            0
        ),
        2
    ) AS evaluation_progress_rate

FROM chatbot_test
WHERE collection_status = 'SUCCESS'
GROUP BY batch_id
ORDER BY batch_id;


-- ------------------------------------------------------------
-- 7. 배치별 품질 KPI 통합 조회
-- 목적:
-- Collection Success / DB Coverage / Answer Accuracy /
-- Evaluation Progress를 한 행에서 확인
-- ------------------------------------------------------------

WITH kpi AS (
    SELECT
        batch_id,

        COUNT(*) AS total_count,

        COUNT(*) FILTER (
            WHERE collection_status = 'SUCCESS'
        ) AS collection_success_count,

        COUNT(*) FILTER (
            WHERE collection_status = 'SUCCESS'
              AND chatbot_result = 'ANSWERED'
        ) AS answered_count,

        COUNT(*) FILTER (
            WHERE collection_status = 'SUCCESS'
              AND chatbot_result = 'NO_MATCH'
        ) AS no_match_count,

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
            WHERE collection_status = 'SUCCESS'
              AND chatbot_result = 'ANSWERED'
              AND evaluation = 'PASS'
        ) AS answered_pass_count,

        COUNT(*) FILTER (
            WHERE collection_status = 'SUCCESS'
              AND chatbot_result = 'ANSWERED'
              AND evaluation = 'FAIL'
        ) AS answered_fail_count

    FROM chatbot_test
    GROUP BY batch_id
)

SELECT
    batch_id,
    total_count,
    collection_success_count,
    answered_count,
    no_match_count,
    pass_count,
    fail_count,
    review_count,

    ROUND(
        100.0 * collection_success_count
        / NULLIF(total_count, 0),
        2
    ) AS collection_success_rate,

    ROUND(
        100.0 * answered_count
        / NULLIF(answered_count + no_match_count, 0),
        2
    ) AS db_coverage_rate,

    ROUND(
        100.0 * answered_pass_count
        / NULLIF(answered_pass_count + answered_fail_count, 0),
        2
    ) AS answer_accuracy,

    ROUND(
    100.0 * (answered_pass_count + answered_fail_count)
    / NULLIF(answered_count, 0),
    2
) AS evaluation_progress_rate

FROM kpi
ORDER BY batch_id;