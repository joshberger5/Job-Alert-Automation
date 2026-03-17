"""Tests for archive_email() in infrastructure.email_notifier."""
import os
from datetime import datetime
from pathlib import Path

import pytest

from infrastructure.email_notifier import archive_email


def test_creates_directory_if_missing(tmp_path: Path) -> None:
    archive_dir: str = str(tmp_path / "new_dir" / "emails")
    archive_email("<html/>", datetime(2024, 1, 15, 10, 30, 0), archive_dir=archive_dir)
    assert os.path.isdir(archive_dir)


def test_saves_file_with_correct_name_and_content(tmp_path: Path) -> None:
    archive_dir: str = str(tmp_path / "emails")
    run_at: datetime = datetime(2024, 6, 5, 9, 7, 3)
    html_content: str = "<html><body>test</body></html>"
    archive_email(html_content, run_at, archive_dir=archive_dir)

    expected_name: str = "email_20240605_090703.html"
    saved_path: Path = tmp_path / "emails" / expected_name
    assert saved_path.exists()
    assert saved_path.read_text(encoding="utf-8") == html_content


def test_trims_to_max_files_deleting_oldest(tmp_path: Path) -> None:
    archive_dir: str = str(tmp_path / "emails")
    os.makedirs(archive_dir)
    # Create 5 existing files sorted oldest → newest by name
    existing: list[str] = [
        "email_20240101_000000.html",
        "email_20240102_000000.html",
        "email_20240103_000000.html",
        "email_20240104_000000.html",
        "email_20240105_000000.html",
    ]
    for name in existing:
        Path(archive_dir, name).write_text("old", encoding="utf-8")

    # Archive a new file with max_files=5 — should drop the oldest
    run_at: datetime = datetime(2024, 1, 6, 0, 0, 0)
    archive_email("<html/>", run_at, archive_dir=archive_dir, max_files=5)

    files: list[str] = sorted(os.listdir(archive_dir))
    assert len(files) == 5
    assert "email_20240101_000000.html" not in files
    assert "email_20240106_000000.html" in files


def test_no_deletion_when_below_max_files(tmp_path: Path) -> None:
    archive_dir: str = str(tmp_path / "emails")
    os.makedirs(archive_dir)
    existing: list[str] = [
        "email_20240101_000000.html",
        "email_20240102_000000.html",
    ]
    for name in existing:
        Path(archive_dir, name).write_text("old", encoding="utf-8")

    run_at: datetime = datetime(2024, 1, 3, 0, 0, 0)
    archive_email("<html/>", run_at, archive_dir=archive_dir, max_files=5)

    files: list[str] = sorted(os.listdir(archive_dir))
    assert len(files) == 3
    for name in existing:
        assert name in files
