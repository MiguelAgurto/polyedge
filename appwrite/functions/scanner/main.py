"""Run PolyEdge's scanner and publish its newest private dashboard state."""

from __future__ import annotations

import gzip
import io
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
from appwrite.client import Client
from appwrite.exception import AppwriteException
from appwrite.id import ID
from appwrite.input_file import InputFile
from appwrite.services.storage import Storage
from appwrite.services.tables_db import TablesDB


ROOT = Path(__file__).resolve().parents[3]
SCANNER_PACKAGE = ROOT / "services" / "scanner"
if str(SCANNER_PACKAGE) not in sys.path:
    sys.path.insert(0, str(SCANNER_PACKAGE))

from polyedge.config import Settings  # noqa: E402
from polyedge.jobs.refresh_now import refresh  # noqa: E402


DATABASE_ID = "polyedge"
TABLE_ID = "state_pointers"
POINTER_ID = "latest"
BUCKET_ID = "polyedge-state"


def _execution_key(context) -> str:
    key = context.req.headers.get("x-appwrite-key") or context.req.headers.get("X-Appwrite-Key")
    if not key:
        raise RuntimeError("Appwrite did not provide an execution API key.")
    return key


def _client(context) -> Client:
    return (
        Client()
        .set_endpoint(os.environ["APPWRITE_FUNCTION_API_ENDPOINT"])
        .set_project(os.environ["APPWRITE_FUNCTION_PROJECT_ID"])
        .set_key(_execution_key(context))
    )


def _download_previous_state(context, file_id: str, destination: Path) -> None:
    endpoint = os.environ["APPWRITE_FUNCTION_API_ENDPOINT"].rstrip("/")
    url = f"{endpoint}/storage/buckets/{BUCKET_ID}/files/{file_id}/download"
    headers = {
        "X-Appwrite-Project": os.environ["APPWRITE_FUNCTION_PROJECT_ID"],
        "X-Appwrite-Key": _execution_key(context),
    }
    response = httpx.get(url, headers=headers, timeout=60)
    response.raise_for_status()
    with gzip.open(io.BytesIO(response.content), "rb") as source:
        destination.write_bytes(source.read())


def _load_previous_state(context, tables: TablesDB, destination: Path) -> str | None:
    try:
        pointer = tables.get_row(
            database_id=DATABASE_ID,
            table_id=TABLE_ID,
            row_id=POINTER_ID,
        )
    except AppwriteException as error:
        if error.code == 404:
            return None
        raise
    file_id = pointer["file_id"]
    _download_previous_state(context, file_id, destination)
    return file_id


def _publish_state(
    tables: TablesDB,
    storage: Storage,
    data_file: Path,
    previous_file_id: str | None,
) -> str:
    compressed = data_file.with_suffix(".json.gz")
    with data_file.open("rb") as source, gzip.open(compressed, "wb", compresslevel=9) as target:
        target.write(source.read())

    file_id = uuid.uuid4().hex
    storage.create_file(
        bucket_id=BUCKET_ID,
        file_id=ID.custom(file_id),
        file=InputFile.from_path(str(compressed)),
    )
    pointer = {
        "file_id": file_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        tables.update_row(
            database_id=DATABASE_ID,
            table_id=TABLE_ID,
            row_id=POINTER_ID,
            data=pointer,
        )
    except AppwriteException as error:
        if error.code != 404:
            raise
        tables.create_row(
            database_id=DATABASE_ID,
            table_id=TABLE_ID,
            row_id=ID.custom(POINTER_ID),
            data=pointer,
        )
    if previous_file_id and previous_file_id != file_id:
        storage.delete_file(bucket_id=BUCKET_ID, file_id=previous_file_id)
    return file_id


def main(context):
    if context.req.method != "POST":
        return context.res.json({"error": "Use POST to run the scanner."}, 405)

    try:
        client = _client(context)
        tables = TablesDB(client)
        storage = Storage(client)
        with tempfile.TemporaryDirectory(prefix="polyedge-") as temporary_dir:
            data_file = Path(temporary_dir) / "polyedge.json"
            previous_file_id = _load_previous_state(context, tables, data_file)
            summary = refresh(Settings(storage="local", data_file=data_file))
            file_id = _publish_state(tables, storage, data_file, previous_file_id)
        context.log(f"Published scanner state {file_id}.")
        return context.res.json({"summary": summary, "state_file_id": file_id})
    except Exception as error:
        context.error(str(error))
        return context.res.json({"error": str(error)}, 500)
