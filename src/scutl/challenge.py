"""Hashcash-style registration challenge solver for Scutl."""

from __future__ import annotations

import hashlib


def solve_challenge(prefix: str, difficulty: int) -> str:
    """Find a nonce such that SHA-256(prefix + nonce) has *difficulty* leading zero bits.

    Returns the nonce as a decimal string.
    """
    target = (1 << (256 - difficulty)) - 1
    nonce = 0
    prefix_bytes = prefix.encode()
    while True:
        nonce_str = str(nonce)
        digest = hashlib.sha256(prefix_bytes + nonce_str.encode()).digest()
        value = int.from_bytes(digest, "big")
        if value <= target:
            return nonce_str
        nonce += 1


def verify_solution(prefix: str, nonce: str, difficulty: int) -> bool:
    """Verify that a nonce satisfies the registration challenge requirement."""
    digest = hashlib.sha256((prefix + nonce).encode()).digest()
    value = int.from_bytes(digest, "big")
    return value <= (1 << (256 - difficulty)) - 1
