"""Helper per l'envelope di risposta (errori e paginazione)."""

from typing import Any


def error_body(
    *, code: str, message: str, details: dict[str, Any] | None, request_id: str
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id,
        }
    }


def page_body(items: list[Any], *, next_cursor: str | None, limit: int) -> dict[str, Any]:
    return {"items": items, "page": {"next_cursor": next_cursor, "limit": limit}}
