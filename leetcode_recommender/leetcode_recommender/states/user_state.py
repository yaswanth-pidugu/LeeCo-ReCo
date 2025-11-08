import reflex as rx
import requests
from typing import List, Dict, Optional
from leetcode_recommender.states.auth_state import AuthState

BASE_URL = "http://127.0.0.1:8100/user"


class SolvedProblem(rx.Base):
    problem_id: Optional[int] = None
    problem_title: str = ""
    tags: str = ""
    difficulty: str = ""
    solved_at: str = ""


class TopicGroup(rx.Base):
    tag: str = ""
    count: int = 0
    problems: List[SolvedProblem] = []


class UserState(rx.State):
    """Manages solved problem state and interaction with backend."""

    solved_status: Dict[int, bool] = {}
    topic_groups: List[TopicGroup] = []
    error: str = ""

    def _auth_headers(self) -> Dict[str, str]:
        token = AuthState.token or ""
        if not token:
            raise ValueError("User not logged in — missing token.")
        return {"Authorization": f"Bearer {token}"}

    def mark_solved(self, problem_id: int, title: str, tags: str, difficulty: str):
        """Mark a problem as solved and update state."""
        try:
            payload = {
                "problem_id": int(problem_id),
                "problem_title": title,
                "tags": tags,
                "difficulty": difficulty,
            }

            res = requests.post(
                f"{BASE_URL}/mark-solved",
                json=payload,
                headers=self._auth_headers(),
                timeout=10,
            )

            if res.status_code == 200:
                self.solved_status[problem_id] = True
                self.solved_status = self.solved_status.copy()
                self.error = ""
                self.fetch_progress()
            else:
                self.error = f"mark_solved failed: {res.status_code} {res.text}"

        except Exception as e:
            self.error = f"mark_solved exception: {e}"

    def unmark_solved(self, problem_id: int):
        """Undo mark solved."""
        try:
            payload = {"problem_id": int(problem_id)}
            res = requests.post(
                f"{BASE_URL}/unmark-solved",
                json=payload,
                headers=self._auth_headers(),
                timeout=10,
            )
            if res.status_code == 200:
                self.solved_status[problem_id] = False
                self.solved_status = self.solved_status.copy()
                self.error = ""
                self.fetch_progress()
            else:
                self.error = f"unmark_solved failed: {res.status_code} {res.text}"
        except Exception as e:
            self.error = f"unmark_solved exception: {e}"

    def toggle_solved(self, problem):
        """Receive full problem object from frontend safely."""
        try:
            problem_id = int(problem.get("frontend_id") or problem.get("problem_id"))
            title = str(problem.get("title") or "Untitled")
            tags = str(problem.get("topic_tags") or problem.get("tags") or "")
            difficulty = str(problem.get("difficulty") or "Unknown")
        except Exception:
            print("[DEBUG] toggle_solved invalid payload:", problem)
            return

        print(f"[DEBUG] toggle_solved CALLED from UI -> problem_id={problem_id} | title={title}")
        if self.solved_status.get(problem_id, False):
            self.unmark_solved(problem_id)
        else:
            self.mark_solved(problem_id, title, tags, difficulty)

    def fetch_progress(self):
        """Pull user's solved data from backend."""
        try:
            res = requests.get(
                f"{BASE_URL}/progress",
                headers=self._auth_headers(),
                timeout=10,
            )

            if res.status_code != 200:
                self.topic_groups = []
                self.error = f"Progress fetch failed: {res.status_code} {res.text}"
                return

            data = res.json()
            topics = data.get("topics") or []

            new_groups: List[TopicGroup] = []
            for group in topics:
                tag = group.get("tag") or "Unknown"
                problems_data = group.get("problems") or []
                problems = [
                    SolvedProblem(
                        problem_id=p.get("problem_id")
                        or p.get("frontend_id"),
                        problem_title=p.get("problem_title")
                        or p.get("title")
                        or "Untitled",
                        tags=p.get("tags") or p.get("topic_tags") or "",
                        difficulty=p.get("difficulty") or "Unknown",
                        solved_at=p.get("solved_at") or "",
                    )
                    for p in problems_data
                ]
                new_groups.append(
                    TopicGroup(tag=tag, count=len(problems), problems=problems)
                )

            self.topic_groups = new_groups
            self.error = ""

        except Exception as e:
            self.topic_groups = []
            self.error = f"fetch_progress: {e}"

    @rx.var
    def solved_ids(self) -> List[int]:
        return [pid for pid, solved in self.solved_status.items() if solved]

    def reset_state(self):
        self.solved_status = {}
        self.topic_groups = []
        self.error = ""
