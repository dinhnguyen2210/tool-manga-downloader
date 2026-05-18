<div align="center">

# 📚 Manga Downloader

**Tool desktop tải truyện tranh từ các trang web tiếng Việt về máy đọc offline**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/GUI-PySide6-41CD52?logo=qt&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Status](https://img.shields.io/badge/Status-Active-success)

[Tính năng](#-tính-năng) • [Cài đặt](#-cài-đặt) • [Sử dụng](#-sử-dụng) • [Plugin mới](#-viết-plugin-cho-site-mới) • [Build .exe](#-build-thành-file-exe)

</div>

---

> [!CAUTION]
> ## Bản quyền & Trách nhiệm pháp lý
>
> **Truyện tranh là tác phẩm sáng tạo được bảo hộ bản quyền.** Tác giả và nhà xuất bản đã đầu tư thời gian, công sức để tạo ra những tác phẩm này — việc tải và phân phối trái phép gây thiệt hại trực tiếp đến thu nhập của họ.
>
> Tool này chỉ được phép dùng để:
> - ✅ **Đọc offline cá nhân** — tải về máy của chính mình để đọc khi không có mạng
> - ✅ **Học tập kỹ thuật** — nghiên cứu cách hoạt động của web scraping, async Python, Qt GUI
>
> Tuyệt đối **không** được phép:
> - ❌ **Phân phối lại** nội dung đã tải — upload lên drive, telegram, web, forum
> - ❌ **Sử dụng thương mại** — bán, kiếm tiền từ nội dung có bản quyền dưới bất kỳ hình thức nào
> - ❌ **Tấn công server** — bắn request liên tục, bỏ qua rate limit, làm gián đoạn dịch vụ
> - ❌ **Bypass paywall** — tải nội dung yêu cầu trả phí mà không trả
>
> **Hãy ủng hộ tác giả** bằng cách đọc trên site chính thức, mua bản in, hoặc ủng hộ qua các kênh chính thống nếu có.
>
> *Người dùng hoàn toàn tự chịu trách nhiệm pháp lý về mọi hành vi sử dụng tool này. Tác giả tool không chịu trách nhiệm cho bất kỳ hành vi vi phạm bản quyền nào.*

---

## ✨ Tính năng

- 🎨 **GUI thân thiện** xây dựng bằng PySide6 (Qt6)
- 🌐 **Multi-site support** qua kiến trúc plugin, dễ dàng mở rộng
- ⚡ **Async download** với `aiohttp`, tải đồng thời nhiều ảnh
- 🔒 **Anti-bot bypass** đầy đủ: User-Agent rotation, Referer, Cloudflare bypass
- 📋 **Đúng thứ tự** đảm bảo chapter và ảnh sắp xếp chính xác
- 📦 **Multi-format export**: Folder ảnh / CBZ / PDF / EPUB
- 🔄 **Resume download** tự skip ảnh đã tải, retry tự động khi lỗi
- 🎯 **Range selection** chọn từ chapter X đến Y, cherry-pick, hoặc **↓ New** tự động chọn chapter chưa tải
- 🔢 **Decimal chapter support** chapter dạng 12.5 được lưu đúng (`Chapter_0012_5`), không bị trùng hay bỏ qua
- 🔍 **URL history** gợi ý các URL đã fetch, hiện ngay khi click vào ô nhập
- 🌙 **Progress tracking** real-time với progress bar tổng và phụ
- 📝 **Logging** chi tiết, dễ debug
- 🚫 **Cancel anytime** dừng tải bất cứ lúc nào không corrupt file

---

## 🌐 Site được hỗ trợ

| Site | Status | Plugin |
|------|--------|--------|
| ![truyenqqko](https://img.shields.io/badge/-truyenqqko.com-success) | ✅ Hoạt động | `app/sites/truyenqqko.py` |
| ![read-haikyuu](https://img.shields.io/badge/-read--haikyuu.com-success) | ✅ Hoạt động | `app/sites/haikyuu.py` |
| ![readhaikyu](https://img.shields.io/badge/-readhaikyu.online-success) | ✅ Hoạt động | `app/sites/haikyuu.py` |
| ![nettruyen](https://img.shields.io/badge/-nettruyen-lightgrey) | 🚧 Coming soon | - |
| ![blogtruyen](https://img.shields.io/badge/-blogtruyen-lightgrey) | 🚧 Coming soon | - |

> Muốn thêm site khác? Xem [Viết plugin cho site mới](#-viết-plugin-cho-site-mới)

---

## 📸 Screenshot

```
┌──────────────────────────────────────────────────────────────┐
│  📚 Manga Downloader                                 _ □ ✕  │
├──────────────────────────────────────────────────────────────┤
│  URL: [https://truyenqqko.com/truyen-tranh/... ] [🔍 Fetch] │
├──────────────────────────────────────────────────────────────┤
│ Manga Info                                                   │
│  ┌────────┐  Hỏa Phụng Liêu Nguyên                          │
│  │        │  ✍️  Trần Mưu                                   │
│  │ COVER  │  📑 601 chapters                                 │
│  │        │  🌐 truyenqqko                                   │
│  └────────┘  🔗 https://truyenqqko.com/truyen-tranh/...     │
│              Câu chuyện về Phụng Cầu Hoàng, một thiếu       │
│              niên với khát vọng trở thành cao thủ võ lâm…   │
├──────────────────────────────────────────────────────────────┤
│ Chapters                                                     │
│  [✓ All] [✗ None] [↓ New]  Range: [  1] to [601] [Apply]  598 / 601 selected  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ ☑ Chapter 1 - Khởi đầu             ⚠ ON DISK  ✅   │   │
│  │ ☑ Chapter 2 - ...                  ⚠ ON DISK  ✅   │   │
│  │ ☑ Chapter 3 - ...                               ⌛   │   │
│  │ ☑ Chapter 4 - ...                              ⏳   │   │
│  └──────────────────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────────────┤
│  Format: [CBZ ▼]  Output: [./output/manga  ] [📁] [⬇️] [⏹] [⚙️] │
│  CBZ: comic archive  •  PDF: single file  •  EPUB: e-book   │
├──────────────────────────────────────────────────────────────┤
│  Total:    ████████████░░░░░░  2/4 chapters                 │
│  Chapter:  ██████████░░░░░░░░  14/20 images                 │
├──────────────────────────────────────────────────────────────┤
│  [09:42:15] Fetched 601 chapters: Hỏa Phụng Liêu Nguyên    │
│  [09:42:16] Saved manga info → output/manga/Hoa.../...json  │
│  [09:42:18] Downloading Chapter 3 (3/4)...                  │
│  [09:42:35] ✓ Chapter 3 done                                │
└──────────────────────────────────────────────────────────────┘
```

---

## 📦 Cài đặt

### Yêu cầu hệ thống

- **Python**: 3.10 trở lên
- **OS**: Windows 10+, macOS 11+, Linux (Ubuntu 20.04+)
- **RAM**: 512 MB trở lên
- **Disk**: ~200 MB cho dependencies + dung lượng truyện

### Bước 1: Clone repository

```bash
git clone https://github.com/dinhnguyen2210/tool-manga-downloader.git
cd tool-manga-downloader
```

### Bước 2: Tạo virtual environment

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
</details>

<details>
<summary><b>macOS / Linux</b></summary>

```bash
python3 -m venv venv
source venv/bin/activate
```
</details>

### Bước 3: Cài dependencies

```bash
pip install -r requirements.txt
```

Với development (có testing tools):
```bash
pip install -r requirements-dev.txt
```

### Bước 4: Verify cài đặt

```bash
python -c "import PySide6; print('PySide6:', PySide6.__version__)"
python -c "import aiohttp; print('aiohttp:', aiohttp.__version__)"
```

---

## 🚀 Sử dụng

### Chạy ứng dụng

**Windows** (double-click hoặc gõ trong CMD):
```bat
run.bat
```

**Bash / Git Bash**:
```bash
bash run.sh
```

**Với tùy chọn** (override config):
```bat
run.bat --output-dir "D:\Manga" --format pdf
```

**Chạy trực tiếp** (có console window):
```bash
python main.py
```

### Workflow cơ bản

1. **Copy URL truyện** từ trình duyệt (ví dụ: `https://truyenqqko.com/truyen-tranh/...`)
2. **Paste vào ô URL** trong app, bấm **Fetch**
3. **Chờ load** danh sách chapter (~2-5s)
4. **Chọn chapter** muốn tải:
   - `✓ All` → tải tất cả
   - `↓ New` → tự động chọn những chapter chưa có trong folder (tiện để tải tiếp)
   - `Range` → nhập từ chapter X đến Y, bấm Apply
   - Hoặc tick từng chapter trong bảng
   - Số chapter đã chọn hiển thị ở góc phải toolbar (`X / Y selected`)
5. **Chọn format export**: Folder / CBZ / PDF / EPUB
6. **Chọn thư mục lưu** (mặc định `output/manga/` trong thư mục app)
7. Bấm **Download** và chờ ☕

### Hotkey

| Phím tắt | Chức năng |
|----------|-----------|
| `Ctrl + V` | Paste URL vào ô input |
| `Enter` | Fetch chapter list |
| `Ctrl + A` | Select all chapter |
| `Ctrl + D` | Bắt đầu download |
| `Esc` | Cancel download đang chạy |
| `Ctrl + ,` | Mở Settings |

---

## ⚙️ Cấu hình

### Settings dialog (`Ctrl + ,`)

| Setting | Default | Khoảng | Mô tả |
|---------|---------|--------|-------|
| Concurrent downloads | 5 | 1-10 | Số ảnh tải đồng thời |
| Delay between requests | 1.5s | 0.0-5.0 | Độ trễ giữa request (tránh ban IP) |
| Retry count | 3 | 0-5 | Số lần thử lại khi lỗi |
| Custom User-Agent | - | - | UA tùy chỉnh (để trống = auto rotate) |
| Proxy | - | - | `http://user:pass@host:port` |

### File config

Settings được lưu tại:
- **Windows**: `%USERPROFILE%\.mangadl\config.json`
- **macOS/Linux**: `~/.mangadl/config.json`

Ví dụ `config.json`:
```json
{
  "concurrent_downloads": 5,
  "delay_seconds": 1.5,
  "retry_count": 3,
  "output_format": "cbz",
  "default_output_dir": "./output/manga",
  "user_agent": null,
  "proxy": null,
  "theme": "dark"
}
```

---

## 📁 Cấu trúc output

Tải về sẽ được tổ chức theo cấu trúc `[output]/[tên truyện]/[format]/`:

```
output/manga/
└── Hoa_Phung_Lieu_Nguyen/
    ├── folder/
    │   ├── Chapter_0001/          # Ảnh gốc giữ nguyên
    │   │   ├── 001.jpg
    │   │   ├── 002.jpg
    │   │   └── ...
    │   └── Chapter_0002/
    ├── cbz/
    │   ├── Chapter_0001/          # Ảnh tạm (xóa sau khi export)
    │   └── Chapter_0001.cbz       # File CBZ đóng gói
    ├── pdf/
    │   └── Chapter_0001.pdf
    └── epub/
        └── Chapter_0001.epub
```

---

## 🔌 Viết plugin cho site mới

### Bước 1: Tạo file plugin

Tạo `app/sites/your_site.py`:

```python
from app.sites.base import BaseSite
from app.core.models import Manga, Chapter
import re

class YourSite(BaseSite):
    name = "yoursite"
    base_url = "https://yoursite.com"
    
    @classmethod
    def matches(cls, url: str) -> bool:
        return "yoursite.com" in url
    
    async def parse_manga_info(self, url: str) -> Manga:
        # Fetch HTML, parse bằng BeautifulSoup
        # Return Manga với chapters đã sort
        ...
    
    async def parse_chapter_images(self, chapter_url: str) -> list[str]:
        # Return list URL ảnh theo thứ tự DOM
        ...
    
    def get_image_headers(self, image_url: str) -> dict[str, str]:
        return {
            "Referer": self.base_url,
            "User-Agent": "...",
        }
```

### Bước 2: Đăng ký plugin

Thêm vào `app/sites/registry.py`:

```python
from app.sites.your_site import YourSite

SITES = [
    TruyenQQKo,
    YourSite,  # ← thêm dòng này
]
```

### Bước 3: Viết test

Tạo `tests/test_parser_your_site.py`:

```python
import pytest
from app.sites.your_site import YourSite

def test_matches_url():
    assert YourSite.matches("https://yoursite.com/abc")
    assert not YourSite.matches("https://other.com/xyz")

@pytest.mark.asyncio
async def test_parse_manga_info(html_fixture):
    site = YourSite()
    manga = await site.parse_manga_info("...")
    assert manga.title == "Expected Title"
    assert len(manga.chapters) > 0
```

### Bước 4: Test với HTML thật

```bash
# Save HTML thật về fixtures
curl -A "Mozilla/5.0..." https://yoursite.com/truyen/abc > tests/fixtures/your_site_manga.html

# Chạy test
pytest tests/test_parser_your_site.py -v
```

> 💡 **Tip**: Mở DevTools (F12) trên browser, tab Elements để xem đúng CSS selector trước khi viết parser.

---

## 🔨 Build thành file .exe

### Windows

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "MangaDownloader" --icon=assets/icon.ico main.py
```

File `.exe` sẽ ở `dist/MangaDownloader.exe`.

### macOS

```bash
pyinstaller --onefile --windowed --name "MangaDownloader" --icon=assets/icon.icns main.py
```

File `.app` sẽ ở `dist/MangaDownloader.app`.

### Linux

```bash
pyinstaller --onefile --name "manga-downloader" main.py
```

Binary sẽ ở `dist/manga-downloader`.

### Tối ưu kích thước

```bash
# Loại bỏ module không cần
pyinstaller --onefile --windowed \
  --exclude-module=tkinter \
  --exclude-module=matplotlib \
  --exclude-module=numpy \
  --upx-dir=/path/to/upx \
  main.py
```

---

## 🧪 Testing

### Chạy toàn bộ test

```bash
pytest
```

### Với coverage report

```bash
pytest --cov=app --cov-report=html
# Mở htmlcov/index.html để xem report
```

### Chỉ test parser (không hit network)

```bash
pytest tests/test_parser_*.py -v
```

### Lint & format

```bash
# Format code
black app/ tests/

# Lint
ruff check app/ tests/

# Type check
mypy app/
```

---

## 🐛 Troubleshooting

### Lỗi: `HTTP 403 Forbidden` khi tải ảnh

**Nguyên nhân**: Site chống hotlink, thiếu Referer header.

**Fix**: Kiểm tra method `get_image_headers()` trong plugin có set đúng Referer chưa.

---

### Lỗi: `Cloudflare challenge` khi fetch trang

**Nguyên nhân**: Cloudflare bảo vệ DDoS, requests thường không vượt qua được.

**Fix**: Tool sẽ tự fallback sang `cloudscraper`. Nếu vẫn fail:
```bash
pip install --upgrade cloudscraper
```
Hoặc đợi 5-10 phút rồi thử lại (Cloudflare có thể đang ban IP).

---

### Lỗi: `ssl.SSLCertVerificationError`

**Nguyên nhân**: Hệ thống thiếu CA certificates (thường gặp trên macOS).

**Fix macOS**:
```bash
/Applications/Python\ 3.10/Install\ Certificates.command
```

---

### Lỗi: UI bị treo khi đang download

**Nguyên nhân**: Async event loop không integrate đúng với Qt.

**Fix**: Đảm bảo dùng `qasync.QEventLoop`, không dùng `asyncio.run()` trong UI thread.

---

### Tải xong nhưng ảnh hiển thị lộn xộn trong reader

**Nguyên nhân**: Filename không zero-padded → reader sort theo string.

**Fix**: Filename phải là `001.jpg`, `002.jpg`, không phải `1.jpg`, `2.jpg`. Đảm bảo `utils/naming.py` hoạt động đúng.

---

### Bị ban IP, không fetch được nữa

**Cách xử lý**:
1. Tăng `delay_seconds` lên 3-5s
2. Giảm `concurrent_downloads` xuống 2-3
3. Dùng proxy
4. Đổi mạng (4G ↔ WiFi) → IP mới
5. Đợi 24h IP cũ unban

---

## 📚 Tech Stack

| Component | Library | Version | Mục đích |
|-----------|---------|---------|----------|
| GUI Framework | PySide6 | 6.6+ | Cross-platform Qt6 binding |
| Async HTTP | aiohttp | 3.9+ | Concurrent download |
| Sync HTTP | requests | 2.31+ | Quick fetch + Cloudscraper |
| Cloudflare bypass | cloudscraper | 1.2.71+ | Fallback khi gặp 403/503 |
| HTML Parse | beautifulsoup4 | 4.12+ | DOM parsing |
| HTML Parser | lxml | 5.0+ | Fast C parser cho BS4 |
| Image | Pillow | 10.0+ | Validate, convert ảnh |
| PDF Export | Pillow | 10.0+ | Native multi-page PDF (`save_all`) — không giới hạn kích thước trang |
| EPUB Export | ebooklib | 0.18+ | Generate EPUB3 |
| Async + Qt | qasync | 0.27+ | Bridge asyncio ↔ Qt |
| Testing | pytest | 8.0+ | Test framework |
| Mock HTTP | aioresponses | 0.7+ | Mock aiohttp trong test |

---

## 🗺️ Roadmap

- [x] Plugin truyenqqko.com
- [x] Export CBZ, PDF, EPUB
- [x] Async download với concurrency control
- [x] Resume capability
- [ ] Plugin nettruyen, blogtruyen, hentaivn
- [ ] Dark mode toggle
- [ ] Đa ngôn ngữ (i18n: VI + EN)
- [ ] Auto-update checker
- [ ] System tray icon
- [ ] Search truyện trong app (không cần copy URL)
- [ ] Schedule download (tải vào giờ định trước)
- [ ] Library mode (quản lý truyện đã tải)
- [ ] Sync với Calibre

---

## 🤝 Contributing

Đóng góp luôn được hoan nghênh! Vui lòng:

1. Fork repository
2. Tạo branch: `git checkout -b feature/AmazingFeature`
3. Commit thay đổi: `git commit -m 'feat: add AmazingFeature'`
4. Push branch: `git push origin feature/AmazingFeature`
5. Mở Pull Request

### Conventions

- **Commit message**: theo [Conventional Commits](https://www.conventionalcommits.org/)
  - `feat:` tính năng mới
  - `fix:` sửa lỗi
  - `docs:` cập nhật docs
  - `refactor:` refactor code
  - `test:` thêm/sửa test
- **Code style**: chạy `black` + `ruff` trước khi commit
- **Type hints**: bắt buộc cho mọi public function
- **Test**: coverage mới phải ≥ 70% cho code mới

---

## 📜 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

```
Copyright (c) 2026 <Your Name>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software")...
```

---

## 🙏 Acknowledgements

- [PySide6](https://www.qt.io/qt-for-python) - Qt for Python
- [aiohttp](https://docs.aiohttp.org/) - Async HTTP client/server
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - HTML parsing
- [Pillow](https://python-pillow.org/) - Image processing & PDF export
- Các tác giả truyện tranh - cảm ơn vì đã sáng tác những tác phẩm tuyệt vời ❤️

---

<div align="center">

**⭐ Nếu tool hữu ích, hãy cho 1 star nhé! ⭐**

Made with ❤️ for manga lovers in Vietnam 🇻🇳

</div>