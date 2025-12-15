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
OUT_TXT_DEPOSITO = os.path.join(OUT_DIR, "deposito_acs.txt")

OUT_ACS_MANIFEST = os.path.join(OUT_DIR, "acs_manifest.json")


def slugify(text: str) -> str:
    text = (text or "").strip().lower()
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

    # 1) latest.json (foto actual)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {"timestamp_utc": now_utc, "sensors": sensors},
            f,
            ensure_ascii=False,
            indent=2,
        )

    # 2) deposito_acs.txt por item S9 (como ya tenías)
    deposito_val = "NOT_FOUND"
    for s in sensors:
        if (s.get("item") or "").strip().upper() == "S9":
            deposito_val = (s.get("value") or "").strip() or "NOT_FOUND"
            break

    with open(OUT_TXT_DEPOSITO, "a", encoding="utf-8") as f:
        f.write(f"{now_utc};{deposito_val}\n")

    # 3) Históricos de TODOS los sensores ACS + manifest
    acs_entries = []
    for s in sensors:
        label = s.get("label", "")
        value = (s.get("value") or "").strip() or "NOT_FOUND"
        units = s.get("units", "")
        item = s.get("item", "")

        if "acs" not in label.lower():
            continue

        file_name = f"acs_{slugify(item)}_{slugify(label)}.txt"
        file_path = os.path.join(OUT_DIR, file_name)

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"{now_utc};{value}\n")

        acs_entries.append({
            "item": item,
            "label": label,
            "units": units,
            "file": file_name,
        })

    with open(OUT_ACS_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(
            {"timestamp_utc": now_utc, "acs": acs_entries},
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"OK: {len(sensors)} sensores. ACS: {len(acs_entries)}")


if __name__ == "__main__":
    main()
