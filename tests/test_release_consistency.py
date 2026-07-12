from __future__ import annotations

from tools.check_release_consistency import main


def test_release_metadata_is_consistent() -> None:
    assert main() == 0
