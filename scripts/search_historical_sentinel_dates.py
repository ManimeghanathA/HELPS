from pathlib import Path
from datetime import date, timedelta
import json

import geopandas as gpd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]

AOI_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "Bhadra"
    / "bhadra_entire_region.geojson"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "Sentinel2"
    / "historical_scene_candidates.json"
)


STAC_URL = "https://stac.dataspace.copernicus.eu/v1/search"

COLLECTION = "sentinel-2-l2a"

MAX_CLOUD = 15.0


# ------------------------------------------------------------
# SEARCH WINDOW
# ------------------------------------------------------------

# Search one year before our current June 1 reference date.
START_DATE = date(2025, 6, 1)

# Do NOT include June 1 itself.
END_DATE = date(2026, 5, 31)


def month_key_for(record):
    return record["date"][:7]


def best_record_per_month(records):
    best = {}
    for record in records:
        if not record.get("date") or record.get("cloud_cover") is None:
            continue
        month_key = month_key_for(record)
        current = best.get(month_key)
        if current is None or record["cloud_cover"] < current["cloud_cover"]:
            best[month_key] = record
    return [
        {
            "month": month,
            "date": record["date"],
            "cloud_cover": record["cloud_cover"],
            "product_id": record.get("product_id"),
        }
        for month, record in sorted(best.items())
    ]


def month_ranges(start_date, end_date):
    current = date(
        start_date.year,
        start_date.month,
        1,
    )

    while current <= end_date:

        if current.month == 12:
            next_month = date(
                current.year + 1,
                1,
                1,
            )
        else:
            next_month = date(
                current.year,
                current.month + 1,
                1,
            )

        month_end = next_month - timedelta(days=1)

        search_start = max(
            current,
            start_date,
        )

        search_end = min(
            month_end,
            end_date,
        )

        yield search_start, search_end

        current = next_month


def load_aoi_bbox():
    gdf = gpd.read_file(
        AOI_PATH
    )

    if gdf.empty:
        raise ValueError(
            "AOI GeoJSON contains no features."
        )

    if gdf.crs is None:
        raise ValueError(
            "AOI GeoJSON has no CRS."
        )

    gdf = gdf.to_crs(
        "EPSG:4326"
    )

    minx, miny, maxx, maxy = (
        gdf.total_bounds
    )

    return [
        float(minx),
        float(miny),
        float(maxx),
        float(maxy),
    ]


def search_month(
    bbox,
    start_date,
    end_date,
):

    datetime_range = (
        f"{start_date.isoformat()}T00:00:00Z/"
        f"{end_date.isoformat()}T23:59:59Z"
    )

    payload = {
        "collections": [
            COLLECTION
        ],
        "bbox": bbox,
        "datetime": datetime_range,
        "query": {
            "eo:cloud_cover": {
                "lt": MAX_CLOUD
            }
        },
        "sortby": [
            {
                "field": "eo:cloud_cover",
                "direction": "asc",
            }
        ],
        "limit": 100,
    }

    response = requests.post(
        STAC_URL,
        json=payload,
        timeout=60,
    )

    response.raise_for_status()

    result = response.json()

    return result.get(
        "features",
        [],
    )


def extract_record(item):

    properties = item.get(
        "properties",
        {},
    )

    datetime_value = properties.get(
        "datetime"
    )

    cloud_cover = properties.get(
        "eo:cloud_cover"
    )

    return {
        "date": (
            datetime_value[:10]
            if datetime_value
            else None
        ),
        "datetime": datetime_value,
        "cloud_cover": cloud_cover,
        "product_id": item.get(
            "id"
        ),
        "collection": item.get(
            "collection"
        ),
    }


def main():

    print("=" * 90)
    print("HELPSs — HISTORICAL SENTINEL-2 DATE SEARCH")
    print("=" * 90)

    print(
        f"AOI        : {AOI_PATH}"
    )

    print(
        f"Period     : {START_DATE} → {END_DATE}"
    )

    print(
        f"Cloud limit: < {MAX_CLOUD}%"
    )

    print(
        f"Collection : {COLLECTION}"
    )

    print()

    bbox = load_aoi_bbox()

    print(
        "AOI WGS84 bounds:"
    )

    print(
        f"  West  : {bbox[0]:.6f}"
    )

    print(
        f"  South : {bbox[1]:.6f}"
    )

    print(
        f"  East  : {bbox[2]:.6f}"
    )

    print(
        f"  North : {bbox[3]:.6f}"
    )

    all_records = []

    monthly_results = {}

    for month_start, month_end in month_ranges(
        START_DATE,
        END_DATE,
    ):

        month_key = (
            f"{month_start.year}-"
            f"{month_start.month:02d}"
        )

        print()
        print("=" * 90)

        print(
            f"{month_key} | "
            f"{month_start} → {month_end}"
        )

        print("=" * 90)

        try:

            features = search_month(
                bbox=bbox,
                start_date=month_start,
                end_date=month_end,
            )

        except requests.RequestException as exc:

            print(
                f"SEARCH FAILED: {exc}"
            )

            monthly_results[
                month_key
            ] = []

            continue

        records = [
            extract_record(item)
            for item in features
        ]

        records = [
            record
            for record in records
            if (
                record["date"] is not None
                and
                record["cloud_cover"] is not None
            )
        ]

        records.sort(
            key=lambda x: (
                x["cloud_cover"],
                x["datetime"],
            )
        )

        monthly_results[
            month_key
        ] = records

        all_records.extend(
            records
        )

        if not records:

            print(
                "No scenes below cloud threshold."
            )

            continue

        for i, record in enumerate(
            records,
            start=1,
        ):

            print(
                f"{i:>3}. "
                f"{record['date']} | "
                f"cloud={record['cloud_cover']:.2f}%"
            )

            print(
                f"     {record['product_id']}"
            )

    # --------------------------------------------------------
    # UNIQUE DATES
    # --------------------------------------------------------

    unique_dates = {}

    for record in all_records:

        scene_date = record[
            "date"
        ]

        # Multiple Sentinel products can occur on the same day.
        # Keep the lowest-cloud product as the representative.
        if (
            scene_date not in unique_dates
            or
            record["cloud_cover"]
            <
            unique_dates[
                scene_date
            ]["cloud_cover"]
        ):

            unique_dates[
                scene_date
            ] = record

    unique_records = sorted(
        unique_dates.values(),
        key=lambda x: x["date"],
    )

    print()
    print()
    print("=" * 90)
    print("ALL UNIQUE DATES WITH CLOUD < 15%")
    print("=" * 90)

    for record in unique_records:

        print(
            f"{record['date']} | "
            f"{record['cloud_cover']:.2f}%"
        )

    print()
    print(
        f"Total qualifying products : "
        f"{len(all_records)}"
    )

    print(
        f"Total unique dates        : "
        f"{len(unique_records)}"
    )

    # --------------------------------------------------------
    # BEST DATE PER MONTH
    # --------------------------------------------------------

    best_per_month = best_record_per_month(all_records)

    print()
    print("=" * 90)
    print("BEST LOW-CLOUD DATE PER MONTH")
    print("=" * 90)

    by_month = {
        record["month"]: record
        for record in best_per_month
    }


def scan_historical_dates():
    bbox = load_aoi_bbox()
    all_records = []
    monthly_results = {}
    for month_start, month_end in month_ranges(
        START_DATE,
        END_DATE,
    ):
        month_key = (
            f"{month_start.year}-"
            f"{month_start.month:02d}"
        )
        features = search_month(
            bbox=bbox,
            start_date=month_start,
            end_date=month_end,
        )
        records = [
            extract_record(item)
            for item in features
        ]
        records = [
            record
            for record in records
            if (
                record["date"] is not None
                and
                record["cloud_cover"] is not None
            )
        ]
        records.sort(
            key=lambda x: (
                x["cloud_cover"],
                x["datetime"],
            )
        )
        monthly_results[month_key] = records
        all_records.extend(records)
    unique_dates = {}
    for record in all_records:
        scene_date = record["date"]
        if (
            scene_date not in unique_dates
            or record["cloud_cover"] < unique_dates[scene_date]["cloud_cover"]
        ):
            unique_dates[scene_date] = record
    unique_records = sorted(
        unique_dates.values(),
        key=lambda x: x["date"],
    )
    return {
        "aoi": str(AOI_PATH),
        "start_date": str(START_DATE),
        "end_date": str(END_DATE),
        "maximum_cloud_percent": MAX_CLOUD,
        "note": (
            "eo:cloud_cover is Sentinel product metadata "
            "cloud cover, not exact AOI-specific cloud cover."
        ),
        "unique_qualifying_dates": unique_records,
        "best_date_per_month": best_record_per_month(all_records),
        "monthly_results": monthly_results,
    }

    for month_key in monthly_results:

        best = by_month.get(month_key)

        if best is None:

            print(
                f"{month_key} : NONE"
            )

            continue

        print(
            f"{month_key} : "
            f"{best['date']} | "
            f"{best['cloud_cover']:.2f}%"
        )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {
        "aoi": str(AOI_PATH),
        "start_date": str(
            START_DATE
        ),
        "end_date": str(
            END_DATE
        ),
        "maximum_cloud_percent": (
            MAX_CLOUD
        ),
        "note": (
            "eo:cloud_cover is Sentinel product metadata "
            "cloud cover, not exact AOI-specific cloud cover."
        ),
        "unique_qualifying_dates": (
            unique_records
        ),
        "best_date_per_month": (
            best_per_month
        ),
        "monthly_results": (
            monthly_results
        ),
    }

    with open(
        OUTPUT_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            output,
            file,
            indent=2,
        )

    print()
    print("=" * 90)

    print(
        f"Saved search results:\n"
        f"{OUTPUT_PATH}"
    )

    print("=" * 90)


if __name__ == "__main__":
    main()
