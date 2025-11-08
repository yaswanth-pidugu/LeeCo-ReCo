from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api import recommender, auth, user_progress
from src.modeling.lightGBM import load_resources


app = FastAPI(
    title="LeetCode Recommender API",
    description="Backend for LeetCode Problem Recommendation System with JWT auth and user progress tracking.",
    version="1.0.0",
)

app.include_router(auth.router)
app.include_router(recommender.app)
app.include_router(user_progress.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    try:
        load_resources()
        print("[READY] Recommender resources loaded successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to load recommender resources: {e}")


@app.get("/")
def root():
    return {
        "message": "LeetCode Recommender API is running",
        "status": "ok",
    }

import signal, sys

def shutdown_handler(sig, frame):
    print("\n[STOP] Server shutting down.")
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown_handler)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8100, reload=True)

