"""Errors of the program: written to error.log next to it and shown in a message box.

Used by main.py (python main.py, or a double-click on main.py) and by the .pyw launcher (no console),
so an error is never lost, however the program was started. The same file is in every program.
"""
import datetime
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "error.log")
MAX_BOXES = 3  # after this, errors are only written to the log (no endless message boxes)

_app = "The program"
_boxes = 0
_showing = False


def write(text, path=None):
    """Add an entry with the date to error.log. False if the file cannot be written."""
    try:
        with open(path or LOG, "a", encoding="utf-8") as f:
            f.write(f"--- {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ---\n{text}\n")
        return True
    except OSError:
        return False


def _message(text):
    """Qt message box if the program is running, otherwise a plain Windows message box."""
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        if QApplication.instance() is not None:
            QMessageBox.critical(None, f"{_app} - Error", text)
            return
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, f"{_app} - Error", 0x10)
    except Exception:
        pass


def report(exc_type, exc, tb):
    """An error nobody caught: console (if there is one), error.log, message box."""
    global _boxes, _showing
    if issubclass(exc_type, KeyboardInterrupt):  # Ctrl+C in the console is not an error
        sys.__excepthook__(exc_type, exc, tb)
        return
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    try:
        if sys.stderr is not None:
            sys.stderr.write(text)
    except Exception:
        pass
    saved = write(text)
    if _showing or _boxes >= MAX_BOXES:
        return
    _boxes += 1
    _showing = True
    try:
        tail = text if len(text) <= 3000 else "...\n" + text[-3000:]
        where = f"\n\nSaved to:\n{LOG}" if saved else ""
        _message(f"{_app} hit an error.\n\n{tail}{where}")
    finally:
        _showing = False


def install(app_name):
    """Catch every error nobody caught, including errors inside Qt event handlers."""
    global _app
    _app = app_name
    sys.excepthook = report
