"""Tests that study-desktop's new lazy-installable deps are registered correctly."""

from tools.lazy_deps import LAZY_DEPS


def test_study_pdf_registered():
    assert "study.pdf" in LAZY_DEPS
    specs = LAZY_DEPS["study.pdf"]
    assert any(spec.startswith("pdfplumber==") for spec in specs)


def test_study_youtube_registered():
    assert "study.youtube" in LAZY_DEPS
    specs = LAZY_DEPS["study.youtube"]
    assert any(spec.startswith("yt-dlp==") for spec in specs)
