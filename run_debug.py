"""Debug launcher — writes all errors to run_debug.log"""
import sys
import traceback
import io

# Force UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

log_path = "run_debug.log"

def log(msg):
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg)

log("=== Starting Manga Downloader ===")

try:
    log("Importing PySide6...")
    from PySide6.QtWidgets import QApplication
    log("PySide6 OK")

    log("Importing qasync...")
    import qasync
    log("qasync OK")

    import asyncio
    log("asyncio OK")

    log("Importing MainWindow...")
    from app.ui.mainWindow import MainWindow
    log("MainWindow OK")

    log("Creating QApplication...")
    app = QApplication(sys.argv)
    app.setApplicationName("Manga Downloader")
    log("QApplication OK")

    log("Creating event loop...")
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    log("Event loop OK")

    log("Creating window...")
    window = MainWindow()
    window.show()
    log("Window shown, entering event loop...")

    with loop:
        loop.run_forever()

    log("Event loop exited normally")

except Exception as e:
    tb = traceback.format_exc()
    log(f"FATAL ERROR: {e}")
    log(tb)
    sys.exit(1)
