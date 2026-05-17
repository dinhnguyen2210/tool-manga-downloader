@echo off
:: Usage:
::   run.bat                                      - default config
::   run.bat --output-dir "D:\Manga"              - custom output folder
::   run.bat --format cbz                         - set download format (folder/cbz/pdf/epub)
::   run.bat --output-dir "D:\Manga" --format pdf - both options
call "%~dp0venv\Scripts\activate.bat"
start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0main.py" %*
