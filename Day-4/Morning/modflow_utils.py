"""Shared helper functions for the Day 4 Morning MODFLOW notebooks."""

from pathlib import Path
from shutil import copy2


__all__ = ["stage_model_workspace"]


def stage_model_workspace(source_dir, target_dir, overwrite=True):
    source_dir = Path(source_dir)
    target_dir = Path(target_dir)
    copied_files = 0

    if not source_dir.exists():
        raise FileNotFoundError(f"Model directory not found: {source_dir}")

    target_dir.mkdir(parents=True, exist_ok=True)

    for src_path in source_dir.rglob("*"):
        rel_path = src_path.relative_to(source_dir)
        dst_path = target_dir / rel_path

        if src_path.is_dir():
            dst_path.mkdir(parents=True, exist_ok=True)
            continue

        if not src_path.is_file():
            continue

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if overwrite or not dst_path.exists():
            copy2(src_path, dst_path)
            copied_files += 1

    print(f"Staged {copied_files} files into {target_dir}")
    return target_dir
