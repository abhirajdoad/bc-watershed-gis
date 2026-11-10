# Data sources

All layers were pulled from the DataBC / BC Geographic Warehouse WFS (`https://openmaps.gov.bc.ca/geo/pub/ows`)
on the date in `download_manifest.json`, requested in **NAD83 / BC Albers (EPSG:3005)**.
Licence for all: **[Open Government Licence – British Columbia](https://www2.gov.bc.ca/gov/content?id=A519A56BC2BF44E4A008B33FCF527F61)**
(contains information licensed under the OGL-BC; attribution to the Province of British Columbia). Raw data are not committed; re-download with script 01.

| Layer | WFS layer | Catalogue record | Publisher | Filter used |
|---|---|---|---|---|
| Assessment watersheds (analysis units) | `WHSE_BASEMAPPING.FWA_ASSESSMENT_WATERSHEDS_POLY` | [freshwater-atlas-assessment-watersheds](https://catalogue.data.gov.bc.ca/dataset/freshwater-atlas-assessment-watersheds) | GeoBC | bbox |
| Streams | `WHSE_BASEMAPPING.FWA_STREAM_NETWORKS_SP` | [freshwater-atlas-stream-network](https://catalogue.data.gov.bc.ca/dataset/freshwater-atlas-stream-network) | GeoBC | bbox, `STREAM_ORDER >= 3` |
| Lakes | `WHSE_BASEMAPPING.FWA_LAKES_POLY` | [freshwater-atlas-lakes](https://catalogue.data.gov.bc.ca/dataset/freshwater-atlas-lakes) | GeoBC | bbox, `AREA_HA >= 10` |
| Watershed groups | `WHSE_BASEMAPPING.FWA_WATERSHED_GROUPS_POLY` | (Freshwater Atlas) | GeoBC | bbox (downloaded for context; not used in analysis) |
| Hydrometric stations | `WHSE_ENVIRONMENTAL_MONITORING.ENVCAN_HYDROMETRIC_STN_SP` | [hydrometric-stations-active-and-discontinued](https://catalogue.data.gov.bc.ca/dataset/hydrometric-stations-active-and-discontinued) | EMA Branch (federal–provincial program with ECCC) | bbox |
| EMS monitoring locations | `WHSE_ENVIRONMENTAL_MONITORING.EMS_MONITORING_LOCN_TYPES_SVW` | [bc-environmental-monitoring-locations](https://catalogue.data.gov.bc.ca/dataset/bc-environmental-monitoring-locations) | EMA Branch | bbox |

**Download extent:** BC Albers x 1,170,000–1,330,000, y 430,000–520,000 (≈ Fraser Valley / Lower Mainland).

**Caveats**
- EMS is a legacy system. Its newest sample date in the downloaded locations is 2026-02-18, and the download was made on 2026-11-06. I understand the province has been moving EMS data to a new system (EnMoDS), but I did not save the catalogue notice, so the replacement date is not stated here. This analysis uses only the EMS location snapshot.
- EMS records with no `LAST_SAMPLE_DATE` (2,718 in the download extent) are treated as not recently sampled. Hydrometric stations with status `NA` (4) are treated as inactive.
- Only station **metadata** (location, sample dates/counts) is used. **No monitoring results/measurements are used or reported.**
- The `LOCATION_TYPE_CD` codes are not decoded: no published code table was found, so EMS locations of all media (air, water, wells, permits…) are in the "recent EMS" set. A spatial proxy (within 200 m of mapped water) is used to flag likely surface-water sites. It is a proxy, not a confirmed site type (see README).
