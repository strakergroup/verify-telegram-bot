import pytest

from src.session.store import SessionStore
from src.verify.client import VerifyClient


@pytest.fixture
def session_store() -> SessionStore:
    """Provide a fresh in-memory session store for each test."""
    return SessionStore()


@pytest.fixture
def verify_client() -> VerifyClient:
    """Provide a VerifyClient pointed at a fake URL for testing."""
    return VerifyClient(base_url="https://test-verify.example.com")
