"""Persistence helpers for .tellijase projects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from .project_model import Project

PathLike = Union[str, Path]
DEFAULT_EXTENSION = ".tellijase"


def ensure_extension(path: Path) -> Path:
    if path.suffix != DEFAULT_EXTENSION:
        return path.with_suffix(DEFAULT_EXTENSION)
    return path


def new_project(name: str = "Untitled") -> Project:
    project = Project()
    project.meta.name = name
    project.touch()
    return project


def load_project(path: PathLike) -> Project:
    project_path = Path(path)
    with project_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return Project.from_dict(data)


def save_project(project: Project, path: PathLike) -> Path:
    project_path = ensure_extension(Path(path))
    project_path.parent.mkdir(parents=True, exist_ok=True)
    project.touch()
    with project_path.open("w", encoding="utf-8") as handle:
        json.dump(project.to_dict(), handle, indent=2)
    return project_path
