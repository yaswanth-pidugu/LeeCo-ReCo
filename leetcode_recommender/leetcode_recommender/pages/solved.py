import reflex as rx
from leetcode_recommender.states.user_state import UserState
from leetcode_recommender.states.auth_state import AuthState


def solved_page() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.hstack(
                rx.heading("Solved Problems — Grouped by Topics", size="6"),
                rx.spacer(),
                rx.cond(
                    AuthState.token != "",
                    rx.button("Refresh", on_click=UserState.fetch_progress, size="2"),
                    rx.link("Login", href="/login"),
                ),
            ),

            rx.cond(
                AuthState.token == "",
                rx.text("Please login to view your solved problems.", color="gray.600"),
                rx.fragment(),
            ),

            rx.cond(
                UserState.topic_groups != [],
                rx.foreach(
                    UserState.topic_groups,
                    lambda g: rx.card(
                        rx.vstack(
                            rx.hstack(
                                rx.text(g.tag.upper(), weight="bold"),
                                rx.text("(" + g.count.to_string() + ")", color="gray.600"),
                                spacing="3",
                            ),
                            rx.foreach(
                                g.problems,
                                lambda p: rx.hstack(
                                    rx.link(
                                        rx.cond(
                                            (p.problem_title != None)
                                            & (p.problem_title != ""),
                                            p.problem_title,
                                            "Untitled",
                                        ),
                                        href=rx.cond(
                                            p.problem_id != None,
                                            "/recommender?problem_id="
                                            + p.problem_id.to_string(),
                                            "#",
                                        ),
                                        color="blue",
                                    ),
                                    rx.text(
                                        rx.cond(
                                            (p.difficulty != None)
                                            & (p.difficulty != ""),
                                            p.difficulty,
                                            "Unknown",
                                        ),
                                        color="gray",
                                    ),
                                    rx.spacer(),
                                    rx.cond(
                                        p.solved_at != None,
                                        rx.text(
                                            "Solved: " + p.solved_at.to_string(),
                                            size="2",
                                            color="gray.500",
                                        ),
                                        rx.fragment(),
                                    ),
                                ),
                            ),
                        ),
                        padding="0.8em",
                        margin_bottom="0.6em",
                        width="700px",
                    ),
                ),
                rx.text(
                    "No solved problems found. Mark some problems as solved to see them here.",
                    color="gray.600",
                ),
            ),

            spacing="6",
            padding="2em",
            align_items="center",
        ),
        min_height="100vh",
    )
