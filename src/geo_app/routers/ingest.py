from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile

from geo_app.dependencies import require_writable
from geo_app.models.schemas import IngestFromURLRequest, IngestResponse
from geo_app.naming import sanitize_name
from geo_app.services.ingestion import ingest_file, new_upload_path
from geo_app.services.safe_fetch import DownloadTooLargeError, download_to_file

router = APIRouter(prefix="/api/ingest", tags=["ingest"], dependencies=[Depends(require_writable)])

_CHUNK_SIZE = 1024 * 1024


@router.post("/upload", response_model=IngestResponse)
async def upload_file(request: Request, file: UploadFile) -> IngestResponse:
    settings = request.app.state.settings
    db = request.app.state.db

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # The client filename is untrusted: it only supplies the extension and a label
    try:
        upload_path = new_upload_path(settings, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    written = 0
    try:
        with upload_path.open("wb") as fh:
            while chunk := await file.read(_CHUNK_SIZE):
                written += len(chunk)
                if written > settings.max_upload_bytes:
                    raise HTTPException(status_code=413, detail="File exceeds MAX_UPLOAD_MB")
                fh.write(chunk)
    except BaseException:
        upload_path.unlink(missing_ok=True)
        raise

    try:
        result = ingest_file(
            db=db,
            settings=settings,
            file_path=upload_path,
            original_filename=file.filename,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    return IngestResponse(**result)


@router.post("/from-url", response_model=IngestResponse)
async def ingest_from_url(request: Request, body: IngestFromURLRequest) -> IngestResponse:
    settings = request.app.state.settings
    db = request.app.state.db

    filename = Path(urlsplit(body.url).path).name or "download"
    name = body.name or sanitize_name(filename)

    try:
        download_path = new_upload_path(settings, filename)
        await download_to_file(body.url, download_path, settings.max_upload_bytes)
    except DownloadTooLargeError as e:
        raise HTTPException(status_code=413, detail=str(e)) from None
    except ValueError as e:
        # UnsafeURLError / DownloadError messages are generated here, not by upstream
        raise HTTPException(status_code=400, detail=str(e)) from None

    try:
        result = ingest_file(
            db=db,
            settings=settings,
            file_path=download_path,
            original_filename=filename,
            dataset_name=name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    return IngestResponse(**result)
