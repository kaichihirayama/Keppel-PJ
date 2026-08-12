"""Tests for the PoC target REIT config loader (src/config.py)."""
from __future__ import annotations

from src.config import load_poc_targets


def test_load_poc_targets_returns_expected_shape():
    targets = load_poc_targets()

    assert 1 <= len(targets) <= 30
    for target in targets:
        assert "reit_code" in target
        assert "reit_name" in target


def test_load_poc_targets_reit_codes_are_unique():
    targets = load_poc_targets()
    codes = [t["reit_code"] for t in targets]
    assert len(codes) == len(set(codes))
