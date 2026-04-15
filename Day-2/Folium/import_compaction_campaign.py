#!/usr/bin/env python3
"""Create an Upstream campaign, stations, and compaction sensor uploads.

This script uses the official `upstream-sdk` workflow:

1. create a campaign with `CampaignsIn`
2. create one station per row in `TABLE1_CompactionSites.csv`
3. generate `sensors.csv` and `measurements.csv` for each station
4. upload those files with `UpstreamClient.upload_csv_data()`
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from upstream.client import UpstreamClient
    from upstream_api_client.models import CampaignsIn, StationCreate


DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "csv_files"
SITE_TABLE_NAME = "TABLE1_CompactionSites.csv"
SENSOR_ALIAS = "cumulative_compaction"
SENSOR_VARIABLE_NAME = "Cumulative Compaction"


@dataclass
class Measurement:
    timestamp: datetime
    value: float


@dataclass
class StationRecord:
    site_no: str
    station_name: str
    general_name: str
    compaction_interval: str
    anchor_depth_ft: int | None
    longitude: float
    latitude: float
    measurement_file: Path
    measurements: list[Measurement]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create an Upstream campaign and upload compaction time series.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=f"Directory containing the compaction CSV files. Default: {DEFAULT_DATA_DIR}",
    )
    parser.add_argument(
        "--campaign-name",
        default="Houston-area extensometer compaction campaign",
        help="Campaign name for Upstream.",
    )
    parser.add_argument(
        "--campaign-description",
        default=(
            "USGS cumulative compaction measurements from Houston-area extensometer "
            "stations used in the DSO Institute 2026 Day 2 Folium exercise."
        ),
        help="Campaign description for Upstream.",
    )
    parser.add_argument(
        "--allocation",
        default=os.environ.get("UPSTREAM_ALLOCATION", "TACC"),
        help="Required Upstream allocation value. Defaults to $UPSTREAM_ALLOCATION or TACC.",
    )
    parser.add_argument(
        "--contact-name",
        default=os.environ.get("UPSTREAM_CONTACT_NAME", "DSO Institute"),
        help="Contact name for campaigns and stations.",
    )
    parser.add_argument(
        "--contact-email",
        default=os.environ.get("UPSTREAM_CONTACT_EMAIL", ""),
        help="Contact email for campaigns and stations.",
    )
    parser.add_argument(
        "--station-type",
        default=os.environ.get("UPSTREAM_STATION_TYPE"),
        help="Optional station_type value if your Upstream deployment requires one.",
    )
    parser.add_argument(
        "--unit",
        default="feet",
        help="Units written to the generated sensors.csv file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be created without calling Upstream.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stations = load_station_records(args.data_dir.resolve())

    campaign_start = min(station.measurements[0].timestamp for station in stations)
    campaign_end = max(station.measurements[-1].timestamp for station in stations)

    if args.dry_run:
        print(f"[dry-run] campaign={args.campaign_name!r} stations={len(stations)}")
        print(
            f"[dry-run] campaign_start={campaign_start.isoformat()} "
            f"campaign_end={campaign_end.isoformat()} allocation={args.allocation!r}"
        )
        for station in stations:
            print(
                f"[dry-run] station={station.general_name!r} site_no={station.site_no} "
                f"measurements={len(station.measurements)} file={station.measurement_file.name}"
            )
        return 0

    client = build_client()
    CampaignsIn, StationCreate = import_upstream_models()

    campaign_data = CampaignsIn(
        name=args.campaign_name,
        description=args.campaign_description,
        contact_name=args.contact_name or None,
        contact_email=args.contact_email or None,
        allocation=args.allocation,
        start_date=campaign_start,
        end_date=campaign_end,
    )
    campaign = client.create_campaign(campaign_data)
    campaign_id = int(campaign.id)
    print(f"Campaign created: {campaign_id}")

    for station in stations:
        station_kwargs: dict[str, Any] = {
            "name": station.station_name,
            "description": build_station_description(station),
            "contact_name": args.contact_name or None,
            "contact_email": args.contact_email or None,
            "start_date": station.measurements[0].timestamp,
        }
        if args.station_type:
            station_kwargs["station_type"] = args.station_type

        station_data = StationCreate(**station_kwargs)
        created_station = client.create_station(campaign_id, station_data)
        station_id = int(created_station.id)

        with tempfile.TemporaryDirectory(prefix=f"upstream-{station.site_no}-") as temp_dir:
            temp_path = Path(temp_dir)
            sensors_csv = temp_path / "sensors.csv"
            measurements_csv = temp_path / "measurements.csv"
            write_sensors_csv(sensors_csv, unit=args.unit)
            write_measurements_csv(measurements_csv, station)
            result = client.upload_csv_data(
                campaign_id=campaign_id,
                station_id=station_id,
                sensors_file=sensors_csv,
                measurements_file=measurements_csv,
            )

        response = result.get("response", result)
        print(
            f"Station created: {station.general_name} -> {station_id}; "
            f"sensors={response.get('Total sensors processed', 'n/a')} "
            f"measurements={response.get('Total measurements added to database', 'n/a')}"
        )

    return 0


def build_client() -> "UpstreamClient":
    try:
        from upstream.client import UpstreamClient
    except ImportError as exc:
        raise RuntimeError(
            "upstream-sdk is not installed. Install it with `python3 -m pip install upstream-sdk`."
        ) from exc

    username = os.environ.get("UPSTREAM_USERNAME", "").strip()
    password = os.environ.get("UPSTREAM_PASSWORD", "").strip()
    base_url = os.environ.get("UPSTREAM_BASE_URL", "").strip()

    if not username or not password or not base_url:
        raise RuntimeError(
            "Set UPSTREAM_USERNAME, UPSTREAM_PASSWORD, and UPSTREAM_BASE_URL before running."
        )

    client = UpstreamClient(
        username=username,
        password=password,
        base_url=base_url,
        ckan_url=os.environ.get("CKAN_URL"),
        ckan_organization=os.environ.get("CKAN_ORGANIZATION"),
    )
    if not client.authenticate():
        raise RuntimeError("Upstream authentication failed.")
    return client


def import_upstream_models() -> tuple[type["CampaignsIn"], type["StationCreate"]]:
    try:
        from upstream_api_client.models import CampaignsIn, StationCreate
    except ImportError as exc:
        raise RuntimeError(
            "upstream-api-client is not available. It should be installed with upstream-sdk."
        ) from exc
    return CampaignsIn, StationCreate


def load_station_records(data_dir: Path) -> list[StationRecord]:
    site_table = data_dir / SITE_TABLE_NAME
    if not site_table.exists():
        raise FileNotFoundError(f"Missing station metadata file: {site_table}")

    measurement_files = {
        normalize_name(path.stem): path
        for path in data_dir.glob("TABLE*.csv")
        if path.name != SITE_TABLE_NAME
    }
    stations: list[StationRecord] = []

    with site_table.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            general_name = require_value(row, "GENERAL_NM")
            measurement_file = resolve_measurement_file(general_name, measurement_files)
            measurements = load_measurements(measurement_file)
            stations.append(
                StationRecord(
                    site_no=require_value(row, "SITE_NO"),
                    station_name=require_value(row, "STATION_NM"),
                    general_name=general_name,
                    compaction_interval=require_value(row, "COMPACTION_INTERVAL"),
                    anchor_depth_ft=parse_int(row.get("ANCHOR_DEPTH")),
                    longitude=float(require_value(row, "DEC_LONG_VA")),
                    latitude=float(require_value(row, "DEC_LAT_VA")),
                    measurement_file=measurement_file,
                    measurements=measurements,
                )
            )

    return stations


def load_measurements(path: Path) -> list[Measurement]:
    measurements: list[Measurement] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            measurements.append(
                Measurement(
                    timestamp=datetime.strptime(require_value(row, "DATE"), "%m/%d/%Y").replace(tzinfo=UTC),
                    value=float(require_value(row, "CUMULATIVE_COMPACTION")),
                )
            )
    if not measurements:
        raise ValueError(f"No measurements found in {path}")
    return measurements


def write_sensors_csv(path: Path, *, unit: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["alias", "variablename", "units", "postprocess", "postprocessscript"])
        writer.writerow([SENSOR_ALIAS, SENSOR_VARIABLE_NAME, unit, "false", ""])


def write_measurements_csv(path: Path, station: StationRecord) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["collectiontime", "Lat_deg", "Lon_deg", SENSOR_ALIAS])
        for measurement in station.measurements:
            writer.writerow(
                [
                    measurement.timestamp.replace(tzinfo=None).isoformat(timespec="seconds"),
                    station.latitude,
                    station.longitude,
                    measurement.value,
                ]
            )


def build_station_description(station: StationRecord) -> str:
    depth = f"{station.anchor_depth_ft} ft" if station.anchor_depth_ft is not None else "unknown depth"
    return (
        f"{station.general_name} extensometer station; interval={station.compaction_interval}; "
        f"anchor_depth={depth}; source_site_no={station.site_no}"
    )


def resolve_measurement_file(general_name: str, measurement_files: dict[str, Path]) -> Path:
    aliases = {
        "baytownshallow": "table13baytownc1shallow2023",
        "baytowndeep": "table14baytownc2deep2023",
        "johnsonspacecenter": "table9johnsonspacecenternasa2023",
        "fortbend": "table15fortbendcincomud2023",
        "clearlakeshallow": "table11clearlakeshallow2023",
        "clearlakedeep": "table12clearlakedeep2023",
        "texascity": "table3texascity2023",
        "lakehouston": "table8lakehouston2023",
    }
    key = normalize_name(general_name)
    candidates = [aliases.get(key), key]

    for candidate in candidates:
        if candidate and candidate in measurement_files:
            return measurement_files[candidate]

    for normalized_name, path in measurement_files.items():
        if key in normalized_name or normalized_name in key:
            return path

    raise KeyError(f"Could not match measurement file for station {general_name!r}")


def require_value(row: dict[str, str | None], key: str) -> str:
    value = (row.get(key) or "").strip()
    if not value:
        raise ValueError(f"Missing required field {key!r} in row: {row}")
    return value


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    stripped = value.strip().replace(",", "")
    if not stripped:
        return None
    return int(stripped)


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
