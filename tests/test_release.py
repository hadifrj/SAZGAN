def test_version_file_exists():
    from pathlib import Path
    assert Path('VERSION').exists()
