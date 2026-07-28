from __future__ import annotations

import json
import time
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

CANDIDATES = [
    ("p8-resolve-22-5564",22,5564),
    ("p8-resolve-22-25388",22,25388),("p8-resolve-22-25588",22,25588),("p8-resolve-22-25383",22,25383),
    *[(f"p8-resolve-28-{p}",28,p) for p in range(25600,25610)],
    ("p8-resolve-28-5738",28,5738),
]
LOCAL="https://ovc.catastro.meh.es/ovcservweb/OVCSWLocalizacionRC/OVCCallejero.asmx/Consulta_DNPPP"
AREA="https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx"
OUT=Path(__file__).with_name("results")

def local(tag): return tag.rsplit("}",1)[-1]
def first(root,name,default=""):
    for e in root.iter():
        if local(e.tag)==name and e.text: return e.text.strip()
    return default
def nodes(root,name): return [e for e in root.iter() if local(e.tag)==name]
def session():
    rt=Retry(total=4,connect=4,read=4,status=4,backoff_factor=.7,status_forcelist=(429,500,502,503,504),allowed_methods=frozenset(["GET"]))
    s=requests.Session(); s.mount("https://",HTTPAdapter(max_retries=rt)); s.headers.update({"User-Agent":"BaldoPage8Resolver/1.0"}); return s

def main():
    OUT.mkdir(parents=True,exist_ok=True); s=session(); results=[]
    for i,(item_id,pol,par) in enumerate(CANDIDATES,1):
        out={"id":item_id,"polygon_requested":pol,"parcel_requested":par,"state":"ERROR"}
        try:
            r=s.get(LOCAL,params={"Provincia":"SORIA","Municipio":"Deza","Poligono":pol,"Parcela":par},timeout=(15,45)); r.raise_for_status(); root=ET.fromstring(r.content)
            exact=[bi for bi in nodes(root,"bi") if int(first(bi,"cpo","-1"))==pol and int(first(bi,"cpa","-1"))==par]
            if not exact: out["state"]="NO_EXISTE"
            else:
                bi=exact[0]; ref=first(bi,"pc1")+first(bi,"pc2")
                out.update(state="VALIDADA",official_place=first(bi,"npa"),parcel_reference=ref,full_reference=ref+first(bi,"car")+first(bi,"cc1")+first(bi,"cc2"),map_url="https://www1.sedecatastro.gob.es/Cartografia/BuscarParcelaInternet.aspx?refcat="+ref,record_url=f"https://www1.sedecatastro.gob.es/CYCBienInmueble/OVCListaBienes.aspx?RC1={ref[:7]}&RC2={ref[7:14]}")
                a=s.get(AREA,params={"service":"wfs","version":"2","request":"getfeature","STOREDQUERIE_ID":"GetParcel","refcat":ref,"srsname":"EPSG::25830"},timeout=(15,45)); a.raise_for_status(); ar=ET.fromstring(a.content); raw=first(ar,"areaValue")
                if raw: m2=float(raw.replace(",",".")); out.update(area_m2=m2,area_ha=round(m2/10000,6))
        except Exception as exc: out["error"]=f"{type(exc).__name__}: {exc}"
        results.append(out); print(f"[{i}/{len(CANDIDATES)}] {pol}/{par} {out['state']} {out.get('official_place','')} {out.get('area_ha','')}",flush=True); time.sleep(.15)
    (OUT/"catastro_page8_resolution.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")

if __name__=="__main__": main()
