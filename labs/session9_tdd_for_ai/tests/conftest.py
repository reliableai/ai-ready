"""
Shared test fixtures for all lessons.

This file is automatically loaded by pytest. Fixtures defined here
are available to all test files.
"""

from pathlib import Path

import pytest
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env
load_dotenv()


@pytest.fixture(scope="session")
def client():
    """Shared OpenAI client for all tests."""
    return OpenAI()


@pytest.fixture(scope="session")
def fixtures_path():
    """Path to the fixtures directory."""
    return Path(__file__).parent / "fixtures"
