import ast
import re
import numpy as np
import pandas as pd
from tqdm import tqdm
from src.modeling.lightGBM import load_resources, get_recommendations

def parse_similar_raw(x):
    """Unwrap deeply nested or triple-encoded similar_questions safely."""
    if not isinstance(x, str) or not x.strip() or x.strip() in ["[]", "nan"]:
        return []

    s = x.strip()
    for _ in range(5):
        try:
            data = ast.literal_eval(s)
        except Exception:
            break

        if isinstance(data, list) and len(data) == 1 and isinstance(data[0], str):
            s = data[0]
            continue

        if isinstance(data, list) and all(isinstance(i, str) for i in data):
            cleaned = []
            for i in data:
                i = re.sub(r"^['\"\[]+|['\"\]]+$", "", i).strip()
                if i:
                    cleaned.append(i.lower())
            return cleaned

        if isinstance(data, str) and ("[" in data and "]" in data):
            s = data
            continue

        break

    return []


def precision_at_k(recommended, ground_truth, k):
    hits = len(set(recommended[:k]) & set(ground_truth))
    return hits / k if k > 0 else 0


def recall_at_k(recommended, ground_truth, k):
    hits = len(set(recommended[:k]) & set(ground_truth))
    return hits / len(ground_truth) if len(ground_truth) > 0 else 0


def ndcg_at_k(recommended, ground_truth, k):
    rel = [1 if r in ground_truth else 0 for r in recommended[:k]]
    dcg = sum([r / np.log2(i + 2) for i, r in enumerate(rel)])
    ideal_rel = sorted(rel, reverse=True)
    idcg = sum([r / np.log2(i + 2) for i, r in enumerate(ideal_rel)])
    return dcg / idcg if idcg > 0 else 0


def intra_list_diversity(embeddings, rec_indices):
    """Average pairwise cosine distance among recommendations."""
    if len(rec_indices) <= 1:
        return 0.0
    rec_embs = embeddings[rec_indices]
    sim_matrix = rec_embs @ rec_embs.T
    upper = np.triu_indices_from(sim_matrix, k=1)
    sims = sim_matrix[upper]
    return 1.0 - float(np.mean(sims))  # higher = more diverse

def evaluate_model(
    df,
    embeddings,
    tag_sims,
    diff_sims,
    pop_score,
    model,
    k=10,
    limit=300,
    use_mmr=False,
    lambda_diversity=0.5,
):
    P, R, N, D = [], [], [], []
    total = min(limit, len(df))

    for i in tqdm(range(total), desc=f"Evaluating {'MMR' if use_mmr else 'Base'}"):
        gt_raw = df.loc[i, "similar_questions"]
        gt = parse_similar_raw(gt_raw)
        if not gt:
            continue

        recs = get_recommendations(
            i,
            df,
            embeddings,
            tag_sims,
            diff_sims,
            pop_score,
            model,
            k=k,
            use_mmr=use_mmr,
            lambda_diversity=lambda_diversity,
        )

        rec_titles = [t.lower().strip() for t in recs["title"].tolist()]
        prec = precision_at_k(rec_titles, gt, k)
        rec = recall_at_k(rec_titles, gt, k)
        ndcg = ndcg_at_k(rec_titles, gt, k)

        rec_indices = (
            recs["df_idx"].astype(int).to_list()
            if "df_idx" in recs.columns
            else recs.index.to_list()
        )
        ild = intra_list_diversity(embeddings, rec_indices)

        P.append(prec)
        R.append(rec)
        N.append(ndcg)
        D.append(ild)

    return {
        "Precision@K": float(np.mean(P)) if P else 0.0,
        "Recall@K": float(np.mean(R)) if R else 0.0,
        "NDCG@K": float(np.mean(N)) if N else 0.0,
        "ILD": float(np.mean(D)) if D else 0.0,
        "Evaluated_Items": len(P),
    }

if __name__ == "__main__":
    print("[INFO] Loading resources...")
    df, emb, tag_sims, diff_sims, pop_score, model = load_resources()

    print("\n[INFO] Evaluating Base LambdaRank model...")
    base_metrics = evaluate_model(
        df, emb, tag_sims, diff_sims, pop_score, model, k=10, limit=300, use_mmr=False
    )
    print("\nBase LambdaRank:")
    for k_name, v in base_metrics.items():
        print(f"{k_name}: {v:.4f}" if isinstance(v, float) else f"{k_name}: {v}")

    print("\n[INFO] Evaluating LambdaRank + MMR model...")
    mmr_metrics = evaluate_model(
        df, emb, tag_sims, diff_sims, pop_score, model, k=10, limit=300, use_mmr=True
    )
    print("\nLambdaRank + MMR:")
    for k_name, v in mmr_metrics.items():
        print(f"{k_name}: {v:.4f}" if isinstance(v, float) else f"{k_name}: {v}")

    print("\n[SUMMARY]")
    print(f"Improvement in NDCG@10: {mmr_metrics['NDCG@K'] - base_metrics['NDCG@K']:.4f}")
    print(f"Increase in Diversity (ILD): {mmr_metrics['ILD'] - base_metrics['ILD']:.4f}")

    lambda_values = [0.2, 0.4, 0.6, 0.8]
    results = []

    print("\n[TUNING] Searching for best λ-diversity...")
    for lam in lambda_values:
        metrics = evaluate_model(
            df,
            emb,
            tag_sims,
            diff_sims,
            pop_score,
            model,
            k=10,
            limit=300,
            use_mmr=True,
            lambda_diversity=lam,
        )
        print(f"λ={lam:.1f} -> NDCG={metrics['NDCG@K']:.4f}, ILD={metrics['ILD']:.4f}")
        results.append((lam, metrics["NDCG@K"], metrics["ILD"]))

    best = sorted(results, key=lambda x: (x[2] - 0.1 * x[1]), reverse=True)[0]
    print(f"\nBest λ = {best[0]} (NDCG={best[1]:.4f}, ILD={best[2]:.4f})")
