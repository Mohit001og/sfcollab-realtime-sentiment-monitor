import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.mood import MoodSnapshot, RollingMoodService
from app.sentiment import SentimentEngine, get_sentiment_engine


MAX_MESSAGE_LENGTH = 1000
DEFAULT_FRONTEND_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173,https://sfcollab-realtime-sentiment-monitor.vercel.app"
logger = logging.getLogger(__name__)


class MessageRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=MAX_MESSAGE_LENGTH,
        description=f"Team-chat message to analyze. Maximum length: {MAX_MESSAGE_LENGTH} characters.",
        examples=["Great work everyone!"],
    )


class MessageResponse(BaseModel):
    message: str
    sentiment: str
    score: float
    latency_ms: float
    timestamp: datetime


class MoodResponse(BaseModel):
    score: float | None
    window_minutes: int = 60
    message_count: int


class MoodHistoryItemResponse(BaseModel):
    timestamp: datetime
    score: float


class MoodStateResponse(BaseModel):
    score: float | None
    window_minutes: int = 60
    message_count: int
    history: list[MoodHistoryItemResponse] = Field(
        default_factory=list,
        description="Signed mood values from messages currently inside the rolling 60-minute window.",
    )


class BroadcastPayload(BaseModel):
    type: str
    data: MessageResponse
    mood: MoodResponse


class ConnectionManager:
    def __init__(self) -> None:
        self._active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._active_connections:
            self._active_connections.remove(websocket)

    async def broadcast(self, payload: BroadcastPayload) -> None:
        message = payload.model_dump(mode="json")
        stale_connections: list[WebSocket] = []
        for connection in list(self._active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                stale_connections.append(connection)
        for connection in stale_connections:
            self.disconnect(connection)


def parse_frontend_origins(value: str | None = None) -> list[str]:
    configured = value if value is not None else os.getenv("FRONTEND_ORIGINS", DEFAULT_FRONTEND_ORIGINS)
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Preload the sentiment pipeline at startup so the first user message
    # does not pay the model initialization or download cost.
    preload_started = datetime.now(timezone.utc)
    logger.info("Sentiment engine preload started")
    get_sentiment_engine()
    elapsed_seconds = (datetime.now(timezone.utc) - preload_started).total_seconds()
    logger.info("Sentiment engine preload finished in %.2fs", elapsed_seconds)
    yield


app = FastAPI(title="SFCollab Backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_frontend_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
manager = ConnectionManager()
mood_service = RollingMoodService()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/mood", response_model=MoodStateResponse)
async def get_mood() -> MoodStateResponse:
    snapshot = mood_service.snapshot()
    history = [
        MoodHistoryItemResponse(timestamp=item.timestamp, score=item.score)
        for item in mood_service.history()
    ]
    return MoodStateResponse(
        score=snapshot.score,
        window_minutes=snapshot.window_minutes,
        message_count=snapshot.message_count,
        history=history,
    )


@app.post("/messages", response_model=MessageResponse)
async def score_message(
    payload: MessageRequest,
    engine: Annotated[SentimentEngine, Depends(get_sentiment_engine)],
) -> MessageResponse:
    if not payload.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="message must not be empty or whitespace only",
        )

    try:
        result = engine.analyze(payload.message)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="sentiment analysis failed",
        ) from exc

    response = MessageResponse(
        message=payload.message,
        sentiment=result.label,
        score=result.score,
        latency_ms=result.latency_ms,
        timestamp=datetime.now(timezone.utc),
    )
    mood_snapshot = mood_service.add_message(
        timestamp=response.timestamp,
        sentiment=response.sentiment,
        score=response.score,
    )
    await manager.broadcast(
        BroadcastPayload(
            type="message",
            data=response,
            mood=MoodResponse(
                score=mood_snapshot.score,
                window_minutes=mood_snapshot.window_minutes,
                message_count=mood_snapshot.message_count,
            ),
        )
    )
    return response


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
