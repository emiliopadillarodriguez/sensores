import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "http://81.60.206.190"
DATA_DIR = Path("data")

SENSORS_LATEST_JSON = DATA_DIR / "latest.json"
ACS_MANIFEST_JSON = DATA_DIR / "acs_manifest.json"

DRIVERS_LATEST_JSON = DATA_DIR / "drivers_latest.json"
DRIVERS_MANIFEST_JSON = DATA_DIR / "drivers_manifest.json"

SESSION_TIMEOUT = 20


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(text: str) -> str:
    """Convierte a nombre de fichero: minus, sin acentos, espacios->'_' y limpia símbolos raros."""
    if text is None:
        return "sin_label"
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join([c for c in text if not unicodedata.combining(c)])
    # limpia caracteres típicos del html mal decodificado
    text = text.replace("Âª", "a").replace("º", "").replace("°", "")
    # solo letras/números/guion/underscore/espacios
    text = re.sub(r"[^a-z0-9 _-]+", "", text)
    text = re.sub(r"\s+", "_", text).strip("_")
    text = re.sub(r"_+", "_", text)
    return text or "sin_label"


def safe_mkdir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def append_line(path: Path, line: str):
    safe_mkdir(path.parent)
    if path.exists():
        existing = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if existing and existing[-1].strip() == line.strip():
            return  # evita duplicar la misma línea exacta
    with open(path, "a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


def write_json(path: Path, obj):
    safe_mkdir(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def fetch_url(url: str) -> str:
    r = requests.get(url, timeout=SESSION_TIMEOUT)
    r.raise_for_status()
    # fuerza utf-8 pero tolerante
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def parse_table_rows(html: str):
    """
    Devuelve lista de filas dict: {"item","label","value","units"} si existe tabla.
    Se adapta a las tablas de Trend (Item/Label/Value/Units).
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    rows = table.find_all("tr")
    out = []

    # Detecta cabecera (th)
    header = [th.get_text(" ", strip=True).lower() for th in rows[0].find_all(["th", "td"])]
    # en Trend a veces aparece: Item Label Value Units
    colmap = {}
    for idx, name in enumerate(header):
        if "item" in name:
            colmap["item"] = idx
        elif "label" in name:
            colmap["label"] = idx
        elif "value" in name:
            colmap["value"] = idx
        elif "unit" in name:
            colmap["units"] = idx

    # si no detecta cabecera, asumimos orden típico
    if not colmap:
        colmap = {"item": 0, "label": 1, "value": 2, "units": 3}

    for tr in rows[1:]:
        tds = tr.find_all("td")
        if not tds:
            continue

        def get_col(key):
            i = colmap.get(key, None)
            if i is None or i >= len(tds):
                return ""
            return tds[i].get_text(" ", strip=True)

        out.append(
            {
                "item": get_col("item"),
                "label": get_col("label"),
                "value": get_col("value"),
                "units": get_col("units"),
            }
        )
    return out


def extract_sensors_from_pages():
    """
    Tu sistema ya genera latest.json; aquí lo recreamos robusto:
    - intenta leer varias páginas S.htm?ovrideStart=... hasta que deje de devolver sensores.
    Si ya tienes un método mejor, puedes dejarlo, pero este suele funcionar.
    """
    sensors = []
    seen = set()

    # En Trend, Sensors suele ir paginado de 0, 12, 24...
    start = 0
    step = 12
    max_pages = 20

    for _ in range(max_pages):
        url = f"{BASE_URL}/S.htm?ovrideStart={start}"
        html = fetch_url(url)
        rows = parse_table_rows(html)

        # Filtra solo items tipo S\d+
        page_s = []
        for r in rows:
            item = (r.get("item") or "").strip()
            if re.fullmatch(r"S\d+", item):
                key = item
                if key not in seen:
                    seen.add(key)
                    page_s.append(r)

        if not page_s:
            # si en esta página no hay ningún sensor, paramos
            break

        sensors.extend(page_s)
        start += step

    # Orden por número
    def s_key(x):
        m = re.search(r"\d+", x.get("item", ""))
        return int(m.group()) if m else 99999

    sensors.sort(key=s_key)

    latest = {"timestamp_utc": utc_now_iso(), "sensors": sensors}
    write_json(SENSORS_LATEST_JSON, latest)
    return latest


def generate_sensor_txts_from_latest(latest_obj):
    """
    Crea los txt tipo acs_s9_t_deposito_acs.txt etc para TODOS los S que haya en latest.json
    """
    ts = latest_obj.get("timestamp_utc") or utc_now_iso()
    sensors = latest_obj.get("sensors", [])

    manifest = {
        "timestamp_utc": ts,
        "files": [],
    }

    for s in sensors:
        item = (s.get("item") or "").strip()
        if not re.fullmatch(r"S\d+", item):
            continue

        label = s.get("label") or ""
        value = (s.get("value") or "").strip()
        units = (s.get("units") or "").strip()

        # nombre fichero al estilo que ya tienes
        fname = f"acs_{item.lower()}_{slugify(label)}.txt"
        fpath = DATA_DIR / fname

        # línea
        line = f"{ts};{value}"
        append_line(fpath, line)

        manifest["files"].append(
            {
                "item": item,
                "label": label,
                "units": units,
                "file": str(fpath).replace("\\", "/"),
            }
        )

    write_json(ACS_MANIFEST_JSON, manifest)
    return manifest


def fetch_all_drivers():
    """
    Scrapea Drivers paginados con D.htm?ovrideStart=0,12,24...
    Devuelve lista de drivers: item Dxx, label, value (On/Off), module status, alarm... (si existe)
    """
    drivers = []
    seen = set()

    start = 0
    step = 12
    max_pages = 50

    for _ in range(max_pages):
        url = f"{BASE_URL}/D.htm?ovrideStart={start}"
        html = fetch_url(url)
        soup = BeautifulSoup(html, "html.parser")

        table = soup.find("table")
        if not table:
            break

        rows = table.find_all("tr")
        if len(rows) < 2:
            break

        # Detecta columnas por cabecera
        header_cells = rows[0].find_all(["th", "td"])
        headers = [c.get_text(" ", strip=True).lower() for c in header_cells]

        # queremos al menos item/label/value
        def col_idx(name_contains):
            for i, h in enumerate(headers):
                if name_contains in h:
                    return i
            return None

        i_item = col_idx("item") if col_idx("item") is not None else 0
        i_label = col_idx("label") if col_idx("label") is not None else 1
        i_value = col_idx("value") if col_idx("value") is not None else 2

        page_count = 0
        for tr in rows[1:]:
            tds = tr.find_all("td")
            if not tds:
                continue

            item = tds[i_item].get_text(" ", strip=True) if i_item < len(tds) else ""
            label = tds[i_label].get_text(" ", strip=True) if i_label < len(tds) else ""
            value = tds[i_value].get_text(" ", strip=True) if i_value < len(tds) else ""

            item = (item or "").strip()
            if not re.fullmatch(r"D\d+", item):
                continue

            if item in seen:
                continue

            seen.add(item)
            page_count += 1
            drivers.append({"item": item, "label": label, "value": value})

        # Si esta página no aporta nuevos D, paramos
        if page_count == 0:
            break

        start += step

    # Orden por número
    def d_key(x):
        m = re.search(r"\d+", x.get("item", ""))
        return int(m.group()) if m else 99999

    drivers.sort(key=d_key)
    return drivers


def generate_driver_txts(drivers, ts_iso):
    """
    Crea drv_Dxx.txt con líneas timestamp;On/Off
    También genera drivers_latest.json y drivers_manifest.json
    """
    latest = {"timestamp_utc": ts_iso, "drivers": drivers}
    write_json(DRIVERS_LATEST_JSON, latest)

    manifest = {"timestamp_utc": ts_iso, "files": []}

    for d in drivers:
        item = (d.get("item") or "").strip()
        if not re.fullmatch(r"D\d+", item):
            continue

        label = d.get("label") or ""
        value = (d.get("value") or "").strip()

        # Normaliza a On/Off
        v = value.strip()
        if v.lower() in ("on", "off"):
            norm = "On" if v.lower() == "on" else "Off"
        else:
            # si viene vacío u otro, lo guardamos tal cual
            norm = v

        fpath = DATA_DIR / f"drv_{item}.txt"
        append_line(fpath, f"{ts_iso};{norm}")

        manifest["files"].append(
            {
                "item": item,
                "label": label,
                "file": str(fpath).replace("\\", "/"),
            }
        )

    write_json(DRIVERS_MANIFEST_JSON, manifest)
    return latest, manifest


def main():
    safe_mkdir(DATA_DIR)

    # 1) Sensores: (re)generamos latest.json (si ya lo generas tú de otra forma, esto igualmente funciona)
    sensors_latest = extract_sensors_from_pages()

    # 2) Genera txt de TODOS los sensores S que haya en latest.json
    generate_sensor_txts_from_latest(sensors_latest)

    # 3) Drivers: scrapea D.htm?ovrideStart=...
    ts = utc_now_iso()
    drivers = fetch_all_drivers()
    generate_driver_txts(drivers, ts)

    print(f"OK: Sensores S -> {ACS_MANIFEST_JSON}")
    print(f"OK: Drivers D -> {DRIVERS_MANIFEST_JSON}")
    print(f"OK: {len(sensors_latest.get('sensors', []))} sensores en latest.json")
    print(f"OK: {len(drivers)} drivers detectados")


if __name__ == "__main__":
    main()
