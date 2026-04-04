from __future__ import annotations

from datetime import datetime

import typer

from stock_report.exceptions import FinMindAPIError, InvalidStockError
from stock_report.services.report_service import ReportService


app = typer.Typer(no_args_is_help=True)


@app.command()
def report(stock_id: str, year: int = typer.Option(2024, "--year")) -> None:
    current_year = datetime.now().year
    if year < 2010 or year > current_year:
        typer.echo(f"Invalid year: {year}. Year must be between 2010 and {current_year}.")
        raise typer.Exit(1)

    service = ReportService()
    try:
        stock_report = service.generate_report(stock_id, year)
    except InvalidStockError as exc:
        typer.echo(f"Invalid stock id: {exc.stock_id}")
        raise typer.Exit(1) from exc
    except FinMindAPIError as exc:
        typer.echo(f"FinMind API error: {exc}")
        raise typer.Exit(1) from exc

    typer.echo(stock_report.summary)


if __name__ == "__main__":
    app()
