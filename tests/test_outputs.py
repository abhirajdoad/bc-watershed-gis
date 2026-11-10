"""Sanity checks on analysis outputs (run after scripts 01-03)."""
import json
from pathlib import Path
import geopandas as gpd, pytest

ROOT = Path(__file__).resolve().parents[1]
GPKG = ROOT / "data/processed/analysis.gpkg"
pytestmark = pytest.mark.skipif(not GPKG.exists(), reason="run scripts first")

def test_all_layers_epsg3005():
    for l in ["watersheds", "ems_recent", "hydrometric", "streams", "lakes"]:
        assert gpd.read_file(GPKG, layer=l).crs.to_epsg() == 3005

def test_areas_match_fwa():
    ws = gpd.read_file(GPKG, layer="watersheds")
    assert ws.area_diff_pct.max() < 0.1

def test_counts_conserved():
    ws = gpd.read_file(GPKG, layer="watersheds")
    assert ws.n_ems.sum() == len(gpd.read_file(GPKG, layer="ems_recent"))
    assert ws.n_hydro_all.sum() == len(gpd.read_file(GPKG, layer="hydrometric"))
    assert (ws.n_hydro_active <= ws.n_hydro_all).all() and (ws.n_ems_sw <= ws.n_ems).all()

def test_percentages_bounded_and_units_nonoverlapping():
    ws = gpd.read_file(GPKG, layer="watersheds")
    assert ws.pct_stream_covered_any.dropna().between(0, 100.0001).all()
    assert (ws.pct_stream_covered_any.fillna(0) >= ws.pct_stream_covered_hydro.fillna(0) - 1e-6).all()
    assert ws.geometry.union_all().area >= ws.geometry.area.sum() * 0.999   # overlap < 0.1%

@pytest.mark.skipif(not (ROOT / "data/raw/ems_locations.geojson").exists(), reason="raw data not downloaded")
def test_ems_coordinate_roundtrip():
    """Reproject raw EMS points to WGS84 and compare with the stored lat/lon (EMS longitude is positive west)."""
    ems = gpd.read_file(ROOT / "data/raw/ems_locations.geojson")
    ll = ems.to_crs(4326)
    stored = gpd.GeoSeries(gpd.points_from_xy(-ems.LONGITUDE.abs(), ems.LATITUDE), crs=4326).to_crs(3005)
    assert ems.geometry.distance(stored).max() < 5      # metres
    assert (ll.geometry.x.sub(-ems.LONGITUDE.abs()).abs() < 1e-3).all()


RAW = ROOT / "data/raw"

@pytest.mark.skipif(not (RAW / "hydrometric.geojson").exists(), reason="raw data not downloaded")
def test_counts_match_unfiltered_raw_data():
    """Independent recount from raw files, so points dropped by a filter or join would be caught."""
    ws = gpd.read_file(GPKG, layer="watersheds")
    aoi = ws.geometry.union_all()
    hyd = gpd.read_file(RAW / "hydrometric.geojson")
    hyd = hyd[hyd.within(aoi)]
    assert ws.n_hydro_all.sum() == len(hyd)
    assert ws.n_hydro_active.sum() == hyd.STATION_OPERATING_STATUS.str.startswith("ACTIVE").sum()
    ems = gpd.read_file(RAW / "ems_locations.geojson")
    ems = ems[(ems.SAMPLE_COUNT > 0) & (ems.LAST_SAMPLE_DATE >= "2016-01-01") & (ems.MOBILE_LOCATION_IND == "N") & ems.within(aoi)]
    unique_sites = ems.geometry.apply(lambda g: (round(g.x, 1), round(g.y, 1))).nunique()
    assert ws.n_ems.sum() == unique_sites

def test_station_classes_consistent():
    ws = gpd.read_file(GPKG, layer="watersheds")
    assert ws.coverage_class.value_counts().sum() == len(ws)
    has_gauge = ws.coverage_class == "Active hydrometric station"
    assert ((ws.n_hydro_active > 0) == has_gauge).all()
    assert (ws.n_sites_comb <= ws.n_hydro_active + ws.n_ems_sw).all()
