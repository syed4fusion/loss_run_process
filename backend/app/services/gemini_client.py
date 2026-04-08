from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from time import monotonic
from typing import Any

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

from app.config import settings

logger = logging.getLogger(__name__)

_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY = 2.0  # seconds


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._model_name = model or settings.GEMINI_MODEL
        self._mock_mode = settings.GEMINI_MOCK_MODE or not bool(self._api_key)
        self._min_interval = (
            1.0 / settings.GEMINI_MAX_REQUESTS_PER_SECOND
            if settings.GEMINI_MAX_REQUESTS_PER_SECOND > 0
            else 0.0
        )
        self._rate_lock = asyncio.Lock()
        self._last_call_ts = 0.0

        if not self._mock_mode:
            genai.configure(api_key=self._api_key)
            self._model = genai.GenerativeModel(self._model_name)
        else:
            self._model = None

    async def _throttle(self) -> None:
        if self._min_interval <= 0:
            return
        async with self._rate_lock:
            now = monotonic()
            wait_for = self._min_interval - (now - self._last_call_ts)
            if wait_for > 0:
                await asyncio.sleep(wait_for)
            self._last_call_ts = monotonic()

    async def upload_pdf(self, file_path: str) -> Any:
        """Upload a PDF to Gemini Files API. Returns a file reference."""
        if self._mock_mode:
            return {"name": Path(file_path).name, "path": file_path}
        await self._throttle()
        loop = asyncio.get_event_loop()
        file_ref = await loop.run_in_executor(
            None,
            lambda: genai.upload_file(file_path, mime_type="application/pdf"),
        )
        logger.info("Uploaded %s → %s", file_path, file_ref.name)
        return file_ref

    async def extract_claims(
        self, file_ref: Any, prompt: str, response_schema: dict
    ) -> dict:
        """Run structured extraction. Returns parsed JSON dict."""
        if self._mock_mode:
            source_name = (
                Path(file_ref["path"]).name
                if isinstance(file_ref, dict)
                else str(file_ref)
            )
            return {
                "carrier_name": "MOCK_CARRIER",
                "carrier_code": "MOCK",
                "lob": "UNKNOWN",
                "policy_period_start": None,
                "policy_period_end": None,
                "earned_premium": None,
                "claims": [],
                "extraction_notes": [
                    f"Mock extraction used for local verification: {source_name}"
                ],
            }

        generation_config = genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
        )

        for attempt in range(_RETRY_ATTEMPTS):
            try:
                await self._throttle()
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self._model.generate_content(
                        [file_ref, prompt],
                        generation_config=generation_config,
                    ),
                )
                return json.loads(response.text)
            except ResourceExhausted:
                if attempt < _RETRY_ATTEMPTS - 1:
                    delay = _RETRY_BASE_DELAY * (2**attempt)
                    logger.warning("Rate limited; retrying in %.1fs", delay)
                    await asyncio.sleep(delay)
                else:
                    raise
            except json.JSONDecodeError as exc:
                logger.error("Gemini returned invalid JSON: %s", exc)
                raise

    async def generate_text(self, prompt: str, context: str = "") -> str:
        """Free-form text generation for narratives."""
        full_prompt = f"{context}\n\n{prompt}" if context else prompt
        if self._mock_mode:
            return "Mock narrative generated in local verification mode."

        for attempt in range(_RETRY_ATTEMPTS):
            try:
                await self._throttle()
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self._model.generate_content(full_prompt),
                )
                return response.text
            except ResourceExhausted:
                if attempt < _RETRY_ATTEMPTS - 1:
                    delay = _RETRY_BASE_DELAY * (2**attempt)
                    await asyncio.sleep(delay)
                else:
                    raise

    def delete_file(self, file_ref: Any) -> None:
        """Clean up uploaded file from Gemini after extraction."""
        if self._mock_mode:
            return
        try:
            genai.delete_file(file_ref.name)
            logger.info("Deleted Gemini file %s", file_ref.name)
        except Exception as exc:
            logger.warning("Could not delete Gemini file %s: %s", file_ref.name, exc)


def get_gemini_client() -> GeminiClient:
    # Return a fresh client per caller so asyncio primitives (e.g. Lock)
    # are always bound to the currently running event loop.
    return GeminiClient()
