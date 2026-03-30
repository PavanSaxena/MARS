"""Compatibility wrapper for the legacy test entrypoint.

Preferred command: pytest tests -v
Legacy command still supported: pytest tests/tests.py -v
"""

from tests.test_agents import *  # noqa: F401,F403
from tests.test_api import *  # noqa: F401,F403
from tests.test_reasoning import *  # noqa: F401,F403
from tests.test_services import *  # noqa: F401,F403
