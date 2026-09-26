"""Optional Arize Phoenix tracing for every Claude Agent SDK call.

Off unless PHOENIX_COLLECTOR_ENDPOINT is set, so the pipeline and the unit
tests run unchanged without a Phoenix server. Invoked from agents/__init__.py
because the instrumentor patches claude_agent_sdk's module attributes: agent
modules bind `query` with a from-import, so it has to be patched before any of
them is imported, or they keep the unpatched function.
"""

import atexit
import os


def init_tracing() -> bool:
    if not os.environ.get("PHOENIX_COLLECTOR_ENDPOINT"):
        return False
    try:
        from openinference.instrumentation.claude_agent_sdk import ClaudeAgentSDKInstrumentor
        from phoenix.otel import register
    except ImportError:
        print("[tracing] PHOENIX_COLLECTOR_ENDPOINT set but tracing packages missing -- pip install -e .[observability]")
        return False

    tracer_provider = register(project_name=os.environ.get("PHOENIX_PROJECT_NAME", "vibe-check"))
    ClaudeAgentSDKInstrumentor().instrument(tracer_provider=tracer_provider)
    # Each agent is a short-lived process; shut down on exit so spans still
    # queued for export aren't dropped with it.
    atexit.register(tracer_provider.shutdown)
    return True
