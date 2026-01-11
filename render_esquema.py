import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

# =========================
# CONFIG
# =========================
TEMPLATE_SVG = "esquema.drawio.svg"
OUT_SVG = "esquema_render.svg"

MAX_S = 29
INCLUDE_UNITS = False

# Color para bombas ON
PUMP_ON_COLOR = "#00c853"  # verde intenso

# Mapa: Driver -> ID de draw.io (data-cell-id en el SVG exportado)
PUMP_CELL_IDS = {
    "D4": "HbhBeWkGyhC53GPZ-frY-33",  # Primario Caldera 2
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

def load_latest_all(latest_path: Path):
    if not latest_path.exists():
        print(f"DEBUG: No existe latest_all.json en: {latest_path}")
        return {}
    return json.loads(latest_path.read_text(encoding="utf-8"))

def build_sensors_map(latest_all: dict) -> dict:
    out = {}
    sensors = latest_all.get("sensors", [])
    for s in sensors:
        item = safe_str(s.get("item", ""))
        m = re.fullmatch(r"S(\d+)", item)
        if not m:
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
        m = re.fullmatch(r"D(\d+)", item)
        if not m:
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
    NO pisa fill:none ni stroke:none.
    """
    if not style:
        return style

    # fill:none -> no tocar
    if not re.search(r"fill\s*:\s*none", style):
        if re.search(r"fill\s*:", style):
            style = re.sub(r"fill\s*:\s*[^;]+", f"fill:{color}", style)
        else:
            style = style.rstrip(";") + f";fill:{color}"

    # stroke:none -> no tocar
    if not re.search(r"stroke\s*:\s*none", style):
        if re.search(r"stroke\s*:", style):
            style = re.sub(r"stroke\s*:\s*[^;]+", f"stroke:{color}", style)

    return style

def paint_group_green(svg_root, cell_id: str, color: str) -> bool:
    """
    Busca el <g ... data-cell-id="..."> y pinta sus hijos.
    Devuelve True si lo encontró y modificó.
    """
    for elem in svg_root.iter():
        if elem.get("data-cell-id") == cell_id:
            # Pintamos todos los descendientes "dibujables"
            for child in elem.iter():
                # fill directo (sin pisar none)
                if "fill" in child.attrib and child.attrib["fill"] != "none":
                    child.attrib["fill"] = color

                # stroke directo (sin pisar none)
                if "stroke" in child.attrib and child.attrib["stroke"] != "none":
                    child.attrib["stroke"] = color

                # style inline
                if "style" in child.attrib:
                    child.attrib["style"] = update_style_color(child.attrib["style"], color)

            return True
    return False

def list_cell_ids(svg_root, limit=20):
    """Debug: lista algunos data-cell-id que existan en el SVG."""
    ids = []
    for e in svg_root.iter():
        cid = e.get("data-cell-id")
        if cid:
            ids.append(cid)
    ids = sorted(set(ids))
    print(f"DEBUG: encontrados {len(ids)} data-cell-id en el SVG.")
    if ids:
        print("DEBUG: primeros IDs:", ids[:limit])

# =========================
# MAIN
# =========================
def main():
    here = Path(__file__).resolve().parent
    svg_path = here / TEMPLATE_SVG
    out_path = here / OUT_SVG
    latest_path = here / "data" / "latest_all.json"

    if not svg_path.exists():
        raise FileNotFoundError(f"No existe {TEMPLATE_SVG} en {here}")

    latest_all = load_latest_all(latest_path)
    smap = build_sensors_map(latest_all)
    dmap = build_drivers_map(latest_all)

    print(f"DEBUG: sensors leídos = {len(smap)} | drivers leídos = {len(dmap)}")
    if "D4" in dmap:
        print(f"DEBUG: D4 raw='{dmap['D4']['value']}' norm='{normalize_on_off(dmap['D4']['value'])}'")
    else:
        print("DEBUG: D4 NO está en drivers.")

    # 1) Reemplazo tokens {{Sx}} en el SVG como texto
    svg_text = svg_path.read_text(encoding="utf-8")

    for n in range(1, MAX_S + 1):
        key = f"S{n}"
        if key not in smap:
            continue

        value = smap[key]["value"]
        units = smap[key]["units"]
        repl = f"{value} {units}".strip() if (INCLUDE_UNITS and units) else value

        svg_text = re.sub(r"\{\{" + re.escape(key) + r"\}\}", repl, svg_text)

    # 2) Parseamos el SVG
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as e:
        raise RuntimeError(f"El SVG no se puede parsear (mal formado). Error: {e}")

    # 3) Pinta D4 si está ON
    driver_key = "D4"
    if driver_key in dmap:
        state = normalize_on_off(dmap[driver_key]["value"])
        if state == "on":
            cell_id = PUMP_CELL_IDS.get(driver_key)
            if cell_id:
                ok = paint_group_green(root, cell_id, PUMP_ON_COLOR)
                print(f"DEBUG: {driver_key}=ON -> pintar verde. data-cell-id encontrado: {ok}")
                if not ok:
                    # Te ayuda a ver qué IDs reales hay en el SVG
                    list_cell_ids(root, limit=30)
                    print(f"DEBUG: revisa PUMP_CELL_IDS['{driver_key}'] porque NO coincide con el SVG.")
            else:
                print(f"DEBUG: No hay cell_id configurado para {driver_key}")
        else:
            print(f"DEBUG: {driver_key} no está ON (value='{dmap[driver_key]['value']}'), no se pinta.")
    else:
        print(f"DEBUG: {driver_key} no existe en latest_all.json, no se pinta.")

    # 4) Guardar SVG final
    svg_final = ET.tostring(root, encoding="unicode")
    out_path.write_text(svg_final, encoding="utf-8")
    print(f"OK: generado {OUT_SVG} (S rellenadas + bomba {driver_key} si ON).")

if __name__ == "__main__":
    main()
