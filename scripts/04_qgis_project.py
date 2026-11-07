"""Build a QGIS project (qgis/bc_watershed_coverage.qgz) from data/processed/analysis.gpkg,
with styled layers and a print layout, and export the layout to maps/04_qgis_coverage_layout.png.

Run with the Python interpreter bundled with QGIS (not the project venv), e.g. on macOS:
  /Applications/QGIS*.app/Contents/MacOS/python scripts/04_qgis_project.py
The project stores relative paths, so it opens from any clone after scripts 01-02 are run.
"""
import sys
from pathlib import Path

from qgis.core import (
    QgsApplication, QgsProject, QgsVectorLayer, QgsCoordinateReferenceSystem,
    QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsSymbol, QgsFillSymbol, QgsLineSymbol,
    QgsMarkerSymbol, QgsPrintLayout, QgsLayoutItemMap, QgsLayoutItemLegend, QgsLayoutItemScaleBar,
    QgsLayoutItemLabel, QgsLayoutItemPicture, QgsLayoutPoint, QgsLayoutSize, QgsLayoutExporter,
    QgsUnitTypes, QgsLegendStyle, QgsRectangle, QgsLayerTreeLayer, QgsTextFormat, Qgis,
)
from qgis.PyQt.QtGui import QColor, QFont

ROOT = Path(__file__).resolve().parents[1]
GPKG = ROOT / "data/processed/analysis.gpkg"
OUT_QGZ = ROOT / "qgis/bc_watershed_coverage.qgz"
OUT_PNG = ROOT / "maps/04_qgis_coverage_layout.png"
MM = QgsUnitTypes.LayoutMillimeters if hasattr(QgsUnitTypes, "LayoutMillimeters") else Qgis.LayoutUnit.Millimeters

qgs = QgsApplication([], False)
qgs.initQgis()
proj = QgsProject.instance()
proj.setCrs(QgsCoordinateReferenceSystem("EPSG:3005"))
proj.setFileName(str(OUT_QGZ))
proj.writeEntryBool("Paths", "/Absolute", False)        # relative data paths


def add(layer_name, title, sql=None):
    uri = f"{GPKG}|layername={layer_name}"
    if sql:
        uri += f"|subset={sql}"
    lyr = QgsVectorLayer(uri, title, "ogr")
    if not lyr.isValid():
        sys.exit(f"Layer failed to load: {layer_name}")
    assert lyr.crs().authid() == "EPSG:3005", (layer_name, lyr.crs().authid())
    proj.addMapLayer(lyr)
    print(f"  {title}: {lyr.featureCount()} features, {lyr.crs().authid()}")
    return lyr


print("Layers:")
ws = add("watersheds", "Assessment watersheds - coverage class")
lakes = add("lakes", "Lakes >= 10 ha")
streams = add("streams", "Streams, order >= 3")
ems = add("ems_recent", "EMS site within 200 m of mapped water (proxy)", "\"near_sw\" = 1")
hyd = add("hydrometric", "Active hydrometric station", "\"STATION_OPERATING_STATUS\" LIKE 'ACTIVE%'")

# --- styling
cats = [("Active hydrometric station", "#4daf4a"), ("Near-water EMS site only", "#ffd966"),
        ("No active gauge or near-water EMS site", "#d9d9d9")]
counts = {c: 0 for c, _ in cats}
for f in ws.getFeatures():
    counts[f["coverage_class"]] += 1
renderer = QgsCategorizedSymbolRenderer("coverage_class", [
    QgsRendererCategory(v, QgsFillSymbol.createSimple({"color": col, "outline_color": "#777777", "outline_width": "0.15"}),
                        f"{v} (n={counts[v]})") for v, col in cats])
ws.setRenderer(renderer)
lakes.setRenderer(lakes.renderer().__class__(QgsFillSymbol.createSimple({"color": "#a9cce3", "outline_style": "no"})))
streams.setRenderer(streams.renderer().__class__(QgsLineSymbol.createSimple({"color": "#2b7bba", "width": "0.2"})))
ems.setRenderer(ems.renderer().__class__(QgsMarkerSymbol.createSimple(
    {"name": "circle", "color": "#1f3b73", "size": "1.2", "outline_style": "no"})))
hyd.setRenderer(hyd.renderer().__class__(QgsMarkerSymbol.createSimple(
    {"name": "triangle", "color": "#c0392b", "size": "2.6", "outline_color": "black", "outline_width": "0.15"})))

# layer order (top first)
root = proj.layerTreeRoot()
for i, lyr in enumerate([hyd, ems, streams, lakes, ws]):
    node = root.findLayer(lyr.id())
    clone = node.clone()
    root.insertChildNode(i, clone)
    root.removeChildNode(node)

# --- print layout (A4 landscape)
layout = QgsPrintLayout(proj)
layout.initializeDefaults()
layout.setName("Coverage map - A4 landscape")
proj.layoutManager().addLayout(layout)

def label(text, x, y, w, h, size, bold=False, color="#000000"):
    it = QgsLayoutItemLabel(layout)
    it.setText(text)
    fmt = QgsTextFormat()
    font = QFont("Helvetica"); font.setBold(bold)
    fmt.setFont(font); fmt.setSize(size); fmt.setColor(QColor(color))
    it.setTextFormat(fmt)
    layout.addLayoutItem(it)
    it.attemptMove(QgsLayoutPoint(x, y, MM)); it.attemptResize(QgsLayoutSize(w, h, MM))
    return it

label("Observed Monitoring Coverage by Assessment Watershed", 10, 6, 270, 10, 17, bold=True)
label("Lower Mainland / Fraser Valley, BC  |  Station presence only - not a measure of water quality or environmental risk",
      10, 15, 270, 7, 9.5, color="#444444")

m = QgsLayoutItemMap(layout)
m.setCrs(QgsCoordinateReferenceSystem("EPSG:3005"))
layout.addLayoutItem(m)
m.attemptMove(QgsLayoutPoint(10, 23, MM)); m.attemptResize(QgsLayoutSize(190, 140, MM))
ext = ws.extent(); ext.grow(4000)
m.zoomToExtent(ext)
m.setFrameEnabled(True)
m.setLayers([hyd, ems, streams, lakes, ws])

leg = QgsLayoutItemLegend(layout)
leg.setLinkedMap(m)
leg.setTitle("Legend")
leg.setAutoUpdateModel(False)
leg.setWrapString('')
lroot = leg.model().rootGroup()
lroot.clear()
for lyr in [ws, hyd, ems, streams, lakes]:
    lroot.addLayer(lyr)
layout.addLayoutItem(leg)
leg.attemptMove(QgsLayoutPoint(204, 26, MM))
leg.setSymbolWidth(6); leg.setSymbolHeight(3.5)
for style in (QgsLegendStyle.Title, QgsLegendStyle.Subgroup, QgsLegendStyle.SymbolLabel):
    fmt = QgsTextFormat(); fmt.setFont(QFont("Helvetica")); fmt.setSize(8 if style != QgsLegendStyle.Title else 11)
    leg.rstyle(style).setTextFormat(fmt)
leg.setColumnCount(1)
leg.adjustBoxSize()

sb = QgsLayoutItemScaleBar(layout)
sb.setStyle("Single Box")
sb.setLinkedMap(m)
sb.setUnits(QgsUnitTypes.DistanceKilometers if hasattr(QgsUnitTypes, "DistanceKilometers") else Qgis.DistanceUnit.Kilometers)
sb.setUnitLabel("km")
sb.setNumberOfSegments(2); sb.setNumberOfSegmentsLeft(0)
sb.setUnitsPerSegment(10)
layout.addLayoutItem(sb)
sb.attemptMove(QgsLayoutPoint(14, 148, MM))

arrow = QgsLayoutItemPicture(layout)
for p_ in [*QgsApplication.svgPaths(), str(Path(QgsApplication.pkgDataPath()) / 'svg')]:
    cand = Path(p_) / "arrows" / "NorthArrow_04.svg"
    if cand.exists():
        arrow.setPicturePath(str(cand)); break
else:
    sys.exit("North arrow SVG not found")
layout.addLayoutItem(arrow)
arrow.attemptMove(QgsLayoutPoint(188, 26, MM)); arrow.attemptResize(QgsLayoutSize(12, 12, MM))

label("Data: Province of British Columbia (DataBC): Freshwater Atlas assessment watersheds, streams and lakes; "
      "EMS monitoring locations; hydrometric stations. Contains information licensed under the Open Government "
      "Licence - British Columbia.\nProjection: NAD83 / BC Albers (EPSG:3005). EMS 'near-water' = recent EMS site within "
      "200 m of a mapped stream (order >= 3) or lake (>= 10 ha) - a spatial proxy.",
      10, 166, 277, 14, 6.5, color="#555555")

# --- export + save
exp = QgsLayoutExporter(layout)
settings = QgsLayoutExporter.ImageExportSettings(); settings.dpi = 200
res = exp.exportToImage(str(OUT_PNG), settings)
ok_val = QgsLayoutExporter.Success if hasattr(QgsLayoutExporter, "Success") else QgsLayoutExporter.ExportResult.Success
assert res == ok_val, f"export failed: {res}"
OUT_QGZ.parent.mkdir(exist_ok=True)
assert proj.write(str(OUT_QGZ)), "project write failed"
# make every stored data source relative (layout map-layer references otherwise keep absolute hints)
import zipfile, shutil
tmp = OUT_QGZ.with_suffix(".tmp")
with zipfile.ZipFile(OUT_QGZ) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename.endswith(".qgs"):
            data = data.decode("utf-8").replace(str(ROOT) + "/", "../").encode("utf-8")
        zout.writestr(item, data)
shutil.move(tmp, OUT_QGZ)
print("wrote", OUT_QGZ.relative_to(ROOT), "and", OUT_PNG.relative_to(ROOT))
qgs.exitQgis()
