"""
Shared test configuration.

Several suites here drive the live API rather than a stub. They need a real key
and a reachable host, so without credentials they are skipped: an unreachable
host is a missing environment, not a failing SDK.
"""
import os

import pytest

PLACEHOLDER_KEY = 'scp-live-YOUR_API_KEY_HERE'


def live_api_credentials_available() -> bool:
    key = os.environ.get('SCRAPFLY_KEY')

    return bool(key) and key != PLACEHOLDER_KEY


def pytest_collection_modifyitems(config, items):
    if live_api_credentials_available():
        return

    skip = pytest.mark.skip(reason='live API test: set SCRAPFLY_KEY (and SCRAPFLY_API_HOST) to run')

    for item in items:
        if 'integration' in item.keywords:
            item.add_marker(skip)
