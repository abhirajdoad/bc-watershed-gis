"""Download BC public datasets for the Lower Mainland / Fraser Valley AOI via the
BC Geographic Warehouse WFS (DataBC). Raw files are written to data/raw/ (git-ignored)
and a manifest with retrieval timestamps + feature counts to docs/download_manifest.json.
Usage: python scripts/01_download_data.py
"""
import json, datetime as dt, sys
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
WFS = "https://openmaps.gov.bc.ca/geo/pub/ows"
# AOI bounding box in BC Albers (EPSG:3005): xmin,ymin,xmax,ymax  (Lower Mainland + Fraser Valley)
BBOX = (1170000, 430000, 1330000, 520000)
PAGE = 5000

# name -> (WFS layer, optional CQL filter)
LAYERS = {
    "watershed_groups": ("WHSE_BASEMAPPING.FWA_WATERSHED_GROUPS_POLY", None),
    "assessment_watersheds": ("WHSE_BASEMAPPING.FWA_ASSESSMENT_WATERSHEDS_POLY", None),
    "lakes": ("WHSE_BASEMAPPING.FWA_LAKES_POLY", "AREA_HA >= 10"),
    "streams": ("WHSE_BASEMAPPING.FWA_STREAM_NETWORKS_SP", "STREAM_ORDER >= 3"),
    "hydrometric": ("WHSE_ENVIRONMENTAL_MONITORING.ENVCAN_HYDROMETRIC_STN_SP", None),
    "ems_locations": ("WHSE_ENVIRONMENTAL_MONITORING.EMS_MONITORING_LOCN_TYPES_SVW", None),
}

def fetch(layer, cql):
    feats, start = [], 0
    bbox = ",".join(map(str, BBOX)) + ",urn:ogc:def:crs:EPSG::3005"
    while True:
        params = dict(service="WFS", version="2.0.0", request="GetFeature",
                      typeNames=f"pub:{layer}", outputFormat="application/json",
                      srsName="EPSG:3005", count=PAGE, startIndex=start,
                      sortBy="OBJECTID")
        # WFS cannot combine bbox= with cql_filter=, so express bbox inside CQL
        x0, y0, x1, y1 = BBOX
        geomcol = "GEOMETRY"
        flt = f"BBOX({geomcol},{x0},{y0},{x1},{y1},'EPSG:3005')"
        if cql: flt += f" AND {cql}"
        params["cql_filter"] = flt
        r = requests.get(WFS, params=params, timeout=180)
        r.raise_for_status()
        batch = r.json()["features"]
        feats += batch
        print(f"  {layer}: {len(feats)}", flush=True)
        if len(batch) < PAGE: return feats
        start += PAGE

def main():
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = {"retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "wfs_endpoint": WFS, "bbox_epsg3005": BBOX, "layers": {}}
    for name, (layer, cql) in LAYERS.items():
        print(name)
        feats = fetch(layer, cql)
        out = RAW / f"{name}.geojson"
        out.write_text(json.dumps({"type": "FeatureCollection", "features": feats,
                                   "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::3005"}}}))
        manifest["layers"][name] = {"layer": layer, "filter": cql, "features": len(feats)}
    (ROOT / "docs" / "download_manifest.json").write_text(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    sys.exit(main())
