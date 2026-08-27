"""Running one ADK agent to completion, the same way every time.

WHY THIS IS SHARED
------------------
`migragent/researcher.py` worked out three things the hard way, and every agent
after it needs the same three:

  - ADK is asynchronous and the code that calls it is not, so someone has to
    start an event loop. It goes on its own thread, because the caller may
    already hold one: Playwright's sync API runs a loop, and starting a second
    in the same thread raises before a page is read. That arrived once as
    "coroutine was never awaited", which says nothing about loops.

  - A turn is a turn of the model, not an event. ADK emits an event for a tool
    call and another for its result, so counting events counts about three to
    one and stops a run early while reporting the cap as though something broke.

  - Abandoning an ADK event stream mid flight leaves OpenTelemetry unwinding a
    span in a context it was not opened in, and it prints a traceback for a stop
    that was chosen. The stream is closed from inside the coroutine that opened
    it.

None of that is specific to the researcher, so it lives here and the agents that
follow call `run_to_completion` instead of copying it.

WHAT THIS DOES NOT DO
--------------------
It does not hold the rules. Those live in each agent's tools, the same as they
do for the researcher. This module only turns the ADK handle and counts turns.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

# A backstop against a loop, not a working limit. An agent that keeps going is
# stopped by the code it runs in, never by being asked nicely in the prompt.
DEFAULT_MAX_TURNS = 120


@dataclass
class Outcome:
    """How a run ended. The agent's findings live on its own desk, not here."""

    turns: int = 0
    stopped_because: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


def build_llm(*, project: str, model: str, location: str, credentials) -> Any:
    """The BaseLlm ADK drives, wired to migragent/model.py and its one retry loop.

    Imported here rather than at module load so a test can run the surrounding
    code without google-adk installed.
    """
    from ..agent_llm import MigragentLlm

    return MigragentLlm(model=model, project=project, location=location,
                        credentials=credentials)


def run_to_completion(
    *,
    agent: Any,
    message: str,
    max_turns: int = DEFAULT_MAX_TURNS,
    on_turn: Callable[[int], None] | None = None,
    stop_when: Callable[[], bool] | None = None,
    app_name: str = "migragent",
    user_id: str = "migragent",
) -> Outcome:
    """Run one ADK agent from one message until it stops, and count its turns.

    Args:
        agent: an ADK agent, already built with its tools bound to its desk.
        message: the opening user message.
        max_turns: the loop stops the run at this many model turns, whatever the
            agent intends. The agent may be told the number so it can plan, but
            the number holds either way.
        on_turn: called with the running turn count after each model turn, for a
            progress line.
        stop_when: checked after each model turn. Returning True ends the run.
            This is how an agent that has called its own `finish` tool gets the
            loop to stop: the tool sets a flag, this reads it.

    Returns:
        An Outcome. A run that raised keeps the turns it had taken and carries
        the error; whatever the agent recorded before the failure is on its desk
        and is the caller's to keep or discard.
    """
    import asyncio
    import threading

    outcome = Outcome()
    failure: list[BaseException] = []

    def loop() -> None:
        try:
            asyncio.run(_drive(agent, message, max_turns, on_turn, stop_when,
                               outcome, app_name, user_id))
        except BaseException as exc:  # noqa: BLE001
            failure.append(exc)

    thread = threading.Thread(target=loop, name="agent", daemon=True)
    thread.start()
    thread.join()

    if failure:
        exc = failure[0]
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise exc
        outcome.error = f"{type(exc).__name__}: {exc}"[:300]

    if not outcome.stopped_because and not outcome.error:
        outcome.stopped_because = "the agent stopped without saying why"
    return outcome


async def _drive(agent, message, max_turns, on_turn, stop_when, outcome,
                 app_name, user_id) -> None:
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    runner = InMemoryRunner(agent=agent, app_name=app_name)
    session = await runner.session_service.create_session(
        app_name=app_name, user_id=user_id)

    events = runner.run_async(
        user_id=user_id, session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=message)]),
    )

    try:
        while True:
            try:
                event = await events.__anext__()
            except StopAsyncIteration:
                break

            content = getattr(event, "content", None)
            if content is not None and getattr(content, "role", None) == "model":
                outcome.turns += 1
                if on_turn is not None:
                    on_turn(outcome.turns)

            if stop_when is not None and stop_when():
                break
            if outcome.turns >= max_turns:
                outcome.stopped_because = f"the turn limit of {max_turns} was reached"
                break
    finally:
        await events.aclose()


def function_tools(functions: Sequence[Callable]) -> list:
    """Wrap desk methods as ADK FunctionTools.

    A thin helper so an agent builder reads as a list of the methods it exposes
    rather than as FunctionTool noise. Imported lazily for the same reason as
    build_llm.
    """
    from google.adk.tools import FunctionTool

    return [FunctionTool(fn) for fn in functions]
