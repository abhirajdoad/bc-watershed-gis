"""Monitoring-network coverage analysis for Lower Mainland / Fraser Valley assessment watersheds.
Reads data/raw/*.geojson (from 01_download_data.py); writes data/processed/analysis.gpkg
and outputs/*.csv.  All geometry work is done in BC Albers (EPSG:3005, metres).
"""
from pathlib import Path
import json, warnings
import geopandas as gpd, pandas as pd, numpy as np
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
RAW, PROC, OUT = ROOT / "data/raw", ROOT / "data/processed", ROOT / "outputs"
CRS = 3005
warnings.filterwarnings('ignore', message='.*keep_geom_type.*')  # line/polygon overlays drop boundary-touch points by design
BBOX = box(1170000, 430000, 1330000, 520000)         # download extent (same as script 01)
GROUPS = ["LFRA", "CHWK", "HARR"]                    # Lower Fraser, Chilliwack, Harrison
RECENT_FROM = pd.Timestamp("2016-01-01")             # EMS "recently sampled" cut-off
COVER_DIST_M = 5_000                                 # "stream within X km of a station"
SW_PROX_M = 200                                      # EMS "near surface water" threshold

def load(name):
    g = gpd.read_file(RAW / f"{name}.geojson")
    assert g.crs.to_epsg() == CRS, f"{name}: unexpected CRS {g.crs}"
    return g

def main():
    PROC.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
    # ---------- watersheds (analysis units) ----------
    ws = load("assessment_watersheds")
    ws = ws[ws.WATERSHED_GROUP_CODE.isin(GROUPS) & ws.within(BBOX)].copy()  # drop cut-off edge units
    ws["ws_id"] = ws.WATERSHED_FEATURE_ID
    ws["ws_name"] = ws.GNIS_NAME_1.fillna("Unnamed (" + ws.WATERSHED_FEATURE_ID.astype(str) + ")")
    ws["area_km2"] = ws.geometry.area / 1e6
    # validation: computed planar area vs FWA-supplied AREA_HA
    ws["area_diff_pct"] = (ws.area_km2 * 100 - ws.AREA_HA).abs() / ws.AREA_HA * 100
    ws = ws[["ws_id", "ws_name", "WATERSHED_GROUP_CODE", "area_km2", "area_diff_pct", "geometry"]].reset_index(drop=True)
    aoi = ws.geometry.union_all()

    # ---------- stations ----------
    ems = load("ems_locations")
    # CRS validation: reprojected geometry should reproduce the stored LATITUDE/LONGITUDE
    # (EMS stores longitude as positive west, hence -abs())
    ll = ems.to_crs(4326)
    ems["coord_err_m"] = gpd.GeoSeries(gpd.points_from_xy(ll.geometry.x, ll.geometry.y), crs=4326).to_crs(CRS).distance(
        gpd.GeoSeries(gpd.points_from_xy(-ems.LONGITUDE.abs(), ems.LATITUDE), crs=4326).to_crs(CRS))
    # Station selection. Stations are selected over the whole download bbox (not just the AOI) so that
    # buffers / nearest-distance near the AOI edge can use stations just outside it (edge-effect control);
    # per-watershed counts use only stations inside each watershed.
    ems_q_bbox = ems[(ems.SAMPLE_COUNT > 0) & (ems.LAST_SAMPLE_DATE >= RECENT_FROM)   # null dates -> excluded
                     & (ems.MOBILE_LOCATION_IND == "N")].copy()
    n_ems_rows = int(ems_q_bbox.within(aoi).sum())
    # several EMS IDs can share one physical site: collapse identical coordinates to one site
    ems_q_bbox = ems_q_bbox.assign(_x=ems_q_bbox.geometry.x.round(1), _y=ems_q_bbox.geometry.y.round(1)) \
        .drop_duplicates(["_x", "_y"]).drop(columns=["_x", "_y"])
    hyd_bbox = load("hydrometric")
    hyd_act_bbox = hyd_bbox[hyd_bbox.STATION_OPERATING_STATUS.str.startswith("ACTIVE")].copy()  # "NA" -> inactive

    # ---------- hydrography ----------
    streams_full = load("streams")                                       # order >= 3, whole bbox
    lakes_full = load("lakes")                                           # >= 10 ha, whole bbox
    streams = streams_full.clip(aoi)
    streams = streams[streams.geom_type.isin(["LineString", "MultiLineString"])]
    lakes = lakes_full[lakes_full.intersects(aoi)].copy()

    # ---------- proximity: EMS sites near mapped surface water ----------
    water = pd.concat([streams_full.geometry, lakes_full.geometry]).union_all()   # unclipped: no edge loss
    ems_q_bbox["dist_water_m"] = ems_q_bbox.distance(water)
    ems_q_bbox["near_sw"] = ems_q_bbox.dist_water_m <= SW_PROX_M
    # EMS sites essentially co-located with an active gauge are not counted as a separate site
    ems_q_bbox["dist_hydro_active_m"] = ems_q_bbox.distance(hyd_act_bbox.geometry.union_all())
    ems_q_bbox["colocated_gauge"] = ems_q_bbox.dist_hydro_active_m <= SW_PROX_M
    ems_sw_bbox = ems_q_bbox[ems_q_bbox.near_sw]

    ems_q = ems_q_bbox[ems_q_bbox.within(aoi)].copy()
    ems_sw = ems_q[ems_q.near_sw].copy()
    hyd = hyd_bbox[hyd_bbox.within(aoi)].copy()
    hyd_act = hyd[hyd.STATION_OPERATING_STATUS.str.startswith("ACTIVE")].copy()

    # ---------- spatial joins -> counts per watershed ----------
    def count(points):
        j = gpd.sjoin(points[["geometry"]], ws[["ws_id", "geometry"]], predicate="within")
        assert len(j) == len(points), "every AOI point must fall in exactly one watershed"
        return ws.ws_id.map(j.groupby("ws_id").size()).fillna(0).astype(int).values
    ws["n_ems"] = count(ems_q)                       # unique recent EMS sites (all media)
    ws["n_ems_sw"] = count(ems_sw)                   # ... of which within 200 m of mapped water
    ws["n_ems_sw_sep"] = count(ems_sw[~ems_sw.colocated_gauge])  # ... and not co-located with an active gauge
    ws["n_hydro_active"] = count(hyd_act)
    ws["n_hydro_all"] = count(hyd)
    ws["n_sites_comb"] = ws.n_hydro_active + ws.n_ems_sw_sep    # distinct monitoring sites, no double count
    for c in ("n_ems", "n_ems_sw", "n_hydro_active", "n_hydro_all", "n_sites_comb"):
        ws[c.replace("n_", "dens_")] = ws[c] / ws.area_km2 * 100   # per 100 km2
    ws["small_unit"] = ws.area_km2 < 5                          # density unstable for tiny units

    # ---------- streams & lakes per watershed ----------
    st_ws = gpd.overlay(streams[["geometry"]], ws[["ws_id", "geometry"]], how="intersection")
    ws["stream_km"] = ws.ws_id.map(st_ws.assign(l=st_ws.length / 1000).groupby("ws_id").l.sum()).fillna(0)
    lk_ws = gpd.overlay(lakes[["geometry"]], ws[["ws_id", "geometry"]], how="intersection")
    ws["lake_km2"] = ws.ws_id.map(lk_ws.assign(a=lk_ws.area / 1e6).groupby("ws_id").a.sum()).fillna(0)

    # ---------- buffer analysis: stream length within 5 km (Euclidean) of a station ----------
    # buffers are unioned first, and st_ws is already split at watershed boundaries -> no double counting
    def stream_cover(points, dist=COVER_DIST_M):
        zone = points.buffer(dist).union_all()
        inside = st_ws.intersection(zone).length / 1000
        return ws.ws_id.map(inside.groupby(st_ws.ws_id).sum()).fillna(0).values
    cover_sets = {"hydro": hyd_act_bbox, "ems_sw": ems_sw_bbox,
                  "any": pd.concat([hyd_act_bbox, ems_sw_bbox]), "hydro_allems": pd.concat([hyd_act_bbox, ems_q_bbox])}
    for k, pts in cover_sets.items():
        ws[f"stream_km_within5km_{k}"] = stream_cover(pts)
    ws["pct_stream_covered_hydro"] = ws.stream_km_within5km_hydro / ws.stream_km.replace(0, np.nan) * 100
    ws["pct_stream_covered_any"] = ws.stream_km_within5km_any / ws.stream_km.replace(0, np.nan) * 100

    # ---------- nearest-station distance from each watershed's representative point ----------
    cen = ws.assign(geometry=ws.geometry.representative_point())[["ws_id", "geometry"]]
    for name, pts in (("hydro_active", hyd_act_bbox), ("ems_sw", ems_sw_bbox)):
        j = gpd.sjoin_nearest(cen, pts[["geometry"]], distance_col="d")
        ws[f"nearest_{name}_km"] = ws.ws_id.map(j.drop_duplicates("ws_id").set_index("ws_id").d / 1000)

    # coverage class per watershed
    ws["coverage_class"] = np.select(
        [ws.n_hydro_active > 0, ws.n_ems_sw > 0],
        ["Active hydrometric station", "Near-water EMS site only"],
        default="No active gauge or near-water EMS site")

    # ---------- write outputs ----------
    gpkg = PROC / "analysis.gpkg"
    gpkg.unlink(missing_ok=True)
    for n, g in dict(watersheds=ws, ems_recent=ems_q, hydrometric=hyd, streams=streams[["GNIS_NAME", "STREAM_ORDER", "geometry"]],
                     lakes=lakes[["GNIS_NAME_1", "AREA_HA", "geometry"]], aoi=gpd.GeoDataFrame(geometry=[aoi], crs=CRS)).items():
        g.to_file(gpkg, layer=n, driver="GPKG")
    ws.drop(columns="geometry").round(3).to_csv(OUT / "watershed_coverage.csv", index=False)

    # ---------- Fraser corridor: share of distinct sites vs share of area within 5 km of the Fraser mainstem ----------
    fraser_zone = streams_full[streams_full.GNIS_NAME == "Fraser River"].buffer(COVER_DIST_M).union_all()
    sites = pd.concat([hyd_act.geometry, ems_sw[~ems_sw.colocated_gauge].geometry])
    fraser = dict(area_pct=round(ws.intersection(fraser_zone).area.sum() / ws.area.sum() * 100, 1),
                  sites_pct=round(sites.within(fraser_zone).mean() * 100, 1), n_sites=len(sites))

    # ---------- summary & validation report ----------
    tot = ws.stream_km.sum()
    pct = lambda c: round(ws[c].sum() / tot * 100, 1)
    neither = ws.coverage_class.str.startswith("No")
    summ = dict(
        n_watersheds=len(ws), aoi_area_km2=round(aoi.area / 1e6, 1),
        ems_rows_total_in_download_bbox=len(ems), ems_recent_rows_in_aoi=n_ems_rows,
        ems_recent_unique_sites_in_aoi=len(ems_q), ems_near_water_200m=len(ems_sw),
        ems_near_water_colocated_with_active_gauge=int(ems_sw.colocated_gauge.sum()),
        ems_null_last_sample_date_in_bbox=int(ems.LAST_SAMPLE_DATE.isna().sum()),
        hydro_in_aoi=len(hyd), hydro_active_in_aoi=len(hyd_act),
        hydro_active_in_bbox_outside_aoi=len(hyd_act_bbox) - len(hyd_act),
        stream_km_order3plus=round(tot, 1), lakes_ge10ha=len(lakes),
        ws_with_active_gauge=int((ws.n_hydro_active > 0).sum()),
        ws_near_water_ems_only=int(((ws.n_hydro_active == 0) & (ws.n_ems_sw > 0)).sum()),
        ws_neither=int(neither.sum()), ws_neither_area_pct=round(ws[neither].area_km2.sum() / ws.area_km2.sum() * 100, 1),
        ws_neither_but_other_recent_ems=int((neither & (ws.n_ems > 0)).sum()),
        pct_stream_within5km={"active_hydrometric": pct("stream_km_within5km_hydro"),
                              "near_water_ems": pct("stream_km_within5km_ems_sw"),
                              "hydrometric_or_near_water_ems": pct("stream_km_within5km_any"),
                              "hydrometric_or_any_recent_ems": pct("stream_km_within5km_hydro_allems")},
        overall_dens_per100km2={"active_hydrometric": round(ws.n_hydro_active.sum() / ws.area_km2.sum() * 100, 3),
                                "near_water_ems": round(ws.n_ems_sw.sum() / ws.area_km2.sum() * 100, 3),
                                "distinct_sites_combined": round(ws.n_sites_comb.sum() / ws.area_km2.sum() * 100, 3)},
        fraser_corridor_5km=fraser,
        median_dens_combined_per100km2=round(ws.dens_sites_comb.median(), 3),
        small_units_lt5km2=ws.loc[ws.small_unit, "ws_name"].tolist(),
        ems_near_water_sensitivity={f"{d}m": int((ems_q.dist_water_m <= d).sum()) for d in (50, 100, 200, 500, 1000)},
        validation=dict(crs=f"EPSG:{CRS} (NAD83 / BC Albers, equal-area)", max_area_diff_pct=round(ws.area_diff_pct.max(), 3),
                        ems_max_coord_err_m=round(ems.coord_err_m.max(), 2),
                        ems_median_coord_err_m=round(ems.coord_err_m.median(), 2),
                        ems_assigned=int(ws.n_ems.sum()), ems_in_aoi=len(ems_q),
                        hydro_assigned=int(ws.n_hydro_all.sum()), hydro_in_aoi=len(hyd)),
        coverage_class_counts=ws.coverage_class.value_counts().to_dict(),
    )
    (OUT / "summary.json").write_text(json.dumps(summ, indent=2))
    print(json.dumps(summ, indent=2))

if __name__ == "__main__":
    main()
