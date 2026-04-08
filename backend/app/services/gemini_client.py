from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from time import monotonic
from typing import Any

from google import genai

from app.config import settings

logger = logging.getLogger(__name__)

_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY = 2.0  # seconds
_MALFORMED_JSON_RAW_LIMIT = 10000


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
            self._client = genai.Client(api_key=self._api_key)
        else:
            self._client = None

    @staticmethod
    def _is_rate_limit_error(exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        if status_code == 429:
            return True
        text = str(exc).lower()
        return "rate limit" in text or "resourceexhausted" in text or "429" in text

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
            lambda: self._client.files.upload(file=file_path),
        )
        logger.info("Uploaded %s -> %s", file_path, getattr(file_ref, "name", "unknown"))
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

        response = await self._generate_structured_response(
            contents=[file_ref, prompt],
            response_schema=response_schema,
        )
        parsed = self._parse_structured_response(response)
        if parsed is not None:
            return parsed

        # Required hardening: one retry on malformed JSON, then retain raw text + error flag.
        retry_response = await self._generate_structured_response(
            contents=[file_ref, prompt],
            response_schema=response_schema,
        )
        retry_parsed = self._parse_structured_response(retry_response)
        if retry_parsed is not None:
            return retry_parsed
        return self._malformed_json_payload(retry_response)

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
                    lambda: self._client.models.generate_content(
                        model=self._model_name,
                        contents=full_prompt,
                    ),
                )
                return response.text
            except Exception as exc:
                if not self._is_rate_limit_error(exc):
                    raise
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
            file_name = getattr(file_ref, "name", None)
            if file_name:
                self._client.files.delete(name=file_name)
                logger.info("Deleted Gemini file %s", file_name)
        except Exception as exc:
            logger.warning("Could not delete Gemini file: %s", exc)

    async def _generate_structured_response(
        self,
        *,
        contents: Any,
        response_schema: dict,
    ) -> Any:
        for attempt in range(_RETRY_ATTEMPTS):
            try:
                await self._throttle()
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    lambda: self._client.models.generate_content(
                        model=self._model_name,
                        contents=contents,
                        config={
                            "response_mime_type": "application/json",
                            "response_schema": response_schema,
                        },
                    ),
                )
            except Exception as exc:
                if not self._is_rate_limit_error(exc):
                    raise
                if attempt < _RETRY_ATTEMPTS - 1:
                    delay = _RETRY_BASE_DELAY * (2**attempt)
                    logger.warning("Rate limited; retrying in %.1fs", delay)
                    await asyncio.sleep(delay)
                else:
                    raise
        raise RuntimeError("Structured generation exhausted retries")

    def _parse_structured_response(self, response: Any) -> dict | None:
        response_text = getattr(response, "text", None)
        if response_text:
            try:
                return json.loads(response_text)
            except json.JSONDecodeError as exc:
                logger.warning("Gemini returned malformed structured JSON: %s", exc)
                return None
        if getattr(response, "parsed", None) is not None:
            parsed = response.parsed
            if isinstance(parsed, dict):
                return parsed
            try:
                return json.loads(json.dumps(parsed, default=str))
            except json.JSONDecodeError:
                return None
        return None

    def _malformed_json_payload(self, response: Any) -> dict:
        raw_text = str(getattr(response, "text", "") or "")
        if len(raw_text) > _MALFORMED_JSON_RAW_LIMIT:
            raw_text = raw_text[:_MALFORMED_JSON_RAW_LIMIT]
        logger.error("Gemini structured output malformed after retry; storing raw payload excerpt")
        return {
            "carrier_name": "UNKNOWN",
            "carrier_code": "UNKNOWN",
            "lob": "UNKNOWN",
            "policy_period_start": None,
            "policy_period_end": None,
            "earned_premium": None,
            "claims": [],
            "extraction_notes": [
                "Gemini returned malformed JSON after one retry; raw response stored for diagnostics."
            ],
            "_malformed_json": True,
            "_raw_response_text": raw_text,
        }


def get_gemini_client() -> GeminiClient:
    # Return a fresh client per caller so asyncio primitives (e.g. Lock)
    # are always bound to the currently running event loop.
    return GeminiClient()
