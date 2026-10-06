"""Chat with a lecture (RAG): streamed answers with timestamp citations."""

import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.api.deps import get_lecture_or_404
from app.api.errors import api_error
from app.api.schemas import ChatIn, ChatMessageOut, SourceOut
from app.db import repository
from app.db.models import ChatEntry, Lecture
from app.db.session import get_session
from app.rag.service import ChatEvent, ChatTurn, RAGService
from app.transcription.models import Transcript

router = APIRouter(prefix="/api/lectures/{lecture_id}/chat", tags=["chat"])


def _to_out(entry: ChatEntry) -> ChatMessageOut:
    return ChatMessageOut(
        id=entry.id,  # type: ignore[arg-type]
        role=entry.role,  # type: ignore[arg-type]
        content=entry.content,
        sources=[SourceOut(**s) for s in json.loads(entry.sources_json or "[]")],
        created_at=entry.created_at,
    )


def _sse(event: ChatEvent) -> str:
    return f"event: {event.type}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"


@router.get("", response_model=list[ChatMessageOut])
def get_history(lecture: Lecture = Depends(get_lecture_or_404), session: Session = Depends(get_session)):
    """The saved conversation for this lecture."""
    return [_to_out(entry) for entry in repository.list_chat(session, lecture.id)]


@router.delete("", status_code=204)
def clear_history(lecture: Lecture = Depends(get_lecture_or_404), session: Session = Depends(get_session)) -> Response:
    repository.clear_chat(session, lecture.id)
    return Response(status_code=204)


@router.post("", response_class=StreamingResponse)
def ask(body: ChatIn, request: Request, lecture: Lecture = Depends(get_lecture_or_404)):
    """Ask a question. The answer streams back as Server-Sent Events:

    - `status`  {"message"}: e.g. indexing the lecture on first use
    - `sources` {"sources": [{start, end, text, similarity}]}: the excerpts used
    - `token`   {"text"}: the next piece of the answer
    - `done`    {"answer", "message_id"}: the full answer (now saved)
    - `error`   {"message", "hint"}
    """
    if lecture.status != "done" or not lecture.transcript_json:
        raise api_error(409, "Chat is available once the lecture has finished processing.")

    rag: RAGService = request.app.state.rag
    engine = request.app.state.engine
    settings = request.app.state.settings
    # Copy plain values now: the database session closes before streaming finishes.
    lecture_id, title, transcript_json = lecture.id, lecture.title, lecture.transcript_json
    question = body.message.strip()

    with Session(engine) as session:
        history = [
            ChatTurn(role=entry.role, content=entry.content)  # type: ignore[arg-type]
            for entry in repository.list_chat(session, lecture_id, limit=settings.rag_history_messages)
        ]

    def events() -> Iterator[str]:
        sources: list[dict] = []
        for event in rag.stream_answer(
            lecture_id,
            question,
            history,
            load_transcript=lambda: Transcript.model_validate_json(transcript_json),
            title=title,
        ):
            if event.type == "sources":
                sources = event.data["sources"]
            elif event.type == "done":
                # Save the question and answer only once the answer is complete.
                with Session(engine) as session:
                    repository.add_chat_entry(session, lecture_id, "user", question)
                    saved = repository.add_chat_entry(
                        session, lecture_id, "assistant", event.data["answer"], json.dumps(sources)
                    )
                    event.data["message_id"] = saved.id
            yield _sse(event)

    # A sync generator: Starlette runs it in a worker thread, so the slow
    # embedding and LLM calls don't block other requests.
    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
