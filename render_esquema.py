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
    "D3": "HbhBeWkGyhC53GPZ-frY-33",   # ON-OFF B. 1 Caldera ACS
    "D4": "HbhBeWkGyhC53GPZ-frY-29",   # M-P B. 2 - Caldera de Calefacción
    "D2": "HbhBeWkGyhC53GPZ-frY-36",   # M-P B. 5.1 - Calefacción
    "D1": "HbhBeWkGyhC53GPZ-frY-39",   # M-P B. 5.2 - Calefacción
    "D24": "HbhBeWkGyhC53GPZ-frY-49",  # M-P B. 4 Retorno ACS
    "D5": "HbhBeWkGyhC53GPZ-frY-52",   # ON-OFF B. 3A.1 - Prim. ACS
    "D6": "HbhBeWkGyhC53GPZ-frY-55",   # ON-OFF B. 3A.2 - Prim. ACS
    "D7": "HbhBeWkGyhC53GPZ-frY-42",   # M-P B. 3B.1 - Sec. ACS
    "D8": "HbhBeWkGyhC53GPZ-frY-45",   # M-P B. 3B.2 - Sec. ACS
    "D17": "KY_yovXKN2bWtjt0556d-11",  # M-P B. 6 - Sec. Paneles Solares
    "D9": "KY_yovXKN2bWtjt0556d-5",    # M-P B. 7.1 - Paneles Solares
    "D10": "KY_yovXKN2bWtjt0556d-8",   # M-P B. 7.2 - Paneles Solares
    "D15": "WpCggooiQa-CKCG4ur4o-82",  # A-C V2V Caldera 1
    "D12": "WpCggooiQa-CKCG4ur4o-80",  # A-C V2V Caldera 2
    "D13": "HbhBeWkGyhC53GPZ-frY-7",   # M-P Quemador Caldera 2
    "D16": "HbhBeWkGyhC53GPZ-frY-8",   # M-P Quemador Caldera 1
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
    return v  # otros formatos (p.ej. "100.00")

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
    if not style:
        return style

    if re.search(r"fill\s*:", style):
        style = re.sub(r"fill\s*:\s*[^;]+", f"fill:{color}", style)
    else:
        style = style.rstrip(";") + f";fill:{color}"

    if re.search(r"stroke\s*:", style):
        style = re.sub(r"stroke\s*:\s*[^;]+", f"stroke:{color}", style)

    return style

def paint_group(svg_root, cell_id: str, color: str) -> bool:
    for elem in svg_root.iter():
        if elem.get("data-cell-id") == cell_id:
            for child in elem.iter():
                if "fill" in child.attrib and child.attrib["fill"] != "none":
                    child.attrib["fill"] = color
                if "stroke" in child.attrib and child.attrib["stroke"] != "none":
                    child.attrib["stroke"] = color
                if "style" in child.attrib:
                    child.attrib["style"] = update_style_color(child.attrib["style"], color)
            return True
    return False

# =========================
# MAIN
# =========================
def main():
    # ✅ Clave: registrar namespaces para no romper xlink:href / href al serializar
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

    here = Path(__file__).resolve().parent
    svg_path = here / TEMPLATE_SVG
    out_path = here / OUT_SVG

    if not svg_path.exists():
        raise FileNotFoundError(f"No existe {TEMPLATE_SVG} en {here}")

    latest_all = load_latest_all()
    smap = build_sensors_map(latest_all)
    dmap = build_drivers_map(latest_all)

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

    # 2) Parseamos el SVG ya con las S rellenadas
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as e:
        raise RuntimeError(f"El SVG no se puede parsear (mal formado). Error: {e}")

    # 3) Pintar en verde TODAS las bombas configuradas que estén ON
    painted = []
    not_found = []
    not_on = []
    not_in_json = []

    for driver_key, cell_id in PUMP_CELL_IDS.items():
        if driver_key not in dmap:
            not_in_json.append(driver_key)
            continue

        state_raw = dmap[driver_key]["value"]
        state = normalize_on_off(state_raw)

        if state != "on":
            not_on.append((driver_key, state_raw))
            continue

        ok = paint_group(root, cell_id, PUMP_ON_COLOR)
        if ok:
            painted.append(driver_key)
        else:
            not_found.append(driver_key)

    print(f"DEBUG: Pintadas en verde (ON): {painted}")
    if not_on:
        print(f"DEBUG: No ON (no se pintan): {not_on}")
    if not_in_json:
        print(f"DEBUG: No existen en latest_all.json: {not_in_json}")
    if not_found:
        print(f"DEBUG: No se encontró data-cell-id en SVG para: {not_found}")

    # 4) Guardar SVG final (✅ bytes + xml_declaration para que GitHub/HTML lo trague bien)
    svg_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True, method="xml")
    out_path.write_bytes(svg_bytes)

    print(f"OK: generado {OUT_SVG} (S rellenadas + bombas ON en verde).")

if __name__ == "__main__":
    main()
