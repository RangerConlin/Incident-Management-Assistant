"""Smoke checks for the SARApp Server Console PyInstaller output."""

from __future__ import annotations

from pathlib import Path


EXE_PATH = Path("dist") / "SARAppServerConsole" / "SARAppServerConsole.exe"


def main() -> int:
    if not EXE_PATH.exists():
        print(f"Missing expected executable: {EXE_PATH}")
        return 1
    if not EXE_PATH.is_file():
        print(f"Expected a file but found something else: {EXE_PATH}")
        return 1
    print(f"Found SARApp Server Console executable: {EXE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
