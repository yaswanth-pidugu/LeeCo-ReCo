# src/api/user_progress.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from src.database.db_config import get_db_connection
from src.api.auth import get_current_user
from typing import Optional

router = APIRouter(prefix="/user", tags=["User Progress"])

print("user_progress router loaded successfully")


class SolveRequest(BaseModel):
    problem_id: int
    problem_title: Optional[str] = None
    tags: Optional[str] = None
    difficulty: Optional[str] = None


@router.post("/mark-solved")
def mark_as_solved(req: SolveRequest, current_user: dict = Depends(get_current_user)):
    """Record a solved problem for the currently logged-in user.
    If the same (user_id, problem_id) exists, update timestamp instead of inserting duplicate.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not found in token payload")

    conn = get_db_connection()
    if isinstance(conn, dict) and "error" in conn:
        raise HTTPException(status_code=500, detail=conn["error"])

    try:
        cursor = conn.cursor()
        # Check if already exists
        cursor.execute(
            "SELECT id FROM interactions WHERE user_id = %s AND problem_id = %s",
            (user_id, req.problem_id),
        )
        row = cursor.fetchone()
        if row:
            # update solved_at (idempotent)
            cursor.execute(
                "UPDATE interactions SET solved_at = CURRENT_TIMESTAMP, problem_title = %s, tags = %s, difficulty = %s WHERE id = %s",
                (req.problem_title or "", req.tags or "", req.difficulty or "", row[0]),
            )
            conn.commit()
            return {"message": f"Problem {req.problem_id} already marked; timestamp updated", "problem_id": req.problem_id}
        else:
            cursor.execute(
                """
                INSERT INTO interactions (user_id, problem_id, problem_title, tags, difficulty)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_id, req.problem_id, req.problem_title or "", req.tags or "", req.difficulty or ""),
            )
            conn.commit()
            return {"message": f"Problem {req.problem_id} marked as solved", "problem_id": req.problem_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


@router.post("/unmark-solved")
def unmark_solved(req: SolveRequest, current_user: dict = Depends(get_current_user)):
    """Remove a solved record (undo)."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User not found in token payload")

    conn = get_db_connection()
    if isinstance(conn, dict) and "error" in conn:
        raise HTTPException(status_code=500, detail=conn["error"])

    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM interactions WHERE user_id = %s AND problem_id = %s",
            (user_id, req.problem_id),
        )
        affected = cursor.rowcount
        conn.commit()
        if affected:
            return {"message": f"Problem {req.problem_id} unmarked for user {user_id}"}
        else:
            return {"message": "No record found to delete", "problem_id": req.problem_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


@router.get("/is-solved/{problem_id}")
def is_solved(problem_id: int, current_user: dict = Depends(get_current_user)):
    """Quick check whether the logged-in user has solved the given problem."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    user_id = current_user.get("id")
    conn = get_db_connection()
    if isinstance(conn, dict) and "error" in conn:
        raise HTTPException(status_code=500, detail=conn["error"])

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, solved_at FROM interactions WHERE user_id = %s AND problem_id = %s",
            (user_id, problem_id),
        )
        row = cursor.fetchone()
        if row:
            return {"solved": True, "solved_at": row[1] if len(row) > 1 else None}
        else:
            return {"solved": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass


@router.get("/progress")
def get_user_progress(current_user: dict = Depends(get_current_user)):
    """Fetch all solved problems grouped by tags for the logged-in user."""
    user_id = current_user.get("id")

    conn = get_db_connection()
    if isinstance(conn, dict) and "error" in conn:
        raise HTTPException(status_code=500, detail=conn["error"])

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT tags, problem_title, difficulty
            FROM interactions
            WHERE user_id = %s
            ORDER BY solved_at DESC
            """,
            (user_id,),
        )
        rows = cursor.fetchall()

        if not rows:
            return {"user_id": user_id, "topics": []}
        tag_groups = {}
        for row in rows:
            raw_tags = row.get("tags") or ""
            tag_list = [t.strip().lower() for t in raw_tags.split(",") if t.strip()]
            for tag in tag_list:
                tag_groups.setdefault(tag, []).append(
                    {
                        "title": row.get("problem_title"),
                        "difficulty": row.get("difficulty"),
                    }
                )

        result = [
            {"tag": tag, "count": len(problems), "problems": problems}
            for tag, problems in tag_groups.items()
        ]

        return {"user_id": user_id, "topics": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass

