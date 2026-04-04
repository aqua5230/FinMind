from __future__ import annotations

from abc import ABC, abstractmethod

import requests

from stock_report.exceptions import FinMindAPIError


class BaseAPIClient(ABC):
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url
        self.token = token

    @abstractmethod
    def get(self, params: dict) -> dict:
        raise NotImplementedError

    def _handle_response(self, response: requests.Response) -> dict:
        if response.status_code != 200:
            raise FinMindAPIError(response.status_code, response.text)

        try:
            payload = response.json()
        except ValueError as exc:
            raise FinMindAPIError(response.status_code, "Invalid JSON response") from exc

        if not isinstance(payload, dict):
            raise FinMindAPIError(response.status_code, "Unexpected response payload type")

        msg = payload.get("msg")
        if msg not in (None, "", "success"):
            raise FinMindAPIError(response.status_code, str(msg))

        return payload
