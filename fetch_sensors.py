#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fetch_sensors.py
- Lee sensores (S) y drivers (D) desde el TREND (web HTML)
- Actualiza:
    data/latest.json              -> SOLO sensores S
    data/drivers_latest.json      -> SOLO drivers D
    data/latest_all.json          -> S + D (combinado, útil para esquema)
- Mantiene históricos:
    data/S1.txt, data/S2.txt, ...                 (timestamp;valor)
    data/drv_D1.txt, data/drv_D2.txt, ...         (timestamp;On/Off o valor)
- Genera manifests:
    data/sensors_manifest.json
    data/drivers_manifest.json
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


BASE_URL = "http://81.60.206.190"
SENSORS_URL = f"{BASE_URL}/S.htm?ovrideStart={{start}}"
DRIVERS_URL = f"{BASE_URL}/D.htm?ovrideStart={{start}}"

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# Normalmente Trend pagina en bloques; con esto cubrimos lo que has visto (0, 12, 27)
SENSORS_STARTS = [0, 12, 27, 40, 60, 80]   # por si crece el nº de sensores
DRIVERS_STARTS = [0, 12, 27, 40, 60, 80]   # por si crece el nº de drivers


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_text(x: str) -> str:
    """Limpieza básica + intenta arreglar algunos 'mojibake' típicos."""
    if x is None:
        return ""
    s = str(x).replace("\xa0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    # Intento suave de arreglar textos tipo "TÂª" (si fuese latin1 mal decodificado)
    try:
        s2 = s.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
        # Si el arreglo parece mejor (contiene menos caracteres raros), lo usamos
        if s2 and ("Â" not in s2) and (len(s2) >= max(1, len(s) // 2)):
            return s2
    except Exception:
        pass
    return s


def fetch_html(url: str) -> str:
    r = requests.get(url, timeout=25)
    r.raise_for_status()
    return r.text


def parse_table_rows(html: str):
    """
    Parse genérico: busca filas con 4 columnas (Item/Label/Value/Units).
    Devuelve lista de dicts: {item,label,value,units}
    """
    soup = BeautifulSoup(html, "html.parser")

    # Busca tabla más probable (la primera grande)
    tables = soup.find_all("table")
    if not tables:
        return []

    best_table = None
    best_score = 0
    for t in tables:
        txt = safe_text(t.get_text(" ", strip=True)).lower()
        score = 0
        if "item" in txt:
            score += 2
        if "label" in txt:
            score += 2
        if "value" in txt:
            score += 2
        if "units" in txt:
            score += 2
        # filas
        score += len(t.find_all("tr")) // 5
        if score > best_score:
            best_score = score
            best_table = t

    if best_table is None:
        return []

    rows = best_table.find_all("tr")
    out = []

    for tr in rows:
        tds = tr.find_all(["td", "th"])
        if len(tds) < 3:
            continue

        cols = [safe_text(td.get_text(" ", strip=True)) for td in tds]
        # Si está en formato: Item | Label | Value | Units
        # A veces hay 5 columnas (Module Status, Alarm, etc.), en drivers.
        # Nos quedamos con las 4 primeras si tienen pinta.
        item = cols[0]
        if not re.match(r"^(S\d+|D\d+)$", item):
            continue

        label = cols[1] if len(cols) >= 2 else ""
        value = cols[2] if len(cols) >= 3 else ""
        units = cols[3] if len(cols) >= 4 else ""

        out.append(
            {
                "item": item,
                "label": label,
                "value": value,
                "units": units,
            }
        )

    return out


def append_history(path: Path, timestamp: str, value: str):
    """
    Añade línea "timestamp;value" si no está ya la misma timestamp al final.
    """
    line = f"{timestamp};{value}\n"

    if path.exists():
        try:
            last = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-1]
            if last.startswith(timestamp + ";"):
                return
        except Exception:
            pass

    with path.open("a", encoding="utf-8") as f:
        f.write(line)


def write_json(path: Path, data: dict):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_latest_all(latest_s: dict, latest_d: dict) -> dict:
    drv_items = []
    for d in latest_d.get("drivers", []):
        drv_items.append(
            {
                "item": d.get("item"),
                "label": d.get("label", ""),
                "value": d.get("value"),
                "units": d.get("units", ""),
            }
        )

    combined = {
        "timestamp_utc": latest_s.get("timestamp_utc") or latest_d.get("timestamp_utc"),
        "sensors": latest_s.get("sensors", []),
        "drivers": latest_d.get("drivers", []),
        "items": latest_s.get("sensors", []) + drv_items,
    }
    return combined


def main():
    ts = now_utc_iso()

    # -------- SENSORS --------
    sensors = []
    for start in SENSORS_STARTS:
        url = SENSORS_URL.format(start=start)
        try:
            html = fetch_html(url)
        except Exception as e:
            print(f"[WARN] No pude leer sensores start={start}: {e}")
            continue

        chunk = parse_table_rows(html)
        # Filtra SOLO S
        chunk = [x for x in chunk if re.match(r"^S\d+$", x.get("item", ""))]
        sensors.extend(chunk)

        # Si una página viene vacía, no es grave: seguimos por si hay saltos.
        # Pero si ya tenemos datos y esta sale vacía, podemos romper:
        if start != 0 and len(chunk) == 0:
            break

    # Deduplicar por item (nos quedamos con el último encontrado)
    by_item = {}
    for s in sensors:
        by_item[s["item"]] = s
    sensors = [by_item[k] for k in sorted(by_item.keys(), key=lambda x: int(x[1:]))]

    latest_s = {"timestamp_utc": ts, "sensors": sensors}
    write_json(DATA_DIR / "latest.json", latest_s)

    # Históricos sensores: S1.txt, S2.txt...
    for s in sensors:
        item = s["item"]
        value = s.get("value", "")
        append_history(DATA_DIR / f"{item}.txt", ts, value)

    # Manifest sensores
    sensors_manifest = {
        "timestamp_utc": ts,
        "files": [
            {
                "item": s["item"],
                "label": s.get("label", ""),
                "units": s.get("units", ""),
                "file": f"{s['item']}.txt",
            }
            for s in sensors
        ],
    }
    write_json(DATA_DIR / "sensors_manifest.json", sensors_manifest)

    # -------- DRIVERS --------
    drivers = []
    for start in DRIVERS_STARTS:
        url = DRIVERS_URL.format(start=start)
        try:
            html = fetch_html(url)
        except Exception as e:
            print(f"[WARN] No pude leer drivers start={start}: {e}")
            continue

        chunk = parse_table_rows(html)
        chunk = [x for x in chunk if re.match(r"^D\d+$", x.get("item", ""))]
        drivers.extend(chunk)

        if start != 0 and len(chunk) == 0:
            break

    # Deduplicar drivers
    by_item = {}
    for d in drivers:
        by_item[d["item"]] = d
    drivers = [by_item[k] for k in sorted(by_item.keys(), key=lambda x: int(x[1:]))]

    latest_d = {"timestamp_utc": ts, "drivers": drivers}
    write_json(DATA_DIR / "drivers_latest.json", latest_d)

    # Históricos drivers: drv_D1.txt, drv_D2.txt...
    for d in drivers:
        item = d["item"]
        value = d.get("value", "")
        append_history(DATA_DIR / f"drv_{item}.txt", ts, value)

    # Manifest drivers
    drivers_manifest = {
        "timestamp_utc": ts,
        "files": [
            {
                "item": d["item"],
                "label": d.get("label", ""),
                "units": d.get("units", ""),
                "file": f"drv_{d['item']}.txt",
            }
            for d in drivers
        ],
    }
    write_json(DATA_DIR / "drivers_manifest.json", drivers_manifest)

    # -------- LATEST ALL (S + D) --------
    latest_all = build_latest_all(latest_s, latest_d)
    write_json(DATA_DIR / "latest_all.json", latest_all)

    print(f"OK: sensores={len(sensors)} drivers={len(drivers)}")
    print("OK: data/latest.json, data/drivers_latest.json, data/latest_all.json")
    print("OK: históricos S*.txt y drv_D*.txt actualizados")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
