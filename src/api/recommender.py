from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import pandas as pd
from src.modeling.lightGBM import load_resources, get_recommendations, get_learning_path

router = APIRouter(prefix="", tags=["recommender"])

df: Optional[pd.DataFrame] = None
embeddings = tag_sims = diff_sims = popularity_score = model = None


def normalize_problem(p):
    """Ensure every problem dict is valid and consistent."""
    if not isinstance(p, dict):
        return {
            "title": str(p),
            "difficulty": "Unknown",
            "topic_tags": "N/A",
            "problem_URL": "",
            "reason": "",
            "score": 0,
            "category": "",
        }

    title = str(p.get("title", "")).strip()
    slug = title.lower().replace(" ", "-") if title else ""

    tags = p.get("topic_tags") or p.get("tags") or "N/A"
    if isinstance(tags, list):
        tags = ", ".join([str(t).strip() for t in tags if t])
    elif isinstance(tags, str):
        if tags.startswith("[") and tags.endswith("]"):
            tags = tags.strip("[]").replace("'", "").replace('"', "")
            tags = ", ".join([t.strip() for t in tags.split(",") if t.strip()])
        tags = tags.strip()
    else:
        tags = "N/A"

    return {
        "title": title or "Unknown Problem",
        "difficulty": p.get("difficulty", "Unknown"),
        "topic_tags": tags if tags else "N/A",
        "problem_URL": f"https://leetcode.com/problems/{slug}/" if slug else "",
        "reason": str(p.get("reason", "")),
        "score": float(p.get("score", 0) or 0),
        "category": p.get("category", ""),
    }

def init_recommender():
    global df, embeddings, tag_sims, diff_sims, popularity_score, model
    df, embeddings, tag_sims, diff_sims, popularity_score, model = load_resources()
    print(f"[READY] Recommender loaded with {len(df)} problems.")

@router.get("/")
def root():
    return {"message": "LeetCode Recommender API running successfully."}


class RecommendRequest(BaseModel):
    problem_id: int
    top_k: Optional[int] = 10
    use_learning_path: Optional[bool] = False


@router.post("/recommend")
def recommend_post(body: RecommendRequest):
    """Unified route for learning path or recommendations."""
    if df is None:
        return JSONResponse(content={"error": "Model not loaded yet."}, status_code=500)

    try:
        problem_id = body.problem_id
        top_k = body.top_k or 10
        use_learning_path = body.use_learning_path

        if problem_id not in df["frontend_id"].values:
            raise HTTPException(status_code=400, detail=f"Problem ID {problem_id} not found.")

        idx = int(df.index[df["frontend_id"] == problem_id][0])
        problem_data = df.iloc[idx][["frontend_id", "title", "difficulty", "topic_tags"]].to_dict()
        problem_data = normalize_problem(problem_data)

        if use_learning_path:
            learning_path = get_learning_path(idx, df, embeddings, popularity_score, model)
            for section in ["before", "similar", "after"]:
                if section in learning_path:
                    learning_path[section] = [normalize_problem(p) for p in learning_path[section]]
            return {"requested_problem": problem_data, "learning_path": learning_path}

        recs = get_recommendations(
            idx, df, embeddings, tag_sims, diff_sims, popularity_score, model, k=top_k, use_mmr=True
        )
        rec_dicts = [
            normalize_problem({
                "title": row["title"],
                "difficulty": row["difficulty"],
                "topic_tags": row["topic_tags"],
                "problem_URL": row["problem_URL"],
                "score": row["score"],
            })
            for _, row in recs.iterrows()
        ]
        return {"requested_problem": problem_data, "recommendations": rec_dicts}

    except HTTPException as he:
        return JSONResponse(content={"error": he.detail}, status_code=he.status_code)
    except Exception as e:
        print("[Backend Exception]", e)
        return JSONResponse(content={"error": str(e)}, status_code=500)
