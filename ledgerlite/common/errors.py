from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str, headers: dict | None = None):
        self.status, self.code, self.message, self.headers = status, code, message, headers


def envelope(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def install_errors(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def api_error(request: Request, exc: APIError):
        return JSONResponse(envelope(exc.code, exc.message), exc.status, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Never echo request bodies, API keys, or arbitrary user data into errors.
        issues = [{"loc": list(e["loc"]), "type": e["type"]} for e in exc.errors()]
        return JSONResponse(
            envelope("validation_error", "Invalid request", {"issues": issues}), 422
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return JSONResponse(
            envelope("http_error", str(exc.detail)), exc.status_code, headers=exc.headers
        )

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception):
        return JSONResponse(envelope("internal_error", "Internal server error"), 500)
