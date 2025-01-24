import pytest
from pathlib import Path

@pytest.fixture
def test_data_dir():
    return Path(__file__).parent / "fixtures"

@pytest.fixture
def flp_project_path(test_data_dir):
    return test_data_dir / "test.flp"

@pytest.fixture(autouse=True)
def setup_test_data(test_data_dir):
    test_data_dir.mkdir(exist_ok=True)
    # Create any necessary test files here
    yield
    # Cleanup if needed