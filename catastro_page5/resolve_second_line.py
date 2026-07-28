from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

OUT = Path(__file__).with_name("results")
LOCAL_ENDPOINT = (
    "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/"
    "OVCCallejero.asmx/Consulta_DNPPP"
)
AREA_ENDPOINT = "https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx"
CANDIDATES = [
    ["p5-camino-second-16-5070", 16, 5070],
    ["p5-camino-second-16-5040", 16, 5040],
]


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def first(root: ET.Element, name: str, default: str = "") -> str:
    for element in root.iter():
        if local(element.tag) == name and element.text:
            return element.text.strip()
    return default


def all_elements(root: ET.Element, name: str):
    return [element for element in root.iter() if local(element.tag) == name]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "BaldoPage5SecondLine/1.0"})
    results = []

    for item_id, polygon, parcel in CANDIDATES:
        response = session.get(
            LOCAL_ENDPOINT,
            params={
                "Provincia": "SORIA",
                "Municipio": "Deza",
                "Poligono": polygon,
                "Parcela": parcel,
            },
            timeout=(15, 45),
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        bienes = all_elements(root, "bi")
        exact = []
        for bi in bienes:
            if int(first(bi, "cpo", "-1")) == polygon and int(first(bi, "cpa", "-1")) == parcel:
                exact.append(bi)
        result = {"id": item_id, "polygon": polygon, "parcel": parcel}
        if not exact:
            result["state"] = "NO_EXISTE"
            results.append(result)
            continue

        bi = exact[0]
        ref = first(bi, "pc1") + first(bi, "pc2")
        result.update({
            "state": "VALIDADA",
            "official_place": first(bi, "npa"),
            "parcel_reference": ref,
            "full_reference": ref + first(bi, "car") + first(bi, "cc1") + first(bi, "cc2"),
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
        results.append(result)
        print(item_id, result, flush=True)

    (OUT / "catastro_page5_second_line.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
