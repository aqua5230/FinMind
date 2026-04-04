from __future__ import annotations

import json
from typing import Any

import requests

from stock_report.config import settings
from stock_report.exceptions import ClaudeAPIError


class DeepSeekClient:
    def __init__(self) -> None:
        if not settings.deepseek_api_key:
            raise ClaudeAPIError("DEEPSEEK_API_KEY not set")

        self.api_key = settings.deepseek_api_key
        self.model = settings.deepseek_model
        self.session = requests.Session()

    def generate(self, prompt: str) -> str:
        try:
            response = self.session.post(
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2048,
                },
                timeout=settings.service.timeout,
            )
        except requests.RequestException as exc:
            raise ClaudeAPIError(self._sanitize_message(str(exc))) from exc

        if response.status_code == 429:
            raise ClaudeAPIError("quota exceeded", 429)
        if response.status_code != 200:
            raise ClaudeAPIError(self._extract_error_message(response), response.status_code)

        try:
            payload = response.json()
        except ValueError as exc:
            raise ClaudeAPIError("Invalid JSON response", response.status_code) from exc

        text = self._extract_text(payload)
        if not text:
            raise ClaudeAPIError("Empty DeepSeek response", response.status_code)
        return text

    @staticmethod
    def _extract_error_message(response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            message = response.text.strip()
            return message or "DeepSeek API request failed"

        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if message:
                return str(message)

        message = payload.get("message")
        if message:
            return str(message)

        return json.dumps(payload, ensure_ascii=False) if payload else "DeepSeek API request failed"

    def _sanitize_message(self, message: str) -> str:
        if self.api_key:
            return message.replace(self.api_key, "***")
        return message

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str | None:
        try:
            choices = payload["choices"]
            if not isinstance(choices, list) or not choices:
                return None
            message = choices[0]["message"]
            text = message["content"]
        except (KeyError, IndexError, TypeError):
            return None

        return str(text).strip() or None
