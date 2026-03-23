"""Tests for registration challenge solver."""

from scutl.challenge import solve_challenge, verify_solution


class TestRegistrationChallenge:
    def test_solve_and_verify(self) -> None:
        prefix = "deadbeef" * 8  # 64-char hex
        difficulty = 8  # Low difficulty for fast tests
        nonce = solve_challenge(prefix, difficulty)
        assert verify_solution(prefix, nonce, difficulty)

    def test_invalid_nonce_fails(self) -> None:
        prefix = "abcdef01" * 8
        assert not verify_solution(prefix, "definitely_wrong", 20)

    def test_nonce_is_string(self) -> None:
        prefix = "00112233" * 8
        nonce = solve_challenge(prefix, 4)
        assert isinstance(nonce, str)
