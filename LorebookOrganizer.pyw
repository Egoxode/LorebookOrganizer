"""Start Lorebook Organizer without a console window: double-click this file on Windows.

Errors that would normally be printed to the console are shown in a message box
and written to error.log next to this file (see error_log.py; main.py does the same).
"""
import os
import runpy
import sys

APP = "Lorebook Organizer"
HERE = os.path.dirname(os.path.abspath(__file__))

# Without a console sys.stdout / sys.stderr are None and print() would fail.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

sys.path.insert(0, HERE)
import error_log  # noqa: E402

error_log.install(APP)

try:
    runpy.run_path(os.path.join(HERE, "main.py"), run_name="__main__")
except SystemExit:
    raise
except BaseException:
    error_log.report(*sys.exc_info())
