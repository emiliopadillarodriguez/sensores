import json
import re
from pathlib import Path

# Archivos
TEMPLATE_SVG = "esquema.drawio.svg"
OUT_SVG = "esquema_render.svg"

# Ahora leemos el combinado (S + D)
LATEST_ALL_JSON = Path("data") / "latest_all.json"

MAX_S = 29
INCLUDE_UNITS = False


def safe_str(x) -> str:
    return "" if x is None else str(x).strip()


def load_latest_sensors_map(data: dict) -> dict:
    """
    Devuelve:
      {"S1": {"value":"-0.96","units":"ºC"}, ...}
    """
    sensors = data.get("sensors", [])
    out = {}

    for s in sensors:
        item = safe_str(s.get("item", ""))
        m = re.fullmatch(r"S(\d+)", item)
        if not m:
            continue

        value = safe_str(s.get("value", ""))
        units = safe_str(s.get("units", ""))

        out[item] = {"value": value, "units": units}

    return out


def load_latest_drivers_map(data: dict) -> dict:
    """
    Devuelve:
      {"D1": "On", "D2": "Off", ...}
    Por ahora NO hacemos nada con esto en el SVG (lo usaremos en el siguiente paso).
    """
    drivers = data.get("drivers", [])
    out = {}
    for d in drivers:
        item = safe_str(d.get("item", ""))
        if not re.fullmatch(r"D(\d+)", item):
            continue
        value = safe_str(d.get("value", ""))
        out[item] = value
    return out


def main():
    here = Path(__file__).resolve().parent
    svg_path = here / TEMPLATE_SVG
    out_path = here / OUT_SVG

    svg = svg_path.read_text(encoding="utf-8")

    if not LATEST_ALL_JSON.exists():
        out_path.write_text(svg, encoding="utf-8")
        print("WARN: no existe data/latest_all.json. Esquema sin cambios.")
        return

    data = json.loads(LATEST_ALL_JSON.read_text(encoding="utf-8"))

    smap = load_latest_sensors_map(data)
    _dmap = load_latest_drivers_map(data)  # preparado para el siguiente paso

    # Reemplaza {{S1}}..{{S29}}
    for n in range(1, MAX_S + 1):
        key = f"S{n}"
        if key not in smap:
            continue

        value = smap[key]["value"]
        units = smap[key]["units"]

        if INCLUDE_UNITS and units:
            repl = f"{value} {units}".strip()
        else:
            repl = value

        svg = re.sub(r"\{\{" + re.escape(key) + r"\}\}", repl, svg)

    out_path.write_text(svg, encoding="utf-8")
    print(f"OK: generado {OUT_SVG} leyendo latest_all.json (S1..S{MAX_S} si existen).")


if __name__ == "__main__":
    main()
