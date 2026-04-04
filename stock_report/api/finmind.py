from __future__ import annotations

import json
from typing import Any

import requests

from stock_report.api.base import BaseAPIClient
from stock_report.config import settings
from stock_report.exceptions import FinMindAPIError
from stock_report.logger import get_logger


logger = get_logger(__name__)


class FinMindClient(BaseAPIClient):
    def __init__(self) -> None:
        session = requests.Session()
        if settings.finmind_token:
            session.headers.update({"Authorization": f"Bearer {settings.finmind_token}"})

        super().__init__(
            base_url=settings.service.api_base_url,
            token=settings.finmind_token or "",
        )
        self.session = session

    def get(self, params: dict[str, Any]) -> dict:
        try:
            response = self.session.get(
                self.base_url,
                params=params,
                timeout=settings.service.timeout,
            )
        except requests.RequestException as exc:
            raise FinMindAPIError(str(exc)) from exc

        return self._handle_response(response)

    def fetch(
        self,
        dataset: str,
        data_id: str,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        params = {
            "dataset": dataset,
            "data_id": data_id,
            "start_date": start_date,
            "end_date": end_date,
        }
        payload = self.get(params)
        data = payload.get("data", [])

        if not isinstance(data, list):
            raise FinMindAPIError("Unexpected data payload type", 200)

        logger.info("Fetched dataset=%s records=%s", dataset, len(data))
        return data

    def fetch_dataset(
        self,
        dataset: str,
        data_id: str,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        return self.fetch(dataset, data_id, start_date, end_date)

    def _handle_response(self, response: requests.Response) -> dict[str, Any]:
        if response.status_code == 402:
            raise FinMindAPIError("quota exceeded", 402)
        if response.status_code != 200:
            message = response.text.strip() or "FinMind API request failed"
            raise FinMindAPIError(message, response.status_code)

        try:
            payload = response.json()
        except ValueError as exc:
            raise FinMindAPIError("Invalid JSON response", response.status_code) from exc

        if not isinstance(payload, dict):
            raise FinMindAPIError("Unexpected response payload type", response.status_code)

        status = payload.get("status")
        if status != 200:
            message = payload.get("msg")
            if isinstance(message, (dict, list)):
                message = json.dumps(message, ensure_ascii=False)
            if not message:
                message = "FinMind API request failed"
            raise FinMindAPIError(str(message), int(status) if isinstance(status, int) else response.status_code)

        return payload
