"""
PREVISION DE TIEMPO SEVERO - NEA (Noreste Argentino)
======================================================

Genera un mapa de "outlook" de tiempo severo para la región del NEA
(Chaco, Formosa, Corrientes, Misiones y alrededores), replicando el
estilo de los outlooks tipo SPC: polígonos anidados de severidad,
marco con coordenadas lat/lon, leyenda, ciudades marcadas, etc.

REQUISITO OBLIGATORIO
----------------------
Este script NO se ejecuta si no encuentra el archivo GeoJSON con los
polígonos de severidad. Configurá la ruta en GEOJSON_PATH más abajo.

Estructura esperada del GeoJSON (podés ajustarla en CONFIG):
    FeatureCollection de polígonos, cada Feature con una propiedad
    (por defecto llamada "nivel") cuyo valor sea uno de:
        "tempestades", "nivel1", "nivel2", "nivel3", "nivel4"

    Ejemplo de properties de un Feature:
        { "nivel": "nivel2" }

Si tu GeoJSON usa otro nombre de campo o otros valores, ajustá
NIVEL_FIELD y el diccionario LEVELS en la sección CONFIG.

INSTALACION (en VSCode / terminal)
-----------------------------------
    python -m venv venv
    venv\\Scripts\\activate        (Windows)
    source venv/bin/activate      (Mac/Linux)
    pip install matplotlib geopandas shapely cartopy pyproj

FUENTES (Tahoma)
-----------------
Tahoma es una fuente propietaria de Microsoft, no se redistribuye
en este script. Para usarla:
    1. Copiá "tahoma.ttf" y "tahomabd.ttf" desde
       C:\\Windows\\Fonts\\ hacia una carpeta "fonts/" al lado de este
       script (fonts/tahoma.ttf, fonts/tahomabd.ttf).
    2. Si no se encuentran, el script usa automáticamente
       "DejaVu Sans" / "DejaVu Sans Bold" (vienen con matplotlib) y
       te avisa por consola, sin fallar.
"""

import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # backend seguro para generar archivos sin GUI

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import matplotlib.patheffects as patheffects
import geopandas as gpd
import cartopy.crs as ccrs
import cartopy.io.shapereader as shpreader
from shapely.geometry import box


# =====================================================================
# CONFIG - Editá esta sección segun tu caso
# =====================================================================

# --- Archivo GeoJSON con los polígonos de severidad ------------------
# Poné aca la ruta real de tu archivo cuando lo tengas armado.
GEOJSON_PATH = "severidad_nea.geojson"

# Nombre del campo dentro de "properties" que indica el nivel.
# Tu GeoJSON actual usa "level" (con valores tipo SPC: TSTM, MRGL, etc.)
NIVEL_FIELD = "level"

# --- Alias / traduccion de valores -------------------------------------
# Si tu GeoJSON usa codigos distintos a las claves internas del script
# (tempestades, nivel1, nivel2, nivel3, nivel4), mapealos aca.
# Si el dia de mañana tu GeoJSON ya usa directamente "nivel1", "nivel2",
# etc., no pasa nada: el alias es transparente (ver _normalize_nivel).
#
# Agregá mas entradas a medida que definas Nivel 2/3/4 (ej: SLGT, ENH,
# MDT, HIGH, o los nombres que decidas usar).
NIVEL_ALIASES = {
    "TSTM": "tempestades",
    "MRGL": "nivel1",
    "SLGT": "nivel2",
    "ENH":  "nivel3",
    "MDT":  "nivel4",   # nivel mas alto usado (rosa/magenta)
    # "HIGH": "nivel4", # el SPC real tiene un nivel mas (HIGH) que no
                         # se usa aca porque el esquema solo tiene 4
                         # niveles + tempestades. Descomentar y ajustar
                         # si en el futuro se agrega un 5to nivel.
}

# --- Titulo ------------------------------------------------------------
TITLE_TEXT = "PREVISION DE TIEMPO SEVERO"
SUBTITLE_DATE = "01/07/2026"   # se concatena como "TITULO - FECHA". Poné None para omitir.

# --- Region del mapa (NEA: Chaco, Formosa, Corrientes, Misiones) -----
LON_MIN, LON_MAX = -61.5, -53.0
LAT_MIN, LAT_MAX = -31.5, -21.0

# --- Colores (HEX que definiste) --------------------------------------
COLOR_BASEMAP = "#f2eeed"        # tierra
COLOR_WATER = "#dce6f0"          # oceano / rios / lagos

LEVELS = {
    # clave interna : (etiqueta en leyenda, color de borde, color de relleno)
    "tempestades": ("Tempestades",  "#bceabf", "#bce9c2"),
    "nivel1":      ("Nivel 1",      "#a5a897", "#ffff00"),
    "nivel2":      ("Nivel 2",      "#e09000", "#fea500"),
    "nivel3":      ("Nivel 3",      "#db0001", "#e94b4b"),
    "nivel4":      ("Nivel 4",      "#cc02d1", "#f300f0"),
}
# Orden de dibujo (de mas grande/externo a mas chico/interno)
LEVEL_ORDER = ["tempestades", "nivel1", "nivel2", "nivel3", "nivel4"]

# --- Ciudades a marcar --------------------------------------------------
# Formato: (nombre, lat, lon, dx, dy, ha)
#   dx, dy : desplazamiento del TEXTO respecto al marcador, en grados
#            (opcional, default 0.08 / 0.05)
#   ha     : alineacion horizontal del texto ("left"/"right", opcional,
#            default "left"). Usar "right" + dx negativo para poner el
#            texto a la izquierda del marcador (util cuando hay ciudades
#            muy cercanas entre si, como Resistencia/Corrientes).
CITIES = [
    ("Resistencia", -27.4514, -58.9867, -0.10, 0.14, "right"),
    ("Corrientes", -27.4806, -58.8341, 0.10, -0.18, "left"),
    ("Formosa", -26.1775, -58.1781, 0.08, 0.05, "left"),
    ("Posadas", -27.3621, -55.9008, 0.08, 0.05, "left"),
    ("Presidencia Roque Sáenz Peña", -26.7852, -60.4388, 0.08, 0.05, "left"),
    ("Reconquista", -29.1500, -59.6500, -0.10, 0.14, "right"),
    ("Goya", -29.1383, -59.2669, 0.10, -0.16, "left"),
    ("Puerto Iguazú", -25.5951, -54.5734, 0.08, 0.05, "left"),
    ("Oberá", -27.4876, -55.1199, 0.08, 0.05, "left"),
    ("Clorinda", -25.2833, -57.7167, 0.08, 0.05, "left"),
    ("Santo Tomé", -28.5522, -56.0522, 0.08, 0.05, "left"),
    ("Charata", -27.2167, -61.1833, 0.08, 0.05, "left"),
]

# --- Salida ------------------------------------------------------------
OUTPUT_PATH = "previsao_tiempo_severo_nea.png"
FIGSIZE = (11, 10)
DPI = 200

# --- Fuentes -------------------------------------------------------------
FONTS_DIR = Path(__file__).resolve().parent / "fonts"
FONT_REGULAR_CANDIDATES = [
    FONTS_DIR / "tahoma.ttf",
    Path("C:/Windows/Fonts/tahoma.ttf"),
]
FONT_BOLD_CANDIDATES = [
    FONTS_DIR / "tahomabd.ttf",
    Path("C:/Windows/Fonts/tahomabd.ttf"),
]


# =====================================================================
# FUENTES: deteccion con fallback seguro
# =====================================================================

def _find_font(candidates, fallback_family, fallback_weight):
    """Busca la primera fuente existente en `candidates`. Si no
    encuentra ninguna, devuelve una FontProperties de fallback y
    avisa por consola."""
    for path in candidates:
        if path and Path(path).is_file():
            fm.fontManager.addfont(str(path))
            prop = fm.FontProperties(fname=str(path))
            print(f"[fuente] Usando: {path}")
            return prop
    print(
        f"[fuente] No se encontro Tahoma en: "
        f"{[str(c) for c in candidates]}. "
        f"Usando fallback '{fallback_family}' (peso: {fallback_weight})."
    )
    return fm.FontProperties(family=fallback_family, weight=fallback_weight)


FONT_REGULAR = _find_font(FONT_REGULAR_CANDIDATES, "DejaVu Sans", "normal")
FONT_BOLD = _find_font(FONT_BOLD_CANDIDATES, "DejaVu Sans", "bold")


# =====================================================================
# GEOJSON: carga obligatoria, el script NO corre sin esto
# =====================================================================

def _normalize_nivel(value):
    """Traduce un valor crudo del GeoJSON (ej: 'TSTM', 'MRGL') a la
    clave interna que usa el script (ej: 'tempestades', 'nivel1').

    Si el valor ya es una clave interna valida (por ejemplo si en el
    futuro tu GeoJSON usa directamente 'nivel1', 'nivel2', etc.), se
    devuelve tal cual, sin necesidad de tocar NIVEL_ALIASES."""
    if value in LEVELS:
        return value
    return NIVEL_ALIASES.get(value, value)


def load_severity_geojson(path):
    """Carga el GeoJSON de poligonos de severidad. Si el archivo no
    existe, aborta la ejecucion del script con un mensaje claro
    (no genera ningun plot)."""
    p = Path(path)
    if not p.is_file():
        sys.exit(
            "\n[ERROR] No se encontro el archivo GeoJSON de severidad en:\n"
            f"    {p.resolve()}\n\n"
            "El script no puede continuar sin este archivo.\n"
            "Pasos:\n"
            "  1. Armá tu GeoJSON con los poligonos de severidad.\n"
            "  2. Cada Feature debe tener en 'properties' un campo "
            f"'{NIVEL_FIELD}' con uno de estos valores: "
            f"{list(LEVELS.keys())}\n"
            f"  3. Actualizá GEOJSON_PATH en este script "
            f"(actualmente: '{GEOJSON_PATH}').\n"
        )

    gdf = gpd.read_file(p)

    if NIVEL_FIELD not in gdf.columns:
        sys.exit(
            f"\n[ERROR] El GeoJSON '{p}' no tiene la columna "
            f"'{NIVEL_FIELD}'.\n"
            f"Columnas encontradas: {list(gdf.columns)}\n"
            "Ajustá NIVEL_FIELD en la seccion CONFIG para que coincida "
            "con tu archivo."
        )

    # Aseguramos CRS geografico (lat/lon) para que coincida con el mapa
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)

    # Traducimos los valores crudos (ej: "TSTM", "MRGL") a las claves
    # internas del script (ej: "tempestades", "nivel1") usando
    # NIVEL_ALIASES. Guardamos el resultado en una columna nueva para
    # no pisar el dato original.
    valores_originales = gdf[NIVEL_FIELD].unique().tolist()
    gdf["_nivel_normalizado"] = gdf[NIVEL_FIELD].apply(_normalize_nivel)

    valores_invalidos = set(gdf["_nivel_normalizado"].unique()) - set(LEVELS.keys())
    if valores_invalidos:
        print(
            f"[AVISO] Estos valores de '{NIVEL_FIELD}' no coinciden con "
            f"ningun nivel conocido (ni directamente ni via NIVEL_ALIASES) "
            f"y sus poligonos NO se van a colorear: {valores_invalidos}\n"
            f"        Valores originales en el archivo: {valores_originales}\n"
            f"        Agregalos a NIVEL_ALIASES si corresponde."
        )
    else:
        print(
            f"[OK] Todos los valores de '{NIVEL_FIELD}' fueron "
            f"reconocidos correctamente: {valores_originales}"
        )

    return gdf


# =====================================================================
# GEOGRAFIA BASE (Natural Earth via cartopy, se descarga automaticamente)
# =====================================================================

def get_base_layers():
    """Devuelve los shapefiles/readers de Natural Earth necesarios.
    Cartopy los descarga automaticamente la primera vez que se usan
    (requiere conexion a internet una sola vez, luego quedan
    cacheados localmente)."""
    countries = shpreader.natural_earth(
        resolution="10m", category="cultural", name="admin_0_countries"
    )
    provinces = shpreader.natural_earth(
        resolution="10m",
        category="cultural",
        name="admin_1_states_provinces",
    )
    lakes = shpreader.natural_earth(
        resolution="10m", category="physical", name="lakes"
    )
    rivers = shpreader.natural_earth(
        resolution="10m",
        category="physical",
        name="rivers_lake_centerlines",
    )
    return countries, provinces, lakes, rivers


# =====================================================================
# FORMATO DE COORDENADAS: grados-minutos-segundos como en el original
# =====================================================================

def _dms_label(value, is_lat):
    hemisferio = ("S" if value < 0 else "N") if is_lat else ("W" if value < 0 else "E")
    value = abs(value)
    grados = int(value)
    minutos_float = (value - grados) * 60
    minutos = int(minutos_float)
    segundos = int(round((minutos_float - minutos) * 60))
    if segundos == 60:
        segundos = 0
        minutos += 1
    if minutos == 60:
        minutos = 0
        grados += 1
    return f"{grados}\u00b0{minutos:02d}'{segundos:02d}\"{hemisferio}"


def lon_formatter(x, pos=None):
    return _dms_label(x, is_lat=False)


def lat_formatter(y, pos=None):
    return _dms_label(y, is_lat=True)


# =====================================================================
# PLOT PRINCIPAL
# =====================================================================

def build_plot(gdf_severity):
    proj = ccrs.PlateCarree()

    fig = plt.figure(figsize=FIGSIZE, dpi=DPI, facecolor="white")
    # OJO: el ancho del mapa (0.62) se deja deliberadamente mas chico que
    # el original para dejar espacio a la derecha para las etiquetas de
    # longitud del borde derecho + la leyenda, sin que se superpongan.
    ax = fig.add_axes([0.08, 0.06, 0.62, 0.82], projection=proj)
    ax.set_extent([LON_MIN, LON_MAX, LAT_MIN, LAT_MAX], crs=proj)

    # --- Fondo: tierra y agua -----------------------------------------
    ax.add_feature(
        matplotlib.patches.Rectangle((0, 0), 1, 1),  # placeholder, se reemplaza abajo
    ) if False else None

    ax.set_facecolor(COLOR_WATER)  # el "agua" queda de fondo por defecto

    countries_path, provinces_path, lakes_path, rivers_path = get_base_layers()

    # Tierra (paises) rellena con color de basemap
    countries_reader = shpreader.Reader(countries_path)
    for rec in countries_reader.records():
        geom = rec.geometry
        ax.add_geometries(
            [geom],
            crs=proj,
            facecolor=COLOR_BASEMAP,
            edgecolor="none",
            zorder=1,
        )

    # Provincias / estados (lineas finas)
    provinces_reader = shpreader.Reader(provinces_path)
    for rec in provinces_reader.records():
        ax.add_geometries(
            [rec.geometry],
            crs=proj,
            facecolor="none",
            edgecolor="black",
            linewidth=0.5,
            zorder=3,
        )

    # Paises (linea de borde un poco mas gruesa)
    for rec in countries_reader.records():
        ax.add_geometries(
            [rec.geometry],
            crs=proj,
            facecolor="none",
            edgecolor="black",
            linewidth=0.9,
            zorder=4,
        )

    # Lagos
    lakes_reader = shpreader.Reader(lakes_path)
    for rec in lakes_reader.records():
        ax.add_geometries(
            [rec.geometry], crs=proj, facecolor=COLOR_WATER,
            edgecolor=COLOR_WATER, zorder=2,
        )

    # Rios (como lineas, coloreadas igual que el agua)
    rivers_reader = shpreader.Reader(rivers_path)
    for rec in rivers_reader.records():
        ax.add_geometries(
            [rec.geometry], crs=proj, facecolor="none",
            edgecolor=COLOR_WATER, linewidth=1.3, zorder=2,
        )

    # --- Poligonos de severidad (orden: mas grande -> mas chico) -----
    for nivel_key in LEVEL_ORDER:
        if nivel_key not in LEVELS:
            continue
        _, edge_color, fill_color = LEVELS[nivel_key]
        subset = gdf_severity[gdf_severity["_nivel_normalizado"] == nivel_key]
        if subset.empty:
            continue
        ax.add_geometries(
            subset.geometry,
            crs=proj,
            facecolor=fill_color,
            edgecolor=edge_color,
            linewidth=1.2,
            zorder=10 + LEVEL_ORDER.index(nivel_key),
        )

    # --- Redibujar fronteras POR ENCIMA de los poligonos de severidad -
    # Los poligonos de severidad se dibujan con zorder mas alto que las
    # fronteras (para que el relleno se vea), pero eso las tapa donde
    # se superponen. Las volvemos a dibujar aca (solo lineas, sin
    # relleno) con un zorder aun mayor, para que los limites
    # provinciales/nacionales queden siempre visibles encima del color.
    for rec in provinces_reader.records():
        ax.add_geometries(
            [rec.geometry],
            crs=proj,
            facecolor="none",
            edgecolor="black",
            linewidth=0.5,
            zorder=16,
        )
    for rec in countries_reader.records():
        ax.add_geometries(
            [rec.geometry],
            crs=proj,
            facecolor="none",
            edgecolor="black",
            linewidth=0.9,
            zorder=17,
        )

    # --- Ciudades: circulo blanco + borde negro fino ------------------
    for name, lat, lon, dx, dy, ha in CITIES:
        if not (LON_MIN <= lon <= LON_MAX and LAT_MIN <= lat <= LAT_MAX):
            continue
        ax.plot(
            lon, lat,
            marker="o",
            markersize=6,
            markerfacecolor="white",
            markeredgecolor="black",
            markeredgewidth=1.0,
            transform=proj,
            zorder=20,
        )
        ax.text(
            lon + dx, lat + dy, name,
            transform=proj,
            fontsize=9,
            ha=ha,
            fontproperties=FONT_REGULAR,
            zorder=21,
            path_effects=[
                patheffects.withStroke(linewidth=2.5, foreground="white")
            ],
        )

    # --- Marco con coordenadas lat/lon en los 4 costados --------------
    gl = ax.gridlines(
        crs=proj,
        draw_labels=True,
        linewidth=0.4,
        color="gray",
        alpha=0.4,
        linestyle="--",
    )
    gl.top_labels = True
    gl.bottom_labels = True
    gl.left_labels = True
    gl.right_labels = True
    gl.xformatter = mticker.FuncFormatter(lon_formatter)
    gl.yformatter = mticker.FuncFormatter(lat_formatter)
    gl.xlabel_style = {"fontproperties": FONT_REGULAR, "size": 9}
    gl.ylabel_style = {"fontproperties": FONT_REGULAR, "size": 9}

    for spine in ax.spines.values():
        spine.set_edgecolor("black")
        spine.set_linewidth(1.2)

    # --- Titulo ---------------------------------------------------------
    titulo = TITLE_TEXT
    if SUBTITLE_DATE:
        titulo = f"{TITLE_TEXT} - {SUBTITLE_DATE}"
    fig.text(
        0.5, 0.955, titulo,
        ha="center", va="center",
        fontsize=20,
        fontproperties=FONT_BOLD,
        color="black",
    )

    # --- Leyenda ---------------------------------------------------------
    # Posicionada bien a la derecha del eje del mapa (que ahora termina
    # en x=0.70) para no solaparse con las etiquetas de longitud del
    # borde derecho del mapa.
    legend_ax = fig.add_axes([0.80, 0.10, 0.18, 0.30])
    legend_ax.axis("off")
    legend_ax.text(
        0.0, 1.0, "NIVEL DE SEVERIDAD",
        fontsize=12, fontproperties=FONT_BOLD,
        ha="left", va="top",
    )

    y0 = 0.82
    dy = 0.16
    for nivel_key in LEVEL_ORDER:
        if nivel_key not in LEVELS:
            continue
        label, edge_color, fill_color = LEVELS[nivel_key]
        legend_ax.add_patch(
            mpatches.Rectangle(
                (0.0, y0 - 0.06), 0.14, 0.10,
                facecolor=fill_color, edgecolor=edge_color, linewidth=1.2,
                transform=legend_ax.transAxes,
            )
        )
        legend_ax.text(
            0.20, y0, label,
            fontsize=11, fontproperties=FONT_REGULAR,
            ha="left", va="center",
            transform=legend_ax.transAxes,
        )
        y0 -= dy

    # --- Fondo blanco general (recuadro) ---------------------------------
    fig.patch.set_facecolor("white")

    return fig


# =====================================================================
# MAIN
# =====================================================================

def main():
    gdf_severity = load_severity_geojson(GEOJSON_PATH)
    fig = build_plot(gdf_severity)
    fig.savefig(OUTPUT_PATH, dpi=DPI, facecolor="white")
    print(f"[OK] Mapa generado en: {Path(OUTPUT_PATH).resolve()}")


if __name__ == "__main__":
    main()
