import json
import re
from pathlib import Path

# Archivos
TEMPLATE_SVG = "esquema.drawio.svg"
OUT_SVG = "esquema_render.svg"
LATEST_JSON = Path("data") / "latest.json"

# Ajusta esto si tu label exacto es distinto
S9_LABEL_CONTAINS = "deposito acs"  # busca "Depósito ACS" aunque venga sin acento


def normalize(s: str) -> str:
    """Normaliza para comparar sin líos de mayúsculas/acentos/espacios."""
    if s is None:
        return ""
    s = str(s).strip().lower()
    # simplifica espacios
    s = " ".join(s.split())
    # quita símbolos raros comunes (por ejemplo TÂª)
    s = s.replace("tª", "t").replace("tÂª", "t").replace("º", "")
    return s


def get_s9_value_from_latest() -> str:
    if not LATEST_JSON.exists():
        return "NO_LATEST_JSON"

    data = json.loads(LATEST_JSON.read_text(encoding="utf-8"))
    sensors = data.get("sensors", [])
    target = normalize(S9_LABEL_CONTAINS)

    # Busca por label
    for s in sensors:
        label = normalize(s.get("label", ""))
        if target in label:
            val = str(s.get("value", "NOT_FOUND")).strip()
            units = str(s.get("units", "")).strip()
            # Si quieres incluir unidades en el dibujo, descomenta esta línea:
            # return f"{val} {units}".strip()
            return val

    return "NOT_FOUND"


def main():
    here = Path(__file__).resolve().parent
    svg_path = here / TEMPLATE_SVG
    out_path = here / OUT_SVG

    # Lee plantilla SVG
    svg = svg_path.read_text(encoding="utf-8")

    # Lee valor real
    s9_value = get_s9_value_from_latest()

    # Sustituye SOLO {{S9}}
    svg = re.sub(r"\{\{S9\}\}", s9_value, svg)

    # Guarda render
    out_path.write_text(svg, encoding="utf-8")
    print(f"OK: generado {OUT_SVG} con S9={s9_value}")


if __name__ == "__main__":
    main()


