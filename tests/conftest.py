import json
from collections.abc import Callable
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def load_fixture() -> Callable[[str], dict]:
    def _load(name: str) -> dict:
        return json.loads((FIXTURES / name).read_text("utf-8"))

    return _load
