"""Verifica que un plan propuesto por el chatbot sea LOGRABLE según los parámetros y la base de datos.

Algoritmo (en orden):
 1. Resolver cada parada contra el catálogo: por nombre+cercanía (250 m), si no por coordenadas (60 m), si no por nombre exacto aproximado.
    Una parada que no aparece en el catálogo se marca (posible lugar inventado o fuera del inventario IDT).
 2. Re-simular el recorrido en el orden dado: traslados (estimación por modo) + minutos en sitio (los declarados o, si faltan, los del catálogo) + regreso.
 3. Comprobar: cupo de tiempo y margen, apertura a la hora de llegada (horario oficial si existe), consistencia con los totales que declaró el chatbot,
    compañía (etiquetas oficiales), mascota, preferencias y número de paradas.
 4. Veredicto: NO LOGRABLE (alguna falla), LOGRABLE CON ADVERTENCIAS, LOGRABLE.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import timedelta
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from construir_catalogo_enriquecido import _dist_m, buscar, norm
from planificador import MARGEN_MIN, Solicitud, evaluar_apertura, haversine_km, horario_oficial, tiempo_traslado

RNT_CSV = Path(__file__).resolve().parents[1] / "datos" / "fuentes_arcgis" / "rnt_gastronomia.csv"
RNT_URL = ("https://services1.arcgis.com/OnwEbGgbiaZUoK0z/arcgis/rest/services/"
           + urllib.parse.quote("Prestadores_de_Servicios_Turísticos_2025") + "/FeatureServer/0/query")
TAG_COMPANIA = {"solo": "solo", "pareja": "pareja", "amigos": "grupo", "ninos": "familias"}
ETIQUETA_PREF = {"comer": "comer", "cultura": "cultura", "naturaleza": "naturaleza", "economico": "economico", "caminar_poco": "caminar_poco"}
NOMBRE_PREF = {"comer": "comer rico", "cultura": "cultura", "naturaleza": "naturaleza", "inesperado": "algo inesperado", "caminar_poco": "caminar poco", "economico": "económico"}


@dataclass
class Chequeo:
    id: str
    titulo: str
    estado: str          # ok | aviso | falla | na
    detalle: str
    parada: int | None = None


@lru_cache(maxsize=1)
def _rnt_local() -> pd.DataFrame | None:
    if not RNT_CSV.exists():
        return None
    df = pd.read_csv(RNT_CSV)
    df["_n"] = [norm(x) for x in df.razon_social]
    return df


def _mejor_nombre(n: str, candidatos) -> tuple[float, int | None]:
    mejor, k = 0.0, None
    for i, m in candidatos:
        r = SequenceMatcher(None, n, m).ratio()
        if n and m and (n in m or m in n) and min(len(n.split()), len(m.split())) >= 2:
            r = max(r, 0.9)
        if r > mejor:
            mejor, k = r, i
    return mejor, k


def buscar_rnt(nombre: str, lat=None, lon=None, en_linea: bool = False) -> dict | None:
    """Busca el lugar en el Registro Nacional de Turismo (prestadores). Candelaria recomienda restaurantes del RNT
    que no están en el inventario de atractivos. Primero la copia local (gastronomía); si no, y se pide, la capa en línea."""
    n = norm(nombre)
    df = _rnt_local()
    if df is not None and n:
        idx = range(len(df))
        if lat is not None and lon is not None:
            d = _dist_m(lat, lon, df.lat.values, df.lon.values)
            idx = np.where(d <= 300)[0]
        r, k = _mejor_nombre(n, [(i, df["_n"].iat[i]) for i in idx])
        if k is not None and r >= 0.85:
            f = df.iloc[k]
            return {"nombre": f.razon_social, "subcategoria": f.subcategoria, "localidad": str(f.localidad).title(), "lat": float(f.lat),
                    "lon": float(f.lon), "codigo_rnt": int(f.codigo_rnt), "fuente": "RNT (copia local)"}
    if not en_linea or not n:
        return None
    try:
        tokens = [t for t in n.split() if len(t) > 2][:2]
        where = " AND ".join(f"UPPER(RAZON_SOCI) LIKE '%{t.upper()}%'" for t in tokens) or "1=0"
        q = {"where": where, "outFields": "CODIGO_RNT,RAZON_SOCI,SUB_CATEGO,LOCALIDAD,CATEGORIA", "returnGeometry": "true", "outSR": 4326, "f": "json"}
        if lat is not None and lon is not None:
            q.update(geometry=f"{lon},{lat}", geometryType="esriGeometryPoint", inSR=4326, spatialRel="esriSpatialRelIntersects", distance=300, units="esriSRUnit_Meter")
        with urllib.request.urlopen(RNT_URL + "?" + urllib.parse.urlencode(q), timeout=8) as resp:
            feats = json.loads(resp.read().decode("utf-8")).get("features", [])
        r, k = _mejor_nombre(n, [(i, norm(f["attributes"]["RAZON_SOCI"])) for i, f in enumerate(feats)])
        if k is not None and r >= 0.85:
            a, g = feats[k]["attributes"], feats[k].get("geometry") or {}
            return {"nombre": a["RAZON_SOCI"], "subcategoria": a.get("SUB_CATEGO"), "localidad": str(a.get("LOCALIDAD", "")).title(),
                    "lat": g.get("y"), "lon": g.get("x"), "codigo_rnt": a.get("CODIGO_RNT"), "fuente": "RNT (en línea)"}
    except Exception:  # noqa: BLE001  (sin red: no se puede confirmar)
        return None
    return None


def _fila_rnt(p: dict) -> pd.Series:
    """Prestador RNT como fila de catálogo (gastronomía, sin horario ni etiquetas)."""
    from construir_catalogo import SUPUESTOS
    m, ap, tags = SUPUESTOS["Gastronomía"]
    return pd.Series({"id": f"rnt-{p['codigo_rnt']}", "nombre": p["nombre"], "categoria": "Gastronomía", "localidad": p["localidad"], "direccion": "",
                      "lat": p["lat"], "lon": p["lon"], "minutos_visita_supuesto": m, "apertura_supuesto": ap, "etiquetas_supuesto": "|".join(sorted(tags)),
                      "es_de_siempre": False, "horario_texto": "", "horario_fuente": "", "para": "", "pet_friendly": "", "accesibilidad_dti": np.nan,
                      "url": "", "fuente": p["fuente"], "_rnt": p})


GENERICAS = {"de", "del", "la", "el", "los", "las", "y", "en", "a", "parque", "museo", "plaza", "plazoleta", "sector", "biblioteca", "publica",
             "iglesia", "casa", "centro", "comercial", "bogota", "calle", "carrera", "distrital", "zona", "restaurante", "cafe", "teatro"}
# Los traslados son una estimación (línea recta × 1,3); un exceso pequeño frente al tiempo disponible no es un dato verificable.
TOLERANCIA_EXCESO_MIN = 10


def resolver(parada: dict, cat: pd.DataFrame, rnt_en_linea: bool = False):
    """(fila|None, forma). forma: 'nombre+lugar' | 'coordenadas' | 'solo nombre' | 'no encontrada'."""
    lat, lon, nombre = parada.get("lat"), parada.get("lon"), parada.get("nombre", "")
    if lat is not None and lon is not None:
        i = buscar(cat, nombre, lat, lon)
        if i is not None:
            return cat.iloc[i], "nombre+lugar"
        # por coordenadas solo si además el nombre se parece (en el centro todo está a 60 m de algo)
        d = _dist_m(lat, lon, cat.lat.values, cat.lon.values)
        n_tok = set(norm(nombre).split())
        for j in np.argsort(d)[:5]:
            if d[j] > 60:
                break
            m_tok = set(cat["_n"].iat[j].split())
            if n_tok and m_tok and len(n_tok & m_tok) / len(n_tok | m_tok) >= 0.4:
                return cat.iloc[j], "coordenadas"
            # mismo punto y al menos dos palabras propias en común: «Parque Simón Bolívar - Sector Virgilio Barco» en las coordenadas
            # exactas de «Biblioteca Pública Virgilio Barco». Las palabras genéricas (parque, museo, plaza…) no cuentan.
            if len((n_tok & m_tok) - GENERICAS) >= 2:
                return cat.iloc[j], "coordenadas"
    n = norm(nombre)
    if n:
        mejor, k = 0.0, None
        for idx, m in enumerate(cat["_n"]):
            r = SequenceMatcher(None, n, m).ratio()
            if r > mejor:
                mejor, k = r, idx
        if mejor >= 0.88:
            return cat.iloc[k], "solo nombre"
    p = buscar_rnt(nombre, lat, lon, en_linea=rnt_en_linea)
    if p:
        return _fila_rnt(p), p["fuente"]
    return None, "no encontrada"


def _tags(fila) -> set[str]:
    return set(filter(None, str(fila.etiquetas_supuesto).split("|")))


def _para(fila) -> set[str]:
    p = fila.get("para", "") if hasattr(fila, "get") else ""
    return {x.strip().lower() for x in (p if isinstance(p, str) else "").split(",") if x.strip()}


def verificar(req: Solicitud, lectura: dict, catalogo: pd.DataFrame, rnt_en_linea: bool = False) -> dict:
    cat = catalogo.copy()
    cat["_n"] = [norm(x) for x in cat.nombre]
    ch: list[Chequeo] = []
    paradas_in = lectura.get("paradas", [])
    n = len(paradas_in)

    # 0. número de paradas
    if n == 0:
        ch.append(Chequeo("paradas", "Hay paradas", "falla", "No se pudo extraer ninguna parada de la respuesta del chatbot."))
    elif n > req.max_paradas:
        ch.append(Chequeo("paradas", "De 1 a 3 paradas", "aviso", f"El chatbot propuso {n} paradas (el alcance del MVP es {req.max_paradas})."))
    else:
        ch.append(Chequeo("paradas", "De 1 a 3 paradas", "ok", f"{n} parada(s)."))

    # 1. resolver
    res = []
    for i, p in enumerate(paradas_in, 1):
        fila, forma = resolver(p, cat, rnt_en_linea)
        res.append((p, fila, forma))
        if fila is None:
            ch.append(Chequeo("catalogo", "Está en la base", "falla", f"«{p.get('nombre')}» no aparece en el catálogo (inventario IDT + Visit Bogotá + Guía) ni en el RNT de gastronomía: puede ser un lugar inventado.", i))
        elif str(forma).startswith("RNT"):
            ch.append(Chequeo("catalogo", "Está en la base", "ok", f"«{p.get('nombre')}» existe como prestador registrado ({forma}: {fila['_rnt']['subcategoria']}, {fila.localidad}). No está en el inventario de atractivos y no tiene horario ni etiquetas.", i))
        elif forma == "solo nombre":
            ch.append(Chequeo("catalogo", "Está en la base", "aviso", f"«{p.get('nombre')}» coincide solo por nombre con «{fila.nombre}»; la respuesta no trae coordenadas.", i))
        else:
            ch.append(Chequeo("catalogo", "Está en la base", "ok", f"«{p.get('nombre')}» → «{fila.nombre}» ({fila.categoria}, {fila.localidad}; por {forma}).", i))

    # 2. simulación
    con_ninos = req.con == "ninos"
    pos = (req.lat, req.lon)
    t = req.cuando
    traslados, paradas, km_total, trans_min, visita_min = [], [], 0.0, 0.0, 0.0
    for i, (p, fila, forma) in enumerate(res, 1):
        dest = (p.get("lat"), p.get("lon"))
        if dest[0] is None and fila is not None:
            dest = (float(fila.lat), float(fila.lon))
        if dest[0] is None:
            continue
        # si hay fila, se usan sus coordenadas oficiales para calcular
        if fila is not None:
            dest = (float(fila.lat), float(fila.lon))
        m, km = tiempo_traslado(pos, dest, req.modo, con_ninos)
        visita = p.get("minutos_en_sitio")
        visita_decl = visita is not None
        if visita is None:
            visita = float(fila.minutos_visita_supuesto) if fila is not None else 30.0
        llegada = t + timedelta(minutes=m)
        salida = llegada + timedelta(minutes=visita)
        info = {"i": i, "id_lugar": str(fila.id) if fila is not None else "", "nombre": p.get("nombre"), "nombre_catalogo": fila.nombre if fila is not None else None, "categoria": fila.categoria if fila is not None else "—",
                "lat": dest[0], "lon": dest[1], "llegada": llegada.strftime("%H:%M"), "salida": salida.strftime("%H:%M"), "minutos_visita": round(visita),
                "visita_declarada": visita_decl, "traslado_min": round(m), "km": round(km, 2), "traslado_declarado_min": p.get("traslado_min"),
                "forma_match": forma, "opcional": bool(p.get("opcional")), "apertura": "sin dato", "horario": "", "para": "", "pet_friendly": False, "direccion": getattr(fila, "direccion", "") if fila is not None else ""}
        if fila is not None:
            ok, det, nivel = evaluar_apertura(fila, llegada, salida)
            info.update(apertura=nivel, apertura_ok=ok, apertura_detalle=det, horario=fila.horario_texto if isinstance(fila.horario_texto, str) else "",
                        para=fila.para if isinstance(fila.para, str) else "", pet_friendly=(fila.pet_friendly == "si"))
            if not ok and nivel == "oficial":
                ch.append(Chequeo("apertura", "Abierto cuando llegas", "falla", f"{info['nombre_catalogo']}: {det} (llegas {info['llegada']}, sales {info['salida']}; horario oficial: {fila.horario_fuente}).", i))
            elif not ok:   # sin horario oficial: no se puede afirmar que esté cerrado
                ch.append(Chequeo("apertura", "Abierto cuando llegas", "aviso", f"{info['nombre_catalogo']}: probablemente cerrado — {det} (llegas {info['llegada']}; supuesto por categoría, sin horario oficial).", i))
            elif nivel == "supuesto":
                ch.append(Chequeo("apertura", "Abierto cuando llegas", "aviso", f"{info['nombre_catalogo']}: {det}. No hay horario oficial en la base.", i))
            else:
                ch.append(Chequeo("apertura", "Abierto cuando llegas", "ok", f"{info['nombre_catalogo']}: {det}.", i))
        traslados.append({"desde": paradas[-1]["nombre"] if paradas else "Tu punto de salida", "hasta": p.get("nombre"), "minutos": round(m), "km": round(km, 2), "declarado": p.get("traslado_min")})
        paradas.append(info)
        km_total += km
        trans_min += m
        visita_min += visita
        t, pos = salida, dest
        dec = p.get("traslado_min")
        if dec is not None and abs(dec - m) > max(6, 0.6 * m) and i > 1:
            ch.append(Chequeo("traslado", "Traslado creíble", "aviso", f"Dice {dec:.0f} min entre paradas; la estimación por {req.modo} es {m:.0f} min ({km:.1f} km).", i))
    regreso_est = 0.0
    if req.regreso and paradas:
        regreso_est, km = tiempo_traslado(pos, (req.lat, req.lon), req.modo, con_ninos)
        traslados.append({"desde": paradas[-1]["nombre"], "hasta": "Tu punto de salida", "minutos": round(regreso_est), "km": round(km, 2), "declarado": lectura.get("regreso_min")})
        t += timedelta(minutes=regreso_est)
        km_total += km
        trans_min += regreso_est
    total = (t - req.cuando).total_seconds() / 60 if paradas else 0.0
    margen = req.minutos - total

    # 3. cupo de tiempo. Falla solo si no cabe ni con estancias mínimas (las declaradas o 15 min); si no cabe con las
    #    duraciones típicas del catálogo, o solo cabe sin las paradas opcionales, es advertencia.
    if paradas:
        tope = req.minutos - MARGEN_MIN
        sin_decl = [p for p in paradas if not p["visita_declarada"]]
        visitas_min = sum(p["minutos_visita"] if p["visita_declarada"] else 15 for p in paradas)
        total_min = trans_min + visitas_min
        detalle = f"Traslados {trans_min:.0f} + visitas {visita_min:.0f} = {total:.0f} min frente a {req.minutos} min disponibles (margen {margen:.0f} min; se pide ≥{MARGEN_MIN})."
        if margen >= MARGEN_MIN:
            ch.append(Chequeo("tiempo", "Cabe en tu tiempo", "ok", detalle))
        elif total_min <= tope and sin_decl:
            maximo = (tope - trans_min - sum(p["minutos_visita"] for p in paradas if p["visita_declarada"])) / len(sin_decl)
            ch.append(Chequeo("tiempo", "Cabe en tu tiempo", "aviso", detalle + f" Con las duraciones típicas no cabe; cabe si pasas en promedio ≤{maximo:.0f} min por parada."))
        elif margen >= -TOLERANCIA_EXCESO_MIN:
            exceso = f"se pasa {-margen:.0f} min" if margen < 0 else f"queda un margen de solo {margen:.0f} min"
            ch.append(Chequeo("tiempo", "Cabe en tu tiempo", "aviso", detalle + f" Con nuestra estimación de traslados {exceso}; la estimación es "
                              f"aproximada (línea recta × 1,3), así que va justo pero es posible. Falla solo si se pasa más de {TOLERANCIA_EXCESO_MIN} min."))
        else:
            nucleo = [p for p in paradas if not p["opcional"]]
            if nucleo and len(nucleo) < len(paradas):
                ch.append(Chequeo("tiempo", "Cabe en tu tiempo", "aviso", detalle + f" El plan marca {len(paradas) - len(nucleo)} parada(s) como opcional(es): revisa la versión corta."))
            else:
                ch.append(Chequeo("tiempo", "Cabe en tu tiempo", "falla", detalle + (f" Ni con 15 min por parada cabe ({total_min:.0f} min)." if sin_decl else "")))
        dec = lectura.get("total_declarado_min")
        if dec is not None:
            ok = abs(dec - total) <= 10
            ch.append(Chequeo("consistencia", "Su total coincide con la suma real", "ok" if ok else "aviso",
                              f"El chatbot declara {dec:.0f} min; la suma recalculada es {total:.0f} min (diferencia {total - dec:+.0f})."))
        if any(not p["visita_declarada"] for p in paradas):
            ch.append(Chequeo("minutos", "Minutos por parada", "aviso", "La respuesta no indica cuánto tiempo estar en cada sitio; se usaron los del catálogo (supuestos por categoría)."))
    for a in lectura.get("avisos", []):
        ch.append(Chequeo("lectura", "Formato de la respuesta", "aviso", a))

    # 4. compañía, mascota, preferencias
    for p in paradas:
        if p["categoria"] == "—":
            continue
        if p["para"]:
            etiqueta = TAG_COMPANIA[req.con]
            tags = {x.strip().lower() for x in p["para"].split(",")}
            ch.append(Chequeo("compania", "Apto para quien va", "ok" if etiqueta in tags else "aviso",
                              f"{p['nombre_catalogo']}: etiquetas oficiales «{p['para']}»" + ("." if etiqueta in tags else f"; no incluyen «{etiqueta}»."), p["i"]))
    if not any(c.id == "compania" for c in ch) and paradas:
        ch.append(Chequeo("compania", "Apto para quien va", "na", "Ningún lugar del plan tiene etiquetas oficiales «para quién» (solo existen en las fichas de Visit Bogotá)."))
    if req.mascota and paradas:
        for p in paradas:
            ch.append(Chequeo("mascota", "Admite mascotas", "ok" if p["pet_friendly"] else "falla",
                              f"{p.get('nombre_catalogo') or p['nombre']}: " + ("etiqueta oficial Pet Friendly." if p["pet_friendly"] else "no está confirmado como Pet Friendly en ninguna fuente."), p["i"]))
    filas = [f for _, f, _ in res if f is not None]
    if req.prefs and filas:
        for pref in req.prefs:
            if pref == "inesperado":
                sig = [f for f in filas if not f.es_de_siempre]
                ch.append(Chequeo("prefs", "Preferencia: algo inesperado", "ok" if len(sig) == len(filas) else "aviso",
                                  "Ninguna parada es de «los de siempre»." if len(sig) == len(filas) else "Incluye lugares de «los de siempre» (Monserrate, Simón Bolívar, Zona T)."))
                continue
            tag = ETIQUETA_PREF.get(pref)
            if tag is None:
                continue
            cumple = [f.nombre for f in filas if tag in _tags(f)]
            ch.append(Chequeo("prefs", f"Preferencia: {NOMBRE_PREF[pref]}", "ok" if cumple else "aviso",
                              ("Cumple: " + ", ".join(cumple[:3]) + ".") if cumple else "Ninguna parada responde a esta preferencia según las etiquetas del catálogo."))
    if "caminar_poco" in req.prefs and req.modo == "pie" and any(p["traslado_min"] > 12 for p in paradas):
        ch.append(Chequeo("caminar", "Caminar poco", "aviso", "Hay tramos a pie de más de 12 min."))

    # 5. veredicto
    fallas = [c for c in ch if c.estado == "falla"]
    avisos = [c for c in ch if c.estado == "aviso"]
    veredicto = "NO LOGRABLE" if fallas else ("LOGRABLE CON ADVERTENCIAS" if avisos else "LOGRABLE")
    oks = sum(c.estado == "ok" for c in ch)
    return {"veredicto": veredicto, "chequeos": [c.__dict__ for c in ch], "n_fallas": len(fallas), "n_avisos": len(avisos),
            "puntaje": round(100 * oks / max(1, sum(c.estado != "na" for c in ch))),
            "paradas": paradas, "traslados": traslados, "duracion_total_min": round(total), "minutos_transporte": round(trans_min),
            "minutos_visita": round(visita_min), "margen_min": round(margen), "termina_a": t.strftime("%H:%M") if paradas else "",
            "km_total": round(km_total, 1), "origen": [req.lat, req.lon]}
