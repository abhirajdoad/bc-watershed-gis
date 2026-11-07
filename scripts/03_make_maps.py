"""Render three PNG maps (BC Albers, EPSG:3005) from data/processed/analysis.gpkg."""
from pathlib import Path
import geopandas as gpd, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

ROOT = Path(__file__).resolve().parents[1]
GPKG, MAPS = ROOT / "data/processed/analysis.gpkg", ROOT / "maps"
MAPS.mkdir(exist_ok=True)
SRC = ("Data: DataBC / GeoBC Freshwater Atlas, EMS Monitoring Locations, Hydrometric Stations (Open Government Licence - BC).\n"
       "Projection: NAD83 / BC Albers (EPSG:3005). Analysis units: FWA assessment watersheds (LFRA, CHWK, HARR groups).")
BLUE, DARK = "#2b7bba", "#1b1b1b"

ws = gpd.read_file(GPKG, layer="watersheds"); st = gpd.read_file(GPKG, layer="streams")
lk = gpd.read_file(GPKG, layer="lakes"); ems = gpd.read_file(GPKG, layer="ems_recent"); hy = gpd.read_file(GPKG, layer="hydrometric")
hya = hy[hy.STATION_OPERATING_STATUS.str.startswith("ACTIVE")]; emsw = ems[ems.near_sw]
minx, miny, maxx, maxy = ws.total_bounds
pad = 5000

def frame(title, subtitle):
    fig, ax = plt.subplots(figsize=(11, 9))
    ax.set_xlim(minx - pad, maxx + pad); ax.set_ylim(miny - pad, maxy + pad); ax.set_aspect("equal")
    ax.set_title(title, fontsize=16, fontweight="bold", loc="left", pad=22)
    ax.text(0, 1.015, subtitle, transform=ax.transAxes, fontsize=10, color="#444")
    ax.ticklabel_format(style="plain"); ax.tick_params(labelsize=7)
    ax.set_xlabel("Easting (m), EPSG:3005", fontsize=8); ax.set_ylabel("Northing (m), EPSG:3005", fontsize=8)
    ax.grid(True, color="#ddd", lw=0.4)
    fig.text(0.01, 0.008, SRC, fontsize=6.5, color="#555", va="bottom")
    return fig, ax

def furniture(ax):
    # scale bar (20 km) and north arrow (grid north; EPSG:3005 convergence is small in this AOI)
    x0, y0 = minx + 4000, maxy - 12000
    ax.add_patch(Rectangle((x0 - 3000, y0 - 3000), 29000, 11500, fc="white", ec="none", alpha=.8, zorder=9))
    for i, c in enumerate(["k", "w"]):
        ax.add_patch(Rectangle((x0 + i * 10000, y0), 10000, 1500, fc=c, ec="k", lw=.6, zorder=10))
    for v in (0, 10, 20): ax.text(x0 + v * 1000, y0 + 2300, str(v), ha="center", fontsize=7, zorder=10)
    ax.text(x0 + 20000, y0 + 4800, "km", fontsize=7, ha="left", zorder=10)
    ax.annotate("N", xy=(0.95, 0.96), xytext=(0.95, 0.88), xycoords="axes fraction", ha="center", fontsize=13, fontweight="bold",
                arrowprops=dict(arrowstyle="-|>", color="k", lw=1.5))

def base(ax, wsfc="#f4f1ea"):
    ws.plot(ax=ax, fc=wsfc, ec="#9a9a9a", lw=0.4, zorder=1)
    lk.plot(ax=ax, fc="#a9cce3", ec="#6ea0c8", lw=0.3, zorder=2)

def save(fig, name):
    fig.subplots_adjust(left=0.08, right=0.97, top=0.9, bottom=0.25)
    fig.savefig(MAPS / name, dpi=200); plt.close(fig); print("wrote", name)

# ---- Map 1: study area, hydrography, stations
fig, ax = frame("Map 1 - Study Area, Hydrography and Monitoring Stations",
                "Lower Mainland / Fraser Valley: Lower Fraser, Chilliwack and Harrison watershed groups")
base(ax)
st.assign(w=0.3 + 0.35 * (st.STREAM_ORDER - 3)).plot(ax=ax, color=BLUE, linewidth=st.STREAM_ORDER.sub(3).mul(.35).add(.3), zorder=3)
ws.boundary.plot(ax=ax, color="#7a7a7a", lw=0.4, zorder=4)
ems.plot(ax=ax, color="#e08a1e", markersize=7, alpha=.7, zorder=5)
hy[~hy.index.isin(hya.index)].plot(ax=ax, color="#888", marker="^", markersize=14, zorder=6)
hya.plot(ax=ax, color="#c0392b", marker="^", markersize=40, edgecolor="k", linewidth=.5, zorder=7)
ax.legend(handles=[Line2D([], [], color=BLUE, lw=1.2, label="Streams, order >= 3 (FWA)"),
                   Patch(fc="#a9cce3", ec="#6ea0c8", label="Lakes >= 10 ha (FWA)"),
                   Patch(fc="#f4f1ea", ec="#9a9a9a", label="Assessment watershed boundary (n=138)"),
                   Line2D([], [], marker="o", ls="", color="#e08a1e", label=f"EMS site, last sampled >= 2016 (n={len(ems)})"),
                   Line2D([], [], marker="^", ls="", color="#c0392b", mec="k", ms=8, label=f"Hydrometric station, active (n={len(hya)})"),
                   Line2D([], [], marker="^", ls="", color="#888", ms=6, label=f"Hydrometric station, discontinued/NA (n={len(hy)-len(hya)})")],
          loc="upper center", bbox_to_anchor=(0.5, -0.085), ncol=2, fontsize=8, title="Legend", title_fontsize=9, framealpha=.95).set_zorder(20)
furniture(ax); save(fig, "01_study_area_stations.png")

# ---- Map 2: station density choropleth
fig, ax = frame("Map 2 - Monitoring-Station Density by Assessment Watershed",
                "Distinct sites per 100 km2: active hydrometric stations + recent EMS sites within 200 m of mapped water (proxy)")
bins = [0, 1e-9, 1, 2, 5, 1e9]; labels = ["0 (none)", "> 0 to 1", "1 to 2", "2 to 5", "> 5"]
cols = ["#f7f7f7", "#fee8c8", "#fdbb84", "#e34a33", "#7f0000"]
cat = np.digitize(ws.dens_sites_comb, bins[1:-1], right=False)
cat = np.where(ws.dens_sites_comb == 0, 0, np.clip(np.digitize(ws.dens_sites_comb, [1, 2, 5]) + 1, 1, 4))
ws.assign(c=[cols[i] for i in cat]).plot(ax=ax, color=[cols[i] for i in cat], ec="#777", lw=.4, zorder=1)
lk.plot(ax=ax, fc="#a9cce3", ec="none", zorder=2)
emsw.plot(ax=ax, color="#1f3b73", markersize=6, zorder=5); hya.plot(ax=ax, color="k", marker="^", markersize=26, zorder=6)
ax.legend(handles=[Patch(fc=c, ec="#777", label=l) for c, l in zip(cols, labels)] + [
    Patch(fc="#a9cce3", label="Lakes >= 10 ha"),
    Line2D([], [], marker="o", ls="", color="#1f3b73", ms=4, label=f"EMS site within 200 m of mapped water (n={len(emsw)})"),
    Line2D([], [], marker="^", ls="", color="k", ms=7, label=f"Active hydrometric (n={len(hya)})")],
    loc="upper center", bbox_to_anchor=(0.5, -0.085), ncol=2, fontsize=8, title="Monitoring sites per 100 km2", title_fontsize=9, framealpha=.95).set_zorder(20)
furniture(ax); save(fig, "02_station_density.png")

# ---- Map 3: observed coverage & 5 km buffers
fig, ax = frame("Map 3 - Observed Monitoring Coverage (not environmental risk)",
                "Station presence per watershed; dashed line = 5 km (straight-line) from active hydrometric stations")
cmap = {"Active hydrometric station": "#4daf4a", "Near-water EMS site only": "#ffd966",
        "No active gauge or near-water EMS site": "#d9d9d9"}
ws.plot(ax=ax, color=ws.coverage_class.map(cmap), ec="#777", lw=.4, zorder=1)
lk.plot(ax=ax, fc="#a9cce3", ec="none", zorder=2)
st.plot(ax=ax, color=BLUE, linewidth=.35, zorder=3)
gpd.GeoSeries(hya.buffer(5000).union_all(), crs=3005).boundary.plot(ax=ax, color="#c0392b", lw=1, ls="--", zorder=4)
hya.plot(ax=ax, color="#c0392b", marker="^", markersize=30, edgecolor="k", linewidth=.4, zorder=6)
emsw.plot(ax=ax, color="#1f3b73", markersize=5, zorder=5)
n = ws.coverage_class.value_counts()
ax.legend(handles=[Patch(fc=c, ec="#777", label=f"{k} (n={n.get(k,0)})") for k, c in cmap.items()] + [
    Line2D([], [], color=BLUE, lw=1, label="Streams, order >= 3"),
    Line2D([], [], color="#c0392b", ls="--", label="5 km from active hydrometric station"),
    Line2D([], [], marker="^", ls="", color="#c0392b", mec="k", ms=7, label="Active hydrometric station"),
    Line2D([], [], marker="o", ls="", color="#1f3b73", ms=4, label="EMS site within 200 m of mapped water (proxy)")],
    loc="upper center", bbox_to_anchor=(0.5, -0.085), ncol=2, fontsize=7.5, title="Watershed coverage class", title_fontsize=9, framealpha=.95).set_zorder(20)
furniture(ax); save(fig, "03_coverage_buffers.png")
