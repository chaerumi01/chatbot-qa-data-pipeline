# Chatbot QA Data Pipeline

실제 운영 중인 챗봇의 반복적인 품질검사 업무를 **자동 수집 → 사람의 평가 → 검증·중복 처리 → PostgreSQL 적재 → SQL 품질 분석 → 후속 개선** 흐름으로 구조화한 프로젝트입니다.

기존 Excel 중심의 QA 관리 업무를 반복 가능한 데이터 처리 프로세스로 전환했습니다. 특히 **DB Coverage와 Answer Accuracy를 분리하여 신규 지식 추가가 필요한 영역과 기존 답변 수정이 필요한 영역을 구분**하는 데 중점을 두었습니다.

형식적 정규화와 중복 후보 탐색은 Python으로 처리하고, 질문·답변의 의미를 바꾸는 내용 정제와 최종 품질 판정은 사람이 수행하는 Human-in-the-loop 방식으로 운영했습니다.

## 1. 주요 결과

| 구분 | 검증 결과 |
|---|---|
| 신규 QA 중복 검증 | 기존 8,354건과 신규 후보 412건 비교 → 중복 4건 제외 → 최종 신규 QA 후보 408건 |
| 테스트 결과 적재 | 원본 977건 → 동일 배치·질문 중복 1건 제외 → PostgreSQL 976건 적재 |
| 재실행 검증 | 동일 입력 재실행 시 신규 INSERT 0건, 최종 976건 유지 |
| 운영 흐름 검증 | 테스트 3건으로 자동 수집 → Sheets 기록 → 재실행 Skip → 사람의 판정 → 후속 조치 연결 확인 |

| 분석 배치 | 테스트 수 | DB Coverage | Answer Accuracy | Evaluation Progress |
|---|---:|---:|---:|---:|
| 2026-07 | 726건 | 65.70% | 85.71% | 88.05% |
| 2026-08 | 250건 | 59.20% | 산출 전 | 0.00% |

위 수치는 해당 배치 검증 당시의 결과입니다. 2026-08 배치는 최종 평가된 답변이 없어 Accuracy를 0%가 아닌 `NULL`로 관리했습니다. 품질 개선 전후의 상승 폭을 측정한 결과는 아닙니다.

분석 과정에서는 `NO_MATCH`에 기록된 FAIL과 실제 답변 오류 FAIL이 혼재된 것을 발견했습니다. 이를 구분하도록 KPI를 수정하여 **지식 공백이 답변 오류로 집계되는 문제를 해결**했습니다.

## 2. 프로젝트 배경

기존에는 외부 제작자와 내부 인원에게서 발생한 질문·답변을 사람이 수집하고, 챗봇용 문장으로 정제한 뒤 기존 QA와의 중복 여부를 수기로 확인했습니다. 연도별 관리 기준도 명확하지 않아 기존 데이터와 신규 데이터의 구분이 어려웠습니다.

정기 품질검사 역시 테스트 질문 작성, 챗봇 질의, 답변 확인, 시트 기록, 사람의 평가를 반복하는 방식이었습니다. 작업량이 많고, 답변을 옮기는 과정에서 내용이 누락되거나 질문과 답변이 잘못 연결될 가능성이 있었습니다.

결과가 쌓여도 어떤 지식을 추가하고 어떤 답변을 수정해야 하는지 파악하기 어려웠기 때문에 다음 세 가지를 중심으로 업무를 재구성했습니다.

1. 반복적인 챗봇 테스트와 응답 수집 자동화
2. 원본 보존, 데이터 검증 및 중복 적재 방지
3. 품질 판정을 실제 개선 작업으로 연결하는 KPI 설계

## 3. 전체 데이터 흐름과 공개 범위

```text
[운영 테스트 흐름]
테스트 질문
  → Playwright 자동 질의 및 응답 수집
  → Google Sheets MASTER 기록
  → 사람의 품질 판정 및 후속 조치 지정
  → 테스트 결과 Excel 내보내기
  → Python/Pandas 검증 및 중복 제거
  → PostgreSQL 적재
  → SQL 품질 분석
  → 신규 지식 추가 / 기존 답변 수정 대상 선정

[신규 QA 검증 흐름]
신규 QA 후보 + 기존 QA
  → 비교용 질문 정규화
  → Exact 중복 검사
  → RapidFuzz 유사 질문 후보 탐지
  → 사람의 의미 중복 판정
  → 최종 신규 QA 및 정제 상태별 파일 생성
```

Google Sheets는 사람이 응답을 확인하고 판정하는 **운영 인터페이스**, PostgreSQL은 검증된 테스트 결과를 저장하고 반복 가능한 SQL 분석을 수행하는 **분석용 저장소**로 사용했습니다. 신규 QA 중복 검증과 테스트 결과 적재는 별도 스크립트로 처리합니다.

이 저장소에는 **데이터 검증·중복 검사·후처리·PostgreSQL 스키마 및 적재·SQL 분석 코드**를 공개했습니다. Playwright 자동질의와 Google Sheets 연동은 운영 서비스의 접근 경로 및 내부 데이터와 연결되어 전체 운영 코드를 포함하지 않았습니다. 아래 자동 수집 및 E2E 검증 내용은 해당 운영 환경에서 수행한 작업을 설명합니다.

## 4. 자동 수집과 Human-in-the-loop 운영

### Playwright 기반 응답 수집

Python과 Playwright로 테스트 질문을 입력하고 응답을 수집했습니다. 챗봇 API 응답과 신규 답변 생성을 확인하고, 답변 텍스트가 안정화될 때까지 기다리도록 구성했습니다. Timeout, Retry, 요청 간 Cooldown을 적용하고 수집 실패 질문은 별도로 기록했습니다.

수집 장애와 챗봇의 답변 불가 응답은 구분했습니다.

| 상황 | 관리 기준 |
|---|---|
| 요청은 정상 처리됐으나 답변을 찾지 못함 | `chatbot_result = NO_MATCH` |
| Playwright / API / Timeout 등 수집 과정 실패 | 수집 상태 및 실패 로그 |

### Google Sheets 운영

MASTER에서 다음 항목을 관리했습니다.

| 용도 | 주요 컬럼 |
|---|---|
| 테스트 식별 및 출처 | `test_id`, `batch_id`, `tested_at`, `source_type`, `category` |
| 질문과 응답 | `question`, `answer_raw`, `chatbot_result` |
| 평가와 후속 조치 | `evaluation`, `failure_type`, `action_required`, `note` |

MASTER 헤더를 검증하고 `test_id`로 기존 수집 여부를 확인하여 동일 입력을 재실행하면 이미 처리한 테스트는 Skip했습니다.

평가 상태는 `PASS`(정상), `PARTIAL`(일부 보완 필요), `FAIL`(오류), `REVIEW`(판정 보류)로 구분합니다. KPI 대상인 2026-07/08 배치에는 `PARTIAL`을 사용하지 않았으므로 현재 SQL은 `PASS`와 `FAIL`만 최종 판정으로 집계합니다. 향후 `PARTIAL`을 사용할 때에는 Accuracy와 평가 진행률의 집계 기준을 함께 정의해야 합니다.

실패 유형에 따라 후속 조치도 분리했습니다.

| 실패 유형 | 후속 검토 방향 |
|---|---|
| `DB_GAP` | 신규 지식·QA 추가 후보 |
| `WRONG_MATCH` | 질문과 답변의 매칭 및 기존 QA 수정 검토 |
| `OUTDATED_ANSWER` | 오래된 답변 갱신 |
| `INCOMPLETE_ANSWER` | 부족한 답변 내용 보완 |

### E2E 검증

운영 테스트 `TEST_0978`~`TEST_0980` 3건으로 다음 흐름을 확인했습니다.

1. Playwright 자동 질의 및 응답 수집 후 Google Sheets MASTER에 기록
2. 동일 입력 재실행 시 기존 `test_id` 3건 모두 Skip, 중복 행 없음
3. `TEST_0978`에 `FAIL / WRONG_MATCH / REVISE_ANSWER` 수동 판정
4. 해당 테스트의 후속 조치 관리 데이터 연결 확인

이 검증 범위는 자동 수집부터 사람의 평가·후속 조치 연결까지입니다. PostgreSQL 적재의 재실행 검증은 아래 테스트 결과 977건을 대상으로 별도로 수행했습니다.

## 5. 신규 QA 중복 검증

| 항목 | 건수 |
|---|---:|
| 기존 QA | 8,354 |
| 신규 QA 후보 | 412 |
| 신규 후보 내부 Exact 중복 | 0 |
| 기존 QA와 Exact 중복 | 3 |
| 유사도 기반 검토 후보 | 3 |
| 유사 후보 중 사람이 실제 중복으로 판정 | 1 |
| 최종 신규 QA 후보 | 408 |

`dedup_check.py`는 질문의 소문자화, 공백·문장부호 제거로 비교용 값을 만들고 Exact Match를 수행합니다. 원본 질문은 별도 컬럼에 보존합니다.

기존 QA와 Exact 중복이 아닌 질문은 RapidFuzz의 `token_set_ratio`로 비교합니다. 각 신규 질문의 최상위 매칭 결과 중 점수가 85 이상인 항목을 검토 후보로 추출합니다. 이 점수는 의미 중복의 확률이나 확정 판정이 아니므로, 사람이 검토 파일에 `DUPLICATE`로 판정한 항목만 Exact 중복과 함께 제외합니다.

최종 후보는 `prepare_final.py`에서 관리 컬럼을 정리하고 `answer_clean` 작성 여부에 따라 정제 완료·대기 파일로 나눕니다. **408건은 중복 제외 후 신규 후보 수이며, 전체 답변의 정제 완료나 운영 DB 반영을 뜻하지 않습니다.**

## 6. 테스트 결과 검증 및 PostgreSQL 적재

`load_chatbot_test.py`는 원본 `chatbot_test.xlsx`를 읽고 다음 처리를 수행합니다.

1. 날짜 형태의 `batch_id`를 `BYYYYMM`으로 변환하고 `tested_at`에 배치 날짜 저장
2. `test_id`·`question`의 NULL 및 `test_id` 중복 검사
3. 동일 `(batch_id, question)` 중복은 첫 행을 남겨 적재 대상 생성
4. DB의 기존 `(batch_id, question)`을 조회하여 이미 적재된 항목 제외
5. 신규 행을 적재하고 적재 전후 건수 검증

원본 Excel을 직접 수정하지 않고 메모리에서 적재 대상을 분리합니다. 테스트 적재에서는 질문 원문을 기준으로 중복을 비교하며, 신규 QA 검증에 사용하는 정규화·유사도 비교는 적용하지 않습니다.

```text
원본 977건
  → 동일 배치·질문 중복 1건 제외
  → 최초 적재 976건
  → 동일 입력 재실행: 신규 INSERT 0건
  → DB 최종 976건 유지
```

원본의 `test_id` 중복과 필수 질문값 NULL은 각각 0건이었습니다. 애플리케이션의 기존 키 확인과 DB의 `UNIQUE(batch_id, question)` 제약조건을 함께 사용해 재실행 시 중복 적재를 방지했습니다.

현재 적재는 신규 행 추가 방식입니다. 이미 적재한 행의 평가값 변경을 갱신하는 Upsert와 동시 실행 충돌 처리는 별도 개선 대상입니다. 또한 `tested_at`은 현재 배치 날짜에서 생성하므로 개별 질의의 실제 수행 시각을 나타내지 않습니다.

### 운영 DB 모델

테스트 결과는 `chatbot_test` 테이블을 중심으로 관리했습니다.

| 항목 | 적용 내용 | 목적 |
|---|---|---|
| Primary Key | `test_id` | 테스트 식별 |
| UNIQUE | `(batch_id, question)` | 동일 배치·동일 질문 중복 방지 |
| NOT NULL | `question` | 필수 질문 NULL 방지 |
| CHECK | `evaluation` 허용값 제한 | 잘못된 평가 상태 방지 |
| Foreign Key | `retest_of_test_id → test_id` | 최초 테스트와 재검사 연결 |
| INDEX | `(batch_id, evaluation)` | 배치·평가 상태별 조회 지원 |
| INDEX | `category` | 카테고리별 조회 지원 |

Sheets의 수집 중복 확인 키는 `test_id`, PostgreSQL 적재 중복 확인 키는 `(batch_id, question)`입니다. 현재 DB 구조에서는 같은 질문을 별도 배치로 재검사할 수 있지만, 동일 배치에 같은 질문을 여러 번 저장할 수는 없습니다.

`retest_of_test_id`는 Before / After 비교를 위한 설계이며 현재 적재 스크립트는 이 값을 비워 둡니다. 테이블과 제약조건은 [sql/00_schema.sql](sql/00_schema.sql)에 정의되어 있습니다. `evaluation`의 CHECK 제약조건은 NULL 또는 `PASS`, `PARTIAL`, `FAIL`, `REVIEW`를 허용합니다.

## 7. 품질 KPI 설계와 분석

### 지표 정의

아래 품질 지표는 정상 수집된 테스트 결과를 기준으로 계산합니다.

| 지표 | 계산식 | 활용 |
|---|---|---|
| DB Coverage | `ANSWERED / (ANSWERED + NO_MATCH) × 100` | 테스트 질문에 대한 답변 제공 범위 파악 |
| Answer Accuracy | `ANSWERED 중 PASS / ANSWERED 중 (PASS + FAIL) × 100` | 최종 평가된 답변의 정확도 파악 |
| Evaluation Progress | `ANSWERED 중 (PASS + FAIL) / 전체 ANSWERED × 100` | 사람의 최종 평가 진행률 파악 |

DB Coverage는 테스트 질문 집합에 대한 지표입니다. `NO_MATCH`만으로 지식 자체의 부재를 확정할 수는 없으므로, 낮은 영역은 신규 지식 추가와 기존 지식의 매칭 점검 후보로 활용합니다.

Accuracy에서는 답변이 없는 `NO_MATCH`, 판정 보류인 `REVIEW`, 미평가인 NULL을 제외합니다. 현재 배치에서 사용하지 않은 `PARTIAL`도 현재 SQL의 최종 평가 집계에는 포함되지 않습니다.

### 2026-07: 지식 공백과 오답의 분리

| 챗봇 결과 | 평가 | 건수 |
|---|---|---:|
| ANSWERED | PASS | 360 |
| ANSWERED | FAIL | 60 |
| ANSWERED | REVIEW | 57 |
| NO_MATCH | FAIL | 249 |
| 합계 | | 726 |

```text
ANSWERED = 360 + 60 + 57 = 477건

DB Coverage         = 477 / 726        = 65.70%
Answer Accuracy     = 360 / (360 + 60)  = 85.71%
Evaluation Progress = (360 + 60) / 477  = 88.05%
```

초기에는 `evaluation = FAIL`을 모두 사람이 평가한 오답처럼 집계했습니다. 하지만 전체 FAIL 309건 중 실제 `ANSWERED + FAIL`은 60건이었고, 차이인 249건은 `NO_MATCH`와 일치했습니다.

`NO_MATCH + FAIL + DB_GAP`은 운영 데이터에서 지식 공백을 나타내기 위해 사용한 조합이었습니다. 이를 오답에 포함하면 답변 정확도가 왜곡됩니다. 따라서 **답변 제공 여부는 `chatbot_result`, 답변 정확도는 `ANSWERED`의 `evaluation`, 개선 방향은 `failure_type`과 `action_required`로 구분**했습니다.

### 2026-08: 미평가와 오답의 분리

250건 중 `ANSWERED`는 148건, `NO_MATCH`는 102건이었습니다. 답변한 148건은 평가 NULL 147건과 `REVIEW` 1건으로 구성됐고, 최종 PASS/FAIL 판정은 없었습니다.

따라서 Coverage는 `148 / 250 = 59.20%`, 평가 진행률은 `0 / 148 = 0.00%`입니다. Accuracy는 분모가 0이므로 SQL의 `NULLIF`를 통해 `NULL`로 반환합니다. 평가가 진행되지 않은 상태를 정확도 0%로 해석하지 않도록 했습니다.

### Collection Success Rate의 측정 한계

실제 수집 성공률은 **수집 성공 건수 / 전체 질의 시도 건수**로 계산해야 합니다. 과거 데이터는 성공적으로 수집되어 저장된 결과 중심으로 남아 있어 전체 시도 건수를 완전히 복원하기 어렵습니다.

공개 적재 코드는 모든 적재 대상에 `collection_status = SUCCESS`를 지정합니다. 따라서 현재 SQL이 반환하는 수집 성공률 100%는 **저장된 행의 상태 비율**이며, 전체 시도의 성공률을 입증하지 않습니다. 위 주요 결과에서도 이를 성과 지표로 제시하지 않았습니다.

신규 수집에서는 성공·실패 시도와 재시도를 일관된 기준으로 기록하고, 실패 로그까지 집계 대상에 포함해야 전체 수집 성공률을 계산할 수 있습니다. 현재 공개 적재 코드는 해당 시도 로그를 통합하지 않습니다.

## 8. 기술 스택과 프로젝트 구조

| 기술 | 사용 목적 |
|---|---|
| Python / Pandas | Excel 로드, 프로파일링, 검증, 비교용 정규화, 처리 파일 생성 |
| RapidFuzz | 유사 질문의 사람 검토 후보 추출 |
| SQLAlchemy / psycopg2 | PostgreSQL 연결 및 신규 데이터 적재 |
| PostgreSQL / SQL | 무결성 관리, 조건부 집계·CTE 기반 배치별 KPI 및 실패 유형 분석 |
| Playwright | 운영 환경의 반복 질의 및 응답 수집 |
| Google Sheets API / gspread | 운영 환경의 수집 결과 기록과 사람의 평가 관리 |
| Git / GitHub | 공개 코드 버전 관리 |

```text
chatbot_qa_dedup/
├── data/                      # 업무 원본·처리 데이터 (Git 제외)
├── sql/
│   ├── 00_schema.sql           # PostgreSQL 테이블·제약조건·인덱스 정의
│   └── 01_quality_kpi.sql      # 품질 KPI 및 실패 유형 분석
├── .gitignore
├── dedup_check.py              # 신규 QA 중복 검증 및 사람 판정 반영
├── inspect_test_data.py        # 테스트 결과 프로파일링
├── load_chatbot_test.py        # 테스트 결과 검증 및 PostgreSQL 적재
├── prepare_final.py            # 신규 QA 후처리 및 정제 상태별 분리
└── README.md
```

업무 데이터인 `data/`와 `.env` 파일은 Git 추적 제외 대상으로 관리합니다. Google API 인증정보는 공개 저장소에 포함하지 않으며, DB 비밀번호는 소스에 하드코딩하지 않고 실행 시 `getpass`로 입력받습니다.

## 9. 실행 안내

공개 코드는 내부 입력 파일과 기존 PostgreSQL 테이블을 사용하는 스크립트입니다. 원본 데이터와 운영 자동화 코드는 포함되어 있지 않으므로 저장소만으로 전체 운영 흐름이 바로 실행되지는 않습니다.

### 환경 준비

Python 환경에서 다음 패키지를 설치하고 저장소 루트에서 실행합니다.

```bash
python -m pip install pandas openpyxl rapidfuzz sqlalchemy psycopg2-binary
```

현재 스크립트의 입력 파일 경로와 DB 연결 대상은 코드에 지정되어 있습니다. 자신의 환경에 맞게 준비하거나 수정해야 합니다.

### 신규 QA 검증

필요한 입력은 다음과 같습니다.

- `data/신규QA.xlsx`: `qa_id`, `question_raw` 및 후처리용 관리 컬럼
- `data/QA2024.xlsx`, `data/QA2025.xlsx`: 기존 QA의 `question` 컬럼
- `data/fuzzy_review.csv`: 사람 검토 결과인 `qa_id`, `review_result` 컬럼. 중복 판정값은 `DUPLICATE`

현재 `dedup_check.py`는 검토 CSV를 읽어 최종 결과까지 생성합니다. 검토 후보 CSV를 저장하는 부분은 주석 처리되어 있으므로, 최초 검토 시에는 해당 저장 부분을 활성화해 후보 파일을 만든 뒤 사람이 판정하고 다시 실행해야 합니다.

```bash
python dedup_check.py
python prepare_final.py
```

`prepare_final.py`에서 사용하는 관리 컬럼은 `qa_id`, `source_type`, `source_id`, `question_raw`, `answer_raw`, `answer_clean`, `confirm_status`, `answer_final`, `note`입니다.

출력은 `qa_new_final.csv`, `qa_ready_for_db.csv`, `qa_ready.csv`, `qa_pending.csv`이며 모두 `data/`에 저장됩니다. 동일 이름의 출력 파일은 재실행 시 덮어씁니다. 이 과정에서 신규 QA를 PostgreSQL에 직접 적재하지는 않습니다.

### 테스트 결과 검증 및 적재

`data/chatbot_test.xlsx`에 다음 컬럼이 필요합니다.

```text
test_id, batch_id, source_type, category, question, answer_raw,
chatbot_result, evaluation, failure_type, action_required, note
```

입력의 `batch_id`는 Pandas에서 날짜로 변환할 수 있어야 합니다. 현재 DB 연결 대상은 `localhost:5432`, DB명은 `chatbot_qa`, 사용자는 `postgres`입니다. DB를 준비한 뒤 [sql/00_schema.sql](sql/00_schema.sql)을 실행하여 `chatbot_test` 테이블을 생성합니다. 이 SQL은 최초 생성용이며 이미 테이블이 있는 DB에 반복 실행하는 마이그레이션 스크립트는 아닙니다.

```bash
python inspect_test_data.py
python load_chatbot_test.py
```

첫 명령으로 데이터 분포와 누락·중복을 확인하고, 두 번째 명령에서 비밀번호를 입력해 적재합니다. 기존 행의 수정 내용은 자동 갱신되지 않습니다.

### SQL 분석

PostgreSQL 클라이언트에서 [sql/01_quality_kpi.sql](sql/01_quality_kpi.sql)을 실행합니다. 배치별 평가 분포, FAIL 원인, 개별 KPI 및 통합 KPI를 조회할 수 있습니다.

파일 상단의 Evaluation Progress 요약 주석에는 이전 정의가 남아 있으나, 실제 6·7번 쿼리는 이 문서에 설명한 `ANSWERED 중 PASS/FAIL / 전체 ANSWERED` 기준으로 계산합니다. Collection Success 쿼리의 결과는 앞서 설명한 저장 데이터의 범위 안에서 해석해야 합니다.

## 10. 설계 판단과 다음 단계

현재 데이터 규모와 실행 주기에서는 원본 보존, 검증, 중복 적재 방지, DB 제약조건, 사람의 최종 판단, KPI 정의의 정확성을 우선했습니다. 복잡한 스케줄링이나 다중 작업 의존성 관리의 필요성이 커지면 Airflow 등 오케스트레이션 도구의 도입을 검토할 계획입니다.

데이터 처리 측면의 다음 개선 대상은 다음과 같습니다.

- 입력 파일의 컬럼·타입 명세와 비식별 샘플 제공을 통한 실행 재현성 개선
- 이미 적재한 평가값의 갱신 정책 및 `ON CONFLICT` 기반 적재 처리
- 실제 수집 시각과 성공·실패 시도 로그를 보존하는 적재 구조
- `retest_of_test_id`를 활용한 수정 전후 평가 이력 연결

### EPUBCheck 도메인 확장

현재 QA 평가 구조를 EPUBCheck 오류코드 도메인으로 확장하는 작업을 진행하고 있습니다. 목표 흐름은 다음과 같습니다.

```text
EPUBCheck 오류코드 기반 챗봇 테스트
  → Coverage / Accuracy 측정
  → 지식 공백과 답변 수정 대상 식별
  → 공식 문서 수집 및 오류코드별 근거 매칭
  → Reference Answer 작성·검수
  → 신규·수정 QA 후보 생성 및 DB 보완
  → 재검사 및 Before / After 비교
```

이 흐름의 전체 구현과 개선 효과 검증은 다음 단계입니다. 공식 근거를 수집·구조화하고 현재 평가 방식으로 개선 효과를 확인하는 것을 우선하며, 문서 규모와 검색 요구가 증가하면 Semantic Search나 RAG 등의 필요성을 검토할 계획입니다.
