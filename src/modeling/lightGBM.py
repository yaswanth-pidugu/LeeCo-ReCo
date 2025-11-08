# src/modeling/lightGBM.py
import os
import re
import ast
import pickle
from pathlib import Path
import inspect

import numpy as np
import pandas as pd
import lightgbm as lgb

try:
    print("[DEBUG] API using lightGBM from:", inspect.getfile(inspect.currentframe()))
except Exception:
    pass

def clean_title(text: str) -> str:
    text = str(text).lower().strip()
    text = re.sub(r'^\d+\.\s*', '', text)
    text = re.sub(r'[^a-z0-9\s\-]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def to_tag_list(s) -> list:
    if isinstance(s, str) and s.strip().startswith('['):
        try:
            vals = ast.literal_eval(s)
            return [str(v).lower().strip() for v in vals if v]
        except Exception:
            pass
    return [t.strip().lower() for t in str(s).split(',') if t.strip()]

def minmax(x: pd.Series) -> pd.Series:
    x = x.fillna(0)
    rng = x.max() - x.min()
    return (x - x.min()) / (rng if rng != 0 else 1.0)

def tag_jaccard_set(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return float(len(a & b) / len(a | b))

def load_resources():
    BASE_DIR = Path(__file__).resolve().parents[2]
    data_path = BASE_DIR / "data" / "processed" / "preprocessed_data.csv"
    emb_path  = BASE_DIR / "models" / "sbert_recommender.pkl"
    model_txt = BASE_DIR / "models" / "lambdarank_model.txt"

    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")

    df = pd.read_csv(data_path)
    df["clean_title"] = df["title"].apply(clean_title)
    df["tag_list"] = df["topic_tags"].apply(to_tag_list)
    df["difficulty"] = df["difficulty"].fillna("Medium")
    if not emb_path.exists():
        raise FileNotFoundError(f"Embeddings cache not found: {emb_path}")
    with open(emb_path, "rb") as f:
        cache = pickle.load(f)
    embeddings = np.array(cache.get("embeddings"), dtype=np.float32)

    if embeddings.shape[0] != len(df):
        raise RuntimeError(f"Embedding rows ({embeddings.shape[0]}) != dataframe rows ({len(df)}). Regenerate embeddings.")
    if np.isnan(embeddings).any():
        raise RuntimeError("Embeddings contain NaNs.")

    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    embeddings = embeddings / norms.astype(np.float32)
    if not model_txt.exists():
        raise FileNotFoundError(f"LambdaRank model text file not found: {model_txt}")
    model = lgb.Booster(model_file=str(model_txt))
    ladder = {"easy": 0, "medium": 1, "hard": 2}
    diff_vals = df["difficulty"].str.lower().map(ladder).fillna(1).to_numpy(dtype=np.int8)
    acc = minmax(df.get("acceptance", pd.Series(np.zeros(len(df)))))
    likes = minmax(df.get("likes", pd.Series(np.zeros(len(df)))))
    subs = minmax(df.get("submission", pd.Series(np.zeros(len(df)))))
    popularity_score = (0.3 * acc + 0.5 * likes + 0.2 * subs).fillna(0).to_numpy(dtype=np.float32)
    tag_sims = np.zeros((len(df), len(df)), dtype=np.float32)
    diff_sims = np.ones((len(df), len(df)), dtype=np.float32)

    print(f"[INFO] Loaded {len(df)} problems, embeddings {embeddings.shape}, model objective={model.params.get('objective','unknown')}")
    return df, embeddings, tag_sims, diff_sims, popularity_score, model

def get_recommendations(
    idx: int,
    df: pd.DataFrame,
    embeddings: np.ndarray,
    tag_sims,
    diff_sims,
    popularity_score: np.ndarray,
    model: lgb.Booster,
    k: int = 10,
    use_mmr: bool = True,
    lambda_diversity: float = 0.6,
    candidate_pool: int = 300,
    debug: bool = False,
):
    N = len(df)
    assert embeddings.shape[0] == N, "Embeddings length mismatch."
    sims = embeddings @ embeddings[idx]
    sims = sims.astype(np.float32)
    sims[idx] = -1.0

    # candidate selection
    m = max(1, min(candidate_pool, N - 1))
    top_k_part = np.argpartition(sims, -m)[-m:]
    top_idx_stage1 = top_k_part[np.argsort(sims[top_k_part])][::-1]
    ladder = {"easy": 0, "medium": 1, "hard": 2}
    diff_vals = df["difficulty"].str.lower().map(ladder).fillna(1).to_numpy(dtype=np.int8)

    # precompute query tags once
    raw_tags = df.iloc[idx].get("tag_list", None)
    if isinstance(raw_tags, (list, set)):
        query_tags = set(raw_tags)
    else:
        query_tags = set(to_tag_list(df.iloc[idx].get("topic_tags", "")))

    rerank_feats = []
    for j in top_idx_stage1:
        cand_tags_raw = df.iloc[j].get("tag_list", None)
        cand_tags = set(cand_tags_raw) if isinstance(cand_tags_raw, (list, set)) else set(to_tag_list(df.iloc[j].get("topic_tags", "")))
        tag_sim = tag_jaccard_set(query_tags, cand_tags)
        diff_sim = 1.0 if abs(int(diff_vals[idx]) - int(diff_vals[j])) == 0 else 0.7 if abs(int(diff_vals[idx]) - int(diff_vals[j])) == 1 else 0.4
        pop_diff = float(abs(float(popularity_score[idx]) - float(popularity_score[j])))
        emb_sim = float(sims[j])
        rerank_feats.append([emb_sim, tag_sim, diff_sim, pop_diff])

    rerank_feats = np.array(rerank_feats, dtype=np.float32)
    if rerank_feats.size == 0:
        empty = pd.DataFrame(columns=["frontend_id", "title", "difficulty", "topic_tags", "problem_URL", "score", "df_idx"])
        return empty

    if debug:
        print(f"[DEBUG] query_idx={idx}, candidates={len(top_idx_stage1)}, feat_mean={rerank_feats.mean(axis=0)}, feat_std={rerank_feats.std(axis=0)}")

    scores = model.predict(rerank_feats)
    rng = np.random.RandomState(42)
    scores = scores + rng.normal(0, 1e-8, size=scores.shape)

    if use_mmr:
        selected_local = []
        candidate_indices = list(range(len(top_idx_stage1)))  # local positions into top_idx_stage1 / rerank_feats
        cand_embs = embeddings[top_idx_stage1]                # shape (m, D)
        relevance = scores.astype(np.float32)                # shape (m,)

        while len(selected_local) < k and candidate_indices:
            if not selected_local:
                pick_pos = int(np.argmax(relevance[candidate_indices]))
                pick_local = candidate_indices[pick_pos]
            else:
                sel_embs = cand_embs[selected_local]          # (s, D)
                cand_subset = cand_embs[candidate_indices]    # (c, D)

                sim_to_selected = cand_subset @ sel_embs.T    # (c, s)
                max_sim = np.max(sim_to_selected, axis=1)     # (c,)
                mmr_scores = (1 - lambda_diversity) * relevance[candidate_indices] - lambda_diversity * max_sim
                pick_pos = int(np.argmax(mmr_scores))
                pick_local = candidate_indices[pick_pos]

            selected_local.append(pick_local)
            candidate_indices.remove(pick_local)

        chosen = selected_local
    else:
        chosen_local = np.argsort(scores)[-k:][::-1]
        chosen = list(chosen_local)


    chosen_df_idx = [int(top_idx_stage1[c]) for c in chosen]
    chosen_scores = [float(scores[c]) for c in chosen]

    recs = df.loc[chosen_df_idx, ["frontend_id", "title", "difficulty", "topic_tags"]].copy()
    recs = recs.reset_index(drop=True)
    recs["problem_URL"] = recs["title"].apply(lambda t: f"https://leetcode.com/problems/{clean_title(t).replace(' ', '-')}/")
    recs["score"] = chosen_scores
    recs["df_idx"] = chosen_df_idx

    return recs

def get_learning_path(idx, df, embeddings, popularity_score, model, candidate_pool=400, lambda_diversity=0.6):
    diff_map = {"easy": 1, "medium": 2, "hard": 3}
    curr_diff = df.iloc[idx]["difficulty"].lower()
    curr_level = diff_map.get(curr_diff, 2)

    sims = embeddings @ embeddings[idx]
    sims[idx] = -1.0
    top_idx = np.argpartition(sims, -candidate_pool)[-candidate_pool:]
    top_idx = top_idx[np.argsort(sims[top_idx])][::-1]

    query_tags = set(df.iloc[idx].get("tag_list", []))
    rerank_feats = []
    ladder = {"easy": 0, "medium": 1, "hard": 2}
    diff_vals = df["difficulty"].str.lower().map(ladder).fillna(1).to_numpy(dtype=np.int8)

    for j in top_idx:
        cand_tags = set(df.iloc[j].get("tag_list", []))
        tag_overlap = query_tags & cand_tags
        tag_sim = len(tag_overlap) / len(query_tags | cand_tags) if (query_tags and cand_tags) else 0
        diff_sim = 1.0 if diff_vals[idx] == diff_vals[j] else 0.7 if abs(diff_vals[idx] - diff_vals[j]) == 1 else 0.4
        pop_diff = abs(popularity_score[idx] - popularity_score[j])
        emb_sim = sims[j]
        rerank_feats.append([emb_sim, tag_sim, diff_sim, pop_diff])

    rerank_feats = np.array(rerank_feats, dtype=np.float32)
    scores = model.predict(rerank_feats)
    ranked = sorted(zip(top_idx, scores), key=lambda x: x[1], reverse=True)

    before, similar, after = [], [], []
    for j, sc in ranked:
        d = df.iloc[j]["difficulty"].lower()
        lvl = diff_map.get(d, 2)
        if lvl < curr_level:
            before.append((j, sc))
        elif lvl == curr_level:
            similar.append((j, sc))
        else:
            after.append((j, sc))

    def explain(j, rel):
        overlap = query_tags & set(df.iloc[j].get("tag_list", []))
        overlap_str = ", ".join(list(overlap)[:2]) if overlap else None
        if rel == "before":
            msg = "helps you build core concepts before attempting this problem"
        elif rel == "similar":
            msg = "shares a similar approach and complexity"
        else:
            msg = "builds upon the same ideas and takes them to an advanced level"
        if overlap_str:
            msg += f" (topics: {overlap_str})"
        return msg

    # assemble structured output
    def build_group(group, rel):
        return [
            {
                "frontend_id": int(df.iloc[j]["frontend_id"]),
                "title": df.iloc[j]["title"],
                "difficulty": df.iloc[j]["difficulty"],
                "tags": df.iloc[j]["tag_list"],
                "reason": explain(j, rel),
                "score": float(sc)
            }
            for j, sc in group[:10]
        ]

    return {
        "before": build_group(before, "before"),
        "similar": build_group(similar, "similar"),
        "after": build_group(after, "after"),
    }

if __name__ == "__main__":
    df, emb, tag_sims, diff_sims, pop_score, model = load_resources()
    print("Sanity check: df rows", len(df), "emb shape", emb.shape)

    matches = df[df["clean_title"].str.contains("non-overlapping intervals", case=False, na=False)]
    if not matches.empty:
        idx = int(matches.index[0])
        print("\n=== Learning Path Test ===")
        path = get_learning_path(idx, df, emb, pop_score, model)
        import json
        print(json.dumps(path, indent=2))
    else:
        print("Problem not found.")
