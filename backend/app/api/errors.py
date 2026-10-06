"""Turn exceptions into consistent JSON error responses.

Every error the frontend receives looks like:
    {"detail": {"message": "What went wrong", "hint": "What to do", "type": "ErrorName"}}
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.errors import (
    ConfigurationError,
    InvalidYouTubeURLError,
    LecturaError,
    RateLimitError,
    UnsupportedFileError,
    VideoUnavailableError,
)

_STATUS_CODES: dict[type[LecturaError], int] = {
    InvalidYouTubeURLError: 422,
    UnsupportedFileError: 415,
    VideoUnavailableError: 404,
    RateLimitError: 429,
    ConfigurationError: 500,
}


def api_error(status_code: int, message: str, hint: str | None = None) -> HTTPException:
    """Create an HTTPException with our standard error body."""
    return HTTPException(status_code=status_code, detail={"message": message, "hint": hint})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(LecturaError)
    async def handle_lectura_error(_request: Request, exc: LecturaError) -> JSONResponse:
        status = next((code for cls, code in _STATUS_CODES.items() if isinstance(exc, cls)), 400)
        return JSONResponse(
            status_code=status,
            content={"detail": {"message": exc.message, "hint": exc.hint or None, "type": type(exc).__name__}},
        )
