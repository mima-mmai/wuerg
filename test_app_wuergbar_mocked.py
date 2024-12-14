import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from app_wuergback import selftest  # Replace with the actual script name

@pytest.fixture
def mock_dependencies():
    """Mock all external dependencies for the selftest function."""
    with patch("os.makedirs"), patch("os.path.join"), patch("os.path.exists", return_value=True):
        with patch("tempfile.gettempdir", return_value="/mocked/tempdir"):
            with patch("logging.info") as mock_logging_info:
                yield mock_logging_info

def test_selftest(mock_dependencies):
    """Test the selftest function in memory."""
    # Mock the return values for the test directories
    mock_test_root = "/mocked/tempdir/wuergback_test"
    mock_source_dir = os.path.join(mock_test_root, "wuergback_source")
    mock_target_dir = os.path.join(mock_test_root, "wuergback_target")

    # Mock the creation of test files
    with patch("builtins.open", MagicMock()) as mock_open:
        # Run the selftest function
        test_root, source_dir, target_dir = selftest()

        # Assertions
        assert test_root == mock_test_root
        assert source_dir == mock_source_dir
        assert target_dir == mock_target_dir

        # Verify that logging.info was called with the correct message
        mock_dependencies.assert_called_with("Testverzeichnis erstellt unter: %s", mock_test_root)

        # Verify that the test files were created
        mock_open.assert_any_call(os.path.join(mock_source_dir, "wtestdir_1", "test.txt"), "w")
        mock_open.assert_any_call(os.path.join(mock_source_dir, "wtestdir_2", "test.txt"), "w")
        mock_open.assert_any_call(os.path.join(mock_source_dir, "wtestdir_3", "test.txt"), "w")