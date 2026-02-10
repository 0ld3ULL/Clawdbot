"""
Leonardo.ai API integration for image generation.
"""

import asyncio
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

LEONARDO_BASE_URL = "https://cloud.leonardo.ai/api/rest/v1"


class LeonardoAPI:
    """Leonardo.ai image generation API client."""

    def __init__(self):
        self._api_key: Optional[str] = None

    def _get_api_key(self) -> str:
        if self._api_key:
            return self._api_key
        key = os.environ.get("LEONARDO_API_KEY", "")
        if not key:
            raise RuntimeError("LEONARDO_API_KEY not configured in .env")
        self._api_key = key
        return key

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_api_key()}",
            "Content-Type": "application/json",
        }

    async def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 576,  # 16:9 for video
        model_id: str = "6b645e3a-d64f-4341-a6d8-7a3690fbf042",  # Leonardo Phoenix
        num_images: int = 1,
        style: str = "CINEMATIC",
    ) -> dict:
        """
        Generate an image with Leonardo.ai.

        Args:
            prompt: Image description
            negative_prompt: What to avoid
            width: Image width
            height: Image height
            model_id: Leonardo model ID
            num_images: Number of images to generate
            style: Style preset (CINEMATIC, PHOTOGRAPHY, etc.)

        Returns:
            dict with generation_id and image URLs
        """
        logger.info(f"Leonardo: Generating image - {prompt[:50]}...")

        async with httpx.AsyncClient(timeout=120) as client:
            # Start generation
            response = await client.post(
                f"{LEONARDO_BASE_URL}/generations",
                headers=self._headers(),
                json={
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "width": width,
                    "height": height,
                    "modelId": model_id,
                    "num_images": num_images,
                    "presetStyle": style,
                    "public": False,
                },
            )

            if not response.is_success:
                raise RuntimeError(f"Leonardo generation failed: {response.text}")

            data = response.json()
            generation_id = data["sdGenerationJob"]["generationId"]
            logger.info(f"Leonardo: Generation started - {generation_id}")

            # Poll for completion
            for _ in range(60):  # 5 minutes max
                await asyncio.sleep(5)

                response = await client.get(
                    f"{LEONARDO_BASE_URL}/generations/{generation_id}",
                    headers=self._headers(),
                )

                if not response.is_success:
                    continue

                gen_data = response.json()
                status = gen_data.get("generations_by_pk", {}).get("status")

                if status == "COMPLETE":
                    images = gen_data["generations_by_pk"]["generated_images"]
                    urls = [img["url"] for img in images]
                    logger.info(f"Leonardo: Generation complete - {len(urls)} images")
                    return {
                        "generation_id": generation_id,
                        "image_urls": urls,
                        "image_url": urls[0] if urls else None,
                    }
                elif status == "FAILED":
                    raise RuntimeError("Leonardo generation failed")

            raise RuntimeError("Leonardo generation timed out")

    async def download_image(self, url: str) -> bytes:
        """Download an image from URL."""
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url)
            if not response.is_success:
                raise RuntimeError(f"Failed to download image: {response.status_code}")
            return response.content
