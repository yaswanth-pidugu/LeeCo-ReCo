# leetcode_recommender/pages/analytics.py
import reflex as rx
import requests
from typing import Dict, List

API_BASE = "http://127.0.0.1:8200/analytics"


class AnalyticsState(rx.State):
    # Raw chart-ready lists
    difficulty_data: List[Dict] = []
    tag_data: List[Dict] = []
    trends: List[Dict] = []

    # Simple primitives for summary cards (avoid indexing into dict Vars)
    total_problems: int = 0
    average_acceptance: float = 0.0
    easy_count: int = 0
    medium_count: int = 0
    hard_count: int = 0

    # Additional visuals
    top_problems: List[Dict] = []  # each: {"frontend_id", "title", "likes", "acceptance", "difficulty"}
    top_tags: List[Dict] = []      # same as tag_data but explicitly stored

    error: str = ""

    def fetch_all(self):
        """Fetch analytics API endpoints and normalize into Reflex-friendly fields."""
        try:
            # call endpoints
            stats_res = requests.get(f"{API_BASE}/stats", timeout=8)
            diff_res = requests.get(f"{API_BASE}/difficulty-distribution", timeout=8)
            tag_res = requests.get(f"{API_BASE}/tag-frequency", timeout=8)
            top_res = requests.get(f"{API_BASE}/top-popular", timeout=8)
            trend_res = requests.get(f"{API_BASE}/acceptance-trends", timeout=8)

            # ensure all ok
            for r in (stats_res, diff_res, tag_res, top_res, trend_res):
                if r.status_code != 200:
                    raise RuntimeError(f"Analytics endpoint error: {r.status_code} {r.text}")

            stats = stats_res.json()
            diff = diff_res.json().get("difficulty_distribution", {})
            tags = tag_res.json().get("tag_frequency", {})
            top = top_res.json().get("popular_problems", [])
            trends = trend_res.json().get("acceptance_trends", {})

            # set summary primitives (safe typed assignments)
            self.total_problems = int(stats.get("total_problems", 0))
            # average acceptance may be float or str, coerce to float then round
            try:
                self.average_acceptance = round(float(stats.get("average_acceptance", 0.0)), 2)
            except Exception:
                self.average_acceptance = 0.0

            # difficulty split -> primitives
            easy = diff.get("Easy", diff.get("easy", 0)) if isinstance(diff, dict) else 0
            medium = diff.get("Medium", diff.get("medium", 0)) if isinstance(diff, dict) else 0
            hard = diff.get("Hard", diff.get("hard", 0)) if isinstance(diff, dict) else 0

            self.easy_count = int(easy or 0)
            self.medium_count = int(medium or 0)
            self.hard_count = int(hard or 0)

            # charts: convert dict -> list-of-dict for Recharts components
            self.difficulty_data = [{"name": k, "value": int(v)} for k, v in diff.items()] if isinstance(diff, dict) else []
            self.tag_data = [{"tag": k, "count": int(v)} for k, v in tags.items()] if isinstance(tags, dict) else []
            self.top_tags = self.tag_data[:20]  # keep top 20 for visual

            # top problems is already list-of-dict from backend
            self.top_problems = top if isinstance(top, list) else []

            # trends: convert map -> list-of-dict sorted by bin order (attempt stable ordering)
            if isinstance(trends, dict):
                self.trends = [{"range": k, "count": int(v)} for k, v in trends.items()]
            else:
                self.trends = []

            self.error = ""
        except Exception as e:
            self.error = str(e)
            # keep previous data if present (or clear selectively)
            # optionally clear lists on error:
            # self.difficulty_data = []; self.tag_data = []; self.trends = []; self.top_problems = []


def analytics_page() -> rx.Component:
    """Reflex analytics dashboard page that uses typed state fields (avoids Var indexing)."""
    return rx.center(
        rx.vstack(
            rx.hstack(
                rx.heading("Analytics Dashboard", size="8"),
                rx.spacer(),
                rx.button("Load Analytics", on_click=AnalyticsState.fetch_all, color_scheme="blue"),
            ),
            rx.cond(
                AnalyticsState.error != "",
                rx.text(AnalyticsState.error, color="red"),
                rx.fragment(),
            ),

            # Summary cards (use simple primitive fields)
            rx.cond(
                (AnalyticsState.total_problems != 0) | (AnalyticsState.average_acceptance != 0.0),
                rx.hstack(
                    rx.card(
                        rx.vstack(
                            rx.text("Total Problems", weight="medium"),
                            rx.heading(AnalyticsState.total_problems),
                        ),
                        padding="1em",
                    ),
                    rx.card(
                        rx.vstack(
                            rx.text("Average Acceptance", weight="medium"),
                            rx.heading(rx.Var.create(AnalyticsState.average_acceptance) ),  # primitive float
                        ),
                        padding="1em",
                    ),
                    rx.card(
                        rx.vstack(
                            rx.text("Difficulty Split", weight="medium"),
                            rx.text(f"Easy: {AnalyticsState.easy_count}", color="green"),
                            rx.text(f"Medium: {AnalyticsState.medium_count}", color="orange"),
                            rx.text(f"Hard: {AnalyticsState.hard_count}", color="red"),
                        ),
                        padding="1em",
                    ),
                    spacing="4",
                ),
                rx.text("Press Load Analytics to populate metrics."),
            ),

            # --- Difficulty Pie ---
            rx.cond(
                AnalyticsState.difficulty_data != [],
                rx.vstack(
                    rx.heading("Difficulty Distribution", size="5"),
                    rx.recharts.pie_chart(
                        rx.recharts.pie(
                            data=AnalyticsState.difficulty_data,
                            data_key="value",
                            name_key="name",
                            label=True,
                        ),
                        rx.recharts.tooltip(),
                        width=520,
                        height=360,
                    ),
                ),
            ),

            # --- Top Tags bar chart ---
            rx.cond(
                AnalyticsState.top_tags != [],
                rx.vstack(
                    rx.heading("Top Tags (frequency)", size="5"),
                    rx.recharts.bar_chart(
                        *[
                            rx.recharts.x_axis(data_key="tag", interval=0, angle= -35, text_anchor="end"),
                            rx.recharts.y_axis(),
                            rx.recharts.tooltip(),
                            rx.recharts.bar(data_key="count"),
                        ],
                        data=AnalyticsState.top_tags,
                        width=900,
                        height=420,
                    ),
                ),
            ),

            # --- Top Popular Problems table (additional visual) ---
            rx.cond(
                AnalyticsState.top_problems != [],
                rx.vstack(
                    rx.heading("Top Popular Problems", size="5"),
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Title"),
                                rx.table.column_header_cell("Likes"),
                                rx.table.column_header_cell("Acceptance"),
                                rx.table.column_header_cell("Difficulty"),
                            )
                        ),
                        rx.table.body(
                            rx.foreach(
                                AnalyticsState.top_problems,
                                lambda p: rx.table.row(
                                    rx.table.cell(
                                        rx.link(
                                            p.get("title", "Untitled"),
                                            href=rx.Var.create(
                                                f"https://leetcode.com/problems/{p.get('frontend_id', '')}"
                                            ),
                                            is_external=True,
                                        )
                                    ),
                                    rx.table.cell(rx.Var.create(p.get("likes", 0))),
                                    rx.table.cell(rx.Var.create(p.get("acceptance", 0))),
                                    rx.table.cell(rx.Var.create(p.get("difficulty", "Unknown"))),
                                ),
                            )
                        ),
                        width="900px",
                    ),
                ),
            ),

            # --- Acceptance Trends line chart ---
            rx.cond(
                AnalyticsState.trends != [],
                rx.vstack(
                    rx.heading("Acceptance Trends (distribution bins)", size="5"),
                    rx.recharts.line_chart(
                        *[
                            rx.recharts.x_axis(data_key="range"),
                            rx.recharts.y_axis(),
                            rx.recharts.tooltip(),
                            rx.recharts.line(data_key="count"),
                        ],
                        data=AnalyticsState.trends,
                        width=900,
                        height=360,
                    ),
                ),
            ),

            spacing="6",
            padding="2em",
        ),
        background_color="gray.50",
        min_height="100vh",
    )
