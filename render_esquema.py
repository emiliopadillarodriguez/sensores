import re
import os
from pathlib import Path

TEMPLATE_SVG = "esquema.drawio.svg"
OUT_SVG = "esquema_render.svg"

def main():
    # Carpeta real desde la que se ejecuta
    cwd = Path.cwd()
    here = Path(__file__).resolve().parent

    print("=== DEBUG ===")
    print("CWD (donde ejecutas):", cwd)
    print("SCRIPT DIR (donde está el .py):", here)
    print("Archivos en CWD:", [p.name for p in cwd.iterdir()])
    print("Archivos en SCRIPT DIR:", [p.name for p in here.iterdir()])
    print("==============")

    # Vamos a leer SIEMPRE desde la carpeta del script (para evitar líos)
    in_path = here / TEMPLATE_SVG
    out_path = here / OUT_SVG

    print("Plantilla esperada en:", in_path)

    if not in_path.exists():
        raise FileNotFoundError(f"No existe la plantilla: {in_path}")

    svg = in_path.read_text(encoding="utf-8", errors="replace")

    pattern = r"\{\{\s*S9\s*\}\}"
    new_svg, n = re.subn(pattern, "PRUEBA 123", svg)
    print(f"Reemplazos realizados: {n}")

    out_path.write_text(new_svg, encoding="utf-8")
    print("✅ Creado:", out_path)

if __name__ == "__main__":
    main()

