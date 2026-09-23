import re
from pathlib import Path

DATASET_NAME_PATTERN = r"^[a-z][a-z0-9_]{0,62}$"
_DATASET_NAME_RE = re.compile(DATASET_NAME_PATTERN)


def is_valid_dataset_name(name: str) -> bool:
    return bool(_DATASET_NAME_RE.fullmatch(name))


def validate_dataset_name(name: str) -> str:
    if not is_valid_dataset_name(name):
        raise ValueError(f"Invalid dataset name: must match {DATASET_NAME_PATTERN}")
    return name


def sanitize_name(name: str) -> str:
    name = Path(name).stem
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_").lower()
    name = name or "dataset"
    if not name[0].isalpha():
        name = f"ds_{name}"
    return name[:63]
