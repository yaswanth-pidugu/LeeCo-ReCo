import reflex as rx
from leetcode_recommender.states.auth_state import AuthState


def register_page() -> rx.Component:
    return rx.center(
        rx.card(
            rx.vstack(
                rx.heading("Register", size="8"),
                rx.input(placeholder="Username", on_change=AuthState.set_username),
                rx.input(placeholder="Email", on_change=AuthState.set_email),
                rx.input(
                    placeholder="Password",
                    type_="password",
                    on_change=AuthState.set_password
                ),
                rx.button("Sign Up", on_click=AuthState.register),
                rx.cond(
                    AuthState.error_message != "",
                    rx.text(AuthState.error_message, color="red")
                ),
                rx.link("Already have an account? Login →", href="/login", color="blue"),
                spacing="4",
                align="center"
            ),
            width="400px",
            padding="24px",
            shadow="lg",
            border_radius="xl"
        ),
        height="100vh"
    )