from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

OUT = Path(__file__).with_name("results")
LOOKUP_RESULTS = OUT / "catastro_page5_results.json"
ENDPOINT = "https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx"


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def texts(root: ET.Element, name: str) -> list[str]:
    return [
        element.text.strip()
        for element in root.iter()
        if local(element.tag) == name and element.text and element.text.strip()
    ]


def make_session() -> requests.Session:
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=0.7,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": "BaldoPage5AreaValidator/1.0"})
    return session


def main() -> None:
    lookups = json.loads(LOOKUP_RESULTS.read_text(encoding="utf-8"))
    valid = [row for row in lookups if row.get("state") == "VALIDADA" and row.get("parcel_reference")]
    session = make_session()
    results = []

    for index, row in enumerate(valid, 1):
        params = {
            "service": "wfs",
            "version": "2",
            "request": "getfeature",
            "STOREDQUERIE_ID": "GetParcel",
            "refcat": row["parcel_reference"],
            "srsname": "EPSG::25830",
        }
        result = {
            "id": row["id"],
            "parcel_reference": row["parcel_reference"],
            "polygon": row.get("polygon"),
            "parcel": row.get("parcel"),
            "official_place": row.get("official_place", ""),
            "state": "ERROR",
        }
        try:
            response = session.get(ENDPOINT, params=params, timeout=(15, 45))
            response.raise_for_status()
            result["query_url"] = response.url
            root = ET.fromstring(response.content)
            refs = texts(root, "nationalCadastralReference")
            areas = texts(root, "areaValue")
            raw = areas[0] if areas else ""
            area_m2 = float(raw.replace(",", ".")) if raw else None
            result.update({
                "state": "VALIDADA" if refs else "NO_EXISTE",
                "returned_reference": refs[0] if refs else "",
                "area_m2": area_m2,
                "area_ha": round(area_m2 / 10000, 6) if area_m2 is not None else None,
            })
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        results.append(result)
        print(f"[{index:02d}/{len(valid)}] {row['parcel_reference']}: {result['state']} {result.get('area_ha','')}", flush=True)
        time.sleep(0.18)

    (OUT / "catastro_page5_areas.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fields = [
        "id", "parcel_reference", "polygon", "parcel", "official_place",
        "state", "returned_reference", "area_m2", "area_ha", "error", "query_url",
    ]
    with (OUT / "catastro_page5_areas.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";")
        writer.writeheader()
        for result in results:
            writer.writerow({key: result.get(key, "") for key in fields})


if __name__ == "__main__":
    main()
