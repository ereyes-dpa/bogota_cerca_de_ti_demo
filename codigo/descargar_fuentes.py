#!/usr/bin/env python3
"""Descarga (o actualiza) en datos/fuentes_arcgis/ las capas públicas del IDT que usa Candelaria.

Fuente: https://services1.arcgis.com/OnwEbGgbiaZUoK0z/arcgis/rest/services (ArcGIS Online del IDT).
Candelaria declaró sus fuentes (Visit Bogotá, inventario IDT en ArcGIS, RNT, agenda de eventos) y su ficha de
ejemplo reveló este servicio. Son capas públicas de solo lectura.

Genera los MISMOS CSV compactos que se copiaron el 9-nov-2026 (mismas columnas), así el resto del código no cambia.
No guarda datos de contacto del RNT (teléfonos, correos, NIT).

Necesita internet. Solo usa la biblioteca estándar.
Uso:  python3 descargar_fuentes.py            # todas
      python3 descargar_fuentes.py --solo guia_destino_diverso,plazas_mercado
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = "https://services1.arcgis.com/OnwEbGgbiaZUoK0z/arcgis/rest/services"
SALIDA = Path(__file__).resolve().parents[1] / "datos" / "fuentes_arcgis"


def txt(h) -> str:
    """HTML -> texto de una línea (igual que en la copia hecha desde el navegador)."""
    s = "" if h is None else str(h)
    s = re.sub(r"<br\s*/?>", " | ", s, flags=re.I)
    s = re.sub(r"<[^>]*>", " ", s).replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", s).strip()


def r6(v):
    return "" if v is None else round(float(v), 6)


def horario_body(b) -> str:
    t = txt(b)
    i = t.lower().find("horario")
    return "" if i < 0 else t[i:i + 260]


def geo(f, eje):
    g = f.get("geometry") or {}
    return r6(g.get(eje))


def _vb(a, f, con_horario=True):
    d = {"nid": a.get("nid"), "title": txt(a.get("title")), "field_direccion": txt(a.get("field_direccion")),
         "field_turpara": txt(a.get("field_turpara")), "field_turzone": txt(a.get("field_turzone")), "field_turdistr": txt(a.get("field_turdistr")),
         "lon": geo(f, "x"), "lat": geo(f, "y"), "ruta_visitbogota": (a.get("view_node") or "").replace("https://visitbogota.co/", "")}
    if con_horario:
        d["horario_en_texto"] = horario_body(a.get("body"))
    return d


def _eventos(a, f):
    d = {k: txt(a.get(k)) for k in ("title", "field_fecha_de_inicio", "field_fecha_de_finalizacion", "field_lugar_del_evento",
                                    "field_categoria_de_evento", "field_turpara", "field_turdistr")}
    d.update(nid=a.get("nid"), lon=geo(f, "x"), lat=geo(f, "y"))
    return d


def _guia(a, f):
    d = {k: txt(a.get(k)) for k in ("Nombre", "Categoria", "Ruta", "Localidad", "Direccion", "Horario", "Estado_Negocio")}
    d.update(lon=geo(f, "x") if f.get("geometry") else r6(a.get("Longitud")), lat=geo(f, "y") if f.get("geometry") else r6(a.get("Latitud")),
             Rating="" if a.get("Rating") is None else a.get("Rating"))
    return d


def _plazas(a, f):
    return {"Nombre": txt(a.get("Nombre")), "Localidad": txt(a.get("Localidad")), "Barrio": txt(a.get("Barrio")),
            "Direccion": txt(a.get("Dirección")), "lon": geo(f, "x"), "lat": geo(f, "y"), "Horario": txt(a.get("Horario"))}


def _dti(a, f):
    d = {k: a.get(k) for k in ("promedio_general", "accesibilidad", "sostenibilidad", "tecnologia", "innovacion", "gobernanza")}
    d.update(nombre=txt(a.get("nombre")), direccion=txt(a.get("direccion")), clasificacion_general=txt(a.get("clasificacion_general")),
             lon=geo(f, "x"), lat=geo(f, "y"))
    return d


def _rnt(a, f):
    return {"codigo_rnt": a.get("CODIGO_RNT"), "razon_social": re.sub(r"\s+", " ", str(a.get("RAZON_SOCI") or "")).strip(),
            "subcategoria": a.get("SUB_CATEGO"), "localidad": a.get("LOCALIDAD"), "lon": geo(f, "x"), "lat": geo(f, "y")}


# clave -> (servicio, filtro where, columnas, transformación, campos a pedir, orden)
CAPAS = {
    "visitbogota_atractivos_es": ("Atractivos_ES", "1=1",
        ["nid", "title", "field_direccion", "field_turpara", "field_turzone", "field_turdistr", "lon", "lat", "ruta_visitbogota", "horario_en_texto"], _vb, "*", None),
    "visitbogota_atractivos_en": ("Atractivos_EN", "1=1",
        ["nid", "title", "field_direccion", "field_turpara", "field_turzone", "field_turdistr", "lon", "lat", "ruta_visitbogota"],
        lambda a, f: _vb(a, f, False), "*", None),
    "visitbogota_eventos_es": ("Eventos_ES", "1=1",
        ["nid", "title", "field_fecha_de_inicio", "field_fecha_de_finalizacion", "field_lugar_del_evento", "field_categoria_de_evento",
         "field_turpara", "field_turdistr", "lon", "lat"], _eventos, "*", None),
    "guia_destino_diverso": ("Guia Bogota Destino Diverso", "1=1",
        ["Nombre", "Categoria", "Ruta", "Localidad", "Direccion", "lon", "lat", "Horario", "Rating", "Estado_Negocio"], _guia, "*", None),
    "plazas_mercado": ("PlazasMercadoFinal", "1=1", ["Nombre", "Localidad", "Barrio", "Direccion", "lon", "lat", "Horario"], _plazas, "*", None),
    "dti_atractivos": ("Atractivos_gdb", "1=1",
        ["nombre", "direccion", "lon", "lat", "clasificacion_general", "promedio_general", "accesibilidad", "sostenibilidad", "tecnologia",
         "innovacion", "gobernanza"], _dti, "*", None),
    "restaurantes_candelaria": ("restaurantes_candelariaJSON", "1=1", ["title", "address", "destacado", "lon", "lat"],
        lambda a, f: {"title": txt(a.get("title")), "address": txt(a.get("address")), "destacado": txt(a.get("destacado")),
                      "lon": geo(f, "x"), "lat": geo(f, "y")}, "*", None),
    "puntos_accesibles": ("PuntosDestinoAccesibleBogota", "1=1", ["Name", "Categoria", "lon", "lat"],
        lambda a, f: {"Name": txt(a.get("Name")), "Categoria": txt(a.get("Categoría")), "lon": geo(f, "x"), "lat": geo(f, "y")}, "*", None),
    # RNT: solo gastronomía activa y SIN datos de contacto (teléfonos, correos, NIT)
    "rnt_gastronomia": ("Prestadores_de_Servicios_Turísticos_2025", "CATEGORIA LIKE '%GASTRONOM%' AND ESTADO_RNT = 'ACTIVO'",
        ["codigo_rnt", "razon_social", "subcategoria", "localidad", "lon", "lat"], _rnt, "CODIGO_RNT,RAZON_SOCI,SUB_CATEGO,LOCALIDAD", "CODIGO_RNT"),
}


def _get(url: str, intentos: int = 3) -> dict:
    ultimo = None
    for i in range(intentos):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "bogota-cerca-de-ti/0.2"}), timeout=60) as r:
                j = json.loads(r.read().decode("utf-8"))
            if "error" in j:
                raise RuntimeError(j["error"])
            return j
        except Exception as e:  # noqa: BLE001
            ultimo = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"falló {url}: {ultimo}")


def descargar(clave: str) -> list[dict]:
    servicio, where, _, transf, campos, orden = CAPAS[clave]
    filas, off = [], 0
    while True:
        q = {"where": where, "outFields": campos, "returnGeometry": "true", "outSR": 4326, "resultOffset": off, "resultRecordCount": 1000, "f": "json"}
        if orden:
            q["orderByFields"] = orden
        j = _get(f"{BASE}/{urllib.parse.quote(servicio)}/FeatureServer/0/query?{urllib.parse.urlencode(q)}")
        lote = j.get("features", [])
        filas += [transf(f.get("attributes", {}), f) for f in lote]
        if not j.get("exceededTransferLimit") or not lote:
            return filas
        off += len(lote)


def escribir(clave: str, filas: list[dict], destino: Path | None = None) -> str:
    cols = CAPAS[clave][2]
    destino = destino or SALIDA / f"{clave}.csv"
    with destino.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for f in filas:
            w.writerow({c: f.get(c, "") for c in cols})
    return hashlib.sha256(destino.read_bytes()).hexdigest()[:16]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solo", default="", help="claves separadas por coma: " + ", ".join(CAPAS))
    a = ap.parse_args()
    claves = [k for k in a.solo.split(",") if k] or list(CAPAS)
    SALIDA.mkdir(parents=True, exist_ok=True)
    man_f = SALIDA / "manifiesto.json"
    man = json.loads(man_f.read_text(encoding="utf-8")) if man_f.exists() else {"base": BASE, "capas": {}}
    for k in claves:
        try:
            filas = descargar(k)
            sha = escribir(k, filas)
            man["capas"][k] = {"servicio": CAPAS[k][0], "filtro": CAPAS[k][1], "filas": len(filas), "sha256_16": sha,
                               "descargado": datetime.now().isoformat(timespec="seconds"), "via": "descargar_fuentes.py"}
            print(f"OK  {k:28s} {len(filas):6d} filas  sha {sha}")
        except Exception as e:  # noqa: BLE001
            print(f"ERR {k:28s} {e}")
    man_f.write_text(json.dumps(man, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Siguiente paso: python3 construir_catalogo_enriquecido.py")


if __name__ == "__main__":
    main()
