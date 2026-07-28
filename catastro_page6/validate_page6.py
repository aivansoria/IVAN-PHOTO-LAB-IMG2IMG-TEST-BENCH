from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# id, municipio, polígono, parcela
CANDIDATES = [
    ["p6-21-5376", "Deza", 21, 5376],
    ["p6-21-5385", "Deza", 21, 5385],
    ["p6-21-5380", "Deza", 21, 5380],
    ["p6-21-5379", "Deza", 21, 5379],
    ["p6-21-5378", "Deza", 21, 5378],
    ["p6-21-5358", "Deza", 21, 5358],
    ["p6-21-5337", "Deza", 21, 5337],
    ["p6-21-5281", "Deza", 21, 5281],

    ["p6-18-5237", "Deza", 18, 5237],
    ["p6-16-5106", "Deza", 16, 5106],
    ["p6-16-5217", "Deza", 16, 5217],

    ["p6-16-5361", "Deza", 16, 5361],
    ["p6-16-25305", "Deza", 16, 25305],
    ["p6-16-15305", "Deza", 16, 15305],
    ["p6-16-25300", "Deza", 16, 25300],
    ["p6-16-15300", "Deza", 16, 15300],
    ["p6-16-15299", "Deza", 16, 15299],
    ["p6-16-5226", "Deza", 16, 5226],
    ["p6-16-5227", "Deza", 16, 5227],
    ["p6-16-5156", "Deza", 16, 5156],
    ["p6-16-15243", "Deza", 16, 15243],
    ["p6-16-25243", "Deza", 16, 25243],
    ["p6-16-25190", "Deza", 16, 25190],
    ["p6-16-25191", "Deza", 16, 25191],
    ["p6-16-5188", "Deza", 16, 5188],
    ["p6-16-5186", "Deza", 16, 5186],
    ["p6-16-5185", "Deza", 16, 5185],

    ["p6-15-5534", "Deza", 15, 5534],
    ["p6-15-25531", "Deza", 15, 25531],
    ["p6-15-15531", "Deza", 15, 15531],
    ["p6-15-15528", "Deza", 15, 15528],
    ["p6-15-25526", "Deza", 15, 25526],
    ["p6-14-5141", "Deza", 14, 5141],
    ["p6-14-5130", "Deza", 14, 5130],
    ["p6-14-5114", "Deza", 14, 5114],
    ["p6-14-5059", "Deza", 14, 5059],
    ["p6-14-5056", "Deza", 14, 5056],
    ["p6-14-5057", "Deza", 14, 5057],
    ["p6-14-5068", "Deza", 14, 5068],
    ["p6-14-5094", "Deza", 14, 5094],
    ["p6-14-5043", "Deza", 14, 5043],
    # alternativas para comprobar los cambios de polígono dudosos
    ["p6-alt-16-5056", "Deza", 16, 5056],
    ["p6-alt-11-5056", "Deza", 11, 5056],
    ["p6-alt-16-5059", "Deza", 16, 5059],
    ["p6-alt-16-5057", "Deza", 16, 5057],

    ["p6-14-5032", "Deza", 14, 5032],
    ["p6-alt-13-5032", "Deza", 13, 5032],
    ["p6-14-5026", "Deza", 14, 5026],
    ["p6-14-5017", "Deza", 14, 5017],
    ["p6-13-5091", "Deza", 13, 5091],
    ["p6-13-5086", "Deza", 13, 5086],
    ["p6-13-5102", "Deza", 13, 5102],

    ["p6-14-5071", "Deza", 14, 5071],
    ["p6-14-5073", "Deza", 14, 5073],

    ["p6-13-5105", "Deza", 13, 5105],
    ["p6-13-5107", "Deza", 13, 5107],
    ["p6-13-5114", "Deza", 13, 5114],
]

LOCAL_ENDPOINT = (
    "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/"
    "OVCCallejero.asmx/Consulta_DNPPP"
)
AREA_ENDPOINT = "https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx"
OUT = Path(__file__).with_name("results")


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def first(node: ET.Element, name: str, default: str = "") -> str:
    for element in node.iter():
        if local(element.tag) == name and element.text:
            return element.text.strip()
    return default


def elements(node: ET.Element, name: str) -> list[ET.Element]:
    return [element for element in node.iter() if local(element.tag) == name]


def as_int(value: str, default: int = -1) -> int:
    try:
        return int(value)
    except Exception:
        return default


def make_session() -> requests.Session:
    retry = Retry(
        total=4, connect=4, read=4, status=4, backoff_factor=0.7,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": "BaldoPage6Validator/1.0"})
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
    parsed = []
    for bi in elements(root, "bi"):
        pc1 = first(bi, "pc1")
        pc2 = first(bi, "pc2")
        parsed.append({
            "polygon": as_int(first(bi, "cpo")),
            "parcel": as_int(first(bi, "cpa")),
            "official_place": first(bi, "npa"),
            "municipality": first(bi, "nm"),
            "parcel_reference": pc1 + pc2,
            "full_reference": pc1 + pc2 + first(bi, "car") + first(bi, "cc1") + first(bi, "cc2"),
        })
    exact = [row for row in parsed if row["polygon"] == polygon and row["parcel"] == parcel]
    result = {
        "id": item_id,
        "municipality_requested": municipality,
        "polygon_requested": polygon,
        "parcel_requested": parcel,
        "state": "VALIDADA" if exact else ("AMBIGUA" if parsed else "NO_EXISTE"),
        "query_url": response.url,
        "properties": parsed,
    }
    if exact:
        selected = exact[0]
        ref = selected["parcel_reference"]
        result.update(selected)
        result["map_url"] = (
            "https://www1.sedecatastro.gob.es/Cartografia/"
            f"BuscarParcelaInternet.aspx?refcat={ref}"
        )
        result["record_url"] = (
            "https://www1.sedecatastro.gob.es/CYCBienInmueble/"
            f"OVCListaBienes.aspx?RC1={ref[:7]}&RC2={ref[7:14]}"
        )
        area_response = session.get(
            AREA_ENDPOINT,
            params={
                "service": "wfs", "version": "2", "request": "getfeature",
                "STOREDQUERIE_ID": "GetParcel", "refcat": ref,
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
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    session = make_session()
    results = []
    for index, item in enumerate(CANDIDATES, 1):
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
            f"[{index:02d}/{len(CANDIDATES)}] {item[2]}/{item[3]} "
            f"{result['state']} {result.get('official_place','')} {result.get('area_ha','')}",
            flush=True,
        )
        time.sleep(0.15)

    (OUT / "catastro_page6_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fields = [
        "id", "state", "municipality_requested", "polygon_requested", "parcel_requested",
        "official_place", "municipality", "parcel_reference", "full_reference",
        "area_m2", "area_ha", "map_url", "record_url", "error", "query_url",
    ]
    with (OUT / "catastro_page6_results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
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
