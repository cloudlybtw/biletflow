"""Shared UTC ranges and safe CSV encoding for private operational reports."""

import csv
import io
import uuid
from datetime import datetime

from fastapi import Query, Response
from pydantic import AwareDatetime, BaseModel, model_validator

from app.core.errors import EXPORT_TOO_LARGE, AppError

EXPORT_LIMIT = 10_000


class ReportFilters(BaseModel):
    date_from: AwareDatetime | None = None
    date_to: AwareDatetime | None = None
    ticket_type_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def ordered(self):
        if self.date_from and self.date_to and self.date_from >= self.date_to:
            raise ValueError("date_to must be after date_from.")
        return self


def report_filters(
    date_from: AwareDatetime | None = None,
    date_to: AwareDatetime | None = None,
    ticket_type_id: uuid.UUID | None = None,
) -> ReportFilters:
    if date_from and date_to and date_from >= date_to:
        from app.core.errors import VALIDATION_ERROR

        raise AppError(VALIDATION_ERROR, "date_to must be after date_from.", 422)
    return ReportFilters(date_from=date_from, date_to=date_to, ticket_type_id=ticket_type_id)


def literal_pattern(value: str) -> str:
    return "%" + value.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def date_filters(
    date_from: AwareDatetime | None = None, date_to: AwareDatetime | None = None
) -> ReportFilters:
    return report_filters(date_from, date_to)


def csv_response(rows: list[dict], columns: list[str], filename: str) -> Response:
    if len(rows) > EXPORT_LIMIT:
        raise AppError(EXPORT_TOO_LARGE, "Narrow the filters to at most 10000 report rows.", 400)
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for row in rows:
        values = []
        for key in columns:
            value = row.get(key)
            if isinstance(value, datetime):
                value = value.isoformat()
            if value is None:
                value = ""
            if isinstance(value, str) and (
                value.lstrip().startswith(("=", "+", "-", "@"))
                or value.startswith(("\t", "\r", "\n"))
            ):
                value = "'" + value
            values.append(value)
        writer.writerow(values)
    return Response(
        buffer.getvalue().encode("utf-8-sig"),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}.csv"',
            "Cache-Control": "private, no-store",
        },
    )


SearchQuery = Query(default=None, min_length=1, max_length=200)
