"""Cancellation boundary for synchronous local tools and isolated workers."""
from contextvars import ContextVar
from functools import wraps
from inspect import signature
from threading import Event
from typing import get_type_hints

import anyio
from h5p_mcp.limits import limit

_cancel: ContextVar[Event | None] = ContextVar('h5p_job_cancel', default=None)


class JobCancelled(BaseException):
    """Control flow, never converted into a per-item validation error."""


def check_cancelled() -> None:
    event = _cancel.get()
    if event is not None and event.is_set():
        raise JobCancelled()


def cancellable(function):
    @wraps(function)
    async def invoke(*args, **kwargs):
        cancelled, started, finished = Event(), Event(), Event()
        token = _cancel.set(cancelled)
        def work():
            started.set()
            try:
                check_cancelled()
                return function(*args, **kwargs)
            finally:
                finished.set()
        try:
            # One deadline per MCP call, including thread admission and all batch
            # items; individual backend invocations must not reset the tool budget.
            with anyio.fail_after(limit('SECONDS', 300)):
                return await anyio.to_thread.run_sync(work, abandon_on_cancel=True)
        except (TimeoutError, anyio.get_cancelled_exc_class()) as error:
            cancelled.set()
            # Wait for subprocess reaping and staging cleanup before returning.
            with anyio.CancelScope(shield=True):
                if started.is_set():
                    await anyio.to_thread.run_sync(finished.wait)
            if isinstance(error, TimeoutError):
                raise RuntimeError('BACKEND_TIMEOUT: MCP tool deadline exceeded') from error
            raise
        finally:
            _cancel.reset(token)
    invoke.__signature__ = signature(function, eval_str=True)
    invoke.__annotations__ = get_type_hints(function)
    return invoke
