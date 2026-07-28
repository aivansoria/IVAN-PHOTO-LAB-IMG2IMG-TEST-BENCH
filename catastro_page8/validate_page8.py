from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# id, polygon, parcel
CANDIDATES = [
    ("p8-23-5086",23,5086),("p8-23-5087",23,5087),
    ("p8-24-5200",24,5200),("p8-24-5188",24,5188),
    ("p8-22-5745",22,5745),("p8-22-5509",22,5509),("p8-alt-22-5609",22,5609),("p8-22-5508",22,5508),
    ("p8-22-5529",22,5529),("p8-22-5527",22,5527),("p8-22-5524",22,5524),
    ("p8-22-5764",22,5764),("p8-22-5615",22,5615),("p8-22-5676",22,5676),("p8-22-5570",22,5570),
    ("p8-22-5565",22,5565),("p8-22-5664",22,5664),("p8-22-5628",22,5628),("p8-22-5627",22,5627),
    ("p8-24-5376",24,5376),("p8-24-5374",24,5374),("p8-24-5383",24,5383),
    ("p8-22-25385",22,25385),
    ("p8-casa-11-5361",11,5361),("p8-casa-6-5361",6,5361),("p8-casa-16-5361",16,5361),
    ("p8-11-5137",11,5137),("p8-11-5126",11,5126),
    ("p8-28-25607",28,25607),("p8-28-5666",28,5666),("p8-28-5673",28,5673),("p8-28-5672",28,5672),
    ("p8-28-5692",28,5692),("p8-28-5693",28,5693),("p8-28-15696",28,15696),
    ("p8-11-5301",11,5301),("p8-11-5302",11,5302),("p8-11-5303",11,5303),("p8-11-5306",11,5306),
    ("p8-11-5320",11,5320),("p8-11-5321",11,5321),("p8-11-5155",11,5155),
    ("p8-28-5621",28,5621),("p8-28-5707",28,5707),
    ("p8-28-6086",28,6086),("p8-28-5716",28,5716),("p8-28-2738",28,2738),("p8-28-5740",28,5740),("p8-28-5741",28,5741),
]

LOCAL = "https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx/Consulta_DNPPP"
AREA = "https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx"
OUT = Path(__file__).with_name("results")


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def first(root: ET.Element, name: str, default: str = "") -> str:
    for e in root.iter():
        if local(e.tag) == name and e.text:
            return e.text.strip()
    return default


def nodes(root: ET.Element, name: str):
    return [e for e in root.iter() if local(e.tag) == name]


def make_session() -> requests.Session:
    retry = Retry(total=4, connect=4, read=4, status=4, backoff_factor=.7,
                  status_forcelist=(429,500,502,503,504), allowed_methods=frozenset(["GET"]))
    s = requests.Session(); s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent":"BaldoPage8Validator/1.0"})
    return s


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    s = make_session(); results=[]
    for i,(item_id,pol,par) in enumerate(CANDIDATES,1):
        result={"id":item_id,"polygon_requested":pol,"parcel_requested":par,"state":"ERROR"}
        try:
            r=s.get(LOCAL,params={"Provincia":"SORIA","Municipio":"Deza","Poligono":pol,"Parcela":par},timeout=(15,45)); r.raise_for_status()
            root=ET.fromstring(r.content); exact=[]
            for bi in nodes(root,"bi"):
                if int(first(bi,"cpo","-1"))==pol and int(first(bi,"cpa","-1"))==par: exact.append(bi)
            if not exact:
                result.update(state="NO_EXISTE",query_url=r.url)
            else:
                bi=exact[0]; ref=first(bi,"pc1")+first(bi,"pc2")
                result.update(state="VALIDADA",query_url=r.url,official_place=first(bi,"npa"),municipality=first(bi,"nm"),
                              parcel_reference=ref,full_reference=ref+first(bi,"car")+first(bi,"cc1")+first(bi,"cc2"),
                              map_url="https://www1.sedecatastro.gob.es/Cartografia/BuscarParcelaInternet.aspx?refcat="+ref,
                              record_url=f"https://www1.sedecatastro.gob.es/CYCBienInmueble/OVCListaBienes.aspx?RC1={ref[:7]}&RC2={ref[7:14]}")
                a=s.get(AREA,params={"service":"wfs","version":"2","request":"getfeature","STOREDQUERIE_ID":"GetParcel","refcat":ref,"srsname":"EPSG::25830"},timeout=(15,45)); a.raise_for_status()
                ar=ET.fromstring(a.content); raw=first(ar,"areaValue")
                if raw:
                    m2=float(raw.replace(",",".")); result.update(area_m2=m2,area_ha=round(m2/10000,6))
        except Exception as exc:
            result["error"]=f"{type(exc).__name__}: {exc}"
        results.append(result)
        print(f"[{i:02d}/{len(CANDIDATES)}] {pol}/{par} {result['state']} {result.get('official_place','')} {result.get('area_ha','')}",flush=True)
        time.sleep(.15)
    (OUT/"catastro_page8_results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    fields=["id","state","polygon_requested","parcel_requested","official_place","municipality","area_ha","parcel_reference","full_reference","map_url","record_url","error","query_url"]
    with (OUT/"catastro_page8_results.csv").open("w",encoding="utf-8-sig",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=fields,delimiter=";"); w.writeheader(); w.writerows({k:r.get(k,"") for k in fields} for r in results)
    summary={}
    for r in results: summary[r["state"]]=summary.get(r["state"],0)+1
    print("SUMMARY="+json.dumps(summary,sort_keys=True),flush=True)

if __name__=="__main__": main()
