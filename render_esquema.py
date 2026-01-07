import json
import re
from pathlib import Path

# Archivos
TEMPLATE_SVG = "esquema.drawio.svg"
OUT_SVG = "esquema_render.svg"
LATEST_JSON = Path("data") / "latest.json"

# Hasta qué S quieres rellenar (ajusta si quieres 18, 26, 29, etc.)
MAX_S = 29

# Si quieres que en el esquema salga "58.27 DegC" pon True
INCLUDE_UNITS = False


def safe_str(x) -> str:
    return "" if x is None else str(x).strip()


def load_latest_sensors_map() -> dict:
    """
    Devuelve un dict tipo:
      {"S1": {"value":"-0.96","units":"ºC"}, ...}
    Ignora filas raras donde item no sea S<number>.
    """
    if not LATEST_JSON.exists():
        return {}

    data = json.loads(LATEST_JSON.read_text(encoding="utf-8"))
    sensors = data.get("sensors", [])
    out = {}

    for s in sensors:
        item = safe_str(s.get("item", ""))
        # Solo items tipo S1, S2, ... S29
        m = re.fullmatch(r"S(\d+)", item)
        if not m:
            continue

        value = safe_str(s.get("value", ""))
        units = safe_str(s.get("units", ""))

        # Guarda aunque value esté vacío; si no quieres, puedes filtrar aquí
        out[item] = {"value": value, "units": units}

    return out


def main():
    here = Path(__file__).resolve().parent
    svg_path = here / TEMPLATE_SVG
    out_path = here / OUT_SVG

    svg = svg_path.read_text(encoding="utf-8")

    smap = load_latest_sensors_map()

    # Reemplaza {{S1}}..{{S29}} si existe en el JSON
    for n in range(1, MAX_S + 1):
        key = f"S{n}"
        if key not in smap:
            # No existe: no tocamos el token y seguimos
            continue

        value = smap[key]["value"]
        units = smap[key]["units"]

        if INCLUDE_UNITS and units:
            repl = f"{value} {units}".strip()
        else:
            repl = value

        # Sustituye exactamente el token {{Sx}} (con llaves)
        svg = re.sub(r"\{\{" + re.escape(key) + r"\}\}", repl, svg)

    out_path.write_text(svg, encoding="utf-8")
    print(f"OK: generado {OUT_SVG} rellenando S1..S{MAX_S} (si existen).")


if __name__ == "__main__":
    main()
