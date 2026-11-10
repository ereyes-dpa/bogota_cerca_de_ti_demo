#!/usr/bin/env python3
"""Bogotá Cerca de ti — de la consulta a la recomendación, en un solo paso.

Recibe la consulta de la app (tiempo, origen, cuándo, con quién, mascota, preferencias, modo) y devuelve la recomendación:
  1. le pide el plan al chatbot (Candelaria en vivo, una respuesta guardada, el asistente nuevo o ninguno),
  2. verifica el plan contra la base (existe, abierto a esa hora, cabe en el tiempo, compañía, mascota),
  3. arma una alternativa con el selector propio y también la verifica,
  4. elige: el plan del chatbot si no es "NO LOGRABLE"; si el chatbot falla o el plan no es lograble, la alternativa.

Usos
  # una consulta (JSON a la salida estándar)
  python3 recomendar.py --minutos 120 --origen "Suba" --cuando "2026-11-14 15:00" --con ninos --prefs naturaleza --modo transporte
  # lote para Power BI: lee un CSV de consultas y escribe consultas.csv, paradas.csv y chequeos.csv
  python3 recomendar.py --lote ../datos/consultas_ejemplo.csv --fuente guardada --salida ../datos/powerbi

En Power BI (Obtener datos → Script de Python):
  import sys; sys.path.insert(0, r"C:/ruta/a/bogota_cerca_de_ti/codigo")
  from recomendar import recomendar_lote
  consultas, paradas, chequeos = recomendar_lote(r"C:/ruta/a/bogota_cerca_de_ti/datos/consultas_ejemplo.csv", fuente="guardada")
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from chatbot import ESPERA_CANDELARIA_S, Backend, consultar, construir_mensaje, leer_respuesta  # noqa: E402
from planificador import Solicitud, _enlaces, cargar_catalogo, planear  # noqa: E402
from verificador import verificar  # noqa: E402

BOGOTA = ZoneInfo("America/Bogota")
COMPANIAS = ("solo", "pareja", "amigos", "ninos")
PREFERENCIAS = ("comer", "cultura", "naturaleza", "inesperado", "caminar_poco", "economico")
MODOS = ("pie", "bici", "transporte", "auto")
# Orígenes con nombre (los mismos que ofrece la interfaz). Suba y Teusaquillo son puntos de ejemplo, no direcciones.
ORIGENES = {
    "Suba": (4.7300, -74.0900),
    "Chapinero": (4.6495, -74.0624),
    "Centro · Plaza de Bolívar": (4.598105, -74.076096),
    "Usaquén": (4.6951, -74.03095),
    "Teusaquillo": (4.6340, -74.0730),
}
_CAT = None


def catalogo() -> pd.DataFrame:
    global _CAT
    if _CAT is None:
        _CAT = cargar_catalogo()
    return _CAT


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9 .,-]", " ", s).split())


def resolver_origen(origen) -> tuple[float, float, str]:
    """dict {lat, lon[, etiqueta]} | "lat, lon" | nombre de un origen | nombre de un lugar del catálogo."""
    if isinstance(origen, dict):
        return float(origen["lat"]), float(origen["lon"]), origen.get("etiqueta") or f"{float(origen['lat']):.4f}, {float(origen['lon']):.4f}"
    t = str(origen or "").strip()
    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*[,;]\s*(-?\d+(?:\.\d+)?)\s*", t)
    if m:
        la, lo = float(m.group(1)), float(m.group(2))
        cerca = [k for k, (a, b) in ORIGENES.items() if abs(a - la) < 0.003 and abs(b - lo) < 0.003]   # ~300 m
        return la, lo, cerca[0] if cerca else t
    n = _norm(t)
    for k, (la, lo) in ORIGENES.items():
        claves = [_norm(x) for x in k.split("·")]
        if any(c and (c in n or n in c) for c in claves):
            return la, lo, k
    cat = catalogo()
    nombres = cat.nombre.map(_norm)
    hit = cat[nombres == n]
    if hit.empty:
        hit = cat[nombres.str.contains(re.escape(n), na=False)] if len(n) >= 5 else hit
    if not hit.empty:
        f = hit.iloc[0]
        return float(f.lat), float(f.lon), f.nombre
    raise ValueError(f"No reconozco el origen «{origen}». Usa uno de {list(ORIGENES)}, un lugar del catálogo o 'lat, lon'.")


def resolver_cuando(cuando, ahora: datetime | None = None) -> datetime:
    """'ahora' | 'HH:MM' (hoy) | 'AAAA-MM-DD HH:MM' | ISO. Hora local de Bogotá, sin zona."""
    ahora = ahora or datetime.now(BOGOTA).replace(tzinfo=None, second=0, microsecond=0)
    if cuando is None or str(cuando).strip().lower() in ("", "ahora", "now"):
        return ahora
    if isinstance(cuando, datetime):
        return cuando.replace(tzinfo=None)
    t = str(cuando).strip().replace("T", " ")
    if re.fullmatch(r"\d{1,2}:\d{2}", t):
        h, m = map(int, t.split(":"))
        return ahora.replace(hour=h, minute=m)
    return datetime.strptime(t[:16], "%Y-%m-%d %H:%M")


def normalizar(consulta: dict) -> tuple[Solicitud, str]:
    """Valida la consulta y la convierte en Solicitud (el formato interno)."""
    prefs = consulta.get("prefs")
    if not isinstance(prefs, (str, list, tuple)):        # vacío o NaN (celda vacía de un CSV / Power BI)
        prefs = []
    if isinstance(prefs, str):
        prefs = [p for p in re.split(r"[|,;]", prefs) if p.strip()]
    prefs = tuple(p.strip() for p in prefs)
    con, modo = str(consulta.get("con", "solo")).strip(), str(consulta.get("modo", "transporte")).strip()
    malas = [p for p in prefs if p not in PREFERENCIAS] + ([con] if con not in COMPANIAS else []) + ([modo] if modo not in MODOS else [])
    if malas:
        raise ValueError(f"Valores no válidos: {malas}. con∈{COMPANIAS}, modo∈{MODOS}, prefs⊂{PREFERENCIAS}")
    minutos = int(round(float(consulta.get("minutos") or float(consulta.get("horas", 2)) * 60)))
    if not 30 <= minutos <= 6 * 60:
        raise ValueError("El tiempo disponible debe estar entre 30 min y 6 h.")
    lat, lon, etiqueta = resolver_origen(consulta.get("origen", "Chapinero"))
    mascota = str(consulta.get("mascota", False)).strip().lower() in ("true", "1", "si", "sí", "yes")
    return Solicitud(lat, lon, minutos, resolver_cuando(consulta.get("cuando")), con, prefs, modo, True, mascota=mascota), etiqueta


def _plan_publico(ver: dict, req: Solicitud) -> dict:
    """Plan verificado en el formato que consumen la app y Power BI."""
    paradas = [{"orden": p["i"], "id_lugar": p.get("id_lugar", ""), "nombre": p.get("nombre_catalogo") or p["nombre"], "nombre_chatbot": p["nombre"], "categoria": p["categoria"],
                "lat": p["lat"], "lon": p["lon"], "llegada": p["llegada"], "salida": p["salida"], "minutos_visita": p["minutos_visita"],
                "minutos_estimados": not p["visita_declarada"], "traslado_min": p["traslado_min"], "km": p["km"], "apertura": p["apertura"],
                "horario": p.get("horario") or "", "para": p.get("para") or "", "pet_friendly": bool(p.get("pet_friendly")),
                "opcional": bool(p.get("opcional")), "direccion": p.get("direccion") or "", "fuente_lugar": p.get("forma_match")}
               for p in ver["paradas"]]
    plan = {"paradas": paradas, "traslados": ver["traslados"], "duracion_total_min": ver["duracion_total_min"],
            "minutos_transporte": ver["minutos_transporte"], "minutos_visita": ver["minutos_visita"], "margen_min": ver["margen_min"],
            "termina_a": ver["termina_a"], "km_total": ver["km_total"], "veredicto": ver["veredicto"], "n_fallas": ver["n_fallas"],
            "n_avisos": ver["n_avisos"], "chequeos": ver["chequeos"]}
    if paradas:
        plan["enlaces"] = _enlaces({"paradas": [{**p} for p in paradas], "termina_a": ver["termina_a"]}, req)
    return plan


def _backend(fuente: str, escenario: str | None, url_nuevo: str) -> Backend | None:
    if fuente == "candelaria":
        return Backend("candelaria")
    if fuente == "guardada":
        if not escenario:
            raise ValueError("fuente='guardada' necesita el nombre del escenario (codigo/pruebas/respuestas_candelaria.json).")
        return Backend("simulado", escenario=escenario)
    if fuente == "nuevo":
        return Backend("nuevo", url_nuevo)
    if fuente == "ninguna":
        return None
    raise ValueError("fuente debe ser candelaria | guardada | nuevo | ninguna")


def recomendar(consulta: dict, fuente: str = "candelaria", escenario: str | None = None, url_nuevo: str = "",
               espera_s: float = ESPERA_CANDELARIA_S, rnt_en_linea: bool = True, excluir: set | None = None) -> dict:
    """Consulta → recomendación verificada (dict serializable a JSON)."""
    cat = catalogo()
    req, etiqueta = normalizar(consulta)
    msg = construir_mensaje(req.lat, req.lon, etiqueta, req.minutos, req.cuando, req.con, req.prefs, req.modo, req.mascota)
    backend = _backend(fuente, escenario, url_nuevo)
    chat = {"fuente": fuente, "escenario": escenario, "consultado": backend is not None}
    ver_chat = None
    if backend is not None:
        resp = consultar(backend, msg, espera_s=espera_s)
        lectura = leer_respuesta(resp.texto, cat) if resp.ok else {"paradas": [], "avisos": [], "via": "ninguna", "total_declarado_min": None}
        chat.update(ok=resp.ok, status=resp.status, segundos=round(resp.segundos, 1), error=resp.error, texto=resp.texto,
                    lectura=lectura.get("via"), mensaje=msg, simulada=resp.simulada)
        if resp.ok:
            ver_chat = verificar(req, lectura, cat, rnt_en_linea=rnt_en_linea)
            chat["plan"] = _plan_publico(ver_chat, req)
    # alternativa del selector propio
    cat_alt = cat if not excluir else cat[~cat.id.isin(excluir)]
    r = planear(req, cat_alt, n_planes=1)
    alt = None
    if r["planes"]:
        p = r["planes"][0]
        lect = {"paradas": [{"nombre": x["nombre"], "lat": x["lat"], "lon": x["lon"], "minutos_en_sitio": x["minutos_visita"], "traslado_min": None}
                            for x in p["paradas"]], "avisos": [], "total_declarado_min": p["duracion_total_min"]}
        alt = _plan_publico(verificar(req, lect, cat), req)
        alt["ids"] = [x["id"] for x in p["paradas"]]
    # decisión
    if ver_chat and ver_chat["paradas"] and ver_chat["veredicto"] != "NO LOGRABLE":
        origen_rec, motivo, plan = "chatbot", f"Plan del chatbot verificado: {ver_chat['veredicto'].lower()}.", chat["plan"]
    elif alt:
        if backend is None:
            motivo = "Plan del selector propio (sin consulta al chatbot)."
        elif not chat.get("ok"):
            motivo = f"El chatbot no respondió ({chat.get('error') or 'sin texto'}); se usa el selector propio."
        else:
            motivo = f"El plan del chatbot no es lograble ({ver_chat['n_fallas'] if ver_chat else 0} falla[s]); se usa el selector propio."
        origen_rec, plan = "selector_propio", alt
    else:
        origen_rec, motivo, plan = "ninguno", "No hay un plan que quepa con estos parámetros (hora, tiempo o mascota).", None
    return {
        "consulta": {"minutos": req.minutos, "origen": etiqueta, "lat": req.lat, "lon": req.lon, "cuando": req.cuando.strftime("%Y-%m-%d %H:%M"),
                     "dia": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][req.cuando.weekday()],
                     "con": req.con, "prefs": list(req.prefs), "modo": req.modo, "mascota": req.mascota},
        "recomendacion": {"origen": origen_rec, "motivo": motivo, "plan": plan},
        "chatbot": chat,
        "alternativa": alt,
        "generado": datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M:%S"),
    }


# ------------------------------------------------------------------ tablas para Power BI
def a_tablas(resultados: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Una lista de resultados de recomendar() → (consultas, paradas, chequeos), listas para Power BI."""
    cons, par, che = [], [], []
    for k, r in enumerate(resultados, 1):
        cid = r.get("id") or f"c{k:04d}"
        c, rec, ch = r["consulta"], r["recomendacion"], r["chatbot"]
        plan = rec["plan"] or {}
        chat_plan = ch.get("plan") or {}
        cons.append({"consulta_id": cid, "generado": r["generado"], **{x: c[x] for x in ("origen", "lat", "lon", "minutos", "cuando", "dia", "con", "modo", "mascota")},
                     "prefs": "|".join(c["prefs"]), "fuente_chatbot": ch["fuente"], "escenario": ch.get("escenario"),
                     "chatbot_status": ch.get("status"), "chatbot_segundos": ch.get("segundos"), "chatbot_respondio": bool(ch.get("ok")),
                     "chatbot_veredicto": chat_plan.get("veredicto", "SIN RESPUESTA" if ch.get("consultado") else "NO CONSULTADO"),
                     "chatbot_paradas": len(chat_plan.get("paradas", [])),
                     "recomendacion_origen": rec["origen"], "recomendacion_veredicto": plan.get("veredicto"), "recomendacion_paradas": len(plan.get("paradas", [])),
                     "duracion_total_min": plan.get("duracion_total_min"), "margen_min": plan.get("margen_min"), "km_total": plan.get("km_total"),
                     "termina_a": plan.get("termina_a"), "motivo": rec["motivo"]})
        for etiqueta, pl in (("recomendado", plan), ("chatbot", chat_plan), ("alternativa", r.get("alternativa") or {})):
            for p in pl.get("paradas", []):
                par.append({"consulta_id": cid, "plan": etiqueta, **{x: p.get(x, "") for x in ("orden", "id_lugar", "nombre", "categoria", "lat", "lon", "llegada", "salida",
                                                                                               "minutos_visita", "traslado_min", "apertura", "horario", "pet_friendly")}})
            if etiqueta != "recomendado":
                for q in pl.get("chequeos", []):
                    che.append({"consulta_id": cid, "plan": etiqueta, "criterio": q["titulo"], "id_criterio": q["id"], "estado": q["estado"],
                                "parada": q["parada"], "detalle": q["detalle"]})
    return pd.DataFrame(cons), pd.DataFrame(par), pd.DataFrame(che)


def leer_consultas(fuente_csv) -> list[dict]:
    df = fuente_csv if isinstance(fuente_csv, pd.DataFrame) else pd.read_csv(fuente_csv, dtype=str, keep_default_na=False)
    return [{k: (None if v is None or (isinstance(v, float) and v != v) or v == "" else v) for k, v in fila.items()}
            for fila in df.to_dict("records")]


def recomendar_lote(consultas, fuente: str = "guardada", espera_s: float = ESPERA_CANDELARIA_S, salida: str | Path | None = None,
                    rnt_en_linea: bool = False):
    """CSV/DataFrame de consultas → (consultas, paradas, chequeos). Con fuente='guardada' usa la columna 'escenario'."""
    resultados = []
    for c in leer_consultas(consultas):
        esc = c.get("escenario") if fuente == "guardada" else None
        try:
            r = recomendar(c, fuente=fuente if (fuente != "guardada" or esc) else "ninguna", escenario=esc, espera_s=espera_s, rnt_en_linea=rnt_en_linea)
        except ValueError as e:
            print(f"Consulta {c.get('id')}: {e}", file=sys.stderr)
            continue
        r["id"] = c.get("id")
        resultados.append(r)
    tablas = a_tablas(resultados)
    if salida:
        d = Path(salida)
        d.mkdir(parents=True, exist_ok=True)
        for nombre, t in zip(("consultas", "paradas", "chequeos"), tablas):
            t.to_csv(d / f"{nombre}.csv", index=False, encoding="utf-8")
    return tablas


def _json(o):
    return o.item() if hasattr(o, "item") else str(o)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minutos", type=int, default=120)
    ap.add_argument("--origen", default="Chapinero", help=f"{list(ORIGENES)}, un lugar del catálogo o 'lat, lon'")
    ap.add_argument("--cuando", default="ahora", help="'ahora', 'HH:MM' o 'AAAA-MM-DD HH:MM' (hora de Bogotá)")
    ap.add_argument("--con", default="solo", choices=COMPANIAS)
    ap.add_argument("--prefs", default="", help="separadas por coma: " + ",".join(PREFERENCIAS))
    ap.add_argument("--modo", default="transporte", choices=MODOS)
    ap.add_argument("--mascota", action="store_true")
    ap.add_argument("--fuente", default="candelaria", choices=["candelaria", "guardada", "nuevo", "ninguna"])
    ap.add_argument("--escenario", default=None, help="con --fuente guardada")
    ap.add_argument("--url-nuevo", default="")
    ap.add_argument("--espera", type=float, default=ESPERA_CANDELARIA_S, help="segundos máximos esperando al chatbot")
    ap.add_argument("--lote", default=None, help="CSV de consultas (id, minutos, origen, cuando, con, prefs, modo, mascota[, escenario])")
    ap.add_argument("--salida", default=None, help="carpeta para consultas.csv, paradas.csv y chequeos.csv")
    a = ap.parse_args()
    if a.lote:
        c, p, q = recomendar_lote(a.lote, fuente=a.fuente, espera_s=a.espera, salida=a.salida)
        print(c[["consulta_id", "chatbot_veredicto", "recomendacion_origen", "recomendacion_veredicto", "recomendacion_paradas"]].to_string(index=False))
        if a.salida:
            print(f"\nTablas escritas en {a.salida}")
        return
    r = recomendar({"minutos": a.minutos, "origen": a.origen, "cuando": a.cuando, "con": a.con, "prefs": a.prefs, "modo": a.modo, "mascota": a.mascota},
                   fuente=a.fuente, escenario=a.escenario, url_nuevo=a.url_nuevo, espera_s=a.espera)
    print(json.dumps(r, ensure_ascii=False, indent=2, default=_json))


if __name__ == "__main__":
    main()
