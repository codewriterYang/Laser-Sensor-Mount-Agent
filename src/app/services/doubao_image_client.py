"""豆包 Seedream 图片生成客户端 — 基于 OpenAI SDK 调用火山引擎 Ark API。

使用 .env 中的 IMAGE_MODEL / IMAGE_BASE_URL / IMAGE_API_KEY 配置。
兼容 OpenAI images.generate 接口格式。
"""

from __future__ import annotations

import base64
import hashlib
import time
from pathlib import Path
from typing import Any

from openai import OpenAI
from openai._exceptions import APIError, RateLimitError, APITimeoutError

from ..config import IMAGE_API_KEY, IMAGE_BASE_URL, IMAGE_MODEL, is_image_configured
from ..logger import logger

# 图片缓存目录
_CACHE_DIR = Path("exports/images/.cache")


class DoubaoImageClient:
    """豆包 Seedream 图片生成客户端。

    调用火山引擎 Ark API 的 images.generate 接口。
    支持 URL 和 base64 两种返回格式。
    内置缓存：相同 Prompt 不重复调用 API。
    """

    def __init__(self):
        if not is_image_configured():
            raise RuntimeError(
                "豆包图片模型未配置。请在 .env 中设置 IMAGE_MODEL / IMAGE_BASE_URL / IMAGE_API_KEY"
            )
        self._client = OpenAI(
            api_key=IMAGE_API_KEY,
            base_url=IMAGE_BASE_URL,
        )
        self._model = IMAGE_MODEL
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"豆包图片客户端已初始化：model={self._model}")

    def generate(self, prompt: str, size: str = "1024x1024", skip_cache: bool = False) -> bytes:
        """调用 Seedream 生成图片。

        Args:
            prompt: 图片生成 Prompt
            size: 图片尺寸，如 "1024x1024", "1536x1024"
            skip_cache: 跳过缓存，强制重新生成

        Returns:
            PNG 图片的字节数据

        Raises:
            RuntimeError: API 调用失败
        """
        # 检查缓存
        cache_key = self._cache_key(prompt, size)
        if not skip_cache:
            cached = self._read_cache(cache_key)
            if cached is not None:
                logger.info(f"图片缓存命中：{cache_key[:12]}...")
                return cached

        # 调用 API（带重试）
        for attempt in range(3):
            try:
                logger.info(
                    f"调用 Seedream API（第 {attempt + 1} 次）："
                    f"prompt={prompt[:60]}... size={size}"
                )
                t0 = time.time()

                response = self._client.images.generate(
                    model=self._model,
                    prompt=prompt,
                    n=1,
                    size=size,
                )

                elapsed = time.time() - t0
                logger.info(f"Seedream API 响应：{elapsed:.1f}s")

                # 提取图片数据
                image_data = self._extract_image_bytes(response)

                # 写入缓存
                self._write_cache(cache_key, image_data)

                return image_data

            except RateLimitError:
                if attempt < 2:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"Seedream API 限流，等待 {wait}s 后重试")
                    time.sleep(wait)
                else:
                    logger.warning("Seedream API 限流，已达最大重试次数")
            except APITimeoutError:
                logger.warning(f"Seedream API 超时（第 {attempt + 1} 次）")
                if attempt < 2:
                    time.sleep(2 ** (attempt + 1))
                else:
                    raise RuntimeError("Seedream API 超时，已重试 3 次")
            except APIError as e:
                logger.error(f"Seedream API 错误：{e}")
                raise RuntimeError(f"Seedream API 调用失败：{e}")

        raise RuntimeError("Seedream API 调用失败，已重试 3 次")

    def generate_with_reference(
        self,
        prompt: str,
        reference_image: bytes,
        strength: float = 0.5,
        size: str = "1024x1024",
        skip_cache: bool = False,
    ) -> bytes:
        """使用参考图进行 image-to-image 生成。

        Args:
            prompt: 图片生成 Prompt（描述材质/光照/风格）
            reference_image: 参考图 PNG 字节数据
            strength: 参考图影响强度 0.0~1.0（0.5 为平衡点）
            size: 输出尺寸
            skip_cache: 跳过缓存，强制重新生成

        Returns:
            PNG 图片的字节数据
        """
        # 检查缓存
        ref_hash = hashlib.md5(reference_image).hexdigest()[:12]
        cache_key = self._cache_key(f"{prompt}|ref:{ref_hash}|s:{strength}", size)
        if not skip_cache:
            cached = self._read_cache(cache_key)
            if cached is not None:
                logger.info(f"img2img 缓存命中：{cache_key[:12]}...")
                return cached

        # 编码参考图为 data URL
        ref_b64 = base64.b64encode(reference_image).decode()
        data_url = f"data:image/png;base64,{ref_b64}"

        # 调用 API（带重试）
        for attempt in range(3):
            try:
                logger.info(
                    f"调用 Seedream img2img（第 {attempt + 1} 次）："
                    f"prompt={prompt[:60]}... strength={strength} size={size}"
                )
                t0 = time.time()

                response = self._client.images.generate(
                    model=self._model,
                    prompt=prompt,
                    n=1,
                    size=size,
                    response_format="b64_json",
                    extra_body={
                        "image": data_url,
                        "strength": strength,
                    },
                )

                elapsed = time.time() - t0
                logger.info(f"Seedream img2img 响应：{elapsed:.1f}s")

                # 提取图片数据（b64_json 模式）
                image_data = self._extract_image_bytes(response)

                # 写入缓存
                self._write_cache(cache_key, image_data)

                return image_data

            except RateLimitError:
                if attempt < 2:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"Seedream img2img 限流，等待 {wait}s 后重试")
                    time.sleep(wait)
                else:
                    logger.warning("Seedream img2img 限流，已达最大重试次数")
            except APITimeoutError:
                logger.warning(f"Seedream img2img 超时（第 {attempt + 1} 次）")
                if attempt < 2:
                    time.sleep(2 ** (attempt + 1))
                else:
                    raise RuntimeError("Seedream img2img 超时，已重试 3 次")
            except APIError as e:
                logger.error(f"Seedream img2img 错误：{e}")
                raise RuntimeError(f"Seedream img2img 调用失败：{e}")

        raise RuntimeError("Seedream img2img 调用失败，已重试 3 次")

    def _extract_image_bytes(self, response: Any) -> bytes:
        """从 API 响应中提取图片字节。

        支持两种格式：
        1. response.data[0].b64_json → base64 解码
        2. response.data[0].url → 下载图片
        """
        if not response.data:
            raise RuntimeError("Seedream API 返回空数据")

        item = response.data[0]

        # 优先 base64
        if hasattr(item, "b64_json") and item.b64_json:
            return base64.b64decode(item.b64_json)

        # 次选 URL
        if hasattr(item, "url") and item.url:
            return self._download_image(item.url)

        raise RuntimeError("Seedream API 响应中无图片数据（无 b64_json 也无 url）")

    @staticmethod
    def _download_image(url: str) -> bytes:
        """从 URL 下载图片，支持 SSL 降级。"""
        import httpx

        logger.info(f"下载图片：{url[:80]}...")

        # 先尝试正常 SSL
        try:
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                resp = client.get(url)
                resp.raise_for_status()
                return resp.content
        except Exception as e:
            logger.warning(f"SSL 下载失败，尝试降级：{e}")

        # SSL 失败时降级：关闭证书验证
        with httpx.Client(timeout=30, follow_redirects=True, verify=False) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.content

    @staticmethod
    def _cache_key(prompt: str, size: str) -> str:
        """生成缓存 key（Prompt + size 的 MD5）。"""
        content = f"{prompt}|{size}"
        return hashlib.md5(content.encode()).hexdigest()

    @staticmethod
    def _read_cache(key: str) -> bytes | None:
        """读取缓存。"""
        cache_path = _CACHE_DIR / f"{key}.png"
        if cache_path.exists():
            try:
                return cache_path.read_bytes()
            except OSError:
                return None
        return None

    @staticmethod
    def _write_cache(key: str, data: bytes) -> None:
        """写入缓存。"""
        cache_path = _CACHE_DIR / f"{key}.png"
        try:
            cache_path.write_bytes(data)
        except OSError as e:
            logger.warning(f"图片缓存写入失败：{e}")
