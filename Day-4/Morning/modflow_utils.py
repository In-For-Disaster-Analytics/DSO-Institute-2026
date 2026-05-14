"""Shared helper functions for the Day 4 Morning MODFLOW notebooks."""

from pathlib import Path
from shutil import copy2
import json
import re
import zipfile
from urllib.parse import parse_qs, quote, unquote, urlparse
from urllib.request import Request, urlopen


__all__ = ["download_ckan_dataset", "stage_model_workspace"]


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


def _safe_filename(value):
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("._")
    return clean or "resource"


def _dataset_base_and_slug(dataset_url):
    parsed = urlparse(dataset_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid CKAN dataset URL: {dataset_url}")

    parts = [p for p in parsed.path.strip("/").split("/") if p]
    slug = ""
    if "dataset" in parts:
        i = parts.index("dataset")
        if i + 1 < len(parts):
            slug = parts[i + 1]
    if not slug:
        q = parse_qs(parsed.query)
        slug = q.get("id", [""])[0]
    if not slug and parts:
        slug = parts[-1]
    if not slug:
        raise ValueError(f"Could not determine dataset slug from URL: {dataset_url}")

    return f"{parsed.scheme}://{parsed.netloc}", unquote(slug)


def _open_url(url):
    req = Request(url, headers={"User-Agent": "flopy-interactive-notebook/1.0"})
    return urlopen(req, timeout=120)


def _load_package(dataset_url):
    base_url, dataset_slug = _dataset_base_and_slug(dataset_url)
    api_url = f"{base_url}/api/3/action/package_show?id={quote(dataset_slug)}"
    with _open_url(api_url) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if not payload.get("success"):
        raise RuntimeError(f"CKAN API package_show failed for '{dataset_slug}': {payload}")
    return base_url, dataset_slug, payload["result"]


def _download_to(url, target_path):
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with _open_url(url) as resp, open(target_path, "wb") as dst:
        dst.write(resp.read())


def download_ckan_dataset(
    dataset_url,
    data_root,
    extract_zips=True,
    overwrite=False,
    max_resources=None,
):
    base_url, dataset_slug, package = _load_package(dataset_url)
    dataset_dir = Path(data_root) / _safe_filename(dataset_slug)
    resources_dir = dataset_dir / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)

    resources = package.get("resources", [])
    if max_resources is not None:
        resources = resources[: int(max_resources)]

    print(f"CKAN base URL: {base_url}")
    print(f"Dataset slug: {dataset_slug}")
    print(f"Resource count: {len(resources)}")

    for i, res in enumerate(resources, start=1):
        url = res.get("url")
        if not url:
            print(f"  - Skipping resource {i} (missing url)")
            continue

        url_path_name = Path(urlparse(url).path).name
        raw_name = res.get("name") or url_path_name or f"resource_{i}"
        fname = _safe_filename(raw_name)

        if "." not in fname and "." in url_path_name:
            fname = f"{fname}{Path(url_path_name).suffix}"

        resource_id = (res.get("id") or f"r{i}").replace("-", "")[:8]
        out_path = resources_dir / f"{i:03d}_{resource_id}_{fname}"

        if out_path.exists() and not overwrite:
            print(f"  - Exists, skipping: {out_path}")
        else:
            print(f"  - Downloading {url} -> {out_path}")
            _download_to(url, out_path)

        if extract_zips and out_path.suffix.lower() == ".zip":
            extract_dir = dataset_dir / "extracted" / out_path.stem
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(out_path, "r") as zf:
                zf.extractall(extract_dir)
            print(f"    Extracted zip -> {extract_dir}")

    return dataset_dir
