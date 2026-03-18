"""
Automates the Edge DevTools full-page screenshot exactly as done manually:
  1. Kills any existing Edge instances
  2. Opens the latest (or specified) email HTML in a fresh Edge window
  3. Opens DevTools (F12), clicks inside the DevTools panel
  4. Opens command palette (Ctrl+Shift+P)
  5. Runs "Capture full size screenshot"
  6. Moves the download to docs/email_preview.png
  7. Crops the top 900px to docs/email_preview_cropped.png

Usage:
  py screenshot_email.py
  py screenshot_email.py docs/emails/some_email.html
"""

import ctypes
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Protocol

import pyautogui  # type: ignore[import-untyped]
import pygetwindow as gw  # type: ignore[import-untyped]
from PIL import Image

EMAILS_DIR = Path("docs/emails")
OUT_FULL = Path("docs/email_preview.png")
OUT_CROP = Path("docs/email_preview_cropped.png")
CROP_HEIGHT = 900
DOWNLOADS = Path.home() / "Downloads"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


class _Window(Protocol):
    _hWnd: int
    left: int
    width: int
    top: int
    height: int
    title: str


def latest_email() -> Path:
    files: list[Path] = sorted(EMAILS_DIR.glob("email_*.html"), key=lambda p: p.name)
    if not files:
        raise FileNotFoundError(f"No email HTML files in {EMAILS_DIR}")
    return files[-1]


def focus_and_click(win: _Window) -> None:
    hwnd: int = win._hWnd
    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)
    pyautogui.click(win.left + win.width // 2, win.top + win.height // 2)
    time.sleep(0.3)


def wait_for_download(before: set[Path], timeout: int = 20) -> Path:
    deadline: float = time.time() + timeout
    while time.time() < deadline:
        after: set[Path] = set(DOWNLOADS.glob("*.png"))
        new: set[Path] = after - before
        if new:
            f: Path = max(new, key=lambda p: p.stat().st_mtime)
            time.sleep(0.5)  # let it finish writing
            return f
        time.sleep(0.3)
    raise TimeoutError("Screenshot did not appear in Downloads")


def main() -> None:
    html: Path = (Path(sys.argv[1]) if len(sys.argv) > 1 else latest_email()).resolve()
    print(f"Source: {html.name}")

    # Snapshot Downloads before we start
    before: set[Path] = set(DOWNLOADS.glob("*.png"))

    # Kill Edge for a clean slate
    subprocess.run(["taskkill", "/f", "/im", "msedge.exe"], capture_output=True)
    time.sleep(1)

    # Open Edge with the file
    subprocess.Popen([EDGE, "--new-window", str(html)])
    time.sleep(4)

    # Focus the Edge page window
    page_wins: list[_Window] = [
        w for w in gw.getAllWindows()
        if "Job Alert" in w.title and "DevTools" not in w.title
    ]
    if not page_wins:
        raise RuntimeError("Could not find Edge window — did Edge open?")
    focus_and_click(page_wins[0])

    # Open DevTools
    print("Opening DevTools...")
    pyautogui.hotkey("f12")
    time.sleep(3)

    # Find and click inside the DevTools window
    dt_wins: list[_Window] = [w for w in gw.getAllWindows() if "DevTools" in w.title]
    if not dt_wins:
        raise RuntimeError("DevTools window did not appear")
    focus_and_click(dt_wins[0])

    # Command palette → Capture full size screenshot
    print("Running capture command...")
    pyautogui.hotkey("ctrl", "shift", "p")
    time.sleep(1)
    pyautogui.typewrite("Capture full size screenshot", interval=0.06)
    time.sleep(0.5)
    pyautogui.press("enter")
    time.sleep(3)

    # Wait for the PNG in Downloads
    print("Waiting for download...")
    downloaded: Path = wait_for_download(before)
    print(f"Downloaded: {downloaded.name}")

    # Move to docs/
    shutil.move(str(downloaded), str(OUT_FULL))
    print(f"Saved: {OUT_FULL}")

    # Crop top for README preview
    img: Image.Image = Image.open(OUT_FULL)
    print(f"Full size: {img.size}")
    img.crop((0, 0, img.width, CROP_HEIGHT)).save(str(OUT_CROP))
    print(f"Saved: {OUT_CROP}")

    # Close Edge
    subprocess.run(["taskkill", "/f", "/im", "msedge.exe"], capture_output=True)
    print("Done.")


if __name__ == "__main__":
    main()
