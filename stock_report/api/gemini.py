from __future__ import annotations

import json
from typing import Any

import requests

from stock_report.config import settings
from stock_report.exceptions import LLMAPIError


class GeminiClient:
    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise LLMAPIError("GEMINI_API_KEY not set")

        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model
        self.session = requests.Session()

    def generate(self, prompt: str) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        body = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt,
                        }
                    ]
                }
            ]
        }

        try:
            response = self.session.post(
                url,
                json=body,
                timeout=settings.service.timeout,
            )
        except requests.RequestException as exc:
            raise LLMAPIError(self._sanitize_message(str(exc))) from exc

        if response.status_code == 429:
            raise LLMAPIError("quota exceeded", 429)
        if response.status_code != 200:
            raise LLMAPIError(self._extract_error_message(response), response.status_code)

        try:
            payload = response.json()
        except ValueError as exc:
            raise LLMAPIError("Invalid JSON response", response.status_code) from exc

        text = self._extract_text(payload)
        if not text:
            raise LLMAPIError("Empty Gemini response", response.status_code)
        return text

    @staticmethod
    def _extract_error_message(response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            message = response.text.strip()
            return message or "Gemini API request failed"

        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if message:
                return str(message)

        message = payload.get("message")
        if message:
            return str(message)

        return json.dumps(payload, ensure_ascii=False) if payload else "Gemini API request failed"

    def _sanitize_message(self, message: str) -> str:
        if self.api_key:
            return message.replace(self.api_key, "***")
        return message

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str | None:
        try:
            candidates = payload["candidates"]
            if not isinstance(candidates, list) or not candidates:
                return None
            content = candidates[0]["content"]
            parts = content["parts"]
            if not isinstance(parts, list) or not parts:
                return None
            text = parts[0]["text"]
        except (KeyError, IndexError, TypeError):
            return None

        return str(text).strip() or None
