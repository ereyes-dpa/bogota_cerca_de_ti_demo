"""Bogotá Cerca de ti — página «Demo» del dashboard piloto (Reto 2).

Izquierda: la pantalla «Cuéntame lo esencial» tal como se verá en la app (componente HTML, mockup de la diapositiva 20).
Derecha: el resultado como lo vería el usuario («ya tiene plan», la ruta, ¿lo ajustamos?, paso a paso).
Abajo: los detalles para el IDT (verificación, respuesta del chatbot, demanda y salida para Power BI).

Toda la lógica está en codigo/recomendar.py (el mismo script que se usará en Power BI); este archivo solo la presenta.

Se abre desde app.py (navegación):  streamlit run app.py
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import folium
import pandas as pd
import requests
import streamlit as st
from streamlit_folium import st_folium

AQUI = Path(__file__).resolve().parents[1]      # carpeta bogota_cerca_de_ti
sys.path.insert(0, str(AQUI / "codigo"))
from chatbot import ESPERA_CANDELARIA_S, RESPUESTAS_REALES  # noqa: E402
from planificador import CATALOGO_ENRIQUECIDO  # noqa: E402
from recomendar import ORIGENES, a_tablas, catalogo, recomendar  # noqa: E402

LOG = AQUI / "datos" / "consultas_dashboard.csv"
FUENTES = {"Respuestas guardadas de Candelaria": "guardada", "Candelaria en vivo": "candelaria",
           "Asistente nuevo (URL)": "nuevo", "Solo selector propio": "ninguna"}
ICONO = {"ok": "✅", "aviso": "⚠️", "falla": "❌", "na": "➖"}
# Paleta de Data-Pop Alliance (logo y sitio web): cian #1DADE4, azul noche #162536, naranja #F37828, verde #0D7D43,
# amarillo #FCD146, rojo #BF2531, morado #51346C. El teléfono y el resultado conservan los colores del mockup de la app.
DPA = {"cian": "#1DADE4", "azul": "#162536", "naranja": "#F37828", "verde": "#0D7D43", "amarillo": "#FCD146", "rojo": "#BF2531",
       "morado": "#51346C", "gris": "#6B7785"}
COLOR_VEREDICTO = {"LOGRABLE": (DPA["verde"], "#ffffff"), "LOGRABLE CON ADVERTENCIAS": (DPA["amarillo"], DPA["azul"]),
                   "NO LOGRABLE": (DPA["rojo"], "#ffffff"), "SIN RESPUESTA": (DPA["gris"], "#ffffff")}
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
CON = {"solo": "Solo", "pareja": "En pareja", "amigos": "Con amigos", "ninos": "Con niños"}
MODO = {"pie": ("A pie", "🚶"), "bici": ("En bici", "🚲"), "transporte": ("En transporte", "🚌"), "auto": ("En carro o taxi", "🚗")}
OSRM = {"pie": "routed-foot", "bici": "routed-bike", "auto": "routed-car"}
AJUSTES = {"Caminar menos": "caminar_poco", "Agregar algo de comer": "comer", "Más económico": "economico", "Cambiar una parada": None}

from telefono_componente import telefono  # noqa: E402

# ------------------------------------------------------------------ estilo (paleta y tipografía del mockup)
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&family=Instrument+Serif:ital@0;1&display=swap');
:root{--dpa-cian:#1DADE4;--dpa-azul:#162536;--dpa-naranja:#F37828;--verde:#1f5a43;--tinta:#1c2a24;--gris:#7d8592;--linea:#e3e6ee;--crema:#fcfaf2;--crema-borde:#ece6d2;--oro:#f2c14e;--terracota:#c8643e}
.block-container{padding-top:1.2rem;max-width:1500px}
.app, .app *{font-family:"DM Sans",system-ui,sans-serif !important}
/* El resultado se dibuja sobre un lienzo blanco, como la pantalla de la app, en modo claro y oscuro */
.st-key-lienzo{background:#ffffff;color:var(--tinta);border-radius:28px;padding:16px 16px 22px;border:1px solid rgba(128,128,128,.22)}
.st-key-lienzo [data-testid="stMarkdownContainer"]{color:var(--tinta)}
.app .serif, .app h1, .app h2, .app h3, .espera .av{font-family:"Instrument Serif",Georgia,serif !important;font-weight:400 !important;letter-spacing:-.01em}
.app h1, .app h2, .app h3{padding:0 !important;line-height:1.08 !important}
.sobre{font-size:11.5px;letter-spacing:.14em;font-weight:600;text-transform:uppercase;border-left:3px solid var(--dpa-cian);padding-left:8px}
.st-key-lienzo .sobre{color:var(--verde);border:0;padding:0}
.peq{opacity:.72;font-size:.85rem}
.hero{border-radius:26px;padding:30px 30px 26px;color:#fff;
      background:radial-gradient(120% 90% at 50% 40%,#a9bdf0 0%,#5d7fdc 38%,#1f3a9a 78%,#13256e 100%)}
.hero *{color:#fff}
.st-key-lienzo .hero .sobre{color:var(--oro)}
.hero h1{font-family:"Instrument Serif",Georgia,serif;font-weight:400;font-size:52px;line-height:1.02;margin:10px 0 14px;letter-spacing:-.015em}
.hero h1 em{color:var(--oro);font-style:italic}
.hero .sub{font-size:17px;opacity:.85;margin:0 0 16px}
.hero .meta{font-size:14px;opacity:.9;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.hero .meta .p{color:var(--oro)}
.fuente{display:inline-flex;gap:8px;align-items:center;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.3);
        border-radius:999px;padding:6px 12px;font-size:13px;margin-top:14px}
.fuente b{color:#fff}
.met{display:grid;grid-template-columns:1fr 1fr;margin-top:18px;border:1px solid rgba(255,255,255,.28);border-radius:18px;
     background:rgba(255,255,255,.1);overflow:hidden}
.met > div{padding:14px 16px;display:flex;gap:12px;align-items:flex-start}
.met > div:nth-child(odd){border-right:1px solid rgba(255,255,255,.2)}
.met > div:nth-child(-n+2){border-bottom:1px solid rgba(255,255,255,.2)}
.met .v{display:block}
.met .i{color:var(--oro);font-size:17px;line-height:1.2}
.met b{font-size:19px;display:block}
.met span{font-size:12px;opacity:.7}
.sec{margin:26px 0 10px}
.sec h2{font-family:"Instrument Serif",Georgia,serif;font-weight:400;font-size:34px;margin:4px 0 12px;letter-spacing:-.01em}
.pildora{display:inline-flex;gap:8px;align-items:center;border:1px solid #d5d9e2;border-radius:999px;padding:7px 14px;font-size:13.5px;
         color:#4a5260;margin:0 8px 10px 0;background:#fff}
.st-key-ruta iframe{border-radius:22px;border:1px solid #d9e0d4 !important}
.ajusta{background:var(--crema);border:1px solid var(--crema-borde);border-bottom:0;border-radius:20px 20px 0 0;padding:18px 20px 10px;margin-top:16px}
.ajusta .t{display:flex;gap:14px;align-items:center}
.ajusta .ic{width:42px;height:42px;border-radius:11px;background:#f8e3a6;display:flex;align-items:center;justify-content:center;font-size:18px}
.ajusta h3{font-family:"Instrument Serif",Georgia,serif;font-weight:400;font-size:24px;margin:0}
.st-key-ajustes{background:var(--crema);border:1px solid var(--crema-borde);border-top:0;border-radius:0 0 20px 20px;padding:4px 18px 16px;margin-top:-1rem}
.st-key-ajustes [data-testid="stHorizontalBlock"]{flex-wrap:wrap;gap:8px}
.st-key-ajustes [data-testid="stColumn"]{flex:0 0 auto !important;width:auto !important;min-width:0 !important}
.st-key-ajustes button{border-radius:999px !important;border:1px solid #d9d4c2 !important;background:#fff !important;color:#4a4f57 !important;
                       font-size:13.5px !important;padding:4px 14px !important;min-height:36px}
.st-key-ajustes button:hover{border-color:var(--verde) !important;color:var(--verde) !important}
.paso{display:grid;grid-template-columns:96px 22px 1fr;gap:0 12px}
.paso .hora{font-weight:600;font-size:14px;text-align:right;padding-top:2px}
.paso .hora small{display:block;color:var(--gris);font-weight:400;white-space:nowrap}
.paso .eje{display:flex;flex-direction:column;align-items:center}
.paso .punto{width:22px;height:22px;border-radius:50%;color:#fff;font-size:11.5px;font-weight:700;display:flex;align-items:center;justify-content:center}
.paso .linea{flex:1;width:2px;background:repeating-linear-gradient(#c8643e 0 4px,transparent 4px 8px);min-height:26px}
.paso .tarjeta{border:1px solid var(--linea);border-radius:16px;padding:12px 14px;margin-bottom:6px;background:#fff}
.paso .tarjeta b{font-size:15.5px}
.etq{display:inline-block;border-radius:6px;padding:1px 7px;font-size:11.5px;margin:6px 6px 0 0;background:#eef1f6;color:#4a5260}
.etq.ok{background:#e3f1e8;color:#1f5a43}.etq.av{background:#fbefd5;color:#7a5410}.etq.pet{background:#ece6fb;color:#4b3a8c}
.tramo{color:var(--gris);font-size:13px;padding:2px 0 10px}
.botones{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 4px}
.botones a{text-decoration:none !important;border-radius:14px;padding:12px 18px;font-weight:600;font-size:14.5px}
.botones a.v{background:var(--verde);color:#fff !important}
.botones a.b{border:1px solid #cfd5e4;color:var(--tinta) !important;background:#fff}
.veredicto{padding:.35rem .8rem;border-radius:8px;color:#fff;font-weight:700;display:inline-block;margin:.2rem 0 .5rem;font-size:.9rem}
/* animación de espera */
.espera{border-radius:26px;padding:34px 30px;background:linear-gradient(160deg,#eef1fb,#dfe6fa);min-height:420px}
.espera .av{width:64px;height:64px;border-radius:50%;background:radial-gradient(circle at 35% 30%,#7da0ff,#1f3a9a);position:relative;
            display:flex;align-items:center;justify-content:center;color:#fff;font:600 26px "Instrument Serif",Georgia,serif}
.espera .av::after{content:"";position:absolute;inset:-8px;border-radius:50%;border:2px solid #5d7fdc;animation:latido 1.6s ease-out infinite}
@keyframes latido{0%{transform:scale(.85);opacity:.9}100%{transform:scale(1.35);opacity:0}}
.espera h2{font-family:"Instrument Serif",Georgia,serif;font-weight:400;font-size:40px;margin:18px 0 6px}
.puntos span{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--verde);margin-right:5px;animation:salta 1.2s infinite}
.puntos span:nth-child(2){animation-delay:.15s}.puntos span:nth-child(3){animation-delay:.3s}
@keyframes salta{0%,80%,100%{transform:translateY(0);opacity:.4}40%{transform:translateY(-6px);opacity:1}}
.rotan{position:relative;height:24px;margin:14px 0 22px;font-size:16px}
.rotan span{position:absolute;left:0;opacity:0;animation:rota 12s infinite}
.rotan span:nth-child(2){animation-delay:3s}.rotan span:nth-child(3){animation-delay:6s}.rotan span:nth-child(4){animation-delay:9s}
@keyframes rota{0%{opacity:0;transform:translateY(6px)}4%,22%{opacity:1;transform:none}26%,100%{opacity:0}}
.barra{height:8px;border-radius:8px;background:#c9d3ef;overflow:hidden}
.barra div{height:100%;width:0;background:linear-gradient(90deg,#1f5a43,#3d8a69);border-radius:8px;animation-name:llena;animation-timing-function:linear;animation-fill-mode:forwards}
@keyframes llena{to{width:100%}}
</style>""", unsafe_allow_html=True)


# ------------------------------------------------------------------ datos
@st.cache_data(show_spinner=False)
def escenarios() -> dict:
    """Respuestas guardadas para la demo: solo consultas reales en las que Candelaria devolvió un plan (HTTP 200) con el mismo
    mensaje que hoy envía el dashboard en vivo. Las fallidas (504), las del mensaje anterior y las sintéticas siguen en el
    archivo para las pruebas automáticas, pero no se ofrecen aquí."""
    todas = json.loads(RESPUESTAS_REALES.read_text(encoding="utf-8"))
    utiles = {k: v for k, v in todas.items() if v.get("real") and v.get("prompt_compacto") and v.get("status") == 200
              and (v.get("respuesta") or "").strip()}
    return dict(sorted(utiles.items(), key=lambda kv: kv[1].get("orden", 99)))


def titulo_escenario(v: dict) -> str:
    resultado = {"chatbot": "plan de Candelaria", "selector_propio": "Candelaria no lograble → plan propio"}.get(v.get("decision"), "")
    return v["titulo"].removeprefix("REAL · ") + (f"  ·  {resultado}" if resultado else "")


@st.cache_data(show_spinner=False, ttl=3600)
def geometria(a: tuple, b: tuple, modo: str):
    """Trazado por calles (OSRM público de FOSSGIS) para pie/bici; None si no hay red o es transporte."""
    if modo not in OSRM:
        return None
    url = f"https://routing.openstreetmap.de/{OSRM[modo]}/route/v1/driving/{a[1]},{a[0]};{b[1]},{b[0]}?overview=full&geometries=geojson"
    try:
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        return [(y, x) for x, y in r.json()["routes"][0]["geometry"]["coordinates"]]
    except Exception:  # noqa: BLE001
        return None


CAT = catalogo()


def origen_de(lat: float, lon: float) -> str:
    """Nombre del origen con nombre más cercano (≈300 m) o 'lat, lon'."""
    for k, (a, b) in ORIGENES.items():
        if abs(a - lat) < 0.003 and abs(b - lon) < 0.003:
            return f"{k}, Bogotá"
    return f"{lat:.5f}, {lon:.5f}"


def cargar_escenario(clave: str):
    p = escenarios()[clave]["parametros"]
    st.session_state.estado_tel = {"version": time.time(), "minutos": p["minutos"], "origen": origen_de(p["lat"], p["lon"]),
                                   "cuando": p["cuando"], "con": p["con"], "prefs": list(p["prefs"]), "modo": p["modo"],
                                   "mascota": bool(p.get("mascota", False))}


def limpiar_origen(t: str) -> str:
    return re.sub(r",\s*bogot[aá](\s*d\.?\s*c\.?)?\s*$", "", (t or "").strip(), flags=re.I) or "Chapinero"


def hora_ampm(hhmm: str | None) -> str:
    if not hhmm:
        return "—"
    h, m = map(int, hhmm.split(":"))
    h %= 24
    return f"{(h % 12) or 12}:{m:02d} {'a. m.' if h < 12 else 'p. m.'}"


def dur(minutos: int | None) -> str:
    if minutos is None:
        return "—"
    return f"{minutos // 60} h {minutos % 60:02d} min" if minutos >= 60 else f"{minutos} min"


def horas_txt(minutos: int) -> str:
    h = minutos / 60
    return "1 hora" if h == 1 else (f"{int(h)} horas" if h == int(h) else f"{dur(minutos)}")


# ------------------------------------------------------------------ barra lateral
with st.sidebar:
    st.subheader("Fuente de la recomendación")
    fuente_txt = st.radio("Chatbot", list(FUENTES), index=0,
                          help="Respuestas guardadas: consultas reales a Candelaria (todas respondieron) para hacer la demo sin esperar. "
                               "En vivo: Candelaria tarda de 1 a 2 min y a veces su servidor corta a los ~120 s (504).")
    fuente = FUENTES[fuente_txt]
    escenario, url_nuevo, reproducir = None, "", False
    espera_s = ESPERA_CANDELARIA_S
    if fuente == "guardada":
        E = escenarios()
        escenario = st.selectbox(f"Respuesta guardada ({len(E)} reales)", list(E), format_func=lambda k: titulo_escenario(E[k]), key="escenario_sel",
                                 on_change=lambda: cargar_escenario(st.session_state.escenario_sel),
                                 help="Solo respuestas reales en las que Candelaria devolvió un plan. Al elegir uno, sus parámetros pasan al teléfono.")
        if "estado_tel" not in st.session_state:          # primera carga: el teléfono arranca con el escenario elegido
            cargar_escenario(escenario)
        it = E[escenario]
        st.caption(f"Consulta real a Candelaria del {it['fecha']}: respondió en {it['segundos']} s con el mismo mensaje que envía el modo en vivo.")
        st.button("Volver a cargar sus parámetros en el teléfono", on_click=cargar_escenario, args=(escenario,), use_container_width=True)
        reproducir = st.toggle("Reproducir el tiempo real de respuesta", value=False,
                               help="Simula la espera que tuvo Candelaria (hasta 2 min) para ver la animación de carga.")
    if fuente in ("candelaria", "nuevo"):
        if fuente == "nuevo":
            url_nuevo = st.text_input("URL base del asistente nuevo", placeholder="https://…azurecontainerapps.io",
                                      help="Mismo contrato que Candelaria: POST {url}/api/chat {message, user_id, session_id}. "
                                           "Token opcional en la variable de entorno NUEVO_CHATBOT_TOKEN.")
        espera_s = st.slider("Espera máxima por el chatbot (s)", 30, 180, int(ESPERA_CANDELARIA_S), step=10,
                             help="Candelaria tarda de 70 a 120 s con el mensaje del piloto y su servidor corta a los ~120 s (504). "
                                  "Pasado este tiempo se usa el selector propio.")
    st.divider()
    st.subheader("Opciones")
    rnt_en_linea = st.toggle("Buscar en el RNT en línea si una parada no está en la base", value=True)
    por_calles = st.toggle("Trazar la ruta por calles (OSRM, requiere internet)", value=True)
    st.divider()
    st.subheader("Base de verificación")
    n_hor = int(CAT["horario_interpretable"].fillna(False).astype(bool).sum()) if "horario_interpretable" in CAT else 0
    st.markdown(f"**{len(CAT)}** lugares · **{n_hor}** con horario oficial · **{int((CAT.para != '').sum())}** con etiquetas «para quién» · "
                f"**{int((CAT.pet_friendly == 'si').sum())}** Pet Friendly · RNT gastronomía como respaldo")
    if not CATALOGO_ENRIQUECIDO.exists() or n_hor == 0:
        st.warning("Base sin fuentes de Candelaria: corre `python3 codigo/descargar_fuentes.py` y `python3 codigo/construir_catalogo_enriquecido.py`.")

# ------------------------------------------------------------------ cabecera y columnas
st.markdown('<div class="app"><span class="sobre">Reto 2 · piloto</span>'
            '<h1 class="serif" style="font-size:40px;margin:2px 0 0">Bogotá Cerca de ti</h1>'
            '<p class="peq" style="margin:2px 0 6px">Izquierda: la app. Derecha: lo que recibe el usuario. '
            'Detrás: chatbot → verificación contra la base → selector propio si el plan no es lograble.</p></div>', unsafe_allow_html=True)
col_tel, col_res = st.columns([1, 1.6], gap="large")

# ¿Llegó un clic nuevo de «Armar mi plan»? (el valor del componente persiste entre ejecuciones; el nonce lo distingue)
previo = st.session_state.get("telefono")
nueva = bool(previo and previo.get("nonce") and previo.get("nonce") != st.session_state.get("ultimo_nonce"))

with col_tel:
    telefono(estado=st.session_state.get("estado_tel"), origenes=list(ORIGENES), ocupado=nueva, key="telefono", default=None)
    st.caption("Igual al mockup «Cuéntame lo esencial» (diap. 20). «Más opciones» (modo y mascota) no está en el mockup: "
               "el verificador lo necesita.")


# ------------------------------------------------------------------ ejecución
def animacion_espera(segundos: float, titulo: str, sub: str) -> str:
    mensajes = ["Buscando lugares cerca de ti…", "Revisando horarios de apertura…", "Calculando traslados…", "Comprobando que todo quepa…"]
    return (f'<div class="app espera"><div class="av">C</div><h2>{titulo}</h2><div class="puntos"><span></span><span></span><span></span></div>'
            f'<div class="rotan">{"".join(f"<span>{m}</span>" for m in mensajes)}</div>'
            f'<div class="barra"><div style="animation-duration:{max(segundos, 1):.0f}s"></div></div>'
            f'<p class="peq" style="margin-top:10px">{sub}</p></div>')


def registrar(R: dict):
    """Registro para el mapa de demanda del IDT: una fila por consulta, solo parámetros (sin datos personales)."""
    try:
        fila = a_tablas([{**R, "id": "d" + datetime.now().strftime("%Y%m%d-%H%M%S")}])[0]     # id único por consulta
        fila.to_csv(LOG, mode="a", header=not LOG.exists(), index=False, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


if nueva:
    v = st.session_state.telefono
    st.session_state.ultimo_nonce = v["nonce"]
    consulta = {"minutos": v["minutos"], "origen": limpiar_origen(v.get("origen")), "cuando": v.get("cuando") or "ahora",
                "con": v["con"], "prefs": v.get("prefs") or [], "modo": v.get("modo") or "transporte", "mascota": bool(v.get("mascota"))}
    with col_res, st.container(key="lienzo"):
        hueco = st.empty()
        if fuente == "guardada":
            seg = float(escenarios()[escenario].get("segundos") or 0) if reproducir else 0
            hueco.markdown(animacion_espera(seg or 2, "Candelaria está armando tu plan",
                                            f"Respuesta guardada del {escenarios()[escenario]['fecha']}"
                                            + (f" · tardó {seg:.0f} s" if seg else "")), unsafe_allow_html=True)
            time.sleep(min(seg, 180) if seg else 0.6)
        elif fuente == "ninguna":
            hueco.markdown(animacion_espera(3, "Armando tu plan", "Selector propio, sin chatbot."), unsafe_allow_html=True)
        else:
            quien = "Candelaria" if fuente == "candelaria" else "El asistente"
            hueco.markdown(animacion_espera(espera_s, f"{quien} está armando tu plan",
                                            f"Puede tardar hasta {espera_s:.0f} s. Si no responde a tiempo, armamos el plan con el selector propio "
                                            "y lo verificamos igual."), unsafe_allow_html=True)
        try:
            R = recomendar(consulta, fuente=fuente, escenario=escenario, url_nuevo=url_nuevo, espera_s=espera_s, rnt_en_linea=rnt_en_linea)
            R["consulta_enviada"], R["ajustes"], R["excluidos"] = consulta, [], []
            if fuente == "guardada":
                R["chatbot"]["mensaje"] = escenarios()[escenario]["mensaje"]      # lo que de verdad se le envió a Candelaria
                R["parametros_escenario"] = escenarios()[escenario]["parametros"]
            st.session_state.res, st.session_state.error = R, None
            registrar(R)
        except ValueError as e:
            st.session_state.error = str(e)
        hueco.empty()
    st.rerun()      # vuelve a pintar el teléfono sin el estado «armando…»


def ajustar(tipo: str):
    """«¿Lo ajustamos a tu gusto?»: rehace el plan con el selector propio sin volver a empezar."""
    R = st.session_state.res
    c = dict(R["consulta_enviada"])
    prefs = set(c.get("prefs") or [])
    for a in R["ajustes"] + [tipo]:
        if AJUSTES.get(a):
            prefs.add(AJUSTES[a])
    c["prefs"] = sorted(prefs)
    if tipo == "Cambiar una parada":
        plan = (R.get("ajuste") or R)["recomendacion"]["plan"] or {}
        nombres = [p["nombre"] for p in plan.get("paradas", [])][:1]
        R["excluidos"] = list(set(R["excluidos"]) | set(CAT[CAT.nombre.isin(nombres)].id))
    R["ajuste"] = recomendar(c, fuente="ninguna", rnt_en_linea=False, excluir=set(R["excluidos"]) or None)
    R["ajustes"].append(tipo)


# ------------------------------------------------------------------ resultado (como en la app)
def hero(R: dict, plan: dict | None):
    c, rec, ch = R["consulta"], (R.get("ajuste") or R)["recomendacion"], R["chatbot"]
    cuando = datetime.strptime(c["cuando"], "%Y-%m-%d %H:%M")
    es_ahora = R["consulta_enviada"].get("cuando", "ahora") == "ahora"
    momento = "AHORA" if es_ahora else f"{DIAS[cuando.weekday()][:3].upper()} {cuando.day} {MESES[cuando.month - 1].upper()} · {hora_ampm(c['cuando'][11:]).upper()}"
    meta = " <span class='p'>•</span> ".join([horas_txt(c["minutos"]), html.escape(c["origen"].split("·")[0].strip()), CON[c["con"]]]
                                             + (["con mascota 🐾"] if c["mascota"] else []) + [MODO[c["modo"]][0].lower()])
    if R.get("ajuste"):
        fuente = f"<b>Plan ajustado</b> · {' → '.join(R['ajustes'])} · selector propio"
    elif rec["origen"] == "chatbot":
        fuente = f"<b>Plan de Candelaria</b> · verificado: {plan['veredicto'].lower()}"
    elif rec["origen"] == "selector_propio":
        motivo = (f"el chatbot no respondió (HTTP {ch.get('status')})" if ch.get("consultado") and not ch.get("ok")
                  else "el plan del chatbot no es lograble" if ch.get("consultado") else "sin chatbot")
        fuente = f"<b>Plan del selector propio</b> · {motivo}"
    else:
        fuente = "<b>Sin plan</b>"
    if not plan:
        st.markdown(f'<div class="app hero"><div class="sobre">SIN PLAN · {momento}</div><h1>No encontramos un plan <em>que quepa.</em></h1>'
                    f'<p class="sub">{html.escape(rec["motivo"])}</p><div class="meta">{meta}</div><div class="fuente">{fuente}</div></div>',
                    unsafe_allow_html=True)
        return
    metricas = [("🕒", dur(plan["duracion_total_min"]), "duración total"), ("🗺️", str(len(plan["paradas"])), "paradas"),
                (MODO[c["modo"]][1], f"{plan['minutos_transporte']} min", "en traslados"), ("✦", f"{plan['margen_min']} min", "de margen")]
    st.markdown(
        f'<div class="app hero"><div class="sobre">PLAN LISTO · {momento}</div>'
        f'<h1>Tu {DIAS[cuando.weekday()]} en<br>Bogotá <em>ya tiene plan.</em></h1>'
        f'<p class="sub">Encontramos una forma diferente de aprovechar tus {horas_txt(c["minutos"])}.</p>'
        f'<div class="meta">{meta}</div><div class="fuente">{fuente}</div>'
        f'<div class="met">{"".join(f"<div><span class=i>{i}</span><div class=v><b>{v}</b><span>{t}</span></div></div>" for i, v, t in metricas)}</div>'
        f'</div>', unsafe_allow_html=True)


def mapa(plan: dict, c: dict):
    o = (c["lat"], c["lon"])
    m = folium.Map(location=o, zoom_start=14, tiles="OpenStreetMap", zoom_control=False, attribution_control=True)
    m.get_root().header.add_child(folium.Element(
        "<style>.leaflet-tile-pane{filter:saturate(.35) sepia(.18) hue-rotate(40deg) brightness(1.04)}</style>"))
    pts = [o] + [(p["lat"], p["lon"]) for p in plan["paradas"]] + [o]
    for k, (a, b) in enumerate(zip(pts[:-1], pts[1:])):
        g = geometria(a, b, c["modo"]) if por_calles else None
        folium.PolyLine(g or [a, b], color="#c8643e", weight=4, opacity=.9 if k < len(pts) - 2 else .45, dash_array="2 9",
                        line_cap="round").add_to(m)
    folium.CircleMarker(o, radius=7, color="#fff", weight=3, fill=True, fill_color="#c8643e", fill_opacity=1, tooltip="Tu punto de salida").add_to(m)
    for p in plan["paradas"]:
        color = "#1f5a43" if p["orden"] % 2 else "#c8643e"
        icono = (f'<div style="background:{color};color:#fff;width:30px;height:30px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);'
                 f'border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.3);display:flex;align-items:center;justify-content:center">'
                 f'<span style="transform:rotate(45deg);font:700 13px DM Sans,sans-serif">{p["orden"]}</span></div>')
        folium.Marker((p["lat"], p["lon"]), icon=folium.DivIcon(html=icono, icon_size=(30, 30), icon_anchor=(15, 30)),
                      tooltip=f'{p["orden"]}. {p["nombre"]} ({p["llegada"]}–{p["salida"]})').add_to(m)
    m.fit_bounds([[min(x[0] for x in pts), min(x[1] for x in pts)], [max(x[0] for x in pts), max(x[1] for x in pts)]], padding=(40, 40))
    with st.container(key="ruta"):
        st_folium(m, height=380, use_container_width=True, returned_objects=[], key="mapa_ruta")


def paso_a_paso(plan: dict, c: dict):
    tr = plan["traslados"]
    icono_modo = MODO[c["modo"]][1]
    filas = []
    for k, p in enumerate(plan["paradas"]):
        filas.append(f'<div class="tramo" style="margin-left:130px">{icono_modo} {tr[k]["minutos"]} min · {tr[k]["km"]:.1f} km</div>')
        ap = {"oficial": ("ok", "Horario oficial"), "abierto": ("ok", "Espacio abierto"), "supuesto": ("av", "Horario por confirmar")}.get(
            p["apertura"], ("av", "Sin dato de horario"))
        etiquetas = [f'<span class="etq {ap[0]}">{ap[1]}</span>', f'<span class="etq">{html.escape(p["categoria"])}</span>']
        if p["pet_friendly"]:
            etiquetas.append('<span class="etq pet">🐾 Pet Friendly</span>')
        if p["opcional"]:
            etiquetas.append('<span class="etq av">Opcional</span>')
        detalle = " · ".join(x for x in [f'{p["minutos_visita"]} min{" (estimado)" if p["minutos_estimados"] else ""}',
                                         html.escape(p["horario"][:90]) if p["horario"] else "", f'para: {html.escape(p["para"])}' if p["para"] else ""] if x)
        color = "#1f5a43" if p["orden"] % 2 else "#c8643e"
        ultimo = k == len(plan["paradas"]) - 1
        filas.append(
            f'<div class="paso"><div class="hora">{hora_ampm(p["llegada"])}<small>hasta {hora_ampm(p["salida"])}</small></div>'
            f'<div class="eje"><div class="punto" style="background:{color}">{p["orden"]}</div>{"" if ultimo else "<div class=linea></div>"}</div>'
            f'<div class="tarjeta"><b>{html.escape(p["nombre"])}</b><div class="peq">{detalle}</div>{"".join(etiquetas)}</div></div>')
    if len(tr) > len(plan["paradas"]):
        filas.append(f'<div class="tramo" style="margin-left:130px">{icono_modo} {tr[-1]["minutos"]} min · {tr[-1]["km"]:.1f} km · '
                     f'regreso a tu punto de salida · terminas a las <b>{hora_ampm(plan["termina_a"])}</b></div>')
    st.markdown(f'<div class="app">{"".join(filas)}</div>', unsafe_allow_html=True)
    e = plan.get("enlaces") or {}
    if e:
        st.markdown(f'<div class="app botones"><a class="v" href="{e["google_maps"]}" target="_blank">Abrir la ruta en Google Maps →</a>'
                    f'<a class="b" href="{e["whatsapp"]}" target="_blank">Compartir por WhatsApp</a></div>', unsafe_allow_html=True)


with col_res:
    R = st.session_state.get("res")
    if st.session_state.get("error"):
        st.error(st.session_state.error)
    lienzo = st.container(key="lienzo")
with lienzo:
    if not R:
        st.markdown('<div class="app espera"><div class="av">C</div><h2>Tu plan aparecerá aquí</h2>'
                    '<p style="font-size:16px;margin:10px 0 18px">Elige los parámetros en el teléfono y pulsa <b>Armar mi plan</b>.</p>'
                    '<p class="peq">Para la demo: elige un escenario guardado en la barra lateral; sus parámetros pasan solos al teléfono. '
                    'La fuente por defecto son respuestas guardadas de Candelaria; en vivo se espera hasta '
                    f'{ESPERA_CANDELARIA_S:.0f} s.</p></div>', unsafe_allow_html=True)
    else:
        vista = R.get("ajuste") or R
        plan, c = vista["recomendacion"]["plan"], R["consulta"]
        hero(R, plan)
        if plan:
            st.markdown('<div class="app sec"><div class="sobre">La ruta</div><h2>Todo queda en el camino</h2>'
                        f'<span class="pildora">🕒 Terminas a las {hora_ampm(plan["termina_a"])}</span>'
                        f'<span class="pildora">〰 {plan["km_total"]:.1f} km en total</span>'
                        f'<span class="pildora">{MODO[c["modo"]][1]} {MODO[c["modo"]][0]}</span></div>', unsafe_allow_html=True)
            mapa(plan, c)
            st.markdown('<div class="app ajusta"><div class="t"><div class="ic">✦</div><div><h3>¿Lo ajustamos a tu gusto?</h3>'
                        '<span class="peq">Sin volver a empezar.</span></div></div></div>', unsafe_allow_html=True)
            with st.container(key="ajustes"):
                cols = st.columns(len(AJUSTES))
                for col, t in zip(cols, AJUSTES):
                    col.button(t, on_click=ajustar, args=(t,), key=f"aj_{t}")
            if R.get("ajuste"):
                st.markdown('<div class="app peq" style="margin-top:6px">Ajustes aplicados: ' + " → ".join(R["ajustes"])
                            + " · el plan ajustado lo arma y verifica el selector propio.</div>", unsafe_allow_html=True)
            momento = int(plan["paradas"][0]["llegada"][:2]) if plan["paradas"] else 12
            st.markdown(f'<div class="app sec"><div class="sobre">Paso a paso</div>'
                        f'<h2>Tu {"mañana" if momento < 12 else "tarde" if momento < 19 else "noche"}, resuelta</h2></div>', unsafe_allow_html=True)
            paso_a_paso(plan, c)

# ------------------------------------------------------------------ detalles para el IDT
R = st.session_state.get("res")
if R:
    st.divider()
    st.markdown('<div class="app"><span class="sobre">Para el IDT</span><h2 class="serif" style="font-size:30px;margin:2px 0 8px">'
                'Cómo se llegó a esta recomendación</h2></div>', unsafe_allow_html=True)
    ch, rec, alt = R["chatbot"], R["recomendacion"], R.get("alternativa")
    st.markdown(f"**Decisión:** {rec['motivo']}")
    if R.get("parametros_escenario"):
        p = R["parametros_escenario"]
        distinto = [k for k in ("minutos", "con", "modo", "mascota") if p.get(k) != R["consulta"].get(k)] + \
                   (["prefs"] if sorted(p.get("prefs", [])) != sorted(R["consulta"]["prefs"]) else []) + \
                   (["origen"] if abs(p["lat"] - R["consulta"]["lat"]) > 0.003 or abs(p["lon"] - R["consulta"]["lon"]) > 0.003 else [])
        if distinto:
            st.warning(f"La respuesta guardada se obtuvo con otros parámetros ({', '.join(distinto)}). La verificación compara esa respuesta "
                       "con los parámetros del teléfono; usa «Volver a cargar sus parámetros en el teléfono» para compararlos en igualdad de condiciones.")
    tabs = st.tabs(["Verificación", "Chatbot", "Demanda (IDT)", "Salida del script (Power BI)"])

    def tabla_chequeos(plan: dict | None, titulo: str):
        st.markdown(f"**{titulo}**")
        if not plan:
            st.info("Sin plan.")
            return
        fondo, letra = COLOR_VEREDICTO[plan["veredicto"]]
        st.markdown(f'<div class="veredicto" style="background:{fondo};color:{letra}">{plan["veredicto"]} · '
                    f'{plan["n_fallas"]} falla(s), {plan["n_avisos"]} advertencia(s)</div>', unsafe_allow_html=True)
        df = pd.DataFrame(plan["chequeos"])
        if len(df):
            df["Estado"] = df.estado.map(ICONO)
            df["Parada"] = df.parada.apply(lambda x: "" if x is None or pd.isna(x) else str(int(x)))
            st.dataframe(df[["Estado", "titulo", "Parada", "detalle"]].rename(columns={"titulo": "Criterio", "detalle": "Detalle"}),
                         hide_index=True, use_container_width=True, height=min(480, 40 + 35 * len(df)))
        st.caption("Paradas: " + " → ".join(f'{p["nombre"]} ({p["llegada"]}–{p["salida"]}, {p["fuente_lugar"] or "sin match"})' for p in plan["paradas"]))

    with tabs[0]:
        a, b = st.columns(2)
        with a:
            if ch.get("consultado") and not ch.get("ok"):
                st.markdown("**Plan del chatbot**")
                st.markdown(f'<div class="veredicto" style="background:{DPA["gris"]};color:#fff">SIN RESPUESTA · HTTP {ch.get("status")}</div>', unsafe_allow_html=True)
                st.caption(ch.get("error") or "")
            elif ch.get("consultado"):
                tabla_chequeos(ch.get("plan"), "Plan del chatbot")
            else:
                st.info("No se consultó al chatbot.")
        with b:
            tabla_chequeos(alt, "Alternativa del selector propio")
        if R.get("ajuste"):
            tabla_chequeos(R["ajuste"]["recomendacion"]["plan"], "Plan ajustado (" + " → ".join(R["ajustes"]) + ")")
        st.caption("❌ falla = dato verificable que lo impide (horario oficial, lugar inexistente, tiempo, mascota). "
                   "⚠️ advertencia = depende de supuestos o falta un dato. Un horario supuesto nunca produce falla.")
    with tabs[1]:
        if not ch.get("consultado"):
            st.info("Fuente: solo selector propio.")
        else:
            st.markdown(f"**Fuente:** {ch['fuente']}{' · ' + ch['escenario'] if ch.get('escenario') else ''} · **HTTP:** {ch.get('status')} · "
                        f"**tiempo:** {ch.get('segundos')} s · **lectura:** {ch.get('lectura')}")
            if ch.get("error"):
                st.caption(ch["error"])
            st.markdown("**Consulta enviada al chatbot**")
            st.code(ch.get("mensaje") or "", language=None, wrap_lines=True)
            st.markdown("**Respuesta del chatbot**")
            st.code(ch.get("texto") or ch.get("error") or "", language=None, wrap_lines=True)
    with tabs[2]:
        if not LOG.exists():
            st.info("Aún no hay consultas registradas.")
        else:
            d = pd.read_csv(LOG)
            k = st.columns(4)
            k[0].metric("Consultas", len(d))
            k[1].metric("Chatbot sin respuesta", f"{(d.chatbot_veredicto == 'SIN RESPUESTA').mean():.0%}")
            k[2].metric("Chatbot lograble", f"{d.chatbot_veredicto.astype(str).str.startswith('LOGRABLE').mean():.0%}")
            k[3].metric("Recomendación lograble", f"{d.recomendacion_veredicto.fillna('').astype(str).str.startswith('LOGRABLE').mean():.0%}")
            md = folium.Map(location=[4.65, -74.08], zoom_start=11, tiles="OpenStreetMap")
            for (lat, lon, o), g in d.groupby(["lat", "lon", "origen"]):
                folium.CircleMarker((lat, lon), radius=6 + 3 * len(g), color=DPA["cian"], fill=True, fill_color=DPA["cian"], fill_opacity=.45,
                                    tooltip=f"{o}: {len(g)} consulta(s)").add_to(md)
            st_folium(md, height=320, use_container_width=True, returned_objects=[], key="mapa_demanda")
            c1, c2 = st.columns(2)
            c1.markdown("**¿Con quién?**")
            c1.bar_chart(d.con.value_counts(), color=DPA["cian"])
            c2.markdown("**¿Qué les provoca?**")
            c2.bar_chart(d.prefs.fillna("").astype(str).str.split("|").explode().replace("", pd.NA).dropna().value_counts(), color=DPA["naranja"])
            st.download_button("Descargar registro (CSV)", d.to_csv(index=False).encode("utf-8"), "consultas_dashboard.csv", "text/csv")
    with tabs[3]:
        st.markdown("Es lo que devuelve `codigo/recomendar.py` para esta consulta; Power BI usa las mismas tablas con `recomendar_lote()`.")
        consultas_t, paradas_t, chequeos_t = a_tablas([R])
        st.dataframe(consultas_t, hide_index=True, use_container_width=True)
        st.dataframe(paradas_t, hide_index=True, use_container_width=True)
        limpio = {k: v for k, v in R.items() if k not in ("ajustes", "excluidos", "ajuste", "parametros_escenario", "consulta_enviada")}
        st.download_button("Descargar JSON de la recomendación", json.dumps(limpio, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
                           "recomendacion.json", "application/json")
