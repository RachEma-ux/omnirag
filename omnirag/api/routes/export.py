"""Export API — GET /v1/export/{format} for JSONL, CSV, Parquet."""

from __future__ import annotations

import csv
import io
import json
import time

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from omnirag.output.index_writers.base import get_writer_registry

router = APIRouter(prefix="/v1")

MAX_ROWS = 100_000


@router.get("/export/{fmt}", tags=["export"])
async def export_chunks(
    fmt: str,
    request: Request,
    doc_id: list[str] = Query(default=[]),
    start_date: str | None = None,
    end_date: str | None = None,
    offset: int = 0,
    limit: int = MAX_ROWS,
):
    """Download chunks in JSONL, CSV, or Parquet format."""
    if fmt not in ("jsonl", "csv", "parquet"):
        raise HTTPException(400, f"Unsupported format: {fmt}. Use jsonl, csv, or parquet.")

    user_principals = getattr(request.state, "user_principals", ["public"])
    limit = min(limit, MAX_ROWS)

    # Get metadata writer for chunk data
    writer = get_writer_registry().get("metadata")
    if not writer:
        raise HTTPException(503, "Metadata store unavailable")

    filters = {}
    if doc_id:
        filters["doc_id"] = doc_id

    results = await writer.search(None, None, user_principals, top_k=limit + offset, filters=filters)
    rows = results[offset:offset + limit]

    if not rows:
        raise HTTPException(404, "No chunks found matching criteria")

    timestamp = int(time.time())

    if fmt == "jsonl":
        def generate_jsonl():
            for row in rows:
                yield json.dumps(row) + "\n"

        return StreamingResponse(
            generate_jsonl(),
            media_type="application/x-jsonlines",
            headers={"Content-Disposition": f'attachment; filename="export_{timestamp}.jsonl"'},
        )

    elif fmt == "csv":
        def generate_csv():
            output = io.StringIO()
            if rows:
                fieldnames = sorted(set().union(*(r.get("payload", r).keys() for r in rows)))
                w = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
                w.writeheader()
                yield output.getvalue()
                output.seek(0)
                output.truncate()

                for row in rows:
                    data = row.get("payload", row)
                    # Flatten nested dicts
                    flat = {}
                    for k, v in data.items():
                        flat[k] = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                    w.writerow(flat)
                    yield output.getvalue()
                    output.seek(0)
                    output.truncate()

        return StreamingResponse(
            generate_csv(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="export_{timestamp}.csv"'},
        )

    elif fmt == "parquet":
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            raise HTTPException(501, "Parquet export requires pyarrow: pip install pyarrow")

        data_rows = [row.get("payload", row) for row in rows]
        if not data_rows:
            raise HTTPException(404, "No data")

        # Build flat table
        columns: dict[str, list] = {}
        for row in data_rows:
            for k, v in row.items():
                if k not in columns:
                    columns[k] = []
                columns[k].append(json.dumps(v) if isinstance(v, (dict, list)) else str(v))

        # Pad columns
        max_len = max(len(v) for v in columns.values())
        for k in columns:
            while len(columns[k]) < max_len:
                columns[k].append("")

        table = pa.table(columns)
        buf = io.BytesIO()
        pq.write_table(table, buf)
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="export_{timestamp}.parquet"'},
        )
