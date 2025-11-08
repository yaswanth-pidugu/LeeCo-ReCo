from fastapi import FastAPI
from fastapi.responses import JSONResponse
import pandas as pd
import os

app = FastAPI(
    title="LeetCode Analytics API",
    description="Provides data insights and analytics for the LeetCode recommender system.",
    version="1.0.0"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "../../data/processed/preprocessed_data.csv")

def load_data():
    try:
        df = pd.read_csv(DATA_PATH)
        if df.empty:
            raise RuntimeError("Dataset is empty.")
        # Convert numeric fields safely
        for col in ["acceptance", "likes"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        return df
    except FileNotFoundError:
        raise RuntimeError(f"Data file not found at path: {DATA_PATH}")
    except Exception as e:
        raise RuntimeError(f"Error loading data: {e}")

@app.get("/")
def root():
    return {"message": "Analytics API active"}

@app.get("/analytics/stats")
def overall_stats():
    try:
        df = load_data()
        total = len(df)
        avg_accept = round(df["acceptance"].mean(), 2) if "acceptance" in df else 0
        easy = len(df[df["difficulty"] == "Easy"]) if "difficulty" in df else 0
        medium = len(df[df["difficulty"] == "Medium"]) if "difficulty" in df else 0
        hard = len(df[df["difficulty"] == "Hard"]) if "difficulty" in df else 0

        return {
            "total_problems": total,
            "average_acceptance": avg_accept,
            "difficulty_breakdown": {
                "easy": easy,
                "medium": medium,
                "hard": hard
            }
        }
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/analytics/difficulty-distribution")
def difficulty_distribution():
    try:
        df = load_data()
        if "difficulty" not in df.columns:
            raise RuntimeError("Missing 'difficulty' column in dataset.")
        counts = df["difficulty"].value_counts().to_dict()
        return {"difficulty_distribution": counts}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/analytics/tag-frequency")
def tag_frequency(top_k: int = 15):
    try:
        df = load_data()
        if "topic_tags" not in df.columns:
            raise RuntimeError("Missing 'topic_tags' column in dataset.")

        tags = df["topic_tags"].dropna().astype(str)
        all_tags = []
        for row in tags:
            all_tags.extend([
                t.strip() for t in row.strip("[]").replace("'", "").split(",") if t.strip()
            ])
        freq = pd.Series(all_tags).value_counts().head(top_k).to_dict()
        return {"tag_frequency": freq}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/analytics/top-popular")
def top_popular(k: int = 10):
    try:
        df = load_data()
        required_cols = ["frontend_id", "title", "likes", "acceptance", "difficulty"]
        for col in required_cols:
            if col not in df.columns:
                raise RuntimeError(f"Missing '{col}' in dataset.")
        df = df.sort_values("likes", ascending=False).head(k)
        return {
            "count": len(df),
            "popular_problems": df[required_cols].to_dict(orient="records")
        }
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/analytics/acceptance-trends")
def acceptance_trends(bins: int = 10):
    try:
        df = load_data()
        if "acceptance" not in df.columns:
            raise RuntimeError("Missing 'acceptance' column in dataset.")

        df["acceptance"] = pd.to_numeric(df["acceptance"], errors="coerce").fillna(0)
        hist, edges = pd.cut(df["acceptance"], bins=bins, retbins=True)
        counts = hist.value_counts().sort_index().to_dict()
        bins_list = [
            f"{round(edges[i], 2)} - {round(edges[i + 1], 2)}"
            for i in range(len(edges) - 1)
        ]
        result = {bins_list[i]: list(counts.values())[i] for i in range(len(bins_list))}
        return {"acceptance_trends": result}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)