"""CKAN and resource helpers for the Day 5 Folium mapping tutorial."""

from __future__ import annotations

import json
import mimetypes
import os
import re
from getpass import getpass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd
import requests


def get_tapis_token(username: str, password: str, *, tapis_url: str) -> str:
    response = requests.post(
        tapis_url,
        data={
            "username": username,
            "password": password,
            "grant_type": "password",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["result"]["access_token"]["access_token"]


class CKANClient:
    def __init__(self, ckan_url: str, auth_header: str):
        self.ckan_url = ckan_url.rstrip("/")
        self.headers = {"Authorization": auth_header}

    def action(
        self,
        action: str,
        *,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        json_payload: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        response = requests.request(
            method,
            f"{self.ckan_url}/api/3/action/{action}",
            headers=self.headers,
            params=params,
            json=json_payload,
            data=data,
            files=files,
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            raise RuntimeError(payload.get("error") or payload)
        return payload["result"]

    def package_show(self, dataset_id: str) -> dict[str, Any]:
        return self.action("package_show", params={"id": dataset_id})

    def package_create(
        self,
        *,
        name: str,
        title: str,
        notes: str,
        owner_org: str,
        tags: list[str] | None = None,
        private: bool = False,
        author: str | None = None,
        author_email: str | None = None,
        maintainer: str | None = None,
        maintainer_email: str | None = None,
        license_id: str | None = None,
        url: str | None = None,
        version: str | None = None,
        dataset_type: str | None = "dataset",
        isopen: bool | None = True,
        spatial: str | None = None,
        temporal_coverage_start: str | None = None,
        temporal_coverage_end: str | None = None,
        extras: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
            "title": title,
            "notes": notes,
            "owner_org": owner_org,
            "private": private,
            "tags": [{"name": slugify(tag)} for tag in tags or [] if slugify(tag)],
        }
        if dataset_type:
            payload["type"] = dataset_type
        if isopen is not None:
            payload["isopen"] = bool(isopen)

        optional_text_fields = {
            "author": author,
            "author_email": author_email,
            "maintainer": maintainer,
            "maintainer_email": maintainer_email,
            "license_id": license_id,
            "url": url,
            "version": version,
            "spatial": spatial,
            "temporal_coverage_start": temporal_coverage_start,
            "temporal_coverage_end": temporal_coverage_end,
        }
        for key, value in optional_text_fields.items():
            value = str(value or "").strip()
            if value:
                payload[key] = value
        if extras:
            payload["extras"] = extras

        return self.action(
            "package_create",
            method="POST",
            json_payload=payload,
        )

    def resource_create(
        self,
        package_id: str,
        file_path: Path,
        *,
        name: str,
        description: str,
        format_name: str,
    ) -> dict[str, Any]:
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        with file_path.open("rb") as fh:
            return self.action(
                "resource_create",
                method="POST",
                data={
                    "package_id": package_id,
                    "name": name,
                    "description": description,
                    "format": format_name,
                },
                files={"upload": (file_path.name, fh, content_type)},
            )

    def resource_update(
        self,
        resource_id: str,
        package_id: str,
        file_path: Path,
        *,
        name: str,
        description: str,
        format_name: str,
    ) -> dict[str, Any]:
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        with file_path.open("rb") as fh:
            return self.action(
                "resource_update",
                method="POST",
                data={
                    "id": resource_id,
                    "package_id": package_id,
                    "name": name,
                    "description": description,
                    "format": format_name,
                },
                files={"upload": (file_path.name, fh, content_type)},
            )

    def resource_view_list(self, resource_id: str) -> list[dict[str, Any]]:
        return self.action("resource_view_list", params={"id": resource_id})

    def resource_view_create(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.action("resource_view_create", method="POST", json_payload=payload)

    def resource_view_update(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.action("resource_view_update", method="POST", json_payload=payload)


def extract_extras(package: dict[str, Any]) -> dict[str, Any]:
    return {extra["key"]: extra["value"] for extra in package.get("extras", [])}


def extract_value(text: str | None, prefix: str, suffix: str | None = None) -> str | None:
    text = text or ""
    if prefix:
        if prefix not in text:
            return None
        value = text.split(prefix, 1)[1]
    else:
        value = text
    if suffix and suffix in value:
        value = value.split(suffix, 1)[0]
    return value.strip()


def spatial_center(spatial_text: str) -> tuple[float, float]:
    spatial = json.loads(spatial_text)
    coordinates = spatial["coordinates"]
    if spatial.get("type") == "Point":
        return coordinates[0], coordinates[1]

    if spatial.get("type") == "Polygon":
        ring = coordinates[0]
        ring_points = ring[:-1] or ring
        longitudes = [point[0] for point in ring_points]
        latitudes = [point[1] for point in ring_points]
        return sum(longitudes) / len(longitudes), sum(latitudes) / len(latitudes)

    raise ValueError(f"Unsupported spatial geometry type: {spatial.get('type')}")


def measurement_resource(package: dict[str, Any]) -> dict[str, Any]:
    for resource in package.get("resources", []):
        name = resource.get("name", "")
        if resource.get("format") == "GeoJSON" and name.endswith("-measurements"):
            return resource
    raise ValueError(f"No measurement resource found for {package['name']}")


def sensor_id_from_measurement_url(url: str) -> str | None:
    if "/sensors/" not in url:
        return None
    return url.split("/sensors/", 1)[1].split("/", 1)[0]


def discover_station_packages(
    *,
    ckan_url: str,
    campaign_tag: str,
    rows: int = 100,
) -> list[dict[str, Any]]:
    params = {
        "q": f"tags:{campaign_tag} AND tags:upstream",
        "rows": rows,
    }
    response = requests.get(
        f"{ckan_url.rstrip('/')}/api/3/action/package_search",
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(payload.get("error") or payload)
    packages = payload["result"]["results"]
    return sorted(packages, key=lambda package: int(extract_extras(package)["station_id"]))


def build_sites_dataframe(packages: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for package in packages:
        extras = extract_extras(package)
        resource = measurement_resource(package)
        measurement_url = resource["url"]
        longitude, latitude = spatial_center(package["spatial"])
        notes = package.get("notes", "")
        general_name = extract_value(notes, "", " extensometer station") or extras["station_name"]
        station_id = int(extras["station_id"])
        campaign_id = int(extras["campaign_id"])

        rows.append(
            {
                "SITE_NO": extract_value(notes, "source_site_no="),
                "STATION_NM": extras["station_name"],
                "COMPACTION_INTERVAL": extract_value(notes, "interval=", ";"),
                "ANCHOR_DEPTH": extract_value(notes, "anchor_depth=", " ft"),
                "DEC_LONG_VA": longitude,
                "DEC_LAT_VA": latitude,
                "GENERAL_NM": general_name,
                "name_condensed": general_name.replace(" ", ""),
                "campaign_id": campaign_id,
                "station_id": station_id,
                "sensor_id": sensor_id_from_measurement_url(measurement_url),
                "measurement_resource_id": resource["id"],
                "measurement_url": measurement_url,
                "dataset_name": package["name"],
                "temporal_coverage_start": package.get("temporal_coverage_start"),
                "temporal_coverage_end": package.get("temporal_coverage_end"),
            }
        )
    return pd.DataFrame(rows)


def build_ckan_client(*, ckan_url: str, tapis_token_url: str) -> CKANClient:
    username = os.environ.get("TACC_USERNAME") or input("TACC username: ").strip()
    password = os.environ.get("TACC_PASSWORD") or getpass("TACC password: ")
    auth_header = f"Bearer {get_tapis_token(username, password, tapis_url=tapis_token_url)}"
    return CKANClient(ckan_url, auth_header)


def slugify(value: str) -> str:
    value = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def create_output_dataset(
    client: CKANClient,
    *,
    name: str,
    title: str,
    notes: str,
    owner_org: str,
    tags: list[str] | None = None,
    private: bool = False,
    author: str | None = None,
    author_email: str | None = None,
    maintainer: str | None = None,
    maintainer_email: str | None = None,
    license_id: str | None = None,
    url: str | None = None,
    version: str | None = None,
    dataset_type: str | None = "dataset",
    isopen: bool | None = True,
    spatial: str | None = None,
    temporal_coverage_start: str | None = None,
    temporal_coverage_end: str | None = None,
    extras: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Create the CKAN package that will hold this run's generated HTML outputs."""
    dataset_name = slugify(name)
    if not dataset_name:
        raise ValueError("Output CKAN dataset name cannot be empty.")
    return client.package_create(
        name=dataset_name,
        title=title,
        notes=notes,
        owner_org=owner_org,
        tags=tags,
        private=private,
        author=author,
        author_email=author_email,
        maintainer=maintainer,
        maintainer_email=maintainer_email,
        license_id=license_id,
        url=url,
        version=version,
        dataset_type=dataset_type,
        isopen=isopen,
        spatial=spatial,
        temporal_coverage_start=temporal_coverage_start,
        temporal_coverage_end=temporal_coverage_end,
        extras=extras,
    )


def resource_download_url(ckan_url: str, dataset: dict[str, Any], resource: dict[str, Any]) -> str:
    filename = quote(resource.get("name") or Path(resource.get("url", "resource")).name)
    return f"{ckan_url.rstrip('/')}/dataset/{dataset['name']}/resource/{resource['id']}/download/{filename}"


def file_size_mb(file_path: str | Path) -> float:
    return Path(file_path).stat().st_size / (1024 * 1024)


def upsert_resource_by_name(
    client: CKANClient,
    dataset: dict[str, Any],
    file_path: str | Path,
    *,
    name: str | None = None,
    description: str = "",
    format_name: str = "HTML",
    max_upload_mb_warning: float = 5,
) -> dict[str, Any]:
    file_path = Path(file_path)
    resource_name = name or file_path.name
    size_mb = file_size_mb(file_path)
    if size_mb > max_upload_mb_warning:
        raise ValueError(
            f"{file_path.name} is {size_mb:.2f} MB before upload. "
            "Regenerate with smaller HTML or raise the warning threshold if the CKAN server allows it."
        )

    existing = next(
        (resource for resource in dataset.get("resources", []) if resource.get("name") == resource_name),
        None,
    )
    if existing:
        resource = client.resource_update(
            existing["id"],
            dataset["id"],
            file_path,
            name=resource_name,
            description=description,
            format_name=format_name,
        )
        dataset["resources"] = [
            resource if item.get("id") == resource["id"] else item
            for item in dataset.get("resources", [])
        ]
    else:
        resource = client.resource_create(
            dataset["id"],
            file_path,
            name=resource_name,
            description=description,
            format_name=format_name,
        )
        dataset.setdefault("resources", []).append(resource)
    return resource


def upsert_webpage_view(
    client: CKANClient,
    resource_id: str,
    *,
    title: str,
    description: str = "",
) -> dict[str, Any]:
    existing_views = client.resource_view_list(resource_id)
    existing = next((view for view in existing_views if view.get("view_type") == "webpage_view"), None)
    payload = {
        "resource_id": resource_id,
        "title": title,
        "description": description,
        "view_type": "webpage_view",
    }
    if existing:
        payload["id"] = existing["id"]
        return client.resource_view_update(payload)
    return client.resource_view_create(payload)


def ckan_package_show(ckan_url: str, dataset_id: str) -> dict[str, Any]:
    response = requests.get(
        f"{ckan_url.rstrip('/')}/api/3/action/package_show",
        params={"id": dataset_id},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(payload.get("error") or payload)
    return payload["result"]


def ckan_resource_url(ckan_url: str, dataset_id: str, resource_name: str) -> str:
    dataset = ckan_package_show(ckan_url, dataset_id)
    for resource in dataset.get("resources", []):
        if resource.get("name") == resource_name:
            return resource["url"]
    raise ValueError(f"Resource {resource_name!r} not found in {dataset_id!r}")
