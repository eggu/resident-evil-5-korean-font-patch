#!/bin/sh
# Double-click on macOS; Linux: sh apply.sh [GAME_FOLDER]. Add --restore to undo.
cd "$(dirname "$0")" && exec python3 re5_korean_patch.py "$@"
