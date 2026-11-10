# Water monitoring station coverage in the Lower Mainland and Fraser Valley, BC

A GIS analysis of which watersheds in the Lower Mainland and Fraser Valley have water monitoring stations and which have none, using public BC data, GeoPandas and QGIS.

![Map 3: monitoring coverage by assessment watershed](maps/03_coverage_buffers.png)

## Purpose

I split the Lower Fraser, Chilliwack and Harrison watershed groups into 138 small watersheds and counted the river-flow gauges and water-sampling sites inside each one. The result shows which watersheds have a station and which have none. It maps where stations are, not what they measure: no flow or water-quality data are used, and an empty watershed is not shown to be at risk.

## Key findings

- 25 of the 138 watersheds contain an active river-flow gauge. Another 32 contain a recently sampled water-monitoring site near a mapped stream or lake. The remaining 81 (49% of the area) have neither.
- The gaps are widest in the Harrison and Chilliwack groups. 24 of the 35 Harrison-group watersheds and 12 of the 23 Chilliwack-group watersheds have neither type of station. These are mostly tributary and upland units (for example the Chehalis, Statlu and Cogburn creek areas), not the far headwaters, which lie outside the study extent.
- Stations are concentrated along the Fraser River. The land within 5 km of the Fraser mainstem is 22% of the study area but holds 42% of the 153 distinct stations.
- About 57% of the 2,427 km of mapped streams (order 3 and above) are within 5 km, in a straight line, of an active gauge or a near-water sampling site. This figure is partly circular: the sampling sites were chosen because they are close to these same streams, so read it as an upper-leaning estimate and not an independent measure.

## Why it matters

Someone planning where to add or keep monitoring can use this as a first screen for watersheds with no station nearby. It is a screening tool only. It says nothing about whether a gap matters, because remote watersheds may reasonably have little monitoring, and it ignores networks I did not have (municipal, BC Hydro, industry, groundwater wells).

## Maps

[1 Study area and stations](maps/01_study_area_stations.png) · [2 Station density](maps/02_station_density.png) · [3 Coverage and 5 km buffers](maps/03_coverage_buffers.png) · [4 QGIS print layout](maps/04_qgis_coverage_layout.png)

## Data sources

Freshwater Atlas assessment watersheds, streams and lakes, hydrometric stations, and Environmental Monitoring System (EMS) location records, downloaded from the DataBC WFS on 2026-11-06 under the Open Government Licence - British Columbia. Layer names, filters and caveats are in [docs/data_sources.md](docs/data_sources.md). Everything is in NAD83 / BC Albers (EPSG:3005), an equal-area projection.

## Method

1. Study area: 138 assessment watersheds (20-100 km target size) from the Lower Fraser, Chilliwack and Harrison groups that lie fully inside the download extent (6,365 km2). Another 23 units from those groups cross the extent edge and were excluded rather than cut.
2. Active gauges: hydrometric stations with status ACTIVE or ACTIVE-REALTIME (30 of the 133 in the study area; status NA counts as inactive).
3. Recent EMS sites: fixed (non-mobile) EMS locations with at least one sample and a last sample on or after 2016-01-01. Records with no sample date are excluded. Records at identical coordinates are merged (344 records become 331 sites).
4. Near-water EMS sites: recent EMS sites within 200 m of a mapped stream (order 3 or higher) or lake (10 ha or larger), which gives 129 sites. This is a spatial stand-in for surface-water sampling sites, because I could not decode the EMS location-type codes. The set can include air, groundwater or discharge sites that happen to be near water, and it misses sites on small streams. Sensitivity: 85, 104, 129, 179 and 213 sites fall within 50, 100, 200, 500 and 1,000 m of mapped water.
5. Counts per watershed come from point-in-polygon joins. Every station falls in exactly one watershed. Six near-water EMS sites within 200 m of an active gauge are not counted as separate sites in the combined density.
6. Stream coverage: 5 km buffers around stations are dissolved and intersected with stream segments already split at watershed boundaries, so no length is counted twice. Stations outside the study area but inside the download extent are included so watersheds on the edge are not penalised.
7. Coverage class: active gauge, near-water EMS site only, or neither.
8. Checks: computed areas match the FWA `AREA_HA` attribute (max difference 0.0%); reprojecting EMS points to WGS84 reproduces the stored latitude and longitude (max error 0.38 m; EMS stores longitude as positive west); counts are conserved through the spatial join; watersheds do not overlap.

## Results in numbers

| Coverage class | Watersheds | Share of area |
|---|---|---|
| Active hydrometric station | 25 | 24% |
| Near-water EMS site only | 32 | 27% |
| No active gauge or near-water EMS site | 81 | 49% |

15 of the 81 watersheds in the last class still contain recent EMS sites that missed the 200 m test, so the class means no gauge and no identified surface-water site, not no monitoring of any kind.

Density is 0.47 active gauges and 2.03 near-water EMS sites per 100 km2 (2.40 distinct sites combined). The median watershed has zero.

| Stations used | Share of the 2,427 km of streams within 5 km |
|---|---|
| Active gauges | 31% |
| Near-water EMS sites | 45% |
| Gauges or near-water EMS | 57% |
| Gauges or any recent EMS | 63% |

## Reproduce

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/01_download_data.py   # about 43 MB into data/raw (not committed)
python scripts/02_analysis.py        # data/processed/analysis.gpkg, outputs/
python scripts/03_make_maps.py       # maps 1-3
pytest -q
```

Tested with Python 3.13 on macOS. The WFS serves current data, so a later download may give slightly different counts.

The QGIS project `qgis/bc_watershed_coverage.qgz` (built with QGIS 4.2.3) loads the layers in `data/processed/analysis.gpkg` and holds the A4 layout behind map 4. `scripts/04_qgis_project.py` rebuilds it with the Python bundled with QGIS (see the script header). Map 4 was not regenerated in the latest edit.

## Repository layout

- `scripts/`: 01 download, 02 analysis, 03 maps, 04 QGIS project
- `data/raw/`: downloaded GeoJSON (not committed); `data/processed/analysis.gpkg`: analysis layers
- `outputs/`: `summary.json` and `watershed_coverage.csv` (every figure above comes from these)
- `maps/`, `qgis/`, `tests/`, `docs/` (data sources, download manifest, progress notes)

## Limitations

- Coverage is presence of stations only. It is not water quality, flow or environmental risk.
- The near-water EMS class is an approximation (method step 4).
- EMS is a legacy snapshot. The 2016 cut-off is my choice. Sampling frequency, parameters and data quality are not assessed.
- Density depends on unit size. One unit (Unnamed 8183, 0.08 km2) is a sliver and its density is not meaningful.
- The study area follows the download extent, not full watershed-group boundaries, so outer edges may under-report coverage.
- 5 km is a screening distance. It is straight-line, ignores flow direction and drainage divides, and does not mean a station represents that stream.
- The 5 km Fraser corridor figure uses the mapped Fraser River line and the same station set as the combined density.

## Licence

Code: MIT (see `LICENSE`). Data: contains information licensed under the [Open Government Licence - British Columbia](https://www2.gov.bc.ca/gov/content?id=A519A56BC2BF44E4A008B33FCF527F61).
