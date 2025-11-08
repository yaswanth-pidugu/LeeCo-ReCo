import reflex as rx

def home() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("LeetCode Problem Recommender", size="9"),
            rx.text(
                "Get personalized problem suggestions and analytics — powered by ML, built by you.",
                size="4",
                color="gray"
            ),
            rx.hstack(
                rx.button("Get Started", on_click=lambda: rx.redirect("/recommender")),
                rx.button("View Analytics", on_click=lambda: rx.redirect("/analytics")),
                spacing="4"
            ),
            margin_top="10em"
        )
    )
