from fastapi import APIRouter, HTTPException, Request

from geo_app.models.schemas import BuiltinDataset, BuiltinLoadRequest, IngestResponse
from geo_app.services.builtin_datasets import get_available, load_builtin

router = APIRouter(prefix="/api/builtins", tags=["builtins"])


@router.get("/available")
async def list_available() -> list[BuiltinDataset]:
    return get_available()


@router.post("/load", response_model=IngestResponse)
async def load_dataset(request: Request, body: BuiltinLoadRequest) -> IngestResponse:
    db = request.app.state.db
    settings = request.app.state.settings
    try:
        result = await load_builtin(db, settings, body.dataset)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from None

    return IngestResponse(**result)
