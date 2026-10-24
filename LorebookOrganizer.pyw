"""Start Lorebook Organizer without a console window: double-click this file on Windows.

Errors that would normally be printed to the console are shown in a message box
and written to error.log next to this file.
"""
import datetime
import os
import runpy
import sys
import traceback

APP = "Lorebook Organizer"
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "error.log")
MAX_BOXES = 3  # after this, errors are only written to the log (no endless message boxes)

_boxes = 0
_showing = False

# Without a console sys.stdout / sys.stderr are None and print() would fail.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _write_log(text):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"--- {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ---\n{text}\n")
        return True
    except OSError:
        return False


def _message(text):
    """Qt message box if the program is running, otherwise a plain Windows message box."""
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        if QApplication.instance() is not None:
            QMessageBox.critical(None, f"{APP} - Error", text)
            return
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, f"{APP} - Error", 0x10)
    except Exception:
        pass


def _excepthook(exc_type, exc, tb):
    global _boxes, _showing
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    saved = _write_log(text)
    if _showing or _boxes >= MAX_BOXES:
        return
    _boxes += 1
    _showing = True
    try:
        tail = text if len(text) <= 3000 else "...\n" + text[-3000:]
        where = f"\n\nSaved to:\n{LOG}" if saved else ""
        _message(f"{APP} hit an error.\n\n{tail}{where}")
    finally:
        _showing = False


sys.excepthook = _excepthook
sys.path.insert(0, HERE)

try:
    runpy.run_path(os.path.join(HERE, "main.py"), run_name="__main__")
except SystemExit:
    raise
except BaseException:
    _excepthook(*sys.exc_info())
