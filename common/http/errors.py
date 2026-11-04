from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def install_error_handler(app: FastAPI) -> None:
    for code, fallback in (
        (401, "Unauthorized"),
        (403, "Forbidden"),
        (404, "Resource was not found"),
        (409, "Conflict"),
    ):

        async def handler(
            request: Request, exc: Exception, *, status_code: int = code, default: str = fallback
        ) -> JSONResponse:
            del request
            message = getattr(exc, "detail", default)
            content = message if isinstance(message, dict) else {"message": str(message)}
            return JSONResponse(status_code=status_code, content=content)

        app.add_exception_handler(code, handler)
