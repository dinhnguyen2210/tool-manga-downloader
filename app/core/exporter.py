from __future__ import annotations
import zipfile
from pathlib import Path

from app.core.models import Chapter
from app.utils.naming import zero_pad, sanitize_filename
from app.utils.logger import logger


def _collect_images(chapter_dir: Path) -> list[Path]:
    """Return all image files in chapter_dir, sorted by stem."""
    exts = {"jpg", "jpeg", "png", "webp"}
    imgs = [p for p in chapter_dir.iterdir() if p.suffix.lstrip(".").lower() in exts]
    return sorted(imgs, key=lambda p: p.stem)


def export_chapter(
    chapter_dir: Path,
    manga_out_dir: Path,
    chapter: Chapter,
    fmt: str,
) -> None:
    manga_out_dir.mkdir(parents=True, exist_ok=True)
    chap_stem = f"Chapter_{zero_pad(int(chapter.number), 4)}"

    if fmt == "cbz":
        _export_cbz(chapter_dir, manga_out_dir / f"{chap_stem}.cbz")
    elif fmt == "pdf":
        _export_pdf(chapter_dir, manga_out_dir / f"{chap_stem}.pdf")
    elif fmt == "epub":
        # EPUB is assembled per-manga after all chapters finish; skip per-chapter step
        pass
    # "folder" needs no extra work — images are already in chapter_dir


def _export_cbz(chapter_dir: Path, cbz_path: Path) -> None:
    images = _collect_images(chapter_dir)
    if not images:
        logger.warning(f"No images to pack into CBZ: {chapter_dir}")
        return

    with zipfile.ZipFile(cbz_path, "w", zipfile.ZIP_STORED) as zf:
        for img in images:
            zf.write(img, img.name)

    logger.info(f"CBZ created: {cbz_path}")


def _export_pdf(chapter_dir: Path, pdf_path: Path) -> None:
    import io
    import img2pdf
    from PIL import Image

    images = _collect_images(chapter_dir)
    if not images:
        logger.warning(f"No images for PDF: {chapter_dir}")
        return

    # img2pdf does not support WEBP → convert on the fly to temporary JPEG bytes
    img_data: list[bytes] = []
    first_size: tuple[int, int] | None = None

    for img_path in images:
        if img_path.suffix.lower() == ".webp":
            with Image.open(img_path) as im:
                if first_size is None:
                    first_size = im.size
                buf = io.BytesIO()
                im.convert("RGB").save(buf, "JPEG", quality=95)
                img_data.append(buf.getvalue())
        else:
            img_data.append(img_path.read_bytes())
            if first_size is None:
                with Image.open(img_path) as im:
                    first_size = im.size

    # Blank white page at the end — signals chapter end to the reader
    w, h = first_size if first_size else (800, 1200)
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color=(255, 255, 255)).save(buf, "JPEG", quality=85)
    img_data.append(buf.getvalue())

    with open(pdf_path, "wb") as f:
        f.write(img2pdf.convert(img_data))

    logger.info(f"PDF created: {pdf_path}")


def export_manga_epub(
    manga_dir: Path,
    manga_title: str,
    chapters: list[Chapter],
) -> Path:
    """Assemble all downloaded chapters into a single EPUB file."""
    from ebooklib import epub

    book = epub.EpubBook()
    book.set_title(manga_title)
    book.set_language("vi")
    book.set_identifier(f"mangadl-{sanitize_filename(manga_title)}")

    epub_chapters: list[epub.EpubHtml] = []

    for chapter in chapters:
        chap_dir = manga_dir / f"Chapter_{zero_pad(int(chapter.number), 4)}"
        if not chap_dir.exists():
            continue

        images = _collect_images(chap_dir)
        html_content = f"<h1>{chapter.title}</h1>\n"

        for img_path in images:
            img_bytes = img_path.read_bytes()
            img_name = f"{chap_dir.name}_{img_path.name}"
            mime = "image/jpeg" if img_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
            epub_img = epub.EpubImage(
                file_name=f"images/{img_name}",
                media_type=mime,
                content=img_bytes,
            )
            book.add_item(epub_img)
            html_content += f'<img src="images/{img_name}" style="max-width:100%"/>\n'

        epub_chap = epub.EpubHtml(
            title=chapter.title,
            file_name=f"chap_{int(chapter.number):04d}.xhtml",
            lang="vi",
        )
        epub_chap.content = html_content
        book.add_item(epub_chap)
        epub_chapters.append(epub_chap)

    if not epub_chapters:
        raise ValueError("No chapter content to pack into EPUB")

    book.toc = tuple(epub_chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"] + epub_chapters

    epub_path = manga_dir.parent / f"{sanitize_filename(manga_title)}.epub"
    epub.write_epub(str(epub_path), book)
    logger.info(f"EPUB created: {epub_path}")
    return epub_path
