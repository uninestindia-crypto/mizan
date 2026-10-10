"""A badly formed Copilot request is answered with one plain sentence about what to fix.

The rest of the app reports a schema failure with the checker's own wording ("String should match pattern ...").
A person filling in the Copilot, a second opinion or an assistant form should never see that, so these routes catch
the failure and say, in words, what to change.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine, Mapping, Sequence
from typing import Any, Final

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from quant_system.server.security import format_error_response

__all__ = ["BAD_REQUEST", "CopilotRoute", "plain_sentence"]

BAD_REQUEST: Final = "BAD_REQUEST"
_FIELD: Final[dict[str, str]] = {
    "symbol": "Use letters and numbers only for the stock symbol, for example TCS.",
    "content": "That message is too long. Please shorten it and send again.",
    "pick_note": "The note about the pick is too long. Shorten it to 300 letters or fewer.",
    "agent_id": "That assistant could not be found. Pick it again from the list.",
    "name": "Check the name: it must be plain text and not extremely long. Then save again.",
    "description": "Check the description: it must be plain text and not extremely long. Then save again.",
    "instructions": "Check the instructions: they must be plain text and not extremely long. Then save again.",
    "tools": "Check the items ticked for this assistant, then save again.",
    "steps": "Check the steps: each one must be a short piece of plain text. Then save again.",
    "body": "That could not be read. Reload the page and try again.",
    "model": "That model name is not allowed. Pick one from the list.",
    "chosen_model": "That model name is not allowed. Pick one from the list.",
    "thinking": "Pick one of the thinking levels in the list.",
    "speed": "Pick Quick, Balanced or Careful.",
    "helpers": "Pick between one and three helpers.",
}
_TOO_SHORT: Final[dict[str, str]] = {
    "messages": "Type a question first, then press Send.",
    "providers": "Pick at least one AI model for the second opinion.",
}
_TOO_LONG: Final[dict[str, str]] = {
    "messages": "This chat has become very long. Start a new chat, then ask again.",
    "providers": "Pick no more than six AI models for the second opinion.",
}
_ANYTHING_ELSE = "Something you entered is not right. Check it and try again."


def plain_sentence(errors: Sequence[Mapping[str, Any]]) -> str:
    """One sentence for the first thing wrong: the checker names the field and the kind of fault, we name the fix."""
    first = errors[0] if errors else {}
    field = next((p for p in reversed(first.get("loc", ())) if isinstance(p, str)), "")
    by_size = _TOO_LONG if "too_long" in str(first.get("type", "")) else _TOO_SHORT
    return by_size.get(field) or _FIELD.get(field) or _ANYTHING_ELSE


Handler = Callable[[Request], Coroutine[Any, Any, Response]]


def _guarded(original: Handler) -> Handler:
    async def handler(request: Request) -> Response:
        try:
            return await original(request)
        except RequestValidationError as error:
            return _bad_request(request, error)

    return handler


def _bad_request(request: Request, error: RequestValidationError) -> JSONResponse:
    body = format_error_response(
        BAD_REQUEST,
        plain_sentence(error.errors()),
        request_id=getattr(request.state, "request_id", None),
    )
    return JSONResponse(status_code=422, content=body)


class CopilotRoute(APIRoute):
    """A route that turns a request the schema refused into the plain sentence above, with HTTP 422."""

    def get_route_handler(self) -> Handler:
        return _guarded(super().get_route_handler())
