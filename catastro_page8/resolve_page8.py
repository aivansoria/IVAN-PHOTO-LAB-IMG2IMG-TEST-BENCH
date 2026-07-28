from __future__ import annotations

import json
import time
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# id, polygon, parcel, expected area (ha), local context
CANDIDATES = [
    ("p8-resolve-dehesa-11-5127", 11, 5127, 0.17, "Dehesa"),
    ("p8-resolve-dehesa-11-5137", 11, 5137, 0.17, "Dehesa"),
    *[(f"p8-resolve-azanon-22-{p}", 22, p, 0.06, "Azañón") for p in range(5660, 5670)],
    ("p8-resolve-melonar-22-5385", 22, 5385, 0.08, "Melonar"),
    ("p8-resolve-melonar-22-25385", 22, 25385, 0.08, "Melonar"),
    ("p8-resolve-dehesa-28-5607", 28, 5607, 0.24, "Dehesa"),
    ("p8-resolve-dehesa-28-25607", 28, 25607, 0.24, "Dehesa"),
    ("p8-resolve-barranco-28-5738", 28, 5738, 0.63, "Barranco Lunar"),
    ("p8-resolve-barranco-28-2738", 28, 2738, 0.63, "Barranco Lunar"),
]

LOCAL = "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx/Consulta_DNPPP"
AREA = "https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx"
OUT = Path(__file__).with_name("results")


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def first(root: ET.Element, name: str, default: str = "") -> str:
    for element in root.iter():
        if local(element.tag) == name and element.text:
            return element.text.strip()
    return default


def nodes(root: ET.Element, name: str):
    return [element for element in root.iter() if local(element.tag) == name]


def make_session() -> requests.Session:
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=.7,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": "BaldoPage8Resolver/2.0"})
    return session


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    session = make_session()
    results = []

    for index, (item_id, polygon, parcel, expected_area, context) in enumerate(CANDIDATES, 1):
        result = {
            "id": item_id,
            "polygon_requested": polygon,
            "parcel_requested": parcel,
            "expected_area_ha": expected_area,
            "context": context,
            "state": "ERROR",
        }
        try:
            response = session.get(
                LOCAL,
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
            exact = [
                bi for bi in nodes(root, "bi")
                if int(first(bi, "cpo", "-1")) == polygon
                and int(first(bi, "cpa", "-1")) == parcel
            ]
            if not exact:
                result.update(state="NO_EXISTE", query_url=response.url)
            else:
                bi = exact[0]
                ref = first(bi, "pc1") + first(bi, "pc2")
                result.update(
                    state="VALIDADA",
                    query_url=response.url,
                    official_place=first(bi, "npa"),
                    municipality=first(bi, "nm"),
                    parcel_reference=ref,
                    full_reference=ref + first(bi, "car") + first(bi, "cc1") + first(bi, "cc2"),
                    map_url="https://www1.sedecatastro.gob.es/Cartografia/BuscarParcelaInternet.aspx?refcat=" + ref,
                    record_url=f"https://www1.sedecatastro.gob.es/CYCBienInmueble/OVCListaBienes.aspx?RC1={ref[:7]}&RC2={ref[7:14]}",
                )
                area_response = session.get(
                    AREA,
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
                raw = first(area_root, "areaValue")
                if raw:
                    area_m2 = float(raw.replace(",", "."))
                    area_ha = round(area_m2 / 10000, 6)
                    result.update(
                        area_m2=area_m2,
                        area_ha=area_ha,
                        difference_ha=round(abs(area_ha - expected_area), 6),
                    )
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"

        results.append(result)
        print(
            f"[{index:02d}/{len(CANDIDATES)}] {polygon}/{parcel} "
            f"{result['state']} {result.get('official_place', '')} "
            f"{result.get('area_ha', '')}",
            flush=True,
        )
        time.sleep(.15)

    (OUT / "catastro_page8_resolution.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
