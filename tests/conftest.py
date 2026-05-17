"""Shared pytest fixtures."""
from __future__ import annotations
from pathlib import Path
import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def sample_manga_html() -> str:
    """Minimal HTML that mimics a truyenqqko manga page."""
    return """
    <html><body>
      <h1 class="title-detail">Hoa Phụng Liêu Nguyện</h1>
      <div class="col-image">
        <img src="https://cdn.example.com/cover.jpg" />
      </div>
      <ul class="list-info">
        <li>
          <p class="name">Tác giả</p>
          <p><a href="/author/xyz">Tác Giả Nào Đó</a></p>
        </li>
      </ul>
      <div id="list-chapter">
        <ul>
          <li class="row"><div class="chapter"><a href="/truyen/hoa-phung/chapter-2/">Chapter 2</a></div></li>
          <li class="row"><div class="chapter"><a href="/truyen/hoa-phung/chapter-1/">Chapter 1</a></div></li>
        </ul>
      </div>
    </body></html>
    """


@pytest.fixture
def sample_chapter_html() -> str:
    """Minimal HTML that mimics a truyenqqko chapter reading page."""
    return """
    <html><body>
      <div class="page-chapter">
        <img src="https://cdn.example.com/img/001.jpg" />
        <img data-src="https://cdn.example.com/img/002.jpg" />
        <img src="https://cdn.example.com/img/003.jpg" />
      </div>
    </body></html>
    """
