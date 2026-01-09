import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "http://81.60.206.190"
SENSORS_URL = f"{BASE_URL}/S.htm?ovrideStart=0"   # tabla de sensores
DRIVERS_URL = f"{BASE_URL}/D.htm?ovrideStart=0"   # tabla de drivers (si ya lo usas)
DATA_DIR = Path("data")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; sensores-bot/1.0)"
}

# --- Helpers -------------------------------------------------

def slugify(text: str) -> str:
    """Convierte texto a slug ascii con guiones bajos."""
    if text is None:
        return "sin_label"

    # Normaliza acentos
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")

    text = text.lower().strip()

    # Limpiezas típicas del label de Trend
    text = text.replace("tª", "t")
    text = text.replace("ta", "t")  # evita variantes ta / tª
    text = text.replace("ºc", "c")

    # Solo alfanum y espacios/guiones
    text = re.sub(r"[^a-z0-9\s\-_/]", "", text)
    # separadores a _
    text = re.sub(r"[\s\-\/]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")

    return text or "sin_label"

def now_utc_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def append_line(path: Path, line: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def fetch_table(url: str):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table")
    if not table:
        return []
    rows = table.find_all("tr")
    data = []
    for tr in rows[1:]:
        tds = tr.find_all(["td", "th"])
        if len(tds) < 4:
            continue
        item = tds[0].get_text(strip=True)
        label = tds[1].get_text(" ", strip=True)
        value = tds[2].get_text(" ", strip=True)
        units = tds[3].get_text(" ", strip=True)
        data.append({"item": item, "label": label, "value": value, "units": units})
    return data

def is_sensor_item(item: str) -> bool:
    return bool(re.fullmatch(r"S\d+", (item or "").strip(), re.IGNORECASE))

def is_driver_item(item: str) -> bool:
    return bool(re.fullmatch(r"D\d+", (item or "").strip(), re.IGNORECASE))

def parse_value_numeric(v: str):
    # Devuelve float si puede, si no None
    if v is None:
        return None
    v = v.strip()
    # Trend a veces mete espacios raros
    v = v.replace("\xa0", " ")
    # Si es "On/Off" no es numérico
    if v.lower() in ("on", "off"):
        return None
    try:
        return float(v)
    except:
        return None

def normalize_on_off(v: str):
    if not v:
        return None
    t = v.strip().lower()
    if t == "on":
        return "On"
    if t == "off":
        return "Off"
    return None

# --- Main ----------------------------------------------------

def main():
    DATA_DIR.mkdir(exist_ok=True)

    timestamp = now_utc_iso()

    # 1) Lee sensores (S)
    sensors = fetch_table(SENSORS_URL)
    sensors_clean = [x for x in sensors if is_sensor_item(x.get("item", ""))]

    latest = {
        "timestamp_utc": timestamp,
        "sensors": sensors_clean
    }
    (DATA_DIR / "latest.json").write_text(json.dumps(latest, indent=2, ensure_ascii=False), encoding="utf-8")

    # 2) Genera históricos SOLO con _t_
    #    Formato línea: timestamp;valor
    #    - Si es numérico: guardamos número
    #    - Si no (raro en sensores): guardamos tal cual
    acs_manifest = []
    for s in sensors_clean:
        item = s["item"].lower()               # s9
        label_slug = slugify(s.get("label", ""))

        # NOMBRE ÚNICO Y CANÓNICO: acs_s9_t_deposito_acs.txt
        fname = f"acs_{item}_t_{label_slug}.txt"
        fpath = DATA_DIR / fname

        val = s.get("value", "").strip()
        # guarda el valor tal cual (num o texto)
        append_line(fpath, f"{timestamp};{val}")

        acs_manifest.append({
            "item": s["item"],
            "label": s.get("label", ""),
            "units": s.get("units", ""),
            "file": f"data/{fname}"
        })

    (DATA_DIR / "acs_manifest.json").write_text(json.dumps({
        "timestamp_utc": timestamp,
        "series": acs_manifest
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    # 3) Drivers (D) (si ya lo estás usando)
    #    Crea drv_D1.txt, drv_D2.txt...
    #    Línea: timestamp;On/Off (o valor si no es On/Off)
    drivers = fetch_table(DRIVERS_URL)
    drivers_clean = [x for x in drivers if is_driver_item(x.get("item", ""))]

    drivers_latest = {"timestamp_utc": timestamp, "drivers": drivers_clean}
    (DATA_DIR / "drivers_latest.json").write_text(json.dumps(drivers_latest, indent=2, ensure_ascii=False), encoding="utf-8")

    drivers_manifest = []
    for d in drivers_clean:
        ditem = d["item"].strip().upper()  # D1
        fname = f"drv_{ditem}.txt"
        fpath = DATA_DIR / fname

        v = d.get("value", "").strip()
        onoff = normalize_on_off(v)
        if onoff:
            store = onoff
        else:
            store = v  # por si hay un 0/100, etc.

        append_line(fpath, f"{timestamp};{store}")

        drivers_manifest.append({
            "item": ditem,
            "label": d.get("label", ""),
            "units": d.get("units", ""),
            "file": f"data/{fname}"
        })

    (DATA_DIR / "drivers_manifest.json").write_text(json.dumps({
        "timestamp_utc": timestamp,
        "series": drivers_manifest
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"OK: {len(sensors_clean)} sensores -> históricos *_t_*.txt (sin duplicados)")
    print(f"OK: {len(drivers_clean)} drivers -> drv_D*.txt")

if __name__ == "__main__":
    main()
