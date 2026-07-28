from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

PARCELS = [
    ["p7-fandanguera-13-5054", "Deza", 13, 5054],
    ["p7-fandanguera-13-5121", "Deza", 13, 5121],
    ["p7-fandanguera-13-5123", "Deza", 13, 5123],
    ["p7-fandanguera-13-5129", "Deza", 13, 5129],
    ["p7-navaseca-14-5153", "Deza", 14, 5153],
    ["p7-navaseca-14-5157", "Deza", 14, 5157],
    ["p7-navaseca-14-5175", "Deza", 14, 5175],
    ["p7-navaseca-14-5237", "Deza", 14, 5237],
    ["p7-navaseca-14-5173", "Deza", 14, 5173],
]

LOCAL_ENDPOINT = (
    "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/"
    "OVCCallejero.asmx/Consulta_DNPPP"
)
AREA_ENDPOINT = "https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx"
OUT = Path(__file__).with_name("results")


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def first(root: ET.Element, name: str, default: str = "") -> str:
    for element in root.iter():
        if local(element.tag) == name and element.text:
            return element.text.strip()
    return default


def elements(root: ET.Element, name: str) -> list[ET.Element]:
    return [element for element in root.iter() if local(element.tag) == name]


def as_int(value: str, default: int = -1) -> int:
    try:
        return int(value)
    except Exception:
        return default


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
    session.headers.update({"User-Agent": "BaldoPage7Validator/1.0"})
    return session


def lookup(session: requests.Session, item: list) -> dict:
    item_id, municipality, polygon, parcel = item
    response = session.get(
        LOCAL_ENDPOINT,
        params={
            "Provincia": "SORIA",
            "Municipio": municipality,
            "Poligono": polygon,
            "Parcela": parcel,
        },
        timeout=(15, 45),
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)
    bienes = elements(root, "bi")
    exact = []
    for bi in bienes:
        if as_int(first(bi, "cpo")) == polygon and as_int(first(bi, "cpa")) == parcel:
            exact.append(bi)

    result = {
        "id": item_id,
        "municipality_requested": municipality,
        "polygon_requested": polygon,
        "parcel_requested": parcel,
        "query_url": response.url,
        "state": "NO_EXISTE",
    }
    if not exact:
        return result

    bi = exact[0]
    ref = first(bi, "pc1") + first(bi, "pc2")
    full_ref = ref + first(bi, "car") + first(bi, "cc1") + first(bi, "cc2")
    result.update({
        "state": "VALIDADA",
        "official_place": first(bi, "npa"),
        "municipality": first(bi, "nm"),
        "parcel_reference": ref,
        "full_reference": full_ref,
        "map_url": (
            "https://www1.sedecatastro.gob.es/Cartografia/"
            f"BuscarParcelaInternet.aspx?refcat={ref}"
        ),
        "record_url": (
            "https://www1.sedecatastro.gob.es/CYCBienInmueble/"
            f"OVCListaBienes.aspx?RC1={ref[:7]}&RC2={ref[7:14]}"
        ),
    })

    area_response = session.get(
        AREA_ENDPOINT,
        params={
            "service": "wfs",
            "version": "2",
            "request": "getfeature",
            "STOREDQUERIE_ID": "GetParcel",
            "refcat": ref,
            "srsname": "EPSG::25830",
        },
        timeout=(15, 45),
    )
    area_response.raise_for_status()
    area_root = ET.fromstring(area_response.content)
    area_raw = first(area_root, "areaValue")
    if area_raw:
        area_m2 = float(area_raw.replace(",", "."))
        result["area_m2"] = area_m2
        result["area_ha"] = round(area_m2 / 10000, 6)
    result["area_query_url"] = area_response.url
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    session = make_session()
    results = []

    for index, item in enumerate(PARCELS, 1):
        try:
            result = lookup(session, item)
        except Exception as exc:
            result = {
                "id": item[0],
                "municipality_requested": item[1],
                "polygon_requested": item[2],
                "parcel_requested": item[3],
                "state": "ERROR",
                "error": f"{type(exc).__name__}: {exc}",
            }
        results.append(result)
        print(
            f"[{index:02d}/{len(PARCELS)}] {item[2]}/{item[3]}: "
            f"{result['state']} {result.get('official_place','')} "
            f"{result.get('area_ha','')}",
            flush=True,
        )
        time.sleep(0.18)

    (OUT / "catastro_page7_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    fields = [
        "id", "state", "municipality_requested", "polygon_requested",
        "parcel_requested", "official_place", "municipality",
        "parcel_reference", "full_reference", "area_m2", "area_ha",
        "map_url", "record_url", "error", "query_url", "area_query_url",
    ]
    with (OUT / "catastro_page7_results.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";")
        writer.writeheader()
        for result in results:
            writer.writerow({key: result.get(key, "") for key in fields})

    summary = {}
    for result in results:
        summary[result["state"]] = summary.get(result["state"], 0) + 1
    print("SUMMARY=" + json.dumps(summary, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
