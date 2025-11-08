import reflex as rx
from leetcode_recommender.pages.home import home
from leetcode_recommender.pages.login import login_page
from leetcode_recommender.pages.register import register_page
from leetcode_recommender.pages.recommender import recommender_page
from leetcode_recommender.pages.solved import solved_page
from leetcode_recommender.states.user_state import UserState
from leetcode_recommender.states.auth_state import AuthState
from leetcode_recommender.states.recommender_state import RecommenderState
from leetcode_recommender.pages.analytics import analytics_page

app = rx.App()
app.add_page(home, route="/", title="Home")
app.add_page(login_page, route="/login", title="Login")
app.add_page(register_page, route="/register", title="Register")
app.add_page(recommender_page, route="/recommender", title="Recommender")
app.add_page(solved_page, route="/solved", title="Solved Problems")
app.add_page(analytics_page, route="/analytics", title="Analytics Dashboard")