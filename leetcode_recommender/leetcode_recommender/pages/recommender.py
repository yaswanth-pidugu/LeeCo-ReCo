import reflex as rx
from leetcode_recommender.states.recommender_state import RecommenderState
from leetcode_recommender.states.auth_state import AuthState


def parse_tags(raw):
    return rx.cond(
        (raw == None) | (raw == "") | (raw == "[]"),
        rx.text("N/A", color="gray.600", size="3"),
        rx.text(raw, color="gray.700", size="3"),
    )


def difficulty_badge(difficulty):
    color = rx.cond(
        difficulty == "Easy",
        "green",
        rx.cond(
            difficulty == "Medium",
            "orange",
            rx.cond(difficulty == "Hard", "red", "gray"),
        ),
    )
    return rx.badge(
        rx.cond(difficulty != None, difficulty, "Unknown"),
        color_scheme=color,
        variant="solid",
        size="2",
    )


def safe_link(title, href):
    return rx.cond(
        (href == None) | (href == "") | (href == "null") | (href == "None"),
        rx.text(title, color="gray.700", weight="bold"),
        rx.link(
            title,
            href=rx.Var.create(str(href)) if hasattr(href, "_var_type") else str(href),
            color="blue",
            is_external=True,
        ),
    )


def recommender_page() -> rx.Component:
    current = RecommenderState.current_problem

    return rx.center(
        rx.vstack(
            # Header
            rx.hstack(
                rx.heading("LeetCode Problem Recommender", size="8"),
                rx.spacer(),
                rx.cond(
                    AuthState.token != "",
                    rx.hstack(
                        rx.text(
                            rx.cond(
                                AuthState.username != "",
                                AuthState.username,
                                "User",
                            ),
                            size="3",
                            weight="medium",
                        ),
                        rx.link("Solved Problems", href="/solved"),
                        rx.button(
                            "Logout",
                            on_click=AuthState.logout,
                            color_scheme="red",
                            size="2",
                        ),
                        spacing="3",
                    ),
                    rx.menu.root(
                        rx.menu.trigger(rx.button("User", color_scheme="blue")),
                        rx.menu.content(
                            rx.menu.item("Login", on_click=lambda: rx.redirect("/login")),
                            rx.menu.item("Sign Up", on_click=lambda: rx.redirect("/register")),
                        ),
                    ),
                ),
                margin_bottom="1em",
            ),

            # Input and toggle
            rx.hstack(
                rx.input(
                    placeholder="Enter Problem ID (e.g., 435)",
                    width="250px",
                    on_change=lambda v: RecommenderState.set_problem_id(v),
                ),
                rx.button("Recommend", on_click=RecommenderState.fetch, size="2"),
                rx.hstack(
                    rx.text("Enable Learning Path"),
                    rx.switch(
                        is_checked=RecommenderState.use_learning_path,
                        on_change=lambda v: RecommenderState.toggle_learning_path(v),
                    ),
                    spacing="2",
                ),
                spacing="4",
            ),

            # Error display
            rx.cond(
                RecommenderState.error != "",
                rx.text(RecommenderState.error, color="red", weight="bold"),
                rx.fragment(),
            ),

            # Current Problem
            rx.cond(
                current,
                rx.card(
                    rx.vstack(
                        rx.text(current.title, weight="bold", size="5"),
                        difficulty_badge(current.difficulty),
                        rx.hstack(
                            rx.text("Tags:", size="3", weight="medium"),
                            parse_tags(current.topic_tags),
                        ),
                        safe_link("View on LeetCode ↗", current.problem_URL),
                    ),
                    padding="1em",
                    width="100%",
                    max_width="600px",
                    box_shadow="md",
                    border_radius="lg",
                    background_color="gray.50",
                    margin_top="1em",
                ),
                rx.text("Enter an ID and press Recommend to get results."),
            ),

            # Learning Path or Normal Recommendations
            rx.cond(
                RecommenderState.use_learning_path,
                # --- Learning Path Mode ---
                rx.vstack(
                    rx.heading("Learning Path", size="6", margin_top="1em"),
                    rx.foreach(
                        RecommenderState.learning_items,
                        lambda p: rx.card(
                            rx.vstack(
                                rx.hstack(
                                    safe_link(p.title, p.problem_URL),
                                    difficulty_badge(p.difficulty),
                                    rx.badge(
                                        rx.cond(
                                            p.category == "before",
                                            "Before",
                                            rx.cond(
                                                p.category == "similar",
                                                "Similar",
                                                rx.cond(
                                                    p.category == "after",
                                                    "After",
                                                    "Other",
                                                ),
                                            ),
                                        ),
                                        color_scheme="blue",
                                        size="2",
                                    ),
                                    spacing="3",
                                ),
                                rx.cond(
                                    (p.reason != None) & (p.reason != ""),
                                    rx.text(p.reason, size="3", color="gray.600"),
                                    rx.text("", size="3"),
                                ),
                                rx.hstack(rx.text("Tags:", size="3"), parse_tags(p.topic_tags)),
                            ),
                            padding="0.7em",
                            margin_bottom="0.5em",
                            background_color="gray.50",
                        ),
                    ),
                    spacing="3",
                ),
                # --- Normal Recommendation Table ---
                rx.cond(
                    RecommenderState.results != [],
                    rx.vstack(
                        rx.heading("Recommended Problems", size="6", margin_top="1em"),
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("Title"),
                                    rx.table.column_header_cell("Difficulty"),
                                    rx.table.column_header_cell("Tags"),
                                )
                            ),
                            rx.table.body(
                                rx.foreach(
                                    RecommenderState.results,
                                    lambda r: rx.table.row(
                                        rx.table.cell(safe_link(r.title, r.problem_URL)),
                                        rx.table.cell(difficulty_badge(r.difficulty)),
                                        rx.table.cell(parse_tags(r.topic_tags)),
                                    ),
                                )
                            ),
                            width="700px",
                        ),
                    ),
                    rx.fragment(),
                ),
            ),
            spacing="6",
            padding="2em",
            align_items="center",
        ),
        background_color="gray.100",
        min_height="100vh",
    )
