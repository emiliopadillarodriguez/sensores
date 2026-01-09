import json
import os
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

# ====== URLs SENSORS (las tuyas) ======
SENSOR_URLS = [
    "http://81.60.206.190/S.htm?ovrideStart=1&",
    "http://81.60.206.190/S.htm?ovrideStart=13&",
    "http://81.60.206.190/S.htm?ovrideStart=23&",
]

# ====== URLs DRIVERS (según tus capturas) ======
DRIVER_URLS = [
    "http://81.60.206.190/D.htm?ovrideStart=0",
    "http://81.60.206.190/D.htm?ovrideStart=12",
    "http://81.60.206.190/D.htm?ovrideStart=27",
]

OUT_DIR = "data"
OUT_SENSORS_JSON = os.path.join(OUT_DIR, "latest.json")

OUT_DRIVERS_JSON = os.path.join(OUT_DIR, "drivers_latest.json")
OUT_DRIVERS_MANIFEST = os.path.join(OUT_DIR, "drivers_manifest.json")

# Driver a probar (TU PRUEBA): D1 = "M-P B. 5.2 - Calefacción"
DRIVERS_TO_TRACK = ["D1"]


def _find_table_by_headers(soup: BeautifulSoup, required_headers_lower):
    """
    Busca una tabla que contenga todos los encabezados indicados (en minúsculas).
    """
    for t in soup.find_all("table"):
        text = " ".join(t.get_text(" ", strip=True).lower().split())
        ok = True
        for h in required_headers_lower:
            if h not in text:
                ok = False
                break
        if ok:
            return t
    return None


def parse_sensor_table(html: str):
    soup = BeautifulSoup(html, "html.parser")
    t = _find_table_by_headers(soup, ["item", "label", "value", "units"])
    if not t:
        return []

    rows = t.find_all("tr")
    out = []
    for r in rows[1:]:
        cols = [c.get_text(" ", strip=True) for c in r.find_all(["td", "th"])]
        if len(cols) < 4:
            continue

        item = cols[0].strip()
        label = cols[1].strip()
        value = cols[2].strip()
        units = cols[3].strip()

        if item and label:
            out.append({"item": item, "label": label, "value": value, "units": units})
    return out


def parse_driver_table(html: str):
    """
    Espera una tabla tipo:
    Item | Label | Value | Module Status | Alarm
    """
    soup = BeautifulSoup(html, "html.parser")
    t = _find_table_by_headers(soup, ["item", "label", "value", "module", "alarm"])
    if not t:
        return []

    rows = t.find_all("tr")
    out = []
    for r in rows[1:]:
        cols = [c.get_text(" ", strip=True) for c in r.find_all(["td", "th"])]
        if len(cols) < 5:
            continue

        item = cols[0].strip()
        label = cols[1].strip()
        value = cols[2].strip()
        module_status = cols[3].strip()
        alarm = cols[4].strip()

        if item and label:
            out.append(
                {
                    "item": item,
                    "label": label,
                    "value": value,
                    "module_status": module_status,
                    "alarm": alarm,
                }
            )
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # =========================
    # 1) SENSORS (como ya tenías)
    # =========================
    combined_s = []
    for url in SENSOR_URLS:
        r = session.get(url, timeout=20)
        r.raise_for_status()
        combined_s.extend(parse_sensor_table(r.text))

    # dedupe por item (S1, S2, ...)
    seen = set()
    sensors = []
    for s in combined_s:
        if s["item"] in seen:
            continue
        seen.add(s["item"])
        sensors.append(s)

    with open(OUT_SENSORS_JSON, "w", encoding="utf-8") as f:
        json.dump({"timestamp_utc": now_utc, "sensors": sensors}, f, ensure_ascii=False, indent=2)

    # =========================
    # 2) DRIVERS (nuevo)
    # =========================
    combined_d = []
    for url in DRIVER_URLS:
        r = session.get(url, timeout=20)
        r.raise_for_status()
        combined_d.extend(parse_driver_table(r.text))

    # dedupe por item (D1, D2, ...)
    seen = set()
    drivers = []
    for d in combined_d:
        if d["item"] in seen:
            continue
        seen.add(d["item"])
        drivers.append(d)

    with open(OUT_DRIVERS_JSON, "w", encoding="utf-8") as f:
        json.dump({"timestamp_utc": now_utc, "drivers": drivers}, f, ensure_ascii=False, indent=2)

    # Manifest (lista rápida)
    manifest = [{"item": d["item"], "label": d["label"]} for d in drivers]
    with open(OUT_DRIVERS_MANIFEST, "w", encoding="utf-8") as f:
        json.dump({"timestamp_utc": now_utc, "drivers": manifest}, f, ensure_ascii=False, indent=2)

    # =========================
    # 3) TXT histórico SOLO del driver en prueba (D1)
    # =========================
    # Busca D1 dentro de drivers y guarda timestamp;On/Off
    drivers_by_item = {d["item"]: d for d in drivers}

    for drv in DRIVERS_TO_TRACK:
        d = drivers_by_item.get(drv)
        if not d:
            continue

        # Normaliza valor (por si viene "On " o "OFF", etc.)
        value = (d.get("value") or "").strip()
        out_txt = os.path.join(OUT_DIR, f"drv_{drv}.txt")

        with open(out_txt, "a", encoding="utf-8") as f:
            f.write(f"{now_utc};{value}\n")

    print(f"OK: sensores={len(sensors)} drivers={len(drivers)} (TXT D1 si existe)")


if __name__ == "__main__":
    main()
