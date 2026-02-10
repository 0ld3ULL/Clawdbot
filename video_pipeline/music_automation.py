"""
Browser automation for ElevenLabs video-to-music.

Uses Playwright to automate the ElevenLabs web interface
until their API is publicly available.

This module is designed to be called by DEVA on David's laptop.
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default download directory
DOWNLOAD_DIR = Path("data/video_pipeline/music_downloads")


class ElevenLabsMusicAutomation:
    """
    Automates ElevenLabs video-to-music via browser.

    Requires: pip install playwright
    Setup: playwright install chromium
    """

    def __init__(self, headless: bool = False, download_dir: Optional[Path] = None):
        """
        Initialize the automation.

        Args:
            headless: Run browser in headless mode (False = visible for debugging)
            download_dir: Where to save downloaded music files
        """
        self.headless = headless
        self.download_dir = download_dir or DOWNLOAD_DIR
        self.download_dir.mkdir(parents=True, exist_ok=True)

    async def generate_music_for_video(
        self,
        video_path: str,
        prompt: Optional[str] = None,
        timeout_seconds: int = 180,
    ) -> str:
        """
        Generate music for a video using ElevenLabs video-to-music.

        Args:
            video_path: Path to the video file
            prompt: Optional style prompt (e.g., "dark cyberpunk ambient")
            timeout_seconds: Max time to wait for generation

        Returns:
            Path to the downloaded music file (MP4 with music)
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            )

        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        logger.info(f"ElevenLabs Music: Starting browser automation for {video_path.name}")

        async with async_playwright() as p:
            # Launch browser with download handling
            browser = await p.chromium.launch(
                headless=self.headless,
                downloads_path=str(self.download_dir),
            )

            context = await browser.new_context(
                accept_downloads=True,
                # Use saved auth state if available
                storage_state=self._get_auth_state_path() if self._has_auth_state() else None,
            )

            page = await context.new_page()

            try:
                # Navigate to video-to-music
                logger.info("Navigating to ElevenLabs video-to-music...")
                await page.goto("https://elevenlabs.io/app/video-to-music", timeout=30000)
                await asyncio.sleep(2)

                # Check if logged in
                if "sign-in" in page.url.lower() or await page.query_selector('text="Sign in"'):
                    logger.warning("Not logged in to ElevenLabs - manual login required")
                    # Wait for manual login
                    logger.info("Please log in to ElevenLabs in the browser window...")
                    await page.wait_for_url("**/app/**", timeout=120000)
                    # Save auth state for next time
                    await context.storage_state(path=self._get_auth_state_path())
                    logger.info("Auth state saved for future runs")
                    await page.goto("https://elevenlabs.io/app/video-to-music")
                    await asyncio.sleep(2)

                # Upload video
                logger.info("Uploading video...")
                file_input = await page.query_selector('input[type="file"]')
                if file_input:
                    await file_input.set_input_files(str(video_path))
                else:
                    # Try clicking upload area first
                    upload_area = await page.query_selector('[data-testid="upload-area"]')
                    if upload_area:
                        await upload_area.click()
                        file_input = await page.wait_for_selector('input[type="file"]', timeout=5000)
                        await file_input.set_input_files(str(video_path))
                    else:
                        raise RuntimeError("Could not find file upload element")

                await asyncio.sleep(3)

                # Enter prompt if provided
                if prompt:
                    logger.info(f"Entering prompt: {prompt}")
                    prompt_input = await page.query_selector('textarea, input[placeholder*="prompt"]')
                    if prompt_input:
                        await prompt_input.fill(prompt)

                # Click generate button
                logger.info("Starting generation...")
                generate_btn = await page.query_selector('button:has-text("Generate")')
                if generate_btn:
                    await generate_btn.click()
                else:
                    # Try alternative selectors
                    await page.click('button[type="submit"]')

                # Wait for generation to complete
                logger.info(f"Waiting for generation (max {timeout_seconds}s)...")
                start_time = time.time()

                while time.time() - start_time < timeout_seconds:
                    await asyncio.sleep(5)

                    # Check for download button
                    download_btn = await page.query_selector(
                        'button:has-text("Download"), a:has-text("Download"), [data-testid="download-button"]'
                    )
                    if download_btn:
                        logger.info("Generation complete, downloading...")

                        # Handle download
                        async with page.expect_download() as download_info:
                            await download_btn.click()

                        download = await download_info.value
                        download_path = self.download_dir / f"elevenlabs_music_{int(time.time())}.mp4"
                        await download.save_as(str(download_path))

                        logger.info(f"Music downloaded: {download_path}")
                        return str(download_path)

                    # Check for error
                    error = await page.query_selector('[class*="error"], [data-testid="error-message"]')
                    if error:
                        error_text = await error.text_content()
                        raise RuntimeError(f"ElevenLabs error: {error_text}")

                raise RuntimeError("Generation timed out")

            finally:
                await browser.close()

    def _get_auth_state_path(self) -> str:
        """Get path for browser auth state storage."""
        return str(Path("data/video_pipeline/elevenlabs_auth.json"))

    def _has_auth_state(self) -> bool:
        """Check if saved auth state exists."""
        return Path(self._get_auth_state_path()).exists()


async def generate_music_for_video(
    video_path: str,
    prompt: Optional[str] = None,
    headless: bool = False,
) -> str:
    """
    Convenience function to generate music for a video.

    Args:
        video_path: Path to the video file
        prompt: Optional style prompt
        headless: Run browser in headless mode

    Returns:
        Path to downloaded music file
    """
    automation = ElevenLabsMusicAutomation(headless=headless)
    return await automation.generate_music_for_video(video_path, prompt)
