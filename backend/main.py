"""Tech AI (Ustoz AI) — FastAPI entry point.

Exposes a small HTTP API in front of the LangGraph multi-agent workflow.
"""
import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.graph.nodes import build_graph

load_dotenv()

app = FastAPI(title="Tech AI Teacher Assistant", version="1.0.0")

allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:8501").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

os.makedirs("creating_files", exist_ok=True)
app.mount("/creating_files", StaticFiles(directory="creating_files"), name="creating_files")


class ChatRequest(BaseModel):
    request: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(min_length=1, max_length=128)


class ChatResponse(BaseModel):
    next_agent: str
    answer: str


@app.get("/")
def index():
    return {"service": "tech-ai-teacher-assistant", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    """Run one request through the supervisor + specialist agent graph."""
    try:
        graph = build_graph()
        final_state = graph.invoke(
            {"request": payload.request, "session_id": payload.session_id}
        )
    except Exception as exc:  # surface a clean error instead of a 500 traceback
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}") from exc

    return ChatResponse(
        next_agent=final_state.get("next_agent", "chat_agent"),
        answer=final_state.get("answer", ""),
    )


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
