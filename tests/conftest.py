"""Pytest configuration and fixtures."""

import os
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Set dummy drivers for headless testing
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pytest


def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Set up test environment."""
    # Ensure we're in test mode
    os.environ.setdefault("ENV", "test")
    yield
