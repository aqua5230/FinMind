from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAPIClient(ABC):
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url
        self.token = token

    @abstractmethod
    def get(self, params: dict) -> dict:
        raise NotImplementedError
