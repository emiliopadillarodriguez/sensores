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
OUT_FILE = os.path.join(OUT_DIR, "latest.json")


def parse_sensor_table(html: str):
    """
    Intenta encontrar la tabla con columnas: Item | Label | Value | Units | ...
    y extrae label/value/units.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Busca una tabla que contenga esos encabezados
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
    for r in rows[1:]:  # salta cabecera
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

    # Quita duplicados por label
    seen = set()
    sensors = []
    for s in combined:
        if s["label"] in seen:
            continue
        seen.add(s["label"])
        sensors.append(s)

    os.makedirs(OUT_DIR, exist_ok=True)

    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sensors": sensors,
    }

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"OK: {OUT_FILE} -> {len(sensors)} sensores")


if __name__ == "__main__":
    main()
