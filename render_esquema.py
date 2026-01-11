import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

# =========================
# CONFIG
# =========================
TEMPLATE_SVG = "esquema.drawio.svg"
OUT_SVG = "esquema_render.svg"
LATEST_ALL_JSON = Path("data") / "latest_all.json"

MAX_S = 29
INCLUDE_UNITS = False

# Color para bombas ON
PUMP_ON_COLOR = "#00c853"  # verde intenso

# Mapa: Driver -> ID de draw.io (data-cell-id en el SVG exportado)
PUMP_CELL_IDS = {
    "D4": "HbhBeWkGyhC53GPZ-frY-33",  # Bomba / Caldera 2 (según tu esquema)
    # Puedes añadir más:
    # "D3": "....",
    # "D5": "....",
}

# =========================
# HELPERS
# =========================
def safe_str(x) -> str:
    return "" if x is None else str(x).strip()

def normalize_on_off(val: str) -> str:
    v = safe_str(val).lower()
    if v in ("on", "1", "true", "yes", "encendida", "encendido"):
        return "on"
    if v in ("off", "0", "false", "no", "apagada", "apagado"):
        return "off"
    return v  # por si viene otro formato

def load_latest_all():
    if not LATEST_ALL_JSON.exists():
        return {}
    return json.loads(LATEST_ALL_JSON.read_text(encoding="utf-8"))

def build_sensors_map(latest_all: dict) -> dict:
    out = {}
    sensors = latest_all.get("sensors", [])
    for s in sensors:
        item = safe_str(s.get("item", ""))
        if not re.fullmatch(r"S(\d+)", item):
            continue
        out[item] = {
            "value": safe_str(s.get("value", "")),
            "units": safe_str(s.get("units", "")),
        }
    return out

def build_drivers_map(latest_all: dict) -> dict:
    out = {}
    drivers = latest_all.get("drivers", [])
    for d in drivers:
        item = safe_str(d.get("item", ""))
        if not re.fullmatch(r"D(\d+)", item):
            continue
        out[item] = {
            "value": safe_str(d.get("value", "")),
            "label": safe_str(d.get("label", "")),
            "units": safe_str(d.get("units", "")),
        }
    return out

def update_style_color(style: str, color: str) -> str:
    """
    Cambia fill/stroke en un string style="...".
    """
    if not style:
        return style

    # Reemplaza fill:...
    if re.search(r"fill\s*:", style):
        style = re.sub(r"fill\s*:\s*[^;]+", f"fill:{color}", style)
    else:
        style = style.rstrip(";") + f";fill:{color}"

    # Reemplaza stroke:... si existe
    if re.search(r"stroke\s*:", style):
        style = re.sub(r"stroke\s*:\s*[^;]+", f"stroke:{color}", style)

    return style

def add_rotation_animation(elem: ET.Element, dur: str = "1.2s"):
    """
    Añade una animación de giro continuo al elemento SVG (normalmente un <g>).
    Nota: usa rotate alrededor de (0,0). Si quieres un giro perfecto alrededor del centro,
    habría que calcular cx/cy con el bbox (más complejo en SVG estático).
    """
    animate = ET.Element("animateTransform")
    animate.set("attributeName", "transform")
    animate.set("type", "rotate")
    animate.set("from", "0 0 0")
    animate.set("to", "360 0 0")
    animate.set("dur", dur)
    animate.set("repeatCount", "indefinite")
    elem.append(animate)

def paint_group_on(svg_root, cell_id: str, color: str, do_rotate: bool = True) -> bool:
    """
    Busca el <g ... data-cell-id="...">, pinta sus hijos y opcionalmente añade giro.
    Devuelve True si lo encontró y modificó.
    """
    for elem in svg_root.iter():
        if elem.get("data-cell-id") == cell_id:
            # Pintamos todos los descendientes "dibujables"
            for child in elem.iter():
                # fill directo
                if "fill" in child.attrib and child.attrib["fill"] != "none":
                    child.attrib["fill"] = color

                # stroke directo
                if "stroke" in child.attrib and child.attrib["stroke"] != "none":
                    child.attrib["stroke"] = color

                # style inline
                if "style" in child.attrib:
                    child.attrib["style"] = update_style_color(child.attrib["style"], color)

            # Animación de giro (solo si ON)
            if do_rotate:
                add_rotation_animation(elem, dur="1.2s")

            return True

    return False

# =========================
# MAIN
# =========================
def main():
    here = Path(__file__).resolve().parent
    svg_path = here / TEMPLATE_SVG
    out_path = here / OUT_SVG

    if not svg_path.exists():
        raise FileNotFoundError(f"No existe {TEMPLATE_SVG} en {here}")

    latest_all = load_latest_all()
    smap = build_sensors_map(latest_all)
    dmap = build_drivers_map(latest_all)

    # 1) Reemplazo tokens {{Sx}} en el SVG como texto (rápido por regex)
    svg_text = svg_path.read_text(encoding="utf-8")

    for n in range(1, MAX_S + 1):
        key = f"S{n}"
        if key not in smap:
            continue

        value = smap[key]["value"]
        units = smap[key]["units"]
        repl = f"{value} {units}".strip() if (INCLUDE_UNITS and units) else value

        svg_text = re.sub(r"\{\{" + re.escape(key) + r"\}\}", repl, svg_text)

    # 2) Parseamos el SVG ya con los S rellenados para pintar bombas por ID
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as e:
        raise RuntimeError(f"El SVG no se puede parsear (mal formado). Error: {e}")

    # 3) Pintar y animar bombas ON según drivers
    for driver_key, cell_id in PUMP_CELL_IDS.items():
        if driver_key not in dmap:
            print(f"DEBUG: {driver_key} no existe en latest_all.json, no se pinta/ani­ma.")
            continue

        state = normalize_on_off(dmap[driver_key]["value"])
        if state == "on":
            ok = paint_group_on(root, cell_id, PUMP_ON_COLOR, do_rotate=True)
            print(f"DEBUG: {driver_key} = ON -> verde + giro. Encontrado ID en SVG: {ok}")
        else:
            print(f"DEBUG: {driver_key} no está ON (value='{dmap[driver_key]['value']}'), no se pinta/ani­ma.")

    # 4) Guardar SVG final
    svg_final = ET.tostring(root, encoding="unicode")
    out_path.write_text(svg_final, encoding="utf-8")
    print(f"OK: generado {OUT_SVG} (S rellenadas + bombas ON en verde y con giro).")

if __name__ == "__main__":
    main()
