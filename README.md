# Chatbot QA Data Pipeline

챗봇 품질검사 과정에서 생성되는 QA 데이터를 체계적으로 관리하고 분석하기 위해 구축한 데이터 파이프라인 프로젝트입니다.

기존 Excel 중심의 QA 관리 데이터를 Python/Pandas로 검증·정제하고 PostgreSQL에 적재한 뒤, SQL을 활용해 챗봇의 품질 지표를 분석할 수 있도록 구성했습니다.

## 프로젝트 배경

챗봇 품질검사 업무에서는 반복적인 테스트를 통해 질문, 챗봇 답변, 평가 결과가 지속적으로 생성됩니다.

기존에는 이러한 데이터를 Excel 중심으로 관리했기 때문에 다음과 같은 개선 필요성이 있었습니다.

- 동일 질문의 중복 적재 방지
- 원본 데이터와 처리 데이터의 분리
- 데이터 무결성 검증
- 반복 실행 시 중복되지 않는 적재 구조
- 챗봇 품질 상태를 정량적으로 분석할 수 있는 지표 구성

이를 개선하기 위해

Playwright
    ↓
Google Sheets
    ↓
Python / Pandas
    ↓
PostgreSQL
    ↓
SQL 분석
    ↓
QA 개선 흐름으로 QA 데이터 처리 구조를 구현했습니다.

## 데이터 처리 흐름

```text
[QA 원천 데이터]
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
  ├─ 월별 평가 현황
  ├─ FAIL 원인 분석
  ├─ DB Coverage
  └─ Answer Accuracy

  ## 주요 처리 결과

### 1. 신규 QA 중복 검증

신규 QA 데이터를 기존 QA 데이터와 비교하여 중복 여부를 검증했습니다.

- 신규 QA: 412건
- 기존 QA: 8,354건
- 신규 데이터 내부 Exact 중복: 0건
- 기존 데이터와 Exact 중복: 3건
- 유사도 기반 검토 후보: 3건
- 유사 후보 중 실제 중복 판정: 1건
- 최종 신규 QA: 408건

Exact 비교만으로 판단하기 어려운 질문은 RapidFuzz를 이용해 유사 질문 후보를 추출하고, 최종 중복 여부는 직접 검토하도록 구성했습니다.

### 2. 챗봇 품질검사 데이터 적재

챗봇 품질검사 원본 977건을 Pandas로 검증한 뒤 PostgreSQL에 적재했습니다.

- 원본 데이터: 977건
- 동일 `(batch_id, question)` 중복: 1건
- 최종 적재 데이터: 976건
- `test_id` 중복: 0건
- 필수 질문값 누락: 0건

원본 Excel 파일에서는 중복 데이터를 삭제하지 않고 보존하며, 데이터 처리 단계에서 적재 대상만 분리했습니다.

### 3. 재실행 중복 적재 방지

동일한 원본 데이터로 적재 스크립트를 다시 실행하여 멱등성을 확인했습니다.

- 최초 적재: 976건
- 동일 데이터 재실행 시 신규 적재: 0건
- 재실행 후 PostgreSQL 총 데이터: 976건

애플리케이션 단계에서 기존 `(batch_id, question)`을 확인하고, 데이터베이스에서는 `UNIQUE` 제약조건을 적용해 중복 적재를 이중으로 방지했습니다.

## PostgreSQL 데이터 모델

챗봇 테스트 결과를 `chatbot_test` 테이블로 관리하고 있으며, 데이터 무결성과 조회 효율을 위해 다음 제약조건과 인덱스를 적용했습니다.

| 항목 | 적용 내용 | 목적 |
|---|---|---|
| Primary Key | `test_id` | 테스트 데이터 식별 |
| UNIQUE | `(batch_id, question)` | 동일 배치 내 동일 질문 중복 방지 |
| NOT NULL | `question` | 필수 데이터 누락 방지 |
| CHECK | `evaluation` | 허용된 평가 상태만 저장 |
| Foreign Key | `retest_of_test_id → test_id` | 향후 재검사 데이터 연결 |
| INDEX | `(batch_id, evaluation)`, `category` | 월별 품질 및 카테고리 분석 지원 |

`evaluation`은 `PASS`, `PARTIAL`, `FAIL`, `REVIEW` 상태를 허용하도록 구성했습니다.

또한 `collection_status`를 별도로 두어 챗봇이 정상적으로 응답했지만 답을 찾지 못한 경우와, 데이터 수집 과정 자체에서 오류가 발생한 경우를 구분할 수 있도록 설계했습니다.

## SQL 품질 분석

PostgreSQL에 적재한 데이터를 기반으로 월별 평가 현황과 실패 원인을 집계하고, 챗봇 품질을 다음 두 지표로 분리해 분석했습니다.

### DB Coverage

챗봇이 답변할 수 있는 지식이 존재하는 정도를 확인하기 위한 지표입니다.

```text
DB Coverage
= (평가 완료 건수 - DB_GAP 건수) / 평가 완료 건수 × 100
```

### Answer Accuracy

답변 가능한 질문 중 챗봇이 올바르게 답변한 비율을 확인하기 위한 지표입니다.

```text
Answer Accuracy
= PASS 건수 / (평가 완료 건수 - DB_GAP 건수) × 100
```

DB 자체에 필요한 지식이 없는 `DB_GAP`과, 답변할 데이터가 존재하지만 잘못된 답변을 반환하는 문제를 분리하여 서로 다른 개선 대상으로 관리할 수 있도록 했습니다.

### 분석 결과

| Batch | 평가 진행률 | DB Coverage | Answer Accuracy |
|---|---:|---:|---:|
| 2026-07 | 100.0% | 65.7% | 75.5% |
| 2026-08 | 41.2% | 1.0% | 0.0% |

2026-08 데이터는 평가가 완료되지 않은 중간 데이터이므로 최종 월간 품질지표로 해석하지 않습니다.

## 기술 스택

- **Python**
  - Pandas를 활용한 Excel 데이터 로드, 검증, 변환 및 중복 처리
  - RapidFuzz를 활용한 유사 질문 후보 탐지
  - SQLAlchemy / psycopg2를 활용한 PostgreSQL 적재
- **PostgreSQL**
  - QA 테스트 데이터 저장
  - PK, UNIQUE, CHECK, FK를 활용한 데이터 무결성 관리
  - 조회 패턴을 고려한 INDEX 구성
- **SQL**
  - GROUP BY 및 조건부 집계를 활용한 품질 현황 분석
  - CTE를 활용한 월별 KPI 산출
  - DB Coverage / Answer Accuracy 지표 계산
- **Git**
  - 소스 코드 버전 관리
  - 실제 업무 데이터 및 환경정보 Git 추적 제외

## 프로젝트 구조

```text
chatbot_qa_dedup/
├── data/                       # 원본/처리 데이터 (Git 제외)
├── sql/
│   └── 01_quality_kpi.sql      # 챗봇 품질 KPI 분석 SQL
├── .gitignore
├── dedup_check.py              # 신규 QA 중복 검증
├── inspect_test_data.py        # 품질검사 데이터 프로파일링
├── load_chatbot_test.py        # PostgreSQL 검증/적재
├── prepare_final.py            # QA 데이터 후처리
└── README.md
```

실제 업무 데이터가 포함된 `data/` 디렉터리는 `.gitignore`에 등록하여 저장소에 포함되지 않도록 했습니다.

## 실행 흐름

### 1. 신규 QA 중복 검증

```bash
python dedup_check.py
```

신규 QA와 기존 QA를 정규화하여 비교하고 Exact 중복 및 유사 질문 검토 후보를 생성합니다.

### 2. 챗봇 테스트 데이터 확인

```bash
python inspect_test_data.py
```

적재 전 데이터의 컬럼, 결측값, 평가 상태, 배치 및 중복 여부를 확인합니다.

### 3. PostgreSQL 적재

```bash
python load_chatbot_test.py
```

원본 데이터를 변환·검증한 뒤 기존 데이터와 비교하여 신규 데이터만 PostgreSQL에 적재합니다.

DB 비밀번호는 소스 코드에 저장하지 않고 실행 시 입력받도록 구성했습니다.

### 4. 품질 KPI 분석

`sql/01_quality_kpi.sql`을 실행하여 월별 평가 진행률, 실패 원인, DB Coverage, Answer Accuracy를 확인합니다.

## 향후 개선

현재는 소규모 업무 데이터를 기준으로 기존 `(batch_id, question)` 키를 애플리케이션에서 조회하여 신규 데이터를 판별합니다.

데이터 규모가 증가할 경우 다음과 같은 방향으로 개선할 수 있습니다.

- Staging Table을 활용한 적재 구조 분리
- `INSERT ... ON CONFLICT` 기반 Upsert 적용
- QA 수정 및 재검사 이력 관리 구조 확장
- 반복 실행되는 데이터 검증 및 적재 작업의 자동화
