import pandas as pd
from sqlalchemy import create_engine, text
from getpass import getpass

# ==========================================
# 1. 원본 데이터 로드
# ==========================================

file_path = "data/chatbot_test.xlsx"

df = pd.read_excel(file_path)

print(f"[1] 원본 데이터: {len(df)}건")


# ==========================================
# 2. batch_id / tested_at 변환
# ==========================================

batch_date = pd.to_datetime(df["batch_id"])

df["tested_at"] = batch_date
df["batch_id"] = batch_date.dt.strftime("B%Y%m")

print("[2] 배치 변환 완료")
print(df["batch_id"].value_counts())


# ==========================================
# 3. 필수값 검증
# ==========================================

if df["test_id"].isna().any():
    raise ValueError("test_id NULL이 존재합니다.")

if df["question"].isna().any():
    raise ValueError("question NULL이 존재합니다.")

if df["test_id"].duplicated().any():
    raise ValueError("test_id 중복이 존재합니다.")

print("[3] 필수값 검증 통과")


# ==========================================
# 4. 동일 배치 + 동일 질문 중복 제거
# ==========================================

before = len(df)

df = df.drop_duplicates(
    subset=["batch_id", "question"],
    keep="first"
)

removed = before - len(df)

print(f"[4] 중복 제거: {removed}건")
print(f"    적재 대상: {len(df)}건")


# ==========================================
# 5. DB 스키마에 맞는 컬럼 준비
# ==========================================

df["collection_status"] = "SUCCESS"
df["retest_of_test_id"] = None

cols = [
    "test_id",
    "batch_id",
    "tested_at",
    "source_type",
    "category",
    "question",
    "answer_raw",
    "chatbot_result",
    "evaluation",
    "failure_type",
    "action_required",
    "note",
    "collection_status",
    "retest_of_test_id",
]

df = df[cols]


# ==========================================
# 6. PostgreSQL 연결
# ==========================================

password = getpass("PostgreSQL postgres 비밀번호: ")

engine = create_engine(
    f"postgresql+psycopg2://postgres:{password}@localhost:5432/chatbot_qa"
)


# ==========================================
# 7. 적재 전 DB 건수 확인
# ==========================================

with engine.connect() as conn:
    before_count = conn.execute(
        text("SELECT COUNT(*) FROM chatbot_test")
    ).scalar_one()

print(f"[5] 적재 전 DB 데이터: {before_count}건")


# ==========================================
# 8. 이미 적재된 데이터 제외
# ==========================================

with engine.connect() as conn:
    existing = pd.read_sql(
        """
        SELECT batch_id, question
        FROM chatbot_test
        """,
        conn
    )

existing_keys = set(
    zip(existing["batch_id"], existing["question"])
)

new_mask = [
    (batch_id, question) not in existing_keys
    for batch_id, question
    in zip(df["batch_id"], df["question"])
]

df_new = df.loc[new_mask].copy()

print(f"[6] 입력 후보: {len(df)}건")
print(f"    기존 중복 제외: {len(df) - len(df_new)}건")
print(f"    신규 적재 대상: {len(df_new)}건")


# ==========================================
# 9. 신규 데이터만 PostgreSQL 적재
# ==========================================

if len(df_new) > 0:
    df_new.to_sql(
        "chatbot_test",
        engine,
        if_exists="append",
        index=False,
        method="multi",
    )

    print("[7] 신규 데이터 적재 완료")
else:
    print("[7] 신규 데이터 없음 - INSERT 생략")


# ==========================================
# 10. 적재 결과 검증
# ==========================================

with engine.connect() as conn:
    after_count = conn.execute(
        text("SELECT COUNT(*) FROM chatbot_test")
    ).scalar_one()

expected_count = before_count + len(df_new)

print(f"[8] 적재 후 DB 데이터: {after_count}건")

if after_count != expected_count:
    raise ValueError(
        f"적재 건수 불일치: 예상 {expected_count}건 / 실제 {after_count}건"
    )

print("\n==============================")
print("적재 검증 성공")
print(f"DB 적재 전       : {before_count}건")
print(f"입력 후보        : {len(df)}건")
print(f"기존 중복 제외   : {len(df) - len(df_new)}건")
print(f"신규 적재        : {len(df_new)}건")
print(f"DB 적재 후       : {after_count}건")
print("==============================")