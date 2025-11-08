import pandas as pd
import joblib
import os
from lightgbm import LGBMRegressor


def train_and_save_model(processed_path="data/processed/preprocessed_data.csv",
                         model_path="models/lightgbm_model.pkl"):
    os.makedirs(os.path.dirname(model_path), exist_ok=True)

    df = pd.read_csv(processed_path)
    print(f"Loaded dataset with {df.shape[0]} rows and {df.shape[1]} columns")

    # You’ll replace this with your recommender logic later
    if "likes" not in df.columns or "dislikes" not in df.columns:
        print("No target columns found for training. Skipping model training.")
        return

    # Use problem stats as simple training example
    features = ["acceptance", "accepted", "submission", "discussion_count", "likes", "dislikes"]
    features = [f for f in features if f in df.columns]

    df = df.dropna(subset=features)
    X = df[features]
    y = df["likebility"] if "likebility" in df.columns else df["likes"]

    print(f"Training LightGBM model on {len(X)} samples with {len(features)} features...")
    model = LGBMRegressor(n_estimators=100, learning_rate=0.05, random_state=42)
    model.fit(X, y)

    joblib.dump(model, model_path)
    print(f"Model saved to {model_path}")