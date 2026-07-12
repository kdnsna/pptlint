from __future__ import annotations

from tools.check_public_proof import main


def test_public_proof_is_generated_by_current_version() -> None:
    assert main() == 0
