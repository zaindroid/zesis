"""Launcher for idf.py under git-bash/MSYS on Windows.

idf.py refuses to run when MSYSTEM is set (even empty). This pops it from
os.environ, then runs idf.py. The Windows-style PATH (semicolon-separated)
is read from IDF_WIN_PATH and set as os.environ['PATH'] inside Python so the
shell (which needs colon separators) is never broken.
"""
import os
import sys

os.environ.pop("MSYSTEM", None)

win_path = os.environ.pop("IDF_WIN_PATH", None)
if win_path:
    os.environ["PATH"] = win_path

idf_py = os.path.join(os.environ["IDF_PATH"], "tools", "idf.py")
sys.argv[0] = idf_py
sys.exit(__import__("runpy").run_path(idf_py, run_name="__main__"))
