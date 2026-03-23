"""
agent/__init__.py
-----------------
Import-compatibility shim for NotiFlow Autonomous.

The old codebase used `from agent.X import Y`.
This shim re-exports from the new app.agents / app.core locations
so any code still using old import paths continues to work
without modification during the migration period.
"""

# Old: from agent.orchestrator import process_message
from app.core.orchestrator import process_message  # noqa: F401

# Old: from agent.router import route_to_skill
from app.services.router import route_to_skill     # noqa: F401

# Old: from agent.intent_agent import detect_intent  (legacy functional API)
from app.agents.intent_agent import IntentAgent    # noqa: F401

# Old: from agent.extraction_agent import extract_fields  (legacy functional API)
from app.agents.extraction_agent import ExtractionAgent  # noqa: F401
