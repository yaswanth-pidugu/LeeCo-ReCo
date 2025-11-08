from src.database.db_config import get_connection
import pandas as pd

#Mark a problem as solved
def mark_problem_solved(user_id: int, problem_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    # Check if interaction exists
    cursor.execute("""
        SELECT interaction_id FROM interactions 
        WHERE user_id = %s AND problem_id = %s
    """, (user_id, problem_id))
    result = cursor.fetchone()

    if result:
        # Update existing interaction
        cursor.execute("""
            UPDATE interactions 
            SET status = 'solved', rating = 5
            WHERE user_id = %s AND problem_id = %s
        """, (user_id, problem_id))
    else:
        # Create a new interaction
        cursor.execute("""
            INSERT INTO interactions (user_id, problem_id, status, rating)
            VALUES (%s, %s, 'solved', 5)
        """, (user_id, problem_id))

    conn.commit()
    conn.close()
    print(f"User {user_id} marked problem {problem_id} as solved.")


#Get solved problems grouped by tags
def get_solved_problems_by_tag(user_id: int):
    conn = get_connection()

    query = """
        SELECT p.problem_id, p.title, p.tags, p.difficulty, p.acceptance
        FROM problems p
        JOIN interactions i ON p.problem_id = i.problem_id
        WHERE i.user_id = %s AND i.status = 'solved';
    """
    df = pd.read_sql(query, conn, params=(user_id,))
    conn.close()

    if df.empty:
        print(f"No solved problems found for user {user_id}.")
        return pd.DataFrame()

    # Expand and group by tag
    tag_map = {}
    for _, row in df.iterrows():
        tags = [t.strip() for t in row['tags'].split(',')]
        for tag in tags:
            tag_map.setdefault(tag, []).append({
                'problem_id': row['problem_id'],
                'title': row['title'],
                'difficulty': row['difficulty'],
                'acceptance': row['acceptance']
            })

    # Convert to displayable DataFrame
    grouped_data = []
    for tag, problems in tag_map.items():
        grouped_data.append({
            'Tag': tag,
            'Problems Solved': len(problems),
            'Titles': [p['title'] for p in problems]
        })

    grouped_df = pd.DataFrame(grouped_data).sort_values(by='Problems Solved', ascending=False)
    print("Solved problems grouped by tag retrieved successfully.")
    return grouped_df
