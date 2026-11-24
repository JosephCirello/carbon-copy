"""Every test starts with the per-address count of new visitors empty, so the many test clients (all one address)
never meet the 30-per-10-minutes limit by accident. The limit itself is tested in test_carbon_round4.py."""
import sys

import pytest


@pytest.fixture(autouse=True)
def _fresh_new_visitor_count():
    mod = sys.modules.get("app")
    if mod is not None:
        mod._NEW_BY_ADDRESS.clear()
        mod._MCP_CALLS.clear()
    yield

