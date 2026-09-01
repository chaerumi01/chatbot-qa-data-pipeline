import pandas as pd

file_path = "data/chatbot_test.xlsx"

df = pd.read_excel(file_path)

print("행/열 개수:", df.shape)

print("\n=== 컬럼명 ===")
print(df.columns.tolist())

print("\n=== 앞 5행 ===")
print(df.head())

print("\n=== 각 컬럼 데이터 개수 ===")
print(df.notna().sum())

print("\n=== evaluation 값 ===")
print(df["evaluation"].value_counts(dropna=False))

print("\n=== category 값 ===")
print(df["category"].value_counts(dropna=False))

print("\n=== batch_id 값 ===")
print(df["batch_id"].value_counts(dropna=False))

# DB에 넣을 형태로 batch_id 변환
batch_date = pd.to_datetime(df["batch_id"])

df["tested_at"] = batch_date
df["batch_id"] = batch_date.dt.strftime("B%Y%m")

print("\n=== 변환된 batch_id ===")
print(df["batch_id"].value_counts())

print("\n=== 동일 배치 + 동일 질문 중복 ===")
duplicates = df[
    df.duplicated(subset=["batch_id", "question"], keep=False)
].sort_values(["batch_id", "question"])

print("중복 행 수:", len(duplicates))

if not duplicates.empty:
    print(
        duplicates[
            ["test_id", "batch_id", "question", "evaluation"]
        ].to_string(index=False)
    )

print("\n=== test_id 중복 ===")
print("중복 행 수:", df["test_id"].duplicated().sum())

print("\n=== question NULL ===")
print("NULL 개수:", df["question"].isna().sum())

before = len(df)

df = df.drop_duplicates(
    subset=["batch_id", "question"],
    keep="first"
)

after = len(df)

print("\n=== 중복 제거 결과 ===")
print("제거 전:", before)
print("제거 후:", after)
print("제거 건수:", before - after)