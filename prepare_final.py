import pandas as pd

df = pd.read_csv("data/qa_new_final.csv")

print("불러온 최종 후보:", len(df))

# 1. qa_id 중복 검사
print("qa_id 누락:", df["qa_id"].isna().sum())

real_duplicate = df.loc[
    df["qa_id"].notna(),
    "qa_id"
].duplicated().sum()

print("실제 qa_id 중복:", real_duplicate)

# 2. 질문 누락 검사
print("question_raw 누락:", df["question_raw"].isna().sum())

# 3. 답변 누락 검사
print("answer_clean 누락:", df["answer_clean"].isna().sum())

# 4. 문자열 앞뒤 공백 제거
df["question_raw"] = df["question_raw"].astype(str).str.strip()

# answer_clean은 비어 있을 수 있으므로 안전하게 처리
df["answer_clean"] = df["answer_clean"].fillna("").astype(str).str.strip()

# 5. 실제 관리할 컬럼만 선택
final_cols = [
    "qa_id",
    "source_type",
    "source_id",
    "question_raw",
    "answer_raw",
    "answer_clean",
    "confirm_status",
    "answer_final",
    "note"
]

df = df[final_cols]

# qa_id 중복 상세 확인
duplicate_ids = df[
    df["qa_id"].duplicated(keep=False)
].sort_values("qa_id")

print("\n===== qa_id 중복 상세 =====")
print(
    duplicate_ids[
        ["qa_id", "source_id", "question_raw"]
    ].to_string(index=False)
)

# 6. 기본 검증
#assert df["qa_id"].is_unique, "qa_id 중복이 있습니다."
assert df["question_raw"].ne("").all(), "빈 질문이 있습니다."

# 7. 저장
df.to_csv(
    "data/qa_ready_for_db.csv",
    index=False,
    encoding="utf-8-sig"
)

print("\n===== 최종 검증 =====")
print("DB 적재 준비 데이터:", len(df))
print("저장 완료: data/qa_ready_for_db.csv")

# 답변 정제가 완료된 데이터
ready_df = df[
    df["answer_clean"].notna()
    & (df["answer_clean"].astype(str).str.strip() != "")
].copy()

# 아직 답변 정제가 필요한 데이터
pending_df = df[
    df["answer_clean"].isna()
    | (df["answer_clean"].astype(str).str.strip() == "")
].copy()

print("\n===== 처리 상태 =====")
print("전체 신규 후보:", len(df))
print("답변 정제 완료:", len(ready_df))
print("답변 정제 필요:", len(pending_df))

ready_df.to_csv(
    "data/qa_ready.csv",
    index=False,
    encoding="utf-8-sig"
)

pending_df.to_csv(
    "data/qa_pending.csv",
    index=False,
    encoding="utf-8-sig"
)

print("저장 완료: data/qa_ready.csv")
print("저장 완료: data/qa_pending.csv")

# qa_id는 없지만 answer_clean은 작성된 행 확인
missing_id_but_answered = df[
    df["qa_id"].isna()
    & df["answer_clean"].notna()
    & (df["answer_clean"].astype(str).str.strip() != "")
]

print("\n===== qa_id 누락 + 답변 작성 완료 =====")
print(
    missing_id_but_answered[
        ["qa_id", "source_id", "question_raw", "answer_clean"]
    ].to_string(index=False)
)