from typing import Any

from fastapi import APIRouter, HTTPException, Request

from geo_app.models.schemas import FilterQuery, NearestQuery, SpatialJoinQuery
from geo_app.services.spatial_query import (
    query_bbox,
    query_filter,
    query_nearest,
    query_spatial_join,
)

router = APIRouter(prefix="/api/query", tags=["query"])


@router.get("/bbox")
async def bbox_query(
    request: Request,
    dataset: str,
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    limit: int = 1000,
) -> dict[str, Any]:
    db = request.app.state.db
    try:
        return query_bbox(db, dataset, minx, miny, maxx, maxy, min(limit, 10000))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.post("/nearest")
async def nearest_query(request: Request, body: NearestQuery) -> dict[str, Any]:
    db = request.app.state.db
    try:
        return query_nearest(db, body.dataset, body.lon, body.lat, body.k)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.post("/spatial-join")
async def spatial_join_query(request: Request, body: SpatialJoinQuery) -> dict[str, Any]:
    db = request.app.state.db
    try:
        return query_spatial_join(
            db, body.left_dataset, body.right_dataset, body.predicate, body.limit
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.post("/filter")
async def filter_query(request: Request, body: FilterQuery) -> dict[str, Any]:
    db = request.app.state.db
    try:
        return query_filter(db, body.dataset, body.filters, body.limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from None
