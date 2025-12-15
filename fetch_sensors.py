import json
import os
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
OUT_TXT = os.path.join(OUT_DIR, "deposito_acs.txt")


def parse_sensor_table(html: str):
    """
    Busca la tabla Sensor Overview (Item | Label | Value | Units) y extrae filas.
    """
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

    rows = target.find_all("tr")
    out = []
    for r in rows[1:]:
        cols = [c.get_text(" ", strip=True) for c in r.find_all(["td", "th"])]
        if len(cols) < 4:
            continue

        label = cols[1].strip()
        value = cols[2].strip()
        units = cols[3].strip()

        if label:
            out.append({"label": label, "value": value, "units": units})

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

    # Guardar JSON general
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {"timestamp_utc": now_utc, "sensors": sensors},
            f,
            ensure_ascii=False,
            indent=2,
        )

    # Guardar en TXT el valor de “Depósito ACS” (robusto)
    value_to_save = "NOT_FOUND"
    for s in sensors:
        lbl = (s.get("label") or "").lower()
        # "depos" cubre deposito / depósito / depÃ³sito y similares
        if ("acs" in lbl) and ("depos" in lbl):
            value_to_save = s.get("value", "")
            break

    # Siempre escribe una línea para que el archivo exista
    with open(OUT_TXT, "a", encoding="utf-8") as f:
        f.write(f"{now_utc};{value_to_save}\n")

    print(f"OK: {len(sensors)} sensores. deposito_acs={value_to_save}")


if __name__ == "__main__":
    main()
