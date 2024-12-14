import os
import tempfile
import shutil
from app_wuergback import selftest

def test_selftest():
    test_root, source_dir, target_dir = selftest()

    # Verify that the test directories are created
    assert os.path.exists(test_root)
    assert os.path.exists(source_dir)
    assert os.path.exists(target_dir)

    # Check if the test files are created correctly
    for i in range(1, 4):
        subdir = os.path.join(source_dir, f"wtestdir_{i}")
        assert os.path.exists(subdir)
        test_file = os.path.join(subdir, "test.txt")
        assert os.path.exists(test_file)
        with open(test_file, "r") as file:
            content = file.read()
            assert content == "hello from wuergback"

    # Clean up the test directories after the test
    shutil.rmtree(test_root)