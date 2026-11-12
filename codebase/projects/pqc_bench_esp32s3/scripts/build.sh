#!/usr/bin/env bash
# Build wrapper for the ESP32-S3 project under git-bash/MSYS.
#
# idf.py refuses to run when MSYSTEM is set, and exporting a Windows-style
# PATH to bash breaks the shell. Solution:
#   - Build the Windows PATH as IDF_WIN_PATH (kept out of the shell PATH).
#   - Run idf.py through scripts/idf_launcher.py which pops MSYSTEM and sets
#     os.environ['PATH'] = IDF_WIN_PATH inside Python.
#
# Usage:  bash build.sh [idf.py args...]   (default: build)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
IDF_PATH="${IDF_PATH:-C:/Users/zain_/esp/esp-idf}"
IDF_TOOLS_PATH="${IDF_TOOLS_PATH:-C:/Users/zain_/.espressif}"
PYENV_ROOT="${IDF_TOOLS_PATH}/python_env/idf5.4_py3.13_env"
PYENV="${PYENV_ROOT}/Scripts"
PYTHON="${PYENV}/python.exe"
XTENSA="${IDF_TOOLS_PATH}/tools/xtensa-esp-elf/esp-14.2.0_20241119/xtensa-esp-elf/bin"
CMAKE_BIN="${IDF_TOOLS_PATH}/tools/cmake/3.30.2/bin"
NINJA_BIN="${IDF_TOOLS_PATH}/tools/ninja/1.12.1"
IDFEXE_BIN="${IDF_TOOLS_PATH}/tools/idf-exe/1.0.3"

# Windows-style PATH (semicolon-separated), delivered via IDF_WIN_PATH so the
# bash shell PATH (colon-separated) stays intact.
winpath_entry() { cygpath -w "$1"; }
WIN_PATH="$(winpath_entry "$PYENV");$(winpath_entry "$XTENSA");$(winpath_entry "$CMAKE_BIN");$(winpath_entry "$NINJA_BIN");$(winpath_entry "$IDFEXE_BIN")"
IFS=':' read -ra ENTRIES <<< "$PATH"
for p in "${ENTRIES[@]}"; do
  [ -z "$p" ] && continue
  WIN_PATH="$WIN_PATH;$(winpath_entry "$p")"
done

cd "$PROJECT_DIR"
export IDF_PATH IDF_TOOLS_PATH
export IDF_PYTHON_ENV_PATH="$PYENV_ROOT"
export PYTHONPATH="$(winpath_entry "$IDF_PATH/tools")"
export IDF_WIN_PATH="$WIN_PATH"

"$PYTHON" "$SCRIPT_DIR/idf_launcher.py" "$@"
