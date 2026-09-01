from rapidfuzz import process, fuzz

import pandas as pd

new_df = pd.read_excel("data/신규QA.xlsx")
qa2025_df = pd.read_excel("data/QA2025.xlsx")
qa2024_df = pd.read_excel("data/QA2024.xlsx")

print("신규 데이터:", len(new_df))
print("2025 기존 데이터:", len(qa2025_df))
print("2024 기존 데이터:", len(qa2024_df))

print("\n신규 데이터 컬럼")
print(new_df.columns.tolist())

print("\n2025 데이터 컬럼")
print(qa2025_df.columns.tolist())

print("\n2024 데이터 컬럼")
print(qa2024_df.columns.tolist())


import re

# 질문 비교용 정규화 함수
def normalize_question(text):
    if pd.isna(text):
        return ""

    text = str(text).lower()
    text = re.sub(r"\s+", "", text)          # 공백 제거
    text = re.sub(r"[^\w가-힣]", "", text)   # 문장부호 제거

    return text


# 각 데이터의 질문 정규화
new_df["question_norm"] = new_df["question_raw"].apply(normalize_question)
qa2025_df["question_norm"] = qa2025_df["question"].apply(normalize_question)
qa2024_df["question_norm"] = qa2024_df["question"].apply(normalize_question)


# 1. 신규 데이터 내부 중복
new_duplicate = new_df[
    new_df.duplicated(subset=["question_norm"], keep=False)
]

print("\n===== 신규 데이터 내부 중복 =====")
print("중복 행 수:", len(new_duplicate))


# 2. 기존 DB 질문 목록 만들기
existing_questions = set(
    qa2025_df["question_norm"].tolist()
    + qa2024_df["question_norm"].tolist()
)


# 3. 신규 데이터와 기존 DB 비교
new_df["existing_duplicate"] = new_df["question_norm"].isin(existing_questions)

existing_duplicate = new_df[
    new_df["existing_duplicate"] == True
]

print("\n===== 기존 DB와 완전 동일 =====")
print("중복 건수:", len(existing_duplicate))

print(
    existing_duplicate[
        ["qa_id", "question_raw"]
    ].to_string(index=False)
)

# 기존 DB 출처 표시
qa2024_df["source_db"] = "QA2024"
qa2025_df["source_db"] = "QA2025"

# 기존 2024 + 2025 데이터 합치기
existing_df = pd.concat(
    [qa2024_df, qa2025_df],
    ignore_index=True
)

print("\n===== 기존 DB 통합 =====")
print("통합 기존 데이터:", len(existing_df))

# 빈 질문 확인
empty_new = new_df[
    new_df["question_norm"] == ""
]

print("\n===== 빈 질문 확인 =====")
print("빈 질문 수:", len(empty_new))

# 기존 DB와 매칭 정보 만들기
lookup = existing_df[
    ["question_norm", "question", "source_db"]
].drop_duplicates(subset=["question_norm"])

lookup = lookup.rename(
    columns={"question": "matched_question"}
)

# 신규 데이터에 기존 DB 정보 붙이기
matched_df = new_df.merge(
    lookup,
    on="question_norm",
    how="left"
)

matched_df["is_existing_dup"] = matched_df["matched_question"].notna()

print("\n===== 기존 DB 중복 상세 =====")

print(
    matched_df[
        matched_df["is_existing_dup"] == True
    ][
        [
            "qa_id",
            "question_raw",
            "matched_question",
            "source_db"
        ]
    ].to_string(index=False)
)

def normalize_question_soft(text):
    if pd.isna(text):
        return ""

    text = str(text).lower()
    text = re.sub(r"[^\w\s]", " ", text)   # 문장부호만 제거
    text = re.sub(r"\s+", " ", text)       # 여러 공백을 한 칸으로

    return text.strip()


new_df["question_soft"] = new_df["question_raw"].apply(normalize_question_soft)
existing_df["question_soft"] = existing_df["question"].apply(normalize_question_soft)

results = []

# exact 중복 3건은 제외하고 검사
fuzzy_target_df = new_df[
    new_df["existing_duplicate"] == False
].copy()

for _, row in fuzzy_target_df.iterrows():

    match = process.extractOne(
        row["question_soft"],
        existing_df["question_soft"],
        scorer=fuzz.token_set_ratio
    )

    if match is None:
        continue

    matched_text, score, matched_index = match

    if score >= 85:
        matched_row = existing_df.iloc[matched_index]

        results.append({
            "qa_id": row["qa_id"],
            "new_question": row["question_raw"],
            "matched_question": matched_row["question"],
            "source_db": matched_row["source_db"],
            "similarity": round(score, 1)
        })


similar_df = pd.DataFrame(results)

print("\n===== 유사 중복 검토 후보 =====")
print("검토 후보 수:", len(similar_df))

if not similar_df.empty:
    print(
        similar_df[
            [
                "qa_id",
                "new_question",
                "matched_question",
                "source_db",
                "similarity"
            ]
        ].to_string(index=False)
    )

    

#similar_df["review_result"] = ""
#similar_df["review_note"] = ""

#similar_df.to_csv(
 #   "data/fuzzy_review.csv",
  #  index=False,
   # encoding="utf-8-sig"
#)

#print("\n검토 파일 저장 완료: data/fuzzy_review.csv")

# ===== 사람 검토 결과 반영 =====

review_df = pd.read_csv("data/fuzzy_review.csv")

# 사람이 DUPLICATE라고 판정한 qa_id
human_duplicate_ids = set(
    review_df.loc[
        review_df["review_result"] == "DUPLICATE",
        "qa_id"
    ]
)

# Exact 중복 + 사람이 판정한 유사 중복 모두 제외
final_df = new_df[
    (~new_df["existing_duplicate"])
    & (~new_df["qa_id"].isin(human_duplicate_ids))
].copy()

print("\n===== 최종 신규 QA =====")
print("최초 신규 데이터:", len(new_df))
print("Exact 기존 DB 중복:", new_df["existing_duplicate"].sum())
print("사람 판정 유사 중복:", len(human_duplicate_ids))
print("최종 신규 QA:", len(final_df))

final_df.to_csv(
    "data/qa_new_final.csv",
    index=False,
    encoding="utf-8-sig"
)

print("최종 파일 저장 완료: data/qa_new_final.csv")