"""Exception handler → envelope errore standard (§5.2 architettura)."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from whisper.shared.core.errors import DomainError
from whisper.shared.core.ids import uuid7
from whisper.shared.infrastructure.http.responses import error_body

logger = logging.getLogger("whisper")


def _request_id(request: Request) -> str:
    existing = getattr(request.state, "request_id", None)
    return existing if existing else str(uuid7())


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=error_body(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                request_id=_request_id(request),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_body(
                code="error.unprocessable",
                message="Payload non valido.",
                details={"errors": exc.errors()},
                request_id=_request_id(request),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(
                code=f"http.{exc.status_code}",
                message=str(exc.detail),
                details=None,
                request_id=_request_id(request),
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Errore non gestito", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=error_body(
                code="error.internal",
                message="Errore interno del server.",
                details=None,
                request_id=_request_id(request),
            ),
        )
