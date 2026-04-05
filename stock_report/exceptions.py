from __future__ import annotations


class FinMindBaseError(Exception):
    """Base exception for the stock report package."""


class FinMindAPIError(FinMindBaseError):
    def __init__(self, msg: str, status_code: int | None = None) -> None:
        self.msg = msg
        self.status_code = status_code
        detail = f"{msg} (status_code={status_code})" if status_code is not None else msg
        super().__init__(detail)


class LLMAPIError(FinMindBaseError):
    def __init__(self, msg: str, status_code: int | None = None) -> None:
        self.msg = msg
        self.status_code = status_code
        detail = f"{msg} (status_code={status_code})" if status_code is not None else msg
        super().__init__(detail)


class DataMissingError(FinMindBaseError):
    def __init__(self, dataset: str, stock_id: str) -> None:
        self.dataset = dataset
        self.stock_id = stock_id
        super().__init__(f"Missing {dataset} data for stock {stock_id}.")


class InvalidStockError(FinMindBaseError):
    def __init__(self, stock_id: str) -> None:
        self.stock_id = stock_id
        super().__init__(f"Invalid stock id: {stock_id}")
