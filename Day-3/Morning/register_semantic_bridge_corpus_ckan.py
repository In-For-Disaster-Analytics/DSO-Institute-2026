#!/usr/bin/env python3
"""Register the semantic bridge corpus as a CKAN dataset.

This script reads the seed URL metadata and the local cleaned corpus files,
creates or updates a CKAN dataset, and uploads one analysis-ready file per
source as a resource. The cleaned directory is treated as the source of truth:
if a file is not present there, it is skipped.
"""

from __future__ import annotations

import argparse
import csv
import mimetypes
import os
import re
from pathlib import Path
from typing import Any

from ckanapi import RemoteCKAN
from semantic_bridge_ckan import DEFAULT_TAPIS_URL, build_ckan_auth_header


DEFAULT_DATASET_NAME = "subsidence-groundwater-semantic-bridge-corpus"
DEFAULT_DATASET_TITLE = "Subsidence and Groundwater Semantic Bridge Corpus"
DEFAULT_DATASET_NOTES = (
    "Analysis-ready tutorial corpus for the DSO Institute semantic bridge "
    "cookbook. Each resource is a local corpus document paired with source "
    "metadata derived from the seed URL list."
)


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def resolve_tutorial_dir() -> Path:
    candidates = [Path.cwd(), *Path.cwd().parents]
    for candidate in candidates:
        direct = candidate / "semantic_bridge_cookbook.ipynb"
        nested = candidate / "DSO-Institute-2026" / "Day-3" / "Morning" / "semantic_bridge_cookbook.ipynb"
        if direct.exists():
            return candidate
        if nested.exists():
            return nested.parent
    raise FileNotFoundError("Could not locate DSO-Institute-2026/Day-3/Morning")


def parse_args() -> argparse.Namespace:
    tutorial_dir = resolve_tutorial_dir()
    default_seed_csv = tutorial_dir / "subsidence_groundwater_seed_urls.csv"
    default_manifest_csv = tutorial_dir / "data" / "subsidence_groundwater_corpus" / "metadata" / "download_manifest.csv"
    default_cleaned_dir = tutorial_dir / "data" / "subsidence_groundwater_corpus" / "cleaned"

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ckan-url", default=os.getenv("CKAN_URL", "").strip(), help="Base CKAN URL")
    parser.add_argument(
        "--auth-mode",
        default=os.getenv("CKAN_AUTH_MODE", "tapis_password").strip(),
        help="CKAN auth mode: api_token or tapis_password",
    )
    parser.add_argument(
        "--api-token",
        default=os.getenv("CKAN_API_TOKEN", os.getenv("CKAN_API_KEY", "")).strip(),
        help="CKAN API token when auth mode is api_token",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("CKAN_USERNAME", "").strip(),
        help="TACC username when auth mode is tapis_password",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("CKAN_PASSWORD", ""),
        help="TACC password when auth mode is tapis_password",
    )
    parser.add_argument(
        "--tapis-url",
        default=os.getenv("CKAN_TAPIS_URL", DEFAULT_TAPIS_URL).strip(),
        help="Tapis token endpoint for tapis_password authentication",
    )
    parser.add_argument(
        "--owner-org",
        default=os.getenv("CKAN_OWNER_ORG", "").strip(),
        help="Owner organization to assign when creating the dataset",
    )
    parser.add_argument("--dataset-name", default=os.getenv("CKAN_DATASET_NAME", DEFAULT_DATASET_NAME))
    parser.add_argument("--dataset-title", default=os.getenv("CKAN_DATASET_TITLE", DEFAULT_DATASET_TITLE))
    parser.add_argument("--dataset-notes", default=DEFAULT_DATASET_NOTES)
    parser.add_argument("--seed-csv", default=str(default_seed_csv))
    parser.add_argument("--manifest-csv", default=str(default_manifest_csv))
    parser.add_argument("--cleaned-dir", default=str(default_cleaned_dir))
    parser.add_argument("--private", action="store_true", help="Create the dataset as private")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing to CKAN")
    return parser.parse_args()


def load_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def nullable_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def resolve_resource_path(row: dict[str, str], cleaned_dir: Path) -> Path:
    extracted_path = nullable_str(row.get("extracted_text_path"))
    saved_path = nullable_str(row.get("saved_path"))
    title = row.get("title") or row.get("name") or ""

    candidates: list[Path] = []
    if extracted_path:
        extracted_candidate = Path(extracted_path)
        candidates.append(cleaned_dir / extracted_candidate.name)
        candidates.append(extracted_candidate)
    if saved_path:
        saved_candidate = Path(saved_path)
        candidates.append(cleaned_dir / saved_candidate.name)
    if title:
        title_slug = slugify(title)
        candidates.extend(sorted(cleaned_dir.glob(f"{title_slug}.*")))

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate

    raise FileNotFoundError(f"No cleaned corpus file found for {row.get('title') or row.get('name')}")


def build_resource_description(seed_row: dict[str, str], manifest_row: dict[str, str], resource_path: Path) -> str:
    parts = [
        f"Tutorial title: {seed_row['title']}",
        f"Category: {seed_row['category']}",
        f"Original source URL: {seed_row['url']}",
        f"Local corpus file: {resource_path.name}",
    ]
    notes = nullable_str(seed_row.get("notes"))
    if notes:
        parts.append(f"Notes: {notes}")
    final_url = nullable_str(manifest_row.get("final_url"))
    if final_url and final_url != seed_row["url"]:
        parts.append(f"Resolved source URL: {final_url}")
    page_title = nullable_str(manifest_row.get("page_title"))
    if page_title:
        parts.append(f"Captured page title: {page_title}")
    return "\n".join(parts)


def dataset_tags(seed_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    tags = {slugify(row["category"]) for row in seed_rows}
    tags.add("semantic-bridge")
    tags.add("tutorial-corpus")
    return [{"name": tag} for tag in sorted(tags) if tag]


def ensure_dataset(
    ckan: RemoteCKAN,
    *,
    dataset_name: str,
    dataset_title: str,
    dataset_notes: str,
    owner_org: str | None,
    private: bool,
    tags: list[dict[str, str]],
    dry_run: bool,
) -> dict[str, Any]:
    package_payload = {
        "name": dataset_name,
        "title": dataset_title,
        "notes": dataset_notes,
        "private": private,
        "tags": tags,
    }
    if owner_org:
        package_payload["owner_org"] = owner_org

    if dry_run:
        print(f"[dry-run] Would create or update dataset: {dataset_name}")
        return {"name": dataset_name, "resources": []}

    try:
        existing = ckan.action.package_show(id=dataset_name)
    except Exception:
        return ckan.action.package_create(**package_payload)

    package_payload["id"] = existing["id"]
    return ckan.action.package_patch(**package_payload)


def existing_resources_by_name(dataset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {resource["name"]: resource for resource in dataset.get("resources", [])}


def upload_resource(
    ckan: RemoteCKAN,
    dataset: dict[str, Any],
    *,
    resource_name: str,
    resource_path: Path,
    source_url: str,
    description: str,
    resource_format: str,
    dry_run: bool,
) -> None:
    mimetype = mimetypes.guess_type(resource_path.name)[0]
    existing = existing_resources_by_name(dataset).get(resource_name)

    payload: dict[str, Any] = {
        "package_id": dataset["name"],
        "name": resource_name,
        "description": description,
        "format": resource_format,
        "url": source_url,
    }
    if mimetype:
        payload["mimetype"] = mimetype

    if dry_run:
        action = "update" if existing else "create"
        print(f"[dry-run] Would {action} resource {resource_name} from {resource_path}")
        return

    with resource_path.open("rb") as handle:
        payload["upload"] = handle
        if existing:
            payload["id"] = existing["id"]
            ckan.action.resource_update(**payload)
        else:
            ckan.action.resource_create(**payload)


def main() -> None:
    args = parse_args()
    if not args.ckan_url:
        raise SystemExit("CKAN URL is required. Set --ckan-url or CKAN_URL.")

    seed_rows = load_csv_rows(Path(args.seed_csv))
    manifest_rows = load_csv_rows(Path(args.manifest_csv))
    cleaned_dir = Path(args.cleaned_dir)
    manifest_by_title = {row["title"]: row for row in manifest_rows}

    auth_header = build_ckan_auth_header(
        auth_mode=args.auth_mode,
        api_token=args.api_token,
        username=args.username,
        password=args.password,
        tapis_url=args.tapis_url,
    )
    ckan = RemoteCKAN(args.ckan_url, apikey=auth_header or None, user_agent="semantic-bridge-corpus-uploader/1.0")
    dataset = ensure_dataset(
        ckan,
        dataset_name=args.dataset_name,
        dataset_title=args.dataset_title,
        dataset_notes=args.dataset_notes,
        owner_org=args.owner_org or None,
        private=args.private,
        tags=dataset_tags(seed_rows),
        dry_run=args.dry_run,
    )

    uploaded = 0
    for seed_row in seed_rows:
        manifest_row = manifest_by_title.get(seed_row["title"])
        if manifest_row is None:
            print(f"Skipping {seed_row['title']}: not found in download_manifest.csv")
            continue

        try:
            resource_path = resolve_resource_path(manifest_row, cleaned_dir)
        except FileNotFoundError as exc:
            print(f"Skipping {seed_row['title']}: {exc}")
            continue

        resource_name = resource_path.name
        description = build_resource_description(seed_row, manifest_row, resource_path)
        resource_format = resource_path.suffix.lstrip(".").upper() or manifest_row.get("content_type", "FILE")
        upload_resource(
            ckan,
            dataset,
            resource_name=resource_name,
            resource_path=resource_path,
            source_url=seed_row["url"],
            description=description,
            resource_format=resource_format,
            dry_run=args.dry_run,
        )
        uploaded += 1

    print(f"Processed {uploaded} corpus resources for dataset {args.dataset_name}")


if __name__ == "__main__":
    main()
