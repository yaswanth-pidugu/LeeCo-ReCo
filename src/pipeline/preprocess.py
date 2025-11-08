import pandas as pd
import numpy as np
import os

def convert_km_to_int(series):
    if series.dtype == 'O':
        series = (
            series.astype(str)
            .str.replace('K', 'e3', regex=False)
            .str.replace('M', 'e6', regex=False)
        )
    return pd.to_numeric(series, errors='coerce').astype('Int32')

def preprocess_data(raw_path="data/raw/leetcode_latest.csv",
                    save_path="data/processed/preprocessed_data.csv"):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    df = pd.read_csv(raw_path)
    df['is_premium'] = df['is_premium'].fillna(True)
    df['frontend_id'] = df['frontend_id'].astype(int)
    if 'similar_questions' in df.columns:
        df['similar_questions'] = df['similar_questions'].fillna('').astype(str).str.split(", ")
        df['no_similar_questions'] = df['similar_questions'].apply(
            lambda x: len(x) if isinstance(x, list) and x != [''] else 0
        )

    for col in ['accepted', 'submission', 'discussion_count', 'likes', 'dislikes']:
        if col in df.columns:
            df[col] = convert_km_to_int(df[col])

    if 'accepted' in df.columns and 'submission' in df.columns:
        df['acceptance_rate'] = (df['accepted'] / (df['submission'] + 1) * 100).round(2)
    if 'likes' in df.columns and 'dislikes' in df.columns:
        df['like_ratio'] = (df['likes'] / (df['likes'] + df['dislikes'] + 1)).round(2)
        df['likebility'] = (df['like_ratio'] * 100).round(2)
        df['is_popular'] = df['likes'] > df['likes'].median()
    if 'solution_URL' in df.columns:
        df['solution_URL'] = df['solution_URL'].fillna('')
    max_id = df['frontend_id'].max() + 50
    df['page_number'] = pd.cut(
        df['frontend_id'], bins=range(1, max_id, 50),
        include_lowest=True, right=False
    ).apply(lambda x: (x.left // 50) + 1)
    df.to_csv(save_path, index=False)
    print(f"Preprocessed data saved to {save_path} ({len(df)} rows)")