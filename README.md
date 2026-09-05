# Chatbot QA Data Pipeline

챗봇 품질검사 과정에서 반복적으로 생성되는 QA 데이터를 자동 수집하고, 사람의 품질 판정 및 후속 조치와 연결한 뒤, Python/Pandas를 통해 검증·정제하여 PostgreSQL에 적재하고 SQL로 품질 KPI를 분석할 수 있도록 구성한 데이터 파이프라인 프로젝트입니다.

기존 Excel 중심의 QA 관리 업무를 데이터 수집 → 검증 → 저장 → 분석 → 개선 대상으로 이어지는 구조로 정리하고, 반복 실행 시에도 동일한 데이터를 중복 적재하지 않는 데이터 처리 흐름을 구현했습니다.

---

## 공개 범위

이 저장소는 QA 데이터의 검증·적재·분석에 필요한 코드와 SQL을 공개합니다.

| 구분 | 공개 여부 | 비고 |
|---|---|---|
| 데이터 검증 / 중복 검사 | 공개 | `dedup_check.py`, `inspect_test_data.py` |
| PostgreSQL 스키마 / 적재 | 공개 | `sql/00_schema.sql`, `load_chatbot_test.py` |
| SQL 품질 KPI 분석 | 공개 | `sql/01_quality_kpi.sql` |
| 운영 자동 수집 / Google Sheets 연동 | 비공개 | 운영 환경 및 인증정보 관련 설정을 포함하여 제외 |
| 실제 QA 데이터 | 비공개 | 업무 데이터로 저장소에 포함하지 않음 |

실제 업무 데이터와 인증정보는 공개 저장소에 포함하지 않았으며, 자동 수집 및 운영 연동 코드는 공개 가능한 범위와 분리했습니다.

---

## 핵심 결과

| Batch | Collection Success | DB Coverage | Answer Accuracy | Evaluation Progress |
|---|---:|---:|---:|---:|
| 2026-07 | 100.00% | 65.70% | 85.71% | 88.05% |
| 2026-08 | 100.00% | 59.20% | 산출 전 | 0.00% |

- 챗봇 품질을 하나의 성공률로 합치지 않고 **DB Coverage와 Answer Accuracy로 분리**하여 분석했습니다.
- 2026-08 Answer Accuracy는 `0%`가 아닌 **산출 전(NULL)** 으로 처리하여 미평가 데이터가 품질지표를 왜곡하지 않도록 했습니다.
- 초기 KPI에서 `NO_MATCH`에 자동 기록된 `FAIL`이 사람의 평가 완료 건으로 집계되면서 Evaluation Progress가 실제보다 높게 계산되는 문제를 발견했습니다.
- 원천 데이터의 `chatbot_result`와 `evaluation`을 교차 검증하여 원인을 확인하고, **응답 가능 여부와 답변 품질을 분리하도록 KPI 정의와 SQL 집계 로직을 수정**했습니다.

---

## 1. 프로젝트 배경

챗봇 품질검사 업무에서는 반복적인 테스트를 통해 질문, 챗봇 답변, 평가 결과가 지속적으로 생성됩니다.

기존에는 이러한 데이터를 Excel 중심으로 관리했기 때문에 다음과 같은 개선 필요성이 있었습니다.

- 반복적인 챗봇 질문 및 답변 수집 작업 자동화
- 원본 데이터와 처리 데이터의 분리
- 동일 데이터의 중복 적재 방지
- 데이터 무결성 검증
- 챗봇 응답 실패와 수집 실패의 구분
- 사람의 품질 판정과 후속 조치 데이터 연결
- 반복 실행 시에도 결과가 중복되지 않는 적재 구조
- 챗봇 품질 상태를 정량적으로 분석할 수 있는 KPI 구성

이를 개선하기 위해 다음과 같은 QA 데이터 처리 흐름을 구성했습니다.

```text
[QA 질문 데이터]
        │
        ▼
[Playwright 자동 질의]
  ├─ 챗봇 질문 입력
  ├─ 응답 완료 대기
  ├─ 응답 안정성 확인
  ├─ Timeout / Retry 처리
  └─ 수집 실패 별도 기록
        │
        ▼
[Google Sheets MASTER]
  ├─ 질문 / 답변 자동 기록
  ├─ test_id 기반 데이터 관리
  ├─ batch_id / 수집일시 기록
  ├─ 챗봇 응답 여부 기록
  └─ 사람의 품질 판정
        │
        ▼
[QA 후속 조치]
  ├─ FAIL 원인 분류
  ├─ 조치 대상 관리
  └─ QA 개선 대상 연결
        │
        ▼
[Python / Pandas]
  ├─ 필수값 검증
  ├─ 질문 텍스트 정규화
  ├─ Exact 중복 검사
  ├─ 유사 질문 후보 탐지
  └─ 적재 대상 데이터 생성
        │
        ▼
[PostgreSQL]
  ├─ PK / UNIQUE 제약조건
  ├─ CHECK / FK
  └─ 조회용 INDEX
        │
        ▼
[SQL 품질 분석]
  ├─ Collection Success Rate
  ├─ DB Coverage Rate
  ├─ Answer Accuracy
  └─ Evaluation Progress Rate
        │
        ▼
[QA 개선]
```

Google Sheets는 사람이 테스트 결과를 확인하고 판정하는 운영 인터페이스로 사용하고, PostgreSQL은 검증된 QA 데이터를 적재하고 KPI를 산출하는 분석용 저장소로 사용했습니다.

---

## 2. 주요 구현 내용

### 2-1. Playwright 기반 챗봇 QA 자동 수집

반복적으로 수행하던 챗봇 질문 및 답변 수집 작업을 Playwright로 자동화했습니다.

자동화 과정에서는 단순히 질문을 입력하고 텍스트를 복사하는 방식이 아니라 다음 항목을 처리하도록 구성했습니다.

- 질문 자동 입력
- 챗봇 API 응답 대기
- 새로운 답변 생성 여부 확인
- 답변 텍스트가 안정화될 때까지 대기
- Timeout 및 Retry 처리
- 요청 간 Cooldown 적용
- 수집 실패 질문 별도 기록
- 수집 완료 결과 Google Sheets 기록

챗봇의 정상적인 `NO_MATCH` 응답과 Playwright/API 등의 수집 과정에서 발생한 실패를 동일하게 처리하지 않고 분리했습니다.

---

### 2-2. Google Sheets 기반 운영 데이터 관리

자동 수집한 결과는 Google Sheets MASTER에 기록하고, 사람이 품질 판정을 수행할 수 있도록 구성했습니다.

주요 관리 항목은 다음과 같습니다.

- `test_id`
- `batch_id`
- `tested_at`
- `source_type`
- `category`
- `question`
- `answer_raw`
- `chatbot_result`
- `evaluation`
- `failure_type`
- `action_required`
- `note`

`test_id`를 기준으로 기존 수집 여부를 확인하여 동일한 입력 파일을 다시 실행하더라도 이미 처리한 테스트는 건너뛰도록 구성했습니다.

따라서 동일한 질문 문장이 존재하더라도 서로 다른 테스트 ID를 가진 경우에는 별도의 테스트 이력으로 관리할 수 있습니다.

또한 사람의 평가 결과에 따라 후속 조치 관리 시트로 데이터가 이어지도록 구성했습니다.

예를 들어 다음과 같은 품질 판정이 발생하면:

```text
evaluation      = FAIL
failure_type    = WRONG_MATCH
action_required = REVISE_ANSWER
```

해당 테스트가 후속 조치 대상으로 연결되도록 했습니다.

---

### 2-3. E2E 데이터 흐름 검증

자동 수집부터 사람의 판정 및 후속 조치까지 실제 데이터로 End-to-End 흐름을 검증했습니다.

테스트 데이터 3건을 이용하여 다음 흐름을 확인했습니다.

```text
TEST_0978 ~ TEST_0980
        │
        ▼
Playwright 자동 질의
        │
        ▼
챗봇 응답 수집
        │
        ▼
Google Sheets MASTER 적재
        │
        ▼
동일 입력 재실행
→ 기존 test_id 3건 모두 Skip
→ 중복 행 생성 없음
        │
        ▼
TEST_0978 수동 품질 판정
FAIL / WRONG_MATCH / REVISE_ANSWER
        │
        ▼
후속 조치 관리 데이터 연결 확인
```

이를 통해 자동 수집 → 운영 데이터 기록 → 사람의 품질 판정 → 후속 조치로 이어지는 흐름이 정상적으로 동작하는 것을 확인했습니다.

---

## 3. 신규 QA 중복 검증

신규 QA 데이터를 기존 QA 데이터와 비교하여 중복 여부를 검증했습니다.

- 신규 QA: **412건**
- 기존 QA: **8,354건**
- 신규 데이터 내부 Exact 중복: **0건**
- 기존 데이터와 Exact 중복: **3건**
- 유사도 기반 검토 후보: **3건**
- 유사 후보 중 실제 중복 판정: **1건**
- 최종 신규 QA: **408건**

질문 텍스트를 정규화한 뒤 Exact 비교를 우선 수행했습니다.

Exact 비교만으로 판단하기 어려운 질문은 RapidFuzz를 이용해 유사 질문 후보를 추출했습니다.

유사도 점수만으로 데이터를 자동 삭제하지 않고, **RapidFuzz는 사람이 검토할 후보 범위를 좁히는 용도로만 사용하고 최종 중복 여부는 직접 판정**하도록 구성했습니다.

---

## 4. 챗봇 품질검사 데이터 검증 및 적재

챗봇 품질검사 원본 977건을 Pandas로 검증한 뒤 PostgreSQL에 적재했습니다.

- 원본 데이터: **977건**
- 동일 `(batch_id, question)` 중복: **1건**
- 최종 적재 데이터: **976건**
- `test_id` 중복: **0건**
- 필수 질문값 누락: **0건**

원본 Excel 파일에서는 문제가 있는 데이터를 직접 삭제하지 않고 그대로 보존했습니다.

검증 및 변환 과정에서 PostgreSQL 적재 대상 데이터만 별도로 구분함으로써 원본 데이터와 처리 데이터를 분리했습니다.

---

## 5. 재실행 중복 적재 방지

동일한 원본 데이터로 적재 스크립트를 다시 실행하여 멱등성을 확인했습니다.

```text
원본 데이터              977건
        ↓
검증 후 적재 대상         976건
        ↓
PostgreSQL 최초 적재      976건
        ↓
동일 데이터 재실행
        ↓
신규 INSERT                 0건
        ↓
PostgreSQL 최종           976건
```

- 최초 적재: **976건**
- 동일 데이터 재실행 시 신규 적재: **0건**
- 재실행 후 PostgreSQL 총 데이터: **976건**

애플리케이션 단계에서 기존 데이터를 확인하고, 데이터베이스에서도 `UNIQUE` 제약조건을 적용하여 중복 적재를 방지했습니다.

이를 통해 동일 배치 작업을 다시 실행해도 기존 데이터가 중복 생성되지 않는 것을 확인했습니다.

---

## 6. PostgreSQL 데이터 모델

챗봇 테스트 결과를 `chatbot_test` 테이블로 관리하고 있으며, 데이터 무결성과 조회 효율을 고려해 제약조건과 인덱스를 구성했습니다.

| 항목 | 적용 내용 | 목적 |
|---|---|---|
| Primary Key | `test_id` | 테스트 데이터 식별 |
| UNIQUE | `(batch_id, question)` | 동일 배치 내 동일 질문 중복 방지 |
| NOT NULL | `question` | 필수 데이터 누락 방지 |
| CHECK | `evaluation` | 허용된 평가 상태만 저장 |
| Foreign Key | `retest_of_test_id → test_id` | 재검사 데이터 연결을 고려한 구조 |
| INDEX | `(batch_id, evaluation)`, `category` | 월별 품질 및 카테고리 분석 지원 |

`evaluation` 컬럼의 DB 제약조건은 다음 상태를 허용하도록 구성했습니다.

```text
PASS
PARTIAL
FAIL
REVIEW
```

`PARTIAL`도 DB 제약조건상 허용되지만, 현재 KPI에서는 `PASS`, `FAIL`을 평가 완료 상태로 사용합니다.

`REVIEW`는 판정 보류 상태로 간주하며 Answer Accuracy와 Evaluation Progress의 평가 완료 건수에서 제외합니다.

또한 `collection_status`를 별도로 관리하여 다음 두 상황을 구분했습니다.

```text
챗봇이 정상적으로 응답했지만 답을 찾지 못함
→ chatbot_result = NO_MATCH

Playwright / API 등 수집 과정 자체에서 실패
→ collection_status로 별도 관리
```

이를 통해 **챗봇 지식 부족과 데이터 수집 장애를 서로 다른 문제로 분석**할 수 있도록 했습니다.

---

## 7. SQL 품질 KPI 분석

PostgreSQL에 적재한 데이터를 기반으로 챗봇 품질을 하나의 성공률로 합치지 않고 다음 네 가지 지표로 분리했습니다.

### 7-1. Collection Success Rate

자동 수집 과정 자체가 정상적으로 완료되었는지를 확인하는 지표입니다.

```text
Collection Success Rate
= 수집 성공 건수 / 전체 테스트 건수 × 100
```

Playwright 또는 API 처리 실패와 챗봇의 `NO_MATCH`를 구분하기 위해 사용합니다.

---

### 7-2. DB Coverage Rate

챗봇이 테스트 질문에 대해 답변 가능한 지식을 보유하고 있는 정도를 확인하는 지표입니다.

```text
DB Coverage Rate
= ANSWERED / (ANSWERED + NO_MATCH) × 100
```

`NO_MATCH`는 챗봇이 정상적으로 요청을 처리했지만 답변 가능한 데이터를 찾지 못한 경우로 판단합니다.

따라서 DB Coverage가 낮다면 챗봇 지식 DB의 추가 구축 대상으로 볼 수 있습니다.

---

### 7-3. Answer Accuracy

챗봇이 실제로 답변한 질문 중 사람이 평가를 완료한 데이터에 대해 올바른 답변을 반환한 비율을 확인합니다.

```text
Answer Accuracy
= ANSWERED이면서 PASS인 건수
  / (ANSWERED이면서 PASS인 건수 + ANSWERED이면서 FAIL인 건수)
  × 100
```

다음 데이터는 Accuracy 계산에서 제외합니다.

- `NO_MATCH`: 답변 자체가 존재하지 않으므로 정확도 평가 대상이 아님
- `REVIEW`: 아직 최종 판정되지 않은 데이터
- 평가값이 없는 데이터: 아직 사람이 평가하지 않은 데이터

이를 통해 **DB에 지식이 없는 문제와, 지식은 있지만 잘못된 답변을 반환하는 문제를 분리**했습니다.

---

### 7-4. Evaluation Progress Rate

챗봇이 실제로 답변한 데이터 중 사람이 PASS 또는 FAIL 판정을 완료한 비율입니다.

```text
Evaluation Progress Rate
= ANSWERED 중 PASS 또는 FAIL 판정 완료 건수
  / 전체 ANSWERED 건수
  × 100
```

`NO_MATCH`에 자동으로 기록되는 FAIL은 사람의 답변 정확도 평가가 완료된 것으로 간주하지 않습니다.

`REVIEW` 역시 판정 보류 상태이므로 평가 완료 건수에서 제외합니다.

이를 통해 QA 작업 자체의 진행 정도와 챗봇 품질을 서로 다른 지표로 관리할 수 있도록 했습니다.

---

## 8. KPI 분석 결과

SQL을 통해 실제 적재 데이터의 월별 KPI를 검증했습니다.

| Batch | Collection Success | DB Coverage | Answer Accuracy | Evaluation Progress |
|---|---:|---:|---:|---:|
| 2026-07 | 100.00% | 65.70% | 85.71% | 88.05% |
| 2026-08 | 100.00% | 59.20% | 산출 전 | 0.00% |

### 2026-07

총 726건 중:

- 수집 성공: **726건**
- `ANSWERED`: **477건**
- `NO_MATCH`: **249건**
- `PASS`: **360건**
- 전체 `FAIL`: **309건**
- `REVIEW`: **57건**
- `ANSWERED + FAIL`: **60건**

따라서:

```text
Collection Success
= 726 / 726
= 100.00%

DB Coverage
= 477 / (477 + 249)
= 65.70%

Answer Accuracy
= 360 / (360 + 60)
= 85.71%

Evaluation Progress
= (360 + 60) / 477
= 88.05%
```

### 2026-08

2026-08 데이터는 아직 사람의 답변 평가가 진행되지 않은 중간 데이터입니다.

- 전체 테스트: **250건**
- 수집 성공: **250건**
- `ANSWERED`: **148건**
- `NO_MATCH`: **102건**
- `ANSWERED + REVIEW`: **1건**
- `ANSWERED + PASS/FAIL`: **0건**

따라서 Answer Accuracy의 분모가 존재하지 않으므로 **0%로 처리하지 않고 NULL(산출 전)로 관리**합니다.

이는 아직 평가하지 않은 데이터를 오답으로 해석하여 KPI가 왜곡되는 것을 방지하기 위한 처리입니다.

---

## 9. KPI 설계 과정에서 발견한 문제

초기에는 `evaluation = FAIL`을 모두 사람이 평가한 오답으로 집계했습니다.

그러나 실제 데이터를 교차 분석한 결과 2026-08 데이터에서 다음 구조를 확인했습니다.

```text
ANSWERED + NULL                 147건
ANSWERED + REVIEW                1건
NO_MATCH + FAIL + DB_GAP       102건
```

즉 `NO_MATCH` 데이터에 기록된 `FAIL`은 챗봇이 잘못된 답변을 생성했다는 의미가 아니라, **답변 가능한 DB가 존재하지 않는 상태를 표현하기 위한 값**이었습니다.

따라서 단순히 `PASS + FAIL`을 평가 완료 건수로 계산하면 아직 사람의 평가가 거의 진행되지 않은 데이터도 평가 완료로 집계되는 문제가 있었습니다.

이를 해결하기 위해 KPI 계산 기준을 다음과 같이 변경했습니다.

```text
Collection 상태
→ collection_status

챗봇 답변 가능 여부
→ chatbot_result

답변 정확도
→ ANSWERED 데이터의 evaluation

평가 진행률
→ ANSWERED 중 PASS / FAIL 판정 여부
```

즉 데이터에 저장된 값 자체만 집계하지 않고 **각 컬럼의 업무적 의미를 기준으로 KPI를 재정의**했습니다.

---

## 10. Google Sheets와 PostgreSQL의 역할 분리

Google Sheets와 PostgreSQL은 동일한 목적으로 사용하지 않고 역할을 분리했습니다.

### Google Sheets

사람이 직접 확인하고 판단해야 하는 운영 데이터 관리에 사용합니다.

```text
자동 수집 결과 확인
→ PASS / FAIL / REVIEW 판정
→ failure_type 분류
→ action_required 지정
→ 후속 QA 조치 관리
```

### PostgreSQL

검증된 QA 데이터를 저장하고 반복 가능한 SQL 분석을 수행하는 분석용 저장소로 사용합니다.

```text
검증된 QA 데이터 적재
→ 데이터 무결성 관리
→ 월별 집계
→ KPI 산출
→ 실패 유형 분석
```

Python/Pandas가 운영 데이터의 검증·변환 및 PostgreSQL 적재 과정에서 ETL 역할을 담당하도록 구성했습니다.

---

## 11. 기술 스택

### Python

- Pandas를 활용한 Excel 데이터 로드, 검증 및 변환
- 질문 텍스트 정규화 및 중복 처리
- RapidFuzz를 활용한 유사 질문 검토 후보 탐지
- SQLAlchemy / psycopg2를 활용한 PostgreSQL 적재
- 반복 실행 시 기존 데이터 확인 및 중복 적재 방지

### Playwright

- 챗봇 질문 자동 입력
- API 응답 및 신규 답변 생성 대기
- 응답 텍스트 안정성 확인
- Timeout / Retry 처리
- 반복 QA 테스트 자동화

### Google Sheets API / gspread

- 자동 수집 결과 Google Sheets 기록
- MASTER 헤더 검증
- `test_id` 기반 기존 데이터 확인
- 동일 데이터 재실행 시 Skip 처리
- 사람이 평가할 수 있는 운영 데이터 제공

### PostgreSQL

- QA 테스트 데이터 저장
- PK, UNIQUE, CHECK, FK를 활용한 데이터 무결성 관리
- 조회 패턴을 고려한 INDEX 구성

### SQL

- `GROUP BY` 및 조건부 집계를 활용한 품질 현황 분석
- CTE를 활용한 월별 KPI 산출
- Collection Success / DB Coverage / Answer Accuracy / Evaluation Progress 계산

### Git

- 소스 코드 버전 관리
- 실제 업무 데이터 Git 추적 제외
- 인증정보 및 환경정보 저장소 제외

---

## 12. 프로젝트 구조

```text
chatbot_qa_dedup/
├── data/                       # 원본/처리 데이터 (Git 제외)
│
├── sql/
│   ├── 00_schema.sql           # PostgreSQL 테이블 및 제약조건 정의
│   └── 01_quality_kpi.sql      # 챗봇 품질 KPI 분석 SQL
│
├── .gitignore
├── dedup_check.py              # 신규 QA 중복 검증
├── inspect_test_data.py        # 품질검사 데이터 프로파일링
├── load_chatbot_test.py        # PostgreSQL 검증/적재
├── prepare_final.py            # QA 데이터 후처리
└── README.md
```

실제 업무 데이터가 포함된 `data/` 디렉터리는 `.gitignore`에 등록하여 저장소에 포함되지 않도록 했습니다.

Google API 인증정보 및 DB 접속정보 역시 저장소에 직접 포함하지 않도록 관리했습니다.

---

## 13. 실행 흐름

### 1. 신규 QA 중복 검증

```bash
python dedup_check.py
```

신규 QA와 기존 QA를 정규화하여 비교하고 Exact 중복 및 유사 질문 검토 후보를 생성합니다.

---

### 2. 챗봇 테스트 데이터 확인

```bash
python inspect_test_data.py
```

적재 전 데이터의 컬럼, 결측값, 평가 상태, 배치 및 중복 여부를 확인합니다.

---

### 3. PostgreSQL 적재

```bash
python load_chatbot_test.py
```

원본 데이터를 변환·검증한 뒤 기존 데이터와 비교하여 신규 데이터만 PostgreSQL에 적재합니다.

DB 비밀번호는 소스 코드에 저장하지 않고 실행 시 입력받도록 구성했습니다.

---

### 4. 품질 KPI 분석

```text
sql/01_quality_kpi.sql
```

SQL을 실행하여 월별 다음 지표를 확인합니다.

- Collection Success Rate
- DB Coverage Rate
- Answer Accuracy
- Evaluation Progress Rate

---

## 14. 설계 원칙

프로젝트를 구성하면서 다음 원칙을 기준으로 작업했습니다.

### 원본 데이터 보존

원본에서 문제가 발견되더라도 직접 삭제하거나 수정하지 않고, 검증 후 처리 데이터를 별도로 생성합니다.

### 멱등성 확보

동일 데이터를 다시 처리해도 기존 데이터가 중복 생성되지 않도록 구성하고 실제 재실행을 통해 검증했습니다.

### 자동 판정과 사람 판정의 분리

Exact 중복처럼 명확한 규칙은 자동 처리하되, 의미적으로 유사한 질문은 RapidFuzz로 후보만 추출하고 최종 판단은 사람이 수행합니다.

### 수집 실패와 챗봇 품질 문제의 분리

자동화 과정의 장애와 챗봇이 답을 찾지 못한 상황을 동일한 실패로 처리하지 않습니다.

### Coverage와 Accuracy의 분리

DB에 답변 가능한 지식이 존재하는지와, 존재하는 지식을 챗봇이 정확하게 반환하는지를 서로 다른 KPI로 관리합니다.

### 운영과 분석 환경의 분리

Google Sheets는 사람의 입력과 판정을 위한 운영 인터페이스로, PostgreSQL은 검증된 데이터의 저장과 SQL 분석을 위한 환경으로 사용합니다.

---

## 15. 향후 개선

현재 데이터 규모와 업무 주기를 고려하여 필요한 범위 내에서 파이프라인을 구성했습니다.

현재 규모에서는 별도의 대규모 분산 처리나 복잡한 오케스트레이션 도구를 추가하기보다 데이터 품질, 재실행 안정성, KPI 정의와 같은 기본적인 데이터 처리 원칙을 우선했습니다.

향후 데이터 규모와 반복 실행 빈도가 증가할 경우 다음과 같은 방향으로 확장할 수 있습니다.

- Staging Table을 활용한 적재 구조 분리
- `INSERT ... ON CONFLICT` 기반 Upsert 적용
- QA 수정 및 재검사 이력 관리 구조 확장
- 반복 데이터 검증 및 적재 작업의 스케줄링
- 자동 수집 → 평가 → 수정 → 재검사 결과를 연결하는 Retest Loop 구현

---

## 16. 프로젝트를 통해 확인한 점

이 프로젝트를 통해 단순히 QA 데이터를 저장하는 것에서 끝나지 않고, 실제 업무 데이터가 생성되고 활용되는 전체 흐름을 데이터 관점에서 재구성했습니다.

특히 다음 과정을 직접 구현하고 검증했습니다.

- Playwright를 활용한 반복 데이터 수집 자동화
- Google Sheets API를 활용한 운영 데이터 기록
- Python/Pandas 기반 데이터 검증 및 정제
- Exact / Fuzzy 방식의 QA 중복 검증
- PostgreSQL 제약조건을 활용한 데이터 무결성 관리
- 재실행 시 중복되지 않는 적재 구조 검증
- SQL 기반 품질 KPI 설계 및 산출
- 실제 데이터 분포를 확인하여 잘못 정의된 KPI 로직 수정
- DB Coverage와 Answer Accuracy를 분리한 품질 분석 구조 설계

이를 통해 **데이터 수집 → 검증 → 저장 → 분석 → 품질 개선으로 이어지는 QA 데이터 파이프라인을 실제 업무에 적용**했습니다.
