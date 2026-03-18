"""
Takes a screenshot of the most recent (or specified) email HTML and writes:
  docs/email_preview.png         — full page
  docs/email_preview_cropped.png — top 900px (header + first few jobs)

Usage:
  py screenshot_email.py                          # uses most recent email
  py screenshot_email.py docs/emails/foo.html    # uses specified file
"""

import asyncio
import os
import sys
from pathlib import Path

from PIL import Image
from playwright.async_api import async_playwright


EMAILS_DIR = Path("docs/emails")
OUT_FULL = Path("docs/email_preview.png")
OUT_CROP = Path("docs/email_preview_cropped.png")
CROP_HEIGHT: int = 900


def latest_email() -> Path:
    files: list[Path] = sorted(EMAILS_DIR.glob("email_*.html"), key=lambda p: p.name)
    if not files:
        raise FileNotFoundError(f"No email HTML files found in {EMAILS_DIR}")
    return files[-1]


async def screenshot(html_path: Path) -> None:
    abs_path: str = str(html_path.resolve())
    print(f"Screenshotting: {abs_path}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--force-dark-mode"])
        page = await browser.new_page(viewport={"width": 900, "height": 900})
        await page.goto(f"file:///{abs_path}")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=str(OUT_FULL), full_page=True)
        await browser.close()

    img: Image.Image = Image.open(OUT_FULL)
    print(f"Full size: {img.size}")
    cropped: Image.Image = img.crop((0, 0, img.width, CROP_HEIGHT))
    cropped.save(str(OUT_CROP))
    print(f"Saved: {OUT_FULL}  ({img.size[1]}px tall)")
    print(f"Saved: {OUT_CROP}  ({CROP_HEIGHT}px tall)")


if __name__ == "__main__":
    target: Path = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_email()
    asyncio.run(screenshot(target))
