import pandas as pd
import random
from src.database.db_config import get_connection
def insert_problems_from_csv(csv_path: str):
    df = pd.read_csv(csv_path)
    conn = get_connection()
    cursor = conn.cursor()

    for _, row in df.iterrows():
        try:
            cursor.execute("""
                INSERT INTO problems 
                (problem_id, title, tags, difficulty, acceptance, likes, dislikes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title),
                    tags = VALUES(tags),
                    difficulty = VALUES(difficulty),
                    acceptance = VALUES(acceptance),
                    likes = VALUES(likes),
                    dislikes = VALUES(dislikes);
            """, (
                int(row['frontend_id']),
                str(row['title']),
                str(row['topic_tags']),
                str(row['difficulty']),
                float(row['acceptance_rate']),
                int(row['likes']),
                int(row['dislikes'])
            ))
        except Exception as e:
            print(f"Error inserting problem {row.get('frontend_id', 'unknown')}: {e}")

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Inserted/updated {len(df)} problems successfully.")


def insert_dummy_users(n: int = 50):
    conn = get_connection()
    cursor = conn.cursor()

    for i in range(n):
        cursor.execute(
            "INSERT INTO users (username, experience_level) VALUES (%s, %s)",
            (f"user_{i+1}", random.choice(['beginner', 'intermediate', 'advanced']))
        )

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Inserted {n} dummy users.")

def insert_dummy_interactions(sample_size: int = 40):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM users")
    user_ids = [u[0] for u in cursor.fetchall()]

    cursor.execute("SELECT problem_id FROM problems")
    problem_ids = [p[0] for p in cursor.fetchall()]

    for uid in user_ids:
        for pid in random.sample(problem_ids, min(sample_size, len(problem_ids))):
            cursor.execute("""
                INSERT INTO interactions (user_id, problem_id, status, rating)
                VALUES (%s, %s, %s, %s)
            """, (
                uid,
                pid,
                random.choice(['attempted', 'solved', 'skipped']),
                random.randint(1, 5)
            ))

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Created {len(user_ids) * sample_size} dummy interactions.")
