from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Request, UploadFile

from geo_app.models.schemas import IngestFromURLRequest, IngestResponse
from geo_app.services.ingestion import ingest_file, sanitize_name

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("/upload", response_model=IngestResponse)
async def upload_file(request: Request, file: UploadFile) -> IngestResponse:
    settings = request.app.state.settings
    db = request.app.state.db

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    upload_path = settings.upload_dir / file.filename
    content = await file.read()
    upload_path.write_bytes(content)

    try:
        result = ingest_file(
            db=db,
            settings=settings,
            file_path=upload_path,
            original_filename=file.filename,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    return IngestResponse(**result)


@router.post("/from-url", response_model=IngestResponse)
async def ingest_from_url(request: Request, body: IngestFromURLRequest) -> IngestResponse:
    settings = request.app.state.settings
    db = request.app.state.db

    # Derive filename from URL
    url_path = Path(body.url.split("?")[0].split("#")[0])
    filename = url_path.name or "download"
    name = body.name or sanitize_name(filename)

    download_path = settings.upload_dir / filename

    try:
        headers = {"User-Agent": "duckdb-geo-demo/0.1.0"}
        async with httpx.AsyncClient(timeout=120.0, headers=headers) as client:
            resp = await client.get(body.url, follow_redirects=True)
            resp.raise_for_status()
            download_path.write_bytes(resp.content)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Download failed: {e}") from None

    try:
        result = ingest_file(
            db=db,
            settings=settings,
            file_path=download_path,
            original_filename=filename,
            dataset_name=name,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    return IngestResponse(**result)
