import re

TEMPLATE_SVG = "esquema.drawio.svg"
OUT_SVG = "esquema_render.svg"

def main():
    with open(TEMPLATE_SVG, "r", encoding="utf-8") as f:
        svg = f.read()

    # Sustituye SOLO {{S9}} por un texto de prueba
    svg = re.sub(r"\{\{S9\}\}", "PRUEBA 123", svg)

    with open(OUT_SVG, "w", encoding="utf-8") as f:
        f.write(svg)

    print("OK: generado esquema_render.svg con PRUEBA 123 en S9")

if __name__ == "__main__":
    main()
