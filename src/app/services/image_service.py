"""Image Generation Service — step descriptions → assembly diagrams via Doubao Seedream.

Uses OpenAI-compatible image generation API (Volcano Engine).
Falls back gracefully when API key is not configured.
"""

from __future__ import annotations

import base64
import os
import uuid
from io import BytesIO
from pathlib import Path

from openai import OpenAI
from PIL import Image

from .. import config

IMAGES_DIR = Path("exports/images")


class ImageService:
    """Generate assembly step illustrations via Doubao Seedream 4.5.

    When IMAGE_API_KEY is not configured, returns placeholder paths.
    """

    def __init__(self):
        self._client: OpenAI | None = None
        if config.IMAGE_API_KEY and config.IMAGE_API_KEY != "your_api_key_here":
            self._client = OpenAI(
                base_url=config.IMAGE_BASE_URL,
                api_key=config.IMAGE_API_KEY,
            )

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def generate_step_image(self, step_title: str, step_description: str, sequence: int) -> str | None:
        """Generate an illustration for one assembly step.

        Returns the file path to the generated image, or None if unavailable.
        """
        if not self._client:
            return None

        prompt = (
            f"Technical assembly illustration, isometric view, clean line drawing style. "
            f"Step {sequence}: {step_title}. {step_description}. "
            f"Show mechanical parts being assembled. Industrial engineering diagram. "
            f"White background, clear labels, professional CAD-style rendering."
        )

        try:
            response = self._client.images.generate(
                model=config.IMAGE_MODEL,
                prompt=prompt,
                size="1024x1024",
                n=1,
                response_format="b64_json",
            )

            IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            image_path = IMAGES_DIR / f"step_{sequence}_{uuid.uuid4().hex[:8]}.png"

            if response.data and response.data[0].b64_json:
                image_data = base64.b64decode(response.data[0].b64_json)
                image = Image.open(BytesIO(image_data))
                image.save(str(image_path), "PNG")
                return str(image_path)
            elif response.data and response.data[0].url:
                # Some APIs return a URL instead
                import urllib.request
                urllib.request.urlretrieve(response.data[0].url, str(image_path))
                return str(image_path)
            else:
                return None

        except Exception:
            return None

    def generate_all_step_images(self, steps: list[dict]) -> dict[int, str]:
        """Generate images for all steps. Returns {sequence: image_path} dict."""
        results = {}
        for step in steps:
            seq = step.get("sequence", 0)
            title = step.get("title", "")
            desc = step.get("description", "")
            path = self.generate_step_image(title, desc, seq)
            if path:
                results[seq] = path
        return results
