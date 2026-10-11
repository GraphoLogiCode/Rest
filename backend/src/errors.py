from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
        details: dict[str, str] | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers
        self.details = details


def not_found(what: str) -> ApiError:
    # Used for both "does not exist" and "belongs to someone else", so a caller
    # cannot learn whether another user's record exists.
    return ApiError(404, "not_found", f"{what} not found.")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        error = {"code": exc.code, "message": exc.message, **(exc.details or {})}
        return JSONResponse({"error": error}, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Report where and why, never the submitted value: notes are sensitive.
        fields = [
            {"field": ".".join(str(part) for part in err["loc"][1:]), "message": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(
            {"error": {"code": "validation_error", "message": "The request is not valid.", "fields": fields}},
            status_code=422,
        )
