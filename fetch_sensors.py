import json
import os
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

URLS = [
    "http://81.60.206.190/S.htm?ovrideStart=1&",
    "http://81.60.206.190/S.htm?ovrideStart=13&",
    "http://81.60.206.190/S.htm?ovrideStart=23&",
]

OUT_DIR = "data"
OUT_JSON = os.path.join(OUT_DIR, "latest.json")
OUT_ACS_MANIFEST = os.path.join(OUT_DIR, "acs_manifest.json")


def slugify(text: str) -> str:
    # fichero seguro: letras/números/_ y sin espacios raros
    text = text.strip().lower()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_]+", "", text)
    return text[:80] or "sensor"


def parse_sensor_table(html: str):
    soup = BeautifulSoup(html, "html.parser")

    tables = soup.find_all("table")
    target = None
    for t in tables:
        text = " ".join(t.get_text(" ", strip=True).lower().split())
        if ("item" in text) and ("label" in text) and ("value" in text) and ("units" in text):
            target = t
            break

    if not target:
        return []

    out = []
    rows = target.find_all("tr")
    for r in rows[1:]:
        cols = [c.get_text(" ", strip=True) for c in r.find_all(["td", "th"])]
        if len(cols) < 4:
            continue

        item = cols[0].strip()
        label = cols[1].strip()
        value = cols[2].strip()
        units = cols[3].strip()

        if label:
            out.append({"item": item, "label": label, "value": value, "units": units})

    return out


def main():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    combined = []
    for url in URLS:
        r = session.get(url, timeout=20)
        r.raise_for_status()
        combined.extend(parse_sensor_table(r.text))

    # Quitar duplicados por label
    seen = set()
    sensors = []
    for s in combined:
        lbl = s.get("label", "")
        if lbl in seen:
            continue
        seen.add(lbl)
        sensors.append(s)

    os.makedirs(OUT_DIR, exist_ok=True)

    now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # 1) Guardar JSON general (última lectura)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {"timestamp_utc": now_utc, "sensors": sensors},
            f,
            ensure_ascii=False,
            indent=2,
        )

    # 2) Guardar históricos por sensor ACS + crear manifest
    acs_entries = []

    for s in sensors:
        label = s.get("label", "")
        units = s.get("units", "")
        value = (s.get("value") or "").strip()

        # Filtrar SOLO los sensores con “ACS” en el label
        if "acs" not in label.lower():
            continue

        # Solo graficamos temperaturas (si quieres incluir otros, lo adaptamos)
        # Aceptamos DegC, °C, etc.
        if not any(u in units.lower() for u in ["degc", "°c", "c"]):
            # lo dejamos en manifest igualmente (por si quieres en el futuro)
            pass

        # Nombre de archivo por item+label (evita colisiones)
        file_name = f"acs_{slugify(s.get('item',''))}_{slugify(label)}.txt"
        file_path = os.path.join(OUT_DIR, file_name)

        # Guardar histórico (si no es numérico, guardamos NOT_FOUND)
        # (Si tu value ya viene bien, quedará numérico)
        if value == "" or value.upper() == "NOT_FOUND":
            line_val = "NOT_FOUND"
        else:
            line_val = value

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"{now_utc};{line_val}\n")

        acs_entries.append({
            "item": s.get("item", ""),
            "label": label,
            "units": units,
            "file": file_name
        })

    # Manifest para que la web sepa qué ficheros cargar
    with open(OUT_ACS_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(
            {"timestamp_utc": now_utc, "acs": acs_entries},
            f,
            ensure_ascii=False,
            indent=2,
        )
print("DEBUG: generando acs_manifest.json y acs_*.txt")

    print(f"OK: {len(sensors)} sensores. ACS: {len(acs_entries)}")


if __name__ == "__main__":
    main()
