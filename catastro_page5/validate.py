from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

CANDIDATES = [
    ["p5-camino-vis-15-5520", "Deza", 15, 5520],
    ["p5-camino-alt-15-5420", "Deza", 15, 5420],
    ["p5-camino-vis-15-5870", "Deza", 15, 5870],
    ["p5-camino-alt-15-5370", "Deza", 15, 5370],
    ["p5-camino-alt-15-5270", "Deza", 15, 5270],
    ["p5-camino-vis-15-5069", "Deza", 15, 5069],
    ["p5-camino-alt-16-5069", "Deza", 16, 5069],
    ["p5-camino-alt-15-5039", "Deza", 15, 5039],
    ["p5-camino-vis-16-5059", "Deza", 16, 5059],
    ["p5-camino-alt-16-5429", "Deza", 16, 5429],
    ["p5-camino-vis-16-5058", "Deza", 16, 5058],
    ["p5-camino-alt-16-5052", "Deza", 16, 5052],
    ["p5-camino-vis-16-5073", "Deza", 16, 5073],
    ["p5-camino-alt-16-5023", "Deza", 16, 5023],
    ["p5-camino-vis-16-5084", "Deza", 16, 5084],
    ["p5-camino-vis-15-5374", "Deza", 15, 5374],
    ["p5-camino-vis-16-5354", "Deza", 16, 5354],
    ["p5-camino-alt-16-5351", "Deza", 16, 5351],
    ["p5-camino-vis-16-5005", "Deza", 16, 5005],
    ["p5-camino-alt-16-5065", "Deza", 16, 5065],
    ["p5-pozo-correct-15-5003", "Deza", 15, 5003],
    ["p5-verdugal-correct-15-5323", "Deza", 15, 5323],
    ["p5-venta-18-125", "Deza", 18, 125],
    ["p5-venta-tachada-17-5078", "Deza", 17, 5078],
    ["p5-venta-tachada-alt-17-5558", "Deza", 17, 5558],
]

ENDPOINT = (
    "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/"
    "OVCCallejero.asmx/Consulta_DNPPP"
)
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


def session() -> requests.Session:
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=0.7,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
    )
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": "BaldoPage5Validator/1.0"})
    return s


def parse(item: list, text: str, url: str) -> dict:
    item_id, municipality, polygon, parcel = item
    root = ET.fromstring(text)
    bienes = elements(root, "bi")
    parsed = []
    for bi in bienes:
        pc1 = first(bi, "pc1")
        pc2 = first(bi, "pc2")
        car = first(bi, "car")
        cc1 = first(bi, "cc1")
        cc2 = first(bi, "cc2")
        subparcels = []
        for spr in elements(bi, "spr"):
            m2 = as_int(first(spr, "ssp"), 0)
            subparcels.append({
                "code": first(spr, "cspr"),
                "use": first(spr, "dcc"),
                "surface_m2": m2,
                "surface_ha": round(m2 / 10000, 6),
            })
        parsed.append({
            "polygon": as_int(first(bi, "cpo")),
            "parcel": as_int(first(bi, "cpa")),
            "official_place": first(bi, "npa"),
            "municipality": first(bi, "nm"),
            "cadastral_municipality_code": first(bi, "cmc"),
            "parcel_reference": pc1 + pc2,
            "full_reference": pc1 + pc2 + car + cc1 + cc2,
            "subparcels": subparcels,
            "total_surface_ha": round(sum(s["surface_m2"] for s in subparcels) / 10000, 6),
        })
    exact = [p for p in parsed if p["polygon"] == polygon and p["parcel"] == parcel]
    selected = exact[0] if exact else (parsed[0] if parsed else None)
    result = {
        "id": item_id,
        "municipality_requested": municipality,
        "polygon_requested": polygon,
        "parcel_requested": parcel,
        "query_url": url,
        "state": "VALIDADA" if exact else ("AMBIGUA" if parsed else "NO_EXISTE"),
        "properties": parsed,
    }
    if selected:
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
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    s = session()
    results = []
    for index, item in enumerate(CANDIDATES, 1):
        item_id, municipality, polygon, parcel = item
        params = {
            "Provincia": "SORIA",
            "Municipio": municipality,
            "Poligono": polygon,
            "Parcela": parcel,
        }
        try:
            response = s.get(ENDPOINT, params=params, timeout=(15, 45))
            response.raise_for_status()
            result = parse(item, response.text, response.url)
        except Exception as exc:
            result = {
                "id": item_id,
                "municipality_requested": municipality,
                "polygon_requested": polygon,
                "parcel_requested": parcel,
                "state": "ERROR",
                "error": f"{type(exc).__name__}: {exc}",
            }
        results.append(result)
        print(f"[{index:02d}/{len(CANDIDATES)}] {polygon}/{parcel}: {result['state']} {result.get('official_place','')}", flush=True)
        time.sleep(0.18)

    (OUT / "catastro_page5_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fields = [
        "id", "state", "municipality_requested", "polygon_requested", "parcel_requested",
        "official_place", "municipality", "parcel_reference", "full_reference",
        "total_surface_ha", "map_url", "record_url", "error", "query_url",
    ]
    with (OUT / "catastro_page5_results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
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
