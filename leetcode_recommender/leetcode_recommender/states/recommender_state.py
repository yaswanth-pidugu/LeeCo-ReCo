import reflex as rx
import requests
from typing import List, Optional


BACKEND_URL = "http://localhost:8100/api/recommend"


class Problem(rx.Base):
    frontend_id: Optional[int] = None  # <— add this line
    title: str
    difficulty: str
    topic_tags: Optional[str] = None
    problem_URL: Optional[str] = None
    reason: Optional[str] = None
    score: Optional[float] = None
    category: Optional[str] = None



class RecommenderState(rx.State):
    problem_id: str = ""
    current_problem: Optional[Problem] = None
    results: List[Problem] = []
    learning_items: List[Problem] = []  # flattened learning path
    use_learning_path: bool = False
    error: str = ""

    def set_problem_id(self, v: str):
        self.problem_id = v

    def toggle_learning_path(self, v: bool):
        self.use_learning_path = v

    def fetch(self):
        """Fetch recommendations or learning path based on toggle.

        Always POST to a single backend endpoint with a JSON payload that includes
        the `use_learning_path` flag. This avoids behavioral differences between GET
        and POST endpoints and ensures the backend can decide which mode to run.
        """
        try:
            # Validate/convert problem id safely
            if not self.problem_id:
                self.error = "Please enter a problem id"
                self.results = []
                self.learning_items = []
                self.current_problem = None
                return

            payload = {
                "problem_id": int(self.problem_id),
                "top_k": 10,
                "use_learning_path": bool(self.use_learning_path),
            }

            res = requests.post(BACKEND_URL, json=payload)

            if res.status_code != 200:
                self.error = f"Error {res.status_code}: {res.text}"
                self.results = []
                self.learning_items = []
                self.current_problem = None
                return

            data = res.json()
            self.error = ""

            # `requested_problem` might be absent; guard against it
            req = data.get("requested_problem") or {}
            try:
                self.current_problem = Problem(**req) if req else None
            except Exception:
                # If structure doesn't match Problem model, keep raw dict as minimal wrapper
                self.current_problem = None

            # If backend returned learning path (and toggle was true) flatten it
            if self.use_learning_path and "learning_path" in data:
                lp = data["learning_path"]
                self.learning_items = []
                for cat in ["before", "similar", "after"]:
                    for item in lp.get(cat, []):
                        # ensure category present
                        wrapped = {**item, "category": cat}
                        try:
                            self.learning_items.append(Problem(**wrapped))
                        except Exception:
                            # partial fallback: build Problem manually with safe keys
                            p = Problem(
                                title=wrapped.get("title", "Untitled"),
                                difficulty=wrapped.get("difficulty", "Unknown"),
                                topic_tags=wrapped.get("tags") or wrapped.get("topic_tags"),
                                problem_URL=wrapped.get("problem_URL"),
                                reason=wrapped.get("reason"),
                                score=wrapped.get("score"),
                                category=cat,
                            )
                            self.learning_items.append(p)
                self.results = []
            else:
                # Normal recommendations mode — expects `recommendations` key
                recs = data.get("recommendations", [])
                self.results = []
                for r in recs:
                    try:
                        self.results.append(Problem(**r))
                    except Exception:
                        # best-effort fallback
                        p = Problem(
                            title=r.get("title", "Untitled"),
                            difficulty=r.get("difficulty", "Unknown"),
                            topic_tags=r.get("topic_tags") or r.get("tags"),
                            problem_URL=r.get("problem_URL"),
                            reason=r.get("reason"),
                            score=r.get("score"),
                        )
                        self.results.append(p)
                self.learning_items = []

        except Exception as e:
            self.error = str(e)
            self.results = []
            self.learning_items = []
            self.current_problem = None