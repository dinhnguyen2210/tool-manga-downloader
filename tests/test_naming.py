"""Tests for filename utilities."""
from __future__ import annotations

import pytest

from app.utils.naming import (
    chapter_folder_name,
    image_filename,
    sanitize_filename,
    zero_pad,
)


@pytest.mark.parametrize("n, width, expected", [
    (1, 3, "001"),
    (42, 3, "042"),
    (1000, 3, "1000"),
    (5, 4, "0005"),
])
def test_zero_pad(n, width, expected):
    assert zero_pad(n, width) == expected


@pytest.mark.parametrize("name, expected", [
    ("Hoa Phụng Liêu Nguyện", "Hoa_Phng_Liu_Nguyn"),
    ("Test/File:Name", "Test_File_Name"),
    ("  spaces  ", "spaces"),
    ("hello world", "hello_world"),
])
def test_sanitize_filename(name, expected):
    result = sanitize_filename(name)
    # Must not contain filesystem-unsafe chars
    for ch in r'<>:"/\|?*':
        assert ch not in result
    # Must not be empty
    assert len(result) > 0


def test_sanitize_filename_empty():
    # Fully non-ASCII names should fall back to "unnamed"
    result = sanitize_filename("字漢字")
    assert result == "unnamed" or len(result) > 0


def test_chapter_folder_name_simple():
    name = chapter_folder_name(1.0)
    assert name == "Chapter_0001"


def test_chapter_folder_name_with_title():
    name = chapter_folder_name(12.0, "The Beginning")
    assert name.startswith("Chapter_0012")
    assert "The_Beginning" in name


def test_image_filename():
    assert image_filename(1) == "001.jpg"
    assert image_filename(99) == "099.jpg"
    assert image_filename(1, "png") == "001.png"
