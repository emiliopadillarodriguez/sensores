import json
from pathlib import Path

# Archivos
SVG_TEMPLATE = Path("esquema.drawio.svg")
SVG_OUTPUT = Path("esquema_render.svg")
LATEST_JSON = Path("data/latest.json")

# Cargar datos de sensores
with open(LATEST_JSON, "r", encoding="utf-8") as f:
    data = json.load(f)

# Buscar S9 (Tª Depósito ACS)
s9_value = "N/A"
for s in data["sensors"]:
    if "depósito" in s["label"].lower():
        s9_value = f'{s["value"]} {s["units"]}'
        break

# Leer SVG plantilla
svg = SVG_TEMPLATE.read_text(encoding="utf-8")

# Reemplazar token
svg = svg.replace("{{S9}}", s9_value)

# Guardar SVG final
SVG_OUTPUT.write_text(svg, encoding="utf-8")

print("OK → esquema_render.svg generado con S9 =", s9_value)
