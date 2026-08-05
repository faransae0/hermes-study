"""Tests for study_sm2.py's SM-2 scheduling algorithm."""

from __future__ import annotations

import pytest

from study_sm2 import compute_sm2_update


def test_first_correct_review():
    ease_factor, interval_days, repetitions = compute_sm2_update(2.5, 0, 0, 5)
    assert ease_factor == pytest.approx(2.6)
    assert interval_days == 1
    assert repetitions == 1


def test_second_correct_review():
    ease_factor, interval_days, repetitions = compute_sm2_update(2.6, 1, 1, 5)
    assert ease_factor == pytest.approx(2.7)
    assert interval_days == 6
    assert repetitions == 2


def test_third_correct_review_uses_ease_factor_multiplier():
    ease_factor, interval_days, repetitions = compute_sm2_update(2.7, 6, 2, 4)
    assert ease_factor == pytest.approx(2.7)
    assert interval_days == 16
    assert repetitions == 3


def test_failed_review_resets_repetitions_and_interval():
    ease_factor, interval_days, repetitions = compute_sm2_update(2.7, 16, 3, 2)
    assert ease_factor == pytest.approx(2.38)
    assert interval_days == 1
    assert repetitions == 0


def test_ease_factor_floor_at_1_3():
    ease_factor, interval_days, repetitions = compute_sm2_update(1.3, 10, 2, 0)
    assert ease_factor == 1.3
    assert interval_days == 1
    assert repetitions == 0
