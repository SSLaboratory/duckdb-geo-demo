from datetime import datetime

from pydantic import BaseModel, Field

from geo_app.naming import DATASET_NAME_PATTERN


class DatasetInfo(BaseModel):
    name: str
    original_filename: str | None = None
    format: str | None = None
    geometry_type: str | None = None
    feature_count: int | None = None
    bbox: list[float] | None = None
    created_at: datetime | None = None


class DatasetList(BaseModel):
    datasets: list[DatasetInfo]
    count: int


class IngestResponse(BaseModel):
    status: str
    dataset_name: str
    feature_count: int | None = None
    geometry_type: str | None = None


class IngestFromURLRequest(BaseModel):
    url: str = Field(max_length=2048)
    name: str | None = Field(default=None, pattern=DATASET_NAME_PATTERN)


class BboxQuery(BaseModel):
    dataset: str
    minx: float
    miny: float
    maxx: float
    maxy: float
    limit: int = Field(default=1000, le=10000)


class NearestQuery(BaseModel):
    dataset: str
    lon: float
    lat: float
    k: int = Field(default=5, le=100)


class SpatialJoinQuery(BaseModel):
    left_dataset: str
    right_dataset: str
    predicate: str = "st_intersects"
    limit: int = Field(default=1000, le=10000)


class AttributeFilter(BaseModel):
    column: str
    op: str = Field(description="Operator: eq, ne, gt, lt, gte, lte, like")
    value: str | int | float


class FilterQuery(BaseModel):
    dataset: str
    filters: list[AttributeFilter] = Field(default_factory=list)
    limit: int = Field(default=1000, le=10000)


class BuiltinDataset(BaseModel):
    id: str
    name: str
    description: str
    url: str
    format: str


class BuiltinLoadRequest(BaseModel):
    dataset: str


class ErrorResponse(BaseModel):
    detail: str
