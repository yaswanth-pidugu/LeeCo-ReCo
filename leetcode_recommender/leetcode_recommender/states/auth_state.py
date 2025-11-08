import reflex as rx
import requests

class AuthState(rx.State):
    username: str = ""
    password: str = ""
    email: str = ""
    token: str = ""
    user_id: int = 0
    error_message: str = ""

    BACKEND_URL = "http://127.0.0.1:8100/auth"   # correct base path


    def set_username(self, value: str):
        self.username = value

    def set_password(self, value: str):
        self.password = value

    def set_email(self, value: str):
        self.email = value

    def _reset_user_progress(self):
        from leetcode_recommender.states.user_state import UserState
        UserState.reset_state(UserState)

    def login(self):
        """Authenticate user and store JWT."""
        try:
            response = requests.post(
                f"{self.BACKEND_URL}/login",
                data={"username": self.username, "password": self.password},
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token", "")
                self.user_id = data.get("user_id", 0)
                self.error_message = ""
                self._reset_user_progress()  # <— clear any previous solved state
                return rx.redirect("/recommender")
            else:
                self.error_message = "Invalid username or password"
        except Exception as e:
            self.error_message = f"Login failed: {e}"

    def register(self):
        """Register new user and redirect to login."""
        try:
            payload = {
                "username": self.username.strip(),
                "email": self.email.strip(),
                "password": self.password,
            }
            response = requests.post(f"{self.BACKEND_URL}/signup", json=payload)
            if response.status_code == 200:
                self.error_message = ""
                return rx.redirect("/login")
            else:
                data = response.json()
                self.error_message = data.get("detail", "Registration failed.")
        except Exception as e:
            self.error_message = f"Signup failed: {e}"

    def logout(self):
        """Clear session, reset progress, and redirect to login."""
        self._reset_user_progress()  # <— clear solved-state cache
        self.token = ""
        self.user_id = 0
        self.error_message = ""
        return rx.redirect("/login")

    def check_auth(self) -> bool:
        """Check if token exists in memory."""
        return bool(self.token)