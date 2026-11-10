#!/usr/bin/env python3
"""Selector de tiempo de "Bogotá Cerca de ti" (Reto 2, propuesta 3).

Dado  tiempo disponible + origen + cuándo + con quién + preferencias,
devuelve hasta 3 planes de 1 a 3 paradas que CABEN en el tiempo, con
traslados, hora de término, margen, enlace de ruta y texto para WhatsApp.

Es una referencia/prototipo de la pieza "Selector de tiempo" de la diapositiva 19
(la API de rutas y los horarios reales aún no están conectados):
  * tiempo_traslado()  -> estimación geométrica; reemplazar por Google Maps / ArcGIS Online.
  * apertura           -> viene de SUPUESTOS por categoría (datos/catalogo_atractivos.csv);
                          reemplazar por horarios reales del catálogo (Visit Bogotá / Planes Locales).

Uso:
  python3 planificador.py --lat 4.7409 --lon -74.0838 --minutos 120 \
      --cuando "2026-11-14 15:00" --con ninos --prefs naturaleza,economico --modo transporte
  python3 planificador.py --autoprueba
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from horarios import esta_abierto, parsear_horario, resumen  # noqa: E402

DATOS = Path(__file__).resolve().parents[1] / "datos"
CATALOGO = DATOS / "catalogo_atractivos.csv"
CATALOGO_ENRIQUECIDO = DATOS / "catalogo_enriquecido.csv"


def cargar_catalogo() -> pd.DataFrame:
    """Catálogo enriquecido (horarios oficiales, etiquetas 'para') si existe; si no, el base con supuestos."""
    df = pd.read_csv(CATALOGO_ENRIQUECIDO if CATALOGO_ENRIQUECIDO.exists() else CATALOGO)
    for c, v in (("horario_texto", ""), ("horario_fuente", ""), ("para", ""), ("pet_friendly", ""), ("url", ""), ("fuente", "inventario_idt")):
        if c not in df:
            df[c] = v
        df[c] = df[c].fillna("")
    if "accesibilidad_dti" not in df:
        df["accesibilidad_dti"] = float("nan")
    df["id"] = df["id"].astype(str)
    df["es_de_siempre"] = df["es_de_siempre"].fillna(False).astype(bool)
    return df

# ---------- supuestos de movilidad (ajustables) ----------
FACTOR_RODEO = 1.3            # distancia por calle ≈ 1,3 × línea recta
V_PIE = 4.8                   # km/h
V_PIE_NINOS = 3.6
V_BICI = 12.0
V_TRANSPORTE = 17.0           # km/h en el vehículo, mezcla troncal (25,2 km/h en 2024) y SITP zonal, más lento
ESPERA_TRANSPORTE_MIN = 6     # espera + acceso
SALIDA_TRANSPORTE_MIN = 4
TRANSPORTE_MIN_KM = 1.2       # por debajo de esta distancia se camina
V_AUTO = 23.0                 # km/h, velocidad promedio diaria en Bogotá (Secretaría de Movilidad, 2023)
ESTACIONAR_AUTO_MIN = 8       # buscar parqueadero o esperar el taxi, por tramo
AUTO_MIN_KM = 0.8             # por debajo de esta distancia se camina
MARGEN_MIN = 5                # holgura mínima para que el plan "quepa" de verdad
# Horario supuesto cuando el catálogo no trae horarios
H_ABRE, H_CIERRA_DIURNO, H_CIERRA_CULTURA = 6.0, 18.0, 17.5
H_CIERRA_COMERCIAL = 21.0
CATEGORIAS_NOCTURNAS = {"Gastronomía", "Comercio"}
CIERRAN_LUNES = {"Museo"}     # supuesto: la mayoría de museos cierra los lunes (Nacional, Oro, Bogotá, Independencia),
                              # pero NO todos (Botero y Casa de la Moneda abren lunes; fuente 2021). Requiere horario real por sitio.


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def tiempo_traslado(a: tuple[float, float], b: tuple[float, float], modo: str, con_ninos: bool) -> tuple[float, float]:
    """(minutos, km por calle). PUNTO DE ENGANCHE con la API de rutas."""
    km = haversine_km(*a, *b) * FACTOR_RODEO
    v_pie = V_PIE_NINOS if con_ninos else V_PIE
    if modo == "bici":
        return km / V_BICI * 60, km
    if modo == "transporte" and km >= TRANSPORTE_MIN_KM:
        return ESPERA_TRANSPORTE_MIN + km / V_TRANSPORTE * 60 + SALIDA_TRANSPORTE_MIN, km
    if modo == "auto" and km >= AUTO_MIN_KM:
        return ESTACIONAR_AUTO_MIN + km / V_AUTO * 60, km
    return km / v_pie * 60, km


@dataclass
class Solicitud:
    lat: float
    lon: float
    minutos: int
    cuando: datetime
    con: str = "solo"                 # solo | pareja | amigos | ninos
    prefs: tuple[str, ...] = ()       # comer cultura naturaleza inesperado caminar_poco economico
    modo: str = "pie"                 # pie | bici | transporte | auto
    regreso: bool = True              # el plan incluye volver al origen
    max_paradas: int = 3
    mascota: bool = False             # viaja con mascota (usa la etiqueta oficial 'Pet Friendly')


def _hora(dt: datetime) -> float:
    return dt.hour + dt.minute / 60


_CACHE_H: dict = {}


def horario_oficial(fila):
    """Horario semanal interpretado desde el texto oficial del catálogo, o None."""
    t = getattr(fila, "horario_texto", "")
    if not isinstance(t, str) or not t.strip():
        return None
    if t not in _CACHE_H:
        _CACHE_H[t] = parsear_horario(t)
    return _CACHE_H[t]


def evaluar_apertura(fila, llegada: datetime, salida: datetime) -> tuple[bool, str, str]:
    """(abierto, detalle, nivel). nivel: 'oficial' (horario del catálogo) | 'abierto' (espacio público) | 'supuesto' (heurística por categoría)."""
    sched = horario_oficial(fila)
    if sched:
        ok, det = esta_abierto(sched, llegada, salida)
        return ok, det, "oficial"
    ap = fila.apertura_supuesto
    if ap == "abierto":
        return True, "espacio público, sin horario de cierre", "abierto"
    h0, h1 = _hora(llegada), _hora(salida)
    if salida.date() != llegada.date():
        return False, "la visita pasa de medianoche", "supuesto"
    if ap == "diurno":
        if h0 >= H_ABRE and h1 <= H_CIERRA_DIURNO:
            return True, "espacio abierto: mejor con luz de día", "supuesto"
        return False, "espacio abierto solo de día (06:00–18:00)", "supuesto"
    tope = H_CIERRA_COMERCIAL if fila.categoria in CATEGORIAS_NOCTURNAS else H_CIERRA_CULTURA
    if fila.categoria in CIERRAN_LUNES and llegada.weekday() == 0:
        return False, "los museos suelen cerrar los lunes", "supuesto"
    if h0 >= H_ABRE + 3 and h1 <= tope:      # abren ~9:00
        return True, "horario por confirmar antes de salir", "supuesto"
    return False, f"fuera del horario típico (09:00–{int(tope):02d}:{int((tope % 1) * 60):02d})", "supuesto"


def _abierto(fila, llegada: datetime, salida: datetime) -> tuple[bool, str]:
    """(se puede incluir, aviso). Con horario oficial se usa; si no, la heurística por categoría."""
    ok, det, nivel = evaluar_apertura(fila, llegada, salida)
    if not ok:
        return False, ""
    return True, {"oficial": f"Horario oficial: {det}.", "abierto": "", "supuesto": det[0].upper() + det[1:] + "."}[nivel]


def _puntaje(fila, req: Solicitud) -> float:
    tags = set(filter(None, str(fila.etiquetas_supuesto).split("|")))
    s = 1.0
    mapa = {"comer": "comer", "cultura": "cultura", "naturaleza": "naturaleza", "economico": "economico", "caminar_poco": "caminar_poco"}
    for p in req.prefs:
        if p in mapa and mapa[p] in tags:
            s += 2.0
    if req.con == "ninos":
        if "ninos" in tags:
            s += 1.5
        elif "ninos_ok" in tags:
            s += 0.5
        if fila.categoria in ("Escenario Religioso", "Monumento y/o escultura", "Biblioteca"):
            s -= 0.8
    if fila.es_de_siempre:
        s -= 2.0 if "inesperado" in req.prefs else 0.8     # la hipótesis es guiar hacia algo distinto
    elif "inesperado" in req.prefs and fila.categoria in ("Atractivo Cultural", "Museo", "Atractivo de Naturaleza", "Jardín Botánico"):
        s += 0.8
    para = {x.strip().lower() for x in (fila.para if isinstance(getattr(fila, "para", ""), str) else "").split(",") if x.strip()}
    if para:                                               # etiquetas oficiales de Visit Bogotá
        s += 1.0 if {"solo": "solo", "pareja": "pareja", "amigos": "grupo", "ninos": "familias"}[req.con] in para else -0.5
    if req.mascota:
        s += 3.0 if "pet friendly" in para else -0.5       # solo "Pet Friendly" es dato oficial; el resto no está verificado
    if fila.apertura_supuesto == "verificar" and not horario_oficial(fila):
        s -= 0.3                                           # horario no verificado
    if fila.minutos_visita_supuesto < 15:
        s *= 0.5                                           # paradas de paso (monumentos) pesan menos: no son un "plan"
    return s


def _plan_para(secuencia, req: Solicitud):
    """Simula el recorrido; devuelve dict o None si no cabe / algo está cerrado."""
    con_ninos = req.con == "ninos"
    pos = (req.lat, req.lon)
    t = req.cuando
    paradas, traslados, avisos = [], [], []
    km_total = trans_min = visita_min = 0.0
    for fila in secuencia:
        dest = (fila.lat, fila.lon)
        m, km = tiempo_traslado(pos, dest, req.modo, con_ninos)
        if "caminar_poco" in req.prefs and m > 12 and req.modo == "pie":
            return None
        llegada = t + timedelta(minutes=m)
        salida = llegada + timedelta(minutes=int(fila.minutos_visita_supuesto))
        ok, aviso = _abierto(fila, llegada, salida)
        if not ok:
            return None
        traslados.append({"desde": paradas[-1]["nombre"] if paradas else "Tu punto de salida", "hasta": fila.nombre,
                          "minutos": round(m), "km": round(km, 2)})
        paradas.append({"nombre": fila.nombre, "categoria": fila.categoria, "localidad": fila.localidad,
                        "direccion": fila.direccion, "lat": fila.lat, "lon": fila.lon,
                        "llegada": llegada.strftime("%H:%M"), "salida": salida.strftime("%H:%M"),
                        "minutos_visita": int(fila.minutos_visita_supuesto),
                        "apertura": fila.apertura_supuesto, "aviso": aviso,
                        "horario": resumen(horario_oficial(fila)) if horario_oficial(fila) else "",
                        "horario_fuente": fila.horario_fuente if horario_oficial(fila) else "",
                        "para": fila.para, "pet_friendly": fila.pet_friendly == "si", "id": str(fila.id)})
        km_total += km
        trans_min += m
        visita_min += fila.minutos_visita_supuesto
        t, pos = salida, dest
    if req.regreso:
        m, km = tiempo_traslado(pos, (req.lat, req.lon), req.modo, con_ninos)
        traslados.append({"desde": paradas[-1]["nombre"], "hasta": "Tu punto de salida", "minutos": round(m), "km": round(km, 2)})
        t += timedelta(minutes=m)
        km_total += km
        trans_min += m
    total = (t - req.cuando).total_seconds() / 60
    if total > req.minutos - MARGEN_MIN:
        return None
    return {"paradas": paradas, "traslados": traslados, "duracion_total_min": round(total),
            "minutos_transporte": round(trans_min), "minutos_visita": int(visita_min),
            "margen_min": round(req.minutos - total), "termina_a": t.strftime("%H:%M"),
            "km_total": round(km_total, 1), "avisos": sorted({p["aviso"] for p in paradas if p["aviso"]})}


def _enlaces(plan: dict, req: Solicitud) -> dict:
    tm = {"pie": "walking", "bici": "bicycling", "transporte": "transit", "auto": "driving"}[req.modo]
    pts = [(p["lat"], p["lon"]) for p in plan["paradas"]]
    destino = (req.lat, req.lon) if req.regreso else pts[-1]
    way = pts if req.regreso else pts[:-1]
    q = {"api": 1, "origin": f"{req.lat},{req.lon}", "destination": f"{destino[0]},{destino[1]}", "travelmode": tm}
    if way:
        q["waypoints"] = "|".join(f"{a},{b}" for a, b in way)
    maps = "https://www.google.com/maps/dir/?" + urllib.parse.urlencode(q, safe=",|")
    lineas = [f"Mi plan de {req.minutos // 60 if req.minutos % 60 == 0 else req.minutos / 60:g} h en Bogotá:"]
    for i, p in enumerate(plan["paradas"], 1):
        lineas.append(f"{i}. {p['nombre']} ({p['llegada']}–{p['salida']})")
    lineas.append(f"Termino a las {plan['termina_a']}. Ruta: {maps}")
    return {"google_maps": maps, "whatsapp": "https://wa.me/?text=" + urllib.parse.quote("\n".join(lineas))}


def planear(req: Solicitud, catalogo: pd.DataFrame | None = None, n_planes: int = 3, k: int = 40) -> dict:
    df = (catalogo if catalogo is not None else cargar_catalogo()).copy()
    if req.mascota:                                    # con mascota solo entran lugares con la etiqueta oficial "Pet Friendly"
        df = df[df.get("pet_friendly", "").astype(str) == "si"]
    con_ninos = req.con == "ninos"
    # radio máximo ida (km en línea recta) que todavía podría caber
    v = {"pie": V_PIE_NINOS if con_ninos else V_PIE, "bici": V_BICI, "transporte": 25.0, "auto": V_AUTO}[req.modo]
    radio = max(0.3, (req.minutos - MARGEN_MIN - 10) * v / 60 / FACTOR_RODEO / (2 if req.regreso else 1))
    df["dist_km"] = [haversine_km(req.lat, req.lon, a, b) for a, b in zip(df.lat, df.lon)]
    df = df[df.dist_km <= radio].copy()
    avisos = []
    if df.empty:
        return {"solicitud": _resumen(req), "planes": [], "avisos": ["No hay atractivos del catálogo dentro del alcance de ese tiempo y modo."]}
    df["puntaje"] = [_puntaje(r, req) for r in df.itertuples()]
    # candidatas: mejor puntaje, pero cercanía pesa (si no, el filtro elige parques lejanos y descarta el barrio de al lado)
    df["rank"] = df.puntaje - 0.5 * df.dist_km
    cand = df.sort_values(["rank", "dist_km"], ascending=[False, True]).head(k)
    filas = list(cand.itertuples())
    puntaje = {r.id: r.puntaje for r in filas}
    resultados = []
    for n in range(1, req.max_paradas + 1):
        for comb in itertools.permutations(filas, n):
            plan = _plan_para(comb, req)
            if plan is None:
                continue
            cats = {p["categoria"] for p in plan["paradas"]}
            valor = (sum(puntaje[f.id] for f in comb)
                     + 0.5 * (len(cats) - 1)
                     + 1.0 * min(plan["minutos_visita"] / 60, 1.5)
                     + 2.0 * min(plan["duracion_total_min"] / req.minutos, 0.85) / 0.85   # aprovechar el tiempo disponible
                     - 0.06 * plan["minutos_transporte"])
            resultados.append((valor, comb, plan))
    # descarta planes que dejan >60 % del tiempo sin usar, salvo que no haya nada mejor
    largos = [r for r in resultados if r[2]["duracion_total_min"] >= 0.4 * req.minutos]
    resultados = largos or resultados
    resultados.sort(key=lambda x: -x[0])
    elegidos, usados = [], []
    for valor, comb, plan in resultados:
        ids = {f.id for f in comb}
        # diversidad: dos opciones no comparten paradas (3 paradas: a lo sumo 1 en común)
        if any(len(ids & u) > (1 if min(len(ids), len(u)) >= 3 else 0) for u in usados):
            continue
        plan["puntaje"] = round(valor, 2)
        plan["enlaces"] = _enlaces(plan, req)
        elegidos.append(plan)
        usados.append(ids)
        if len(elegidos) == n_planes:
            break
    if not elegidos:
        avisos.append("Ningún plan cabe en el tiempo con los horarios supuestos (posible: es de noche, lunes o el tiempo es muy corto).")
    return {"solicitud": _resumen(req), "planes": elegidos, "avisos": avisos}


def _resumen(req: Solicitud) -> dict:
    return {"origen": [req.lat, req.lon], "minutos": req.minutos, "cuando": req.cuando.strftime("%Y-%m-%d %H:%M (%A)"),
            "con": req.con, "prefs": list(req.prefs), "modo": req.modo, "regreso": req.regreso}


def a_markdown(res: dict, titulo: str = "") -> str:
    s = res["solicitud"]
    out = [f"### {titulo}" if titulo else "### Plan", "",
           f"**Entrada:** {s['minutos']} min · {s['cuando']} · con {s['con']} · modo {s['modo']} · preferencias: {', '.join(s['prefs']) or '—'} · origen ({s['origen'][0]}, {s['origen'][1]})", ""]
    if not res["planes"]:
        out += ["_Sin planes que quepan._ " + " ".join(res["avisos"]), ""]
        return "\n".join(out)
    for i, p in enumerate(res["planes"], 1):
        out += [f"**Opción {i}** — {p['duracion_total_min']} min en total · {len(p['paradas'])} parada(s) · {p['minutos_transporte']} min de traslado · margen {p['margen_min']} min · termina {p['termina_a']} · {p['km_total']} km", ""]
        k = 0
        for j, pa in enumerate(p["paradas"]):
            t = p["traslados"][j]
            out.append(f"- {t['minutos']} min ({t['km']} km) → **{pa['nombre']}** · {pa['categoria']} · {pa['localidad']} · {pa['llegada']}–{pa['salida']} ({pa['minutos_visita']} min)" + (f" · _{pa['aviso']}_" if pa["aviso"] else ""))
        if s["regreso"]:
            t = p["traslados"][-1]
            out.append(f"- {t['minutos']} min ({t['km']} km) → regreso al punto de salida")
        out += ["", f"[Ruta en Google Maps]({p['enlaces']['google_maps']}) · [Compartir por WhatsApp]({p['enlaces']['whatsapp']})", ""]
    return "\n".join(out)


def autoprueba(catalogo: pd.DataFrame) -> None:
    """Verificaciones de coherencia (todas deben pasar)."""
    casos = [
        Solicitud(4.7409, -74.0838, 120, datetime(2026, 11, 14, 15, 0), "ninos", ("naturaleza", "economico"), "transporte"),
        Solicitud(4.6495, -74.0624, 120, datetime(2026, 11, 9, 19, 30), "solo", ("comer",), "bici"),
        Solicitud(4.5981, -74.0760, 180, datetime(2026, 11, 14, 10, 0), "pareja", ("cultura", "comer"), "pie"),
        Solicitud(4.6280, -74.0650, 60, datetime(2026, 11, 15, 11, 0), "amigos", ("inesperado", "caminar_poco"), "pie"),
    ]
    for i, c in enumerate(casos, 1):
        r = planear(c, catalogo)
        for p in r["planes"]:
            assert p["duracion_total_min"] <= c.minutos - MARGEN_MIN, (i, "excede el tiempo")
            assert 1 <= len(p["paradas"]) <= 3, (i, "paradas fuera de rango")
            assert p["margen_min"] >= MARGEN_MIN - 1, (i, "margen insuficiente")  # -1 por redondeo
            suma = sum(t["minutos"] for t in p["traslados"])
            assert abs(suma - p["minutos_transporte"]) <= len(p["traslados"]), (i, "traslados no suman")
            tot = suma + p["minutos_visita"]
            assert abs(tot - p["duracion_total_min"]) <= len(p["traslados"]) + 1, (i, "total no coincide con la suma de partes")
            for pa in p["paradas"]:
                assert pa["apertura"] != "verificar" or pa["aviso"], (i, "falta aviso de horario")
        print(f"caso {i}: OK — {len(r['planes'])} plan(es)")
    print("Autoprueba superada.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--minutos", type=int, default=120)
    ap.add_argument("--cuando", default=None, help='"AAAA-MM-DD HH:MM" (por defecto, ahora)')
    ap.add_argument("--con", default="solo", choices=["solo", "pareja", "amigos", "ninos"])
    ap.add_argument("--prefs", default="", help="comer,cultura,naturaleza,inesperado,caminar_poco,economico")
    ap.add_argument("--modo", default="pie", choices=["pie", "bici", "transporte", "auto"])
    ap.add_argument("--sin-regreso", action="store_true")
    ap.add_argument("--mascota", action="store_true", help="viaja con mascota (prioriza 'Pet Friendly')")
    ap.add_argument("--formato", default="md", choices=["md", "json"])
    ap.add_argument("--autoprueba", action="store_true")
    a = ap.parse_args()
    cat = cargar_catalogo()
    if a.autoprueba:
        autoprueba(cat)
        return
    if a.lat is None or a.lon is None:
        ap.error("--lat y --lon son obligatorios")
    cuando = datetime.strptime(a.cuando, "%Y-%m-%d %H:%M") if a.cuando else datetime.now().replace(second=0, microsecond=0)
    req = Solicitud(a.lat, a.lon, a.minutos, cuando, a.con, tuple(p for p in a.prefs.split(",") if p), a.modo, not a.sin_regreso, mascota=a.mascota)
    res = planear(req, cat)
    print(json.dumps(res, ensure_ascii=False, indent=2) if a.formato == "json" else a_markdown(res))


if __name__ == "__main__":
    main()
