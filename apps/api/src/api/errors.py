"""AppError hierarchy and the handlers that turn every error into one envelope."""

from typing import Any, ClassVar, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class AppError(Exception):
    status: ClassVar[int] = 400
    code: ClassVar[str] = "bad_request"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class Unauthorized(AppError):
    status = 401
    code = "unauthorized"


class QuotaExceeded(AppError):
    status = 402
    code = "quota_exceeded"


class PlanRequired(AppError):
    """The chosen AI model needs the Pro plan."""

    status = 402
    code = "plan_required"


class Forbidden(AppError):
    status = 403
    code = "forbidden"


class NotFound(AppError):
    status = 404
    code = "not_found"


class Conflict(AppError):
    status = 409
    code = "conflict"


class ValidationFailed(AppError):
    status = 422
    code = "validation_failed"


class RenderFailed(AppError):
    """Typst could not compile the CV; `details["diagnostics"]` lists line, column and message."""

    status = 422
    code = "render_failed"


class ProviderError(AppError):
    status = 502
    code = "provider_error"


class ServiceUnavailable(AppError):
    status = 503
    code = "service_unavailable"


class ProviderTimeout(AppError):
    status = 504
    code = "provider_timeout"


# Documented on every route so generated clients know the error shape.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope, "description": "Not signed in"},
    404: {"model": ErrorEnvelope, "description": "Not found"},
    422: {"model": ErrorEnvelope, "description": "Invalid request"},
}

# Routes that call an AI provider can also fail upstream.
AI_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    **ERROR_RESPONSES,
    502: {"model": ErrorEnvelope, "description": "The AI provider failed"},
    504: {"model": ErrorEnvelope, "description": "The AI provider took too long"},
}

_HTTP_CODES = {404: "not_found", 405: "method_not_allowed"}


def _envelope(status: int, code: str, message: str, details: dict[str, Any]) -> JSONResponse:
    body = ErrorEnvelope(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(body.model_dump(), status_code=status)


async def _app_error(_: Request, exc: Exception) -> JSONResponse:
    error = cast(AppError, exc)
    return _envelope(error.status, error.code, error.message, error.details)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    # Field locations and messages only: never echo the submitted values.
    raw = cast(RequestValidationError, exc).errors()
    errors = [{"loc": list(e["loc"]), "message": e["msg"]} for e in raw]
    first = errors[0] if errors else None
    message = (
        f"Check {'.'.join(str(part) for part in first['loc'][1:])}: {first['message']}"
        if first
        else "The request is not valid."
    )
    return _envelope(422, ValidationFailed.code, message, {"errors": errors})


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    error = cast(HTTPException, exc)
    code = _HTTP_CODES.get(error.status_code, "http_error")
    return _envelope(error.status_code, code, str(error.detail), {})


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(HTTPException, _http_error)
