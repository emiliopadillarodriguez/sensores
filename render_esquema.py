import re
from pathlib import Path

TEMPLATE_SVG = "esquema.drawio.svg"
OUT_SVG = "esquema_render.svg"

def main():
    base = Path(__file__).resolve().parent
    in_path = base / TEMPLATE_SVG
    out_path = base / OUT_SVG

    if not in_path.exists():
        raise FileNotFoundError(f"No encuentro el fichero plantilla: {in_path}")

    # Lee el SVG (si hay caracteres raros, no revienta)
    svg = in_path.read_text(encoding="utf-8", errors="replace")

    # Reemplazo robusto: acepta espacios dentro de {{  S9  }}
    pattern = r"\{\{\s*S9\s*\}\}"
    new_svg, n = re.subn(pattern, "PRUEBA 123", svg)

    if n == 0:
        # Plan B: por si draw.io ha dejado algo “raro”, te lo deja claro
        print("AVISO: No se encontró el token {{S9}} en el SVG.")
        # Para ayudarte, prueba a buscar simplemente 'S9' (sin llaves)
        if "S9" in svg:
            print("Pero sí existe 'S9' en el fichero. Puede que el token no sea exactamente {{S9}}.")
        else:
            print("Tampoco aparece 'S9' en el fichero. Revisa el texto del token en draw.io.")
    else:
        print(f"OK: Reemplazado {{S9}} {n} vez/veces por PRUEBA 123")

    out_path.write_text(new_svg, encoding="utf-8")
    print(f"OK: generado {out_path}")

if __name__ == "__main__":
    main()
