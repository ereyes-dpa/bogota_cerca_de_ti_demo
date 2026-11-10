"""Cliente del chatbot de recomendación y lector de sus respuestas.

Contrato de Candelaria (observado en el JS público del widget):
    POST {base}/api/chat   {"message": str, "user_id": str, "session_id"?: str}
    -> {"answer": str, "session_id": str, "user_id": str}
El asistente nuevo (Azure OpenAI) usará, mientras no se diga otra cosa, el mismo contrato: solo cambia la URL.
La llave/token, si hace falta, se lee de la variable de entorno NUEVO_CHATBOT_TOKEN (nunca se guarda en archivos).
"""
from __future__ import annotations

import json
import os
import re
import socket
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CANDELARIA_URL = "https://azurecandelaria.visitbogota.co"
ZONA = ZoneInfo("America/Bogota")
RESPUESTAS_REALES = Path(__file__).resolve().parent / "pruebas" / "respuestas_candelaria.json"
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
COMPANIA = {"solo": "voy solo/a", "pareja": "voy en pareja", "amigos": "voy con amigos", "ninos": "voy con niños (familia)"}
PREFS = {"comer": "comer rico", "cultura": "cultura", "naturaleza": "naturaleza", "inesperado": "algo inesperado (que no sea lo de siempre: Monserrate, Parque Simón Bolívar, Zona T)",
         "caminar_poco": "caminar poco", "economico": "económico / gratis"}
MODOS = {"pie": "a pie", "bici": "en bicicleta", "transporte": "en transporte público (TransMilenio/SITP)", "auto": "en carro o taxi"}


@dataclass
class Backend:
    nombre: str                 # 'candelaria' | 'nuevo' | 'simulado'
    url: str = ""
    escenario: str = ""         # solo simulado


@dataclass
class Respuesta:
    ok: bool
    texto: str = ""
    status: int | None = None
    segundos: float = 0.0
    intentos: int = 0
    error: str = ""
    session_id: str | None = None
    simulada: bool = False


# Versión compacta de la consulta (10-nov-2026). La versión larga anterior ("Arma un plan turístico… Reglas: … usa los nombres y
# coordenadas exactos del inventario…") hacía que Candelaria pasara de los ~120 s de Cloudflare y respondiera 504 en 4 de 5 casos.
# Con los mismos datos y menos instrucciones, respondió en 48 s.
MODOS_CORTO = {"pie": "a pie", "bici": "en bici", "transporte": "en transporte público", "auto": "en carro o taxi"}
COMPANIA_CORTA = {"solo": "solo", "pareja": "en pareja", "amigos": "con amigos", "ninos": "con niños"}
PREFS_CORTO = {"comer": "comer rico", "cultura": "cultura", "naturaleza": "naturaleza", "inesperado": "algo inesperado (no lo típico)",
               "caminar_poco": "caminar poco", "economico": "económico"}
FORMA_JSON = ('Responde solo con JSON: {"paradas":[{"nombre":"","lat":0,"lon":0,"minutos_en_sitio":0,"traslado_desde_anterior_min":0,'
              '"horario_hoy":""}],"regreso_min":0,"total_min":0}')


def construir_mensaje(lat: float, lon: float, etiqueta_origen: str, minutos: int, cuando: datetime, con: str, prefs, modo: str, mascota: bool, regreso: bool = True) -> str:
    """Convierte los parámetros de la app en una consulta corta para el chatbot, pidiendo JSON para poder verificarlo."""
    c = cuando.astimezone(ZONA) if cuando.tzinfo else cuando
    dur = f"{minutos // 60} h" + (f" {minutos % 60} min" if minutos % 60 else "") if minutos >= 60 else f"{minutos} min"
    origen = etiqueta_origen if "bogot" in etiqueta_origen.lower() else f"{etiqueta_origen}, Bogotá"
    s = (f"Plan de {dur}{' (con regreso al punto de salida)' if regreso else ''} desde {origen} (lat {lat:.4f}, lon {lon:.4f}), "
         f"el {DIAS[c.weekday()]} {c:%d/%m/%Y} a las {c:%H:%M}, {MODOS_CORTO[modo]}, {COMPANIA_CORTA[con]}"
         + (", con mascota (solo lugares Pet Friendly)" if mascota else "") + ".")
    if prefs:
        s += " Le provoca: " + ", ".join(PREFS_CORTO[p] for p in prefs) + "."
    return s + " De 1 a 3 paradas abiertas a esa hora. " + FORMA_JSON


# Identificación honesta del piloto. Sin User-Agent, Python se presenta como "Python-urllib" y Cloudflare lo rechaza (403).
USER_AGENT = "BogotaCercaDeTi-Piloto/0.2 (DPA para IDT; dashboard de verificacion)"


def _post(url: str, cuerpo: dict, timeout: int, token: str | None):
    req = urllib.request.Request(url, data=json.dumps(cuerpo).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": USER_AGENT,
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode("utf-8"))


ESPERA_CANDELARIA_S = 120   # su servidor (Cloudflare) corta a los ~120 s con 504; esperar más no sirve


def _es_timeout(e: Exception) -> bool:
    return isinstance(e, (TimeoutError, socket.timeout)) or isinstance(getattr(e, "reason", None), (TimeoutError, socket.timeout))


def consultar(backend: Backend, mensaje: str, user_id: str = "dashboard-piloto", session_id: str | None = None,
              espera_s: float = ESPERA_CANDELARIA_S, reintentos: int = 1) -> Respuesta:
    """Llama al backend esperando como máximo `espera_s` segundos EN TOTAL (incluidos reintentos).
    Reintenta solo ante 502/503/504 rápidos y si queda tiempo; un 401/403 no se reintenta."""
    t0 = time.time()
    if backend.nombre == "simulado":
        datos = json.loads(RESPUESTAS_REALES.read_text(encoding="utf-8"))
        item = datos[backend.escenario]
        ok = item.get("status", 200) == 200
        return Respuesta(ok, item["respuesta"] if ok else "", item.get("status", 200), float(item.get("segundos") or 0), 1,
                         "" if ok else f"HTTP {item.get('status')} — {item['respuesta']}", simulada=True)
    base = (CANDELARIA_URL if backend.nombre == "candelaria" else backend.url).rstrip("/")
    if not base:
        return Respuesta(False, error="Falta la URL del asistente nuevo.")
    cuerpo = {"message": mensaje, "user_id": user_id, **({"session_id": session_id} if session_id else {})}
    token = os.environ.get("NUEVO_CHATBOT_TOKEN") if backend.nombre == "nuevo" else None
    limite = t0 + espera_s
    ultimo, status, i = "", None, 0
    for i in range(1, reintentos + 2):
        restante = limite - time.time()
        if restante < 3:
            break
        try:
            status, j = _post(f"{base}/api/chat", cuerpo, restante, token)
            texto = next((j[k] for k in ("answer", "response", "message", "text", "output") if isinstance(j.get(k), str)), "")
            return Respuesta(bool(texto), texto, status, time.time() - t0, i, "" if texto else "La respuesta no trae texto.", j.get("session_id"))
        except urllib.error.HTTPError as e:
            status, ultimo = e.code, f"HTTP {e.code}"
            if e.code in (401, 403):
                ultimo = (f"HTTP {e.code}: el servidor rechazó la consulta automática (Cloudflare/firewall) antes de llegar al chatbot. "
                          "El endpoint solo acepta el widget del navegador; para consultarlo desde el piloto hace falta acceso del IDT "
                          "(API key o lista blanca). Mientras tanto usa las respuestas guardadas.")
            if e.code not in (502, 503, 504):
                break
            if e.code == 504:
                ultimo = "HTTP 504: el servidor de Candelaria cortó la consulta (límite de ~120 s) sin respuesta."
        except Exception as e:  # noqa: BLE001
            if _es_timeout(e):
                ultimo = f"Candelaria no respondió en {espera_s:.0f} s (espera máxima configurada)."
                break
            ultimo = f"{type(e).__name__}: {e}"
        if limite - time.time() < 15:                  # no vale la pena reintentar sin tiempo
            break
        time.sleep(2)
    return Respuesta(False, status=status, segundos=time.time() - t0, intentos=i, error=ultimo)


# ---------------------------------------------------------------- lectura de la respuesta
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s).split())


def _json_en(texto: str):
    t = re.sub(r"```(?:json)?", "", texto)
    i = t.find("{")
    while i >= 0:
        prof = 0
        for j in range(i, len(t)):
            prof += (t[j] == "{") - (t[j] == "}")
            if prof == 0:
                try:
                    return json.loads(t[i:j + 1])
                except json.JSONDecodeError:
                    break
        i = t.find("{", i + 1)
    return None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def leer_respuesta(texto: str, catalogo=None) -> dict:
    """Extrae las paradas de la respuesta. Orden de intentos: JSON -> enlaces 'Cómo llegar' -> nombres del catálogo.
    Devuelve {paradas:[{nombre,lat,lon,minutos_en_sitio,traslado_min}], total_declarado_min, regreso_min, via, avisos}."""
    out = {"paradas": [], "total_declarado_min": None, "regreso_min": None, "via": "ninguna", "avisos": []}
    j = _json_en(texto or "")
    lista = None
    if isinstance(j, dict):
        lista = j.get("paradas") or j.get("stops")
        tot = j.get("total_min", j.get("total_minutes"))
        out["total_declarado_min"] = _num(tot)
        out["regreso_min"] = _num(j.get("regreso_min", j.get("return_minutes")))
    if isinstance(lista, list) and lista:
        for p in lista:
            out["paradas"].append({
                "nombre": str(p.get("nombre", p.get("name", ""))).strip(), "lat": _num(p.get("lat")), "lon": _num(p.get("lon")),
                "minutos_en_sitio": _num(p.get("minutos_en_sitio", p.get("minutes_there"))),
                "traslado_min": _num(p.get("traslado_desde_anterior_min", p.get("travel_minutes_from_previous"))),
                "horario_declarado": str(p.get("horario_hoy", "") or "")})
        out["via"] = "json"
        return out
    # prosa: si trae varios planes ("Opción si vas en bici", "Alternativa"...), se verifica solo el primero
    texto = texto or ""
    corte = re.search(r"^\s*(?:opci[oó]n\b|alternativa\b|plan\s+(?:b|alternativo)\b)", texto, flags=re.I | re.M)
    if corte and "latdestino=" in texto[:corte.start()]:
        texto = texto[:corte.start()]
        out["avisos"].append("La respuesta trae más de un plan; se verifica el primero.")
    # enlaces con coordenadas (Candelaria los incluye en cada parada)
    vistos = set()
    for m in re.finditer(r"latdestino=(-?[\d.]+)&longdestino=(-?[\d.]+)&title=([^\s)&]+)", texto):
        lat, lon, title = m.groups()
        k = (round(float(lat), 5), round(float(lon), 5))
        if k in vistos:
            continue
        vistos.add(k)
        cab = list(re.finditer(r"parada\s*\d+[^\n:]*", texto[:m.start()], flags=re.I))
        opcional = bool(cab) and "opcional" in cab[-1].group(0).lower()
        out["paradas"].append({"nombre": urllib.parse.unquote(title), "lat": float(lat), "lon": float(lon),
                               "minutos_en_sitio": None, "traslado_min": None, "horario_declarado": "", "opcional": opcional})
    if out["paradas"]:
        out["via"] = "enlaces"
        out["avisos"].append("La respuesta es prosa: paradas tomadas de los enlaces 'Cómo llegar'; los minutos por parada no vienen y se usan los del catálogo.")
    elif catalogo is not None and len(catalogo):
        t = " " + _norm(texto) + " "
        hallados = []
        for r in catalogo.itertuples():
            n = _norm(r.nombre)
            if len(n) >= 10 and f" {n} " in t:
                hallados.append((t.index(f" {n} "), len(n), r))
        hallados.sort()
        usados = []
        for pos, ln, r in hallados:                       # descarta nombres contenidos en otro ya encontrado
            if not any(pos >= p0 and pos + ln <= p0 + l0 for p0, l0, _ in usados):
                usados.append((pos, ln, r))
        for _, _, r in usados:
            out["paradas"].append({"nombre": r.nombre, "lat": float(r.lat), "lon": float(r.lon), "minutos_en_sitio": None,
                                   "traslado_min": None, "horario_declarado": ""})
        if out["paradas"]:
            out["via"] = "nombres"
            out["avisos"].append("La respuesta es prosa sin enlaces: paradas detectadas por coincidencia de nombres con el catálogo.")
    m = re.search(r"tiempo total[^\d]{0,40}(\d+)\s*[–-]\s*(\d+)\s*min", texto, flags=re.I)
    if m:
        out["total_declarado_min"] = (int(m.group(1)) + int(m.group(2))) / 2
        out["avisos"].append(f"Total declarado en el texto: {m.group(1)}–{m.group(2)} min (se usa el punto medio).")
    return out
