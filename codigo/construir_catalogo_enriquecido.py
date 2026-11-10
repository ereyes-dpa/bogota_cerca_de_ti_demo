#!/usr/bin/env python3
"""Une el inventario IDT con las capas de Candelaria (datos/fuentes_arcgis/) y produce datos/catalogo_enriquecido.csv.

Qué agrega al catálogo base (datos/catalogo_atractivos.csv):
  * horario_texto / horario_fuente : Guía Destino Diverso, Plazas de Mercado y, si el texto de Visit Bogotá lo dice, su descripción
  * para / pet_friendly            : etiquetas oficiales de Visit Bogotá (Solo, Pareja, Familias, Grupo, Pet Friendly, LGBTI)
  * accesibilidad_dti              : puntaje del Destino Turístico Inteligente (solo 23 atractivos)
  * lugares nuevos que no están en el inventario (Visit Bogotá, Guía Destino Diverso, Plazas de Mercado)
Sin fuentes descargadas, genera el mismo catálogo base con las columnas vacías.
Uso: python3 construir_catalogo_enriquecido.py
"""
from __future__ import annotations

import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from construir_catalogo import SUPUESTOS  # noqa: E402
from horarios import parsear_horario  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
BASE_CSV = RAIZ / "datos" / "catalogo_atractivos.csv"
FUENTES = RAIZ / "datos" / "fuentes_arcgis"
SALIDA = RAIZ / "datos" / "catalogo_enriquecido.csv"
COLUMNAS = ["id", "nombre", "categoria", "localidad", "direccion", "lat", "lon", "minutos_visita_supuesto", "apertura_supuesto",
            "etiquetas_supuesto", "es_de_siempre", "horario_texto", "horario_fuente", "para", "pet_friendly", "accesibilidad_dti", "url", "fuente"]
_STOP = {"de", "del", "la", "el", "los", "las", "y", "e", "en", "bogota", "parque", "plaza"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(w for w in re.sub(r"[^a-z0-9 ]", " ", s).split() if w not in _STOP)


def _dist_m(lat, lon, lats, lons):
    kx = 111320 * np.cos(np.radians(lat))
    return np.hypot((lons - lon) * kx, (lats - lat) * 110540)


def buscar(df: pd.DataFrame, nombre: str, lat: float, lon: float, radio_m: float = 250, umbral: float = 0.78):
    """Índice del registro de df que corresponde a (nombre, lat, lon), o None. Exige cercanía Y nombre parecido."""
    if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
        return None
    d = _dist_m(lat, lon, df.lat.values, df.lon.values)
    n = norm(nombre)
    mejor, idx = 0.0, None
    for i in np.where(d <= max(radio_m, 1000))[0]:
        m = norm(df.nombre.iat[i])
        if d[i] > radio_m and n != m:
            continue                                   # lejos: solo si el nombre es idéntico
        r = SequenceMatcher(None, n, m).ratio()
        if n and m and (n in m or m in n) and min(len(n.split()), len(m.split())) >= 2:   # 'lourdes' solo no basta
            r = max(r, 0.9)
        if r > mejor:
            mejor, idx = r, i
    return idx if mejor >= umbral else None


def _categoria_guia(c: str) -> str | None:
    c = norm(c)
    if any(k in c for k in ("hotel", "alojamiento", "hostal")):
        return None
    for k, v in (("mercado", "Gastronomía"), ("licor", "Gastronomía"), ("deporte", "Escenario Deportivo"), ("museo", "Museo"), ("bibliotec", "Biblioteca"), ("cerro", "Atractivo de Naturaleza"), ("sendero", "Atractivo de Naturaleza"),
                 ("humedal", "Atractivo de Naturaleza"), ("compras", "Comercio"), ("centro comercial", "Comercio"), ("anticuario", "Comercio"),
                 ("centro comerciales", "Comercio"), ("nocturn", "Gastronomía"), ("cafe", "Gastronomía"), ("cocina", "Gastronomía"),
                 ("gastron", "Gastronomía"), ("restaurante", "Gastronomía"), ("zona", "Gastronomía"), ("parque", "Parque"), ("plaza", "Parque")):
        if k in c:
            return v
    return "Atractivo Cultural"


def _categoria_vb(url: str) -> str:
    u = norm(url)
    for k, v in (("museo", "Museo"), ("deport", "Escenario Deportivo"), ("natur", "Atractivo de Naturaleza"), ("aire libre", "Atractivo de Naturaleza"),
                 ("gastron", "Gastronomía"), ("compras", "Comercio"), ("religio", "Escenario Religioso"), ("parque", "Parque")):
        if k in u:
            return v
    return "Atractivo Cultural"


def _supuestos(cat: str):
    m, ap, tags = SUPUESTOS.get(cat, (30, "verificar", set()))
    return m, ap, "|".join(sorted(tags))


def _horario_en_texto(texto: str) -> str | None:
    """Si la descripción trae 'horario ...' que se pueda interpretar, devuelve ese fragmento."""
    if not isinstance(texto, str):
        return None
    i = texto.lower().find("horario")
    if i < 0:
        return None
    frag = texto[i:i + 280]
    return frag if parsear_horario(frag) else None


def _leer(nombre: str) -> pd.DataFrame | None:
    f = FUENTES / f"{nombre}.csv"
    return pd.read_csv(f) if f.exists() else None


def construir(base: pd.DataFrame | None = None, leer=_leer) -> pd.DataFrame:
    df = (base if base is not None else pd.read_csv(BASE_CSV)).copy()
    df["id"] = df["id"].astype(str)
    df["url"] = ""
    df["fuente"] = "inventario_idt"
    for c in ("horario_texto", "horario_fuente", "para", "pet_friendly"):
        df[c] = ""
    df["accesibilidad_dti"] = np.nan
    nuevos = []

    def agregar(id_, nombre, cat, loc, dirc, lat, lon, **extra):
        m, ap, tags = _supuestos(cat)
        fila = dict(id=id_, nombre=nombre, categoria=cat, localidad=loc or "", direccion=dirc or "", lat=lat, lon=lon,
                    minutos_visita_supuesto=m, apertura_supuesto=ap, etiquetas_supuesto=tags, es_de_siempre=False,
                    horario_texto="", horario_fuente="", para="", pet_friendly="", accesibilidad_dti=np.nan, url="", fuente="")
        fila.update(extra)
        nuevos.append(fila)

    # --- Visit Bogotá (etiquetas "para", horario en el texto)
    vb = leer("visitbogota_atractivos_es")
    if vb is not None:
        for r in vb.itertuples():
            para = r.field_turpara if isinstance(getattr(r, "field_turpara", None), str) else ""
            hor = _horario_en_texto(getattr(r, "horario_en_texto", None))
            ruta = r.ruta_visitbogota if isinstance(getattr(r, "ruta_visitbogota", None), str) else ""
            i = buscar(df, r.title, r.lat, r.lon)
            extra = dict(para=para, pet_friendly="si" if "pet friendly" in para.lower() else "", url=("https://visitbogota.co/" + ruta) if ruta else "")
            if i is not None:
                for k, v in extra.items():
                    df.at[i, k] = v
                if hor and not df.at[i, "horario_texto"]:
                    df.at[i, "horario_texto"], df.at[i, "horario_fuente"] = hor, "visitbogota_texto"
                df.at[i, "fuente"] = "inventario_idt+visitbogota"
            elif getattr(r, "field_turzone", "") != "Cerca a Bogotá":      # fuera de la ciudad: no entra como parada nueva
                cat = _categoria_vb(ruta)
                agregar(f"vb-{int(r.nid)}", r.title, cat, getattr(r, "field_turdistr", ""), getattr(r, "field_direccion", ""), r.lat, r.lon,
                        horario_texto=hor or "", horario_fuente="visitbogota_texto" if hor else "", fuente="visitbogota", **extra)
    if nuevos:                                          # disponibles para emparejar con la siguiente fuente
        df = pd.concat([df, pd.DataFrame(nuevos)], ignore_index=True)
        nuevos.clear()
    # --- Guía Destino Diverso y Plazas de Mercado (campo Horario oficial)
    for clave, nom_col, hor_col, dir_col, loc_col, lat_col, lon_col, pref in (
        ("guia_destino_diverso", "Nombre", "Horario", "Direccion", "Localidad", "lat", "lon", "gd"),
        ("plazas_mercado", "Nombre", "Horario", "Direccion", "Localidad", "lat", "lon", "pm"),
    ):
        g = leer(clave)
        if g is None:
            continue
        for k, r in g.iterrows():
            hor = r.get(hor_col) if isinstance(r.get(hor_col), str) else ""
            if "dormir" in str(r.get("Ruta", "")).lower():
                continue                                   # alojamiento: no es parada
            cat = "Gastronomía" if pref == "pm" else _categoria_guia(str(r.get("Categoria", "")))
            if cat is None:
                continue
            i = buscar(df, r[nom_col], r[lat_col], r[lon_col])
            if i is not None:
                if hor:
                    df.at[i, "horario_texto"], df.at[i, "horario_fuente"] = hor, clave
                df.at[i, "fuente"] = str(df.at[i, "fuente"]) + f"+{clave}"
            else:
                agregar(f"{pref}-{k}", r[nom_col].title() if r[nom_col].isupper() else r[nom_col], cat, r.get(loc_col, ""), r.get(dir_col, ""),
                        r[lat_col], r[lon_col], horario_texto=hor, horario_fuente=clave if hor else "", fuente=clave)
        if nuevos:
            df = pd.concat([df, pd.DataFrame(nuevos)], ignore_index=True)
            nuevos.clear()
    # --- DTI: puntaje de accesibilidad
    d = leer("dti_atractivos")
    if d is not None:
        for r in d.itertuples():
            i = buscar(df, r.nombre, r.lat, r.lon, radio_m=400)
            if i is not None:
                df.at[i, "accesibilidad_dti"] = r.accesibilidad
    if nuevos:
        df = pd.concat([df, pd.DataFrame(nuevos)], ignore_index=True)
    df = df.drop_duplicates(["nombre", "lat", "lon"])
    # etiqueta 'comer' para cualquier gastronomía; apertura 'oficial' cuando el horario se interpreta
    ok = df.horario_texto.apply(lambda t: bool(parsear_horario(t)) if isinstance(t, str) and t else False)
    df["horario_interpretable"] = ok
    return df[COLUMNAS + ["horario_interpretable"]]


def main() -> None:
    df = construir()
    df.to_csv(SALIDA, index=False, encoding="utf-8")
    print(f"{len(df)} lugares -> {SALIDA}")
    print("con horario oficial interpretable:", int(df.horario_interpretable.sum()),
          "| con etiquetas 'para':", int((df.para != "").sum()), "| pet friendly:", int((df.pet_friendly == "si").sum()),
          "| con puntaje de accesibilidad:", int(df.accesibilidad_dti.notna().sum()))
    print(df.fuente.value_counts().to_string())


if __name__ == "__main__":
    main()
