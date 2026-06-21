import pytest

from conftest import FIXTURES_DIR
from devtime.fixtures.loader import discover_fixtures
from devtime.fixtures.runner import run_fixture


@pytest.mark.parametrize("directory", discover_fixtures(FIXTURES_DIR), ids=lambda p: p.name)
def test_fixture(directory):
    result = run_fixture(directory)
    assert result.passed, "\n".join(result.failures())
