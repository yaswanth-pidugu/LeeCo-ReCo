from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api import auth, user_progress, recommender
from src.api.recommender import init_recommender
from src.modeling.lightGBM import load_resources

app = FastAPI(title="LeetCode Recommender Backend")

app.include_router(recommender.router, prefix="/api")

@app.on_event("startup")
def startup_event():
    init_recommender()

app.include_router(auth.router)
app.include_router(user_progress.router)


from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
