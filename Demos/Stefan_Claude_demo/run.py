#!/usr/bin/env python3
"""
BiteRec launcher.

Lets you start the app like a normal program:

    python run.py

It simply invokes `streamlit run app.py` so you don't have to remember the
command. Works on Windows, macOS and Linux.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    app = HERE / "app.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(app)]
    print("Starting BiteRec…  (press Ctrl+C to stop)")
    try:
        return subprocess.call(cmd, cwd=str(HERE))
    except FileNotFoundError:
        print("Streamlit is not installed. Run:  pip install -r requirements.txt")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
