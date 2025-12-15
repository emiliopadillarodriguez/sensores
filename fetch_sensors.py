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

TARGET_LABELS = {"Tª Depósito ACS", "TÂª DepÃ³sito ACS"}


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
        if s["label"] in seen:
            continue
        seen.add(s["label"])
        sensors.append(s)

    os.makedirs(OUT_DIR, exist_ok=True)

    now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Guardar JSON general
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp_utc": now_utc,
                "sensors": sensors,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

  # 👉 Guardar SOLO Depósito ACS en TXT (acepta label correcto y el “raro”)
found = False
for s in sensors:
    label = (s.get("label") or "").strip()
    if label in TARGET_LABELS:
        with open(OUT_TXT, "a", encoding="utf-8") as f:
            f.write(f"{now_utc};{s.get('value','')}\n")
        found = True
        break

# (Opcional pero recomendado) si no lo encuentra, escribe NOT_FOUND para que el TXT exista siempre
if not found:
    with open(OUT_TXT, "a", encoding="utf-8") as f:
        f.write(f"{now_utc};NOT_FOUND\n")


    print("OK: datos actualizados")


if __name__ == "__main__":
    main()
