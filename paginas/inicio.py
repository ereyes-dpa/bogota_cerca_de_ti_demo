"""Página «Inicio»: cómo usar el demo y cómo funciona el algoritmo, organizada por pestañas.

Las cifras (velocidades, minutos fijos, margen, tolerancias, duraciones típicas) se leen del código para que esta página
nunca se separe de lo que de verdad hace recomendar.py.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

AQUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI / "codigo"))
import planificador as pl  # noqa: E402
import verificador as vf  # noqa: E402
from chatbot import ESPERA_CANDELARIA_S, RESPUESTAS_REALES  # noqa: E402
from construir_catalogo import SUPUESTOS  # noqa: E402

# Paleta de Data-Pop Alliance (logo y sitio web)
DPA = {"cian": "#1DADE4", "azul": "#162536", "naranja": "#F37828", "verde": "#0D7D43", "amarillo": "#FCD146", "rojo": "#BF2531",
       "morado": "#51346C", "gris": "#6B7785"}


def num(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def tabla(df: pd.DataFrame) -> str:
    """Tabla en markdown (a diferencia de st.dataframe, el texto largo se ajusta en varias líneas)."""
    filas = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    filas += ["| " + " | ".join(str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(filas)


def diagrama(cuerpo: str, direccion: str = "TB", ancho: bool = False):
    """Diagrama con el estilo de la página (Graphviz, se dibuja en el navegador)."""
    st.graphviz_chart(f"""digraph {{
      rankdir={direccion}; bgcolor="transparent"; nodesep=0.45; ranksep=0.35; pad=0.1;
      node [shape=box, style="rounded,filled", fillcolor="#ffffff", color="#8fd3ef", fontcolor="#162536", fontname="Helvetica", fontsize=11, margin="0.18,0.08", penwidth=1.3];
      edge [color="#737F8D", fontcolor="#737F8D", fontname="Helvetica", fontsize=10, arrowsize=0.7];
      graph [fontcolor="#737F8D"];
      {cuerpo}
    }}""", use_container_width=ancho)


def html(s: str):
    st.markdown(s, unsafe_allow_html=True)


def sub(texto: str):
    html(f'<div class="ini"><h3 class="sub">{texto}</h3></div>')


# ------------------------------------------------------------------ estilo
html("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,600;9..40,700&family=Instrument+Serif&display=swap');
/* Paleta DPA. Los textos heredan el color del tema (claro u oscuro); los fondos son semitransparentes para servir en ambos. */
:root{--cian:#1DADE4;--azul:#162536;--naranja:#F37828;--verde:#0D7D43;--amarillo:#FCD146;--rojo:#BF2531;--morado:#51346C;--borde:rgba(128,128,128,.32)}
.block-container{max-width:1060px;padding-top:1.4rem}
.ini, .ini *{font-family:"DM Sans",system-ui,sans-serif}
.ini h1, .ini h3.sub{font-family:"Instrument Serif",Georgia,serif !important;font-weight:400 !important;letter-spacing:-.01em;padding:0 !important;color:inherit}
.ini h1{font-size:52px;line-height:1.02;margin:4px 0 10px}
.ini h3.sub{font-size:26px;margin:18px 0 6px}
.sobre{font-size:11.5px;letter-spacing:.14em;font-weight:600;text-transform:uppercase;border-left:3px solid var(--cian);padding-left:8px}
.lead{font-size:17.5px;opacity:.85;max-width:820px;margin-bottom:6px}
/* flujo en una mirada */
.flujo{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0 6px}
.flujo .c{position:relative;border:1px solid var(--borde);border-top:4px solid var(--cian);border-radius:14px;padding:12px 14px;background:rgba(29,173,228,.06)}
.flujo .c:nth-child(2){border-top-color:var(--naranja)}.flujo .c:nth-child(3){border-top-color:var(--amarillo)}
.flujo .c.fin{border-top-color:var(--verde);background:rgba(13,125,67,.10)}
.flujo .c:not(:last-child)::after{content:"→";position:absolute;right:-11px;top:42%;opacity:.55;font-size:18px;z-index:1}
.flujo .n{width:26px;height:26px;border-radius:50%;background:var(--azul);color:#fff;font-weight:700;font-size:13px;display:flex;align-items:center;justify-content:center;margin-bottom:8px;box-shadow:0 0 0 2px var(--cian)}
.flujo b{display:block;font-size:15px;margin-bottom:4px}
.flujo span{font-size:13px;opacity:.8;line-height:1.35}
/* esquema de la pantalla Demo */
.esquema{display:grid;grid-template-columns:1.1fr 1.3fr 2.2fr;grid-template-rows:auto auto;gap:8px;margin:8px 0 14px;font-size:13px}
.esquema div{border:1.5px dashed var(--borde);border-radius:12px;padding:12px;background:rgba(128,128,128,.06);position:relative}
.esquema b{display:block;font-size:14px;margin-bottom:3px}
.esquema .lat{grid-row:1 / span 2;background:rgba(128,128,128,.12)}
.esquema .idt{grid-column:2 / span 2}
.esquema i, .pasos i{width:22px;height:22px;border-radius:50%;background:var(--naranja);color:var(--azul);font-style:normal;font-weight:700;font-size:12px;display:flex;align-items:center;justify-content:center}
.esquema i{position:absolute;top:-10px;left:-8px}
.pasos{margin:4px 0 10px}
.pasos div{display:flex;gap:10px;margin:7px 0;font-size:15px}
.pasos i{flex:none;margin-top:1px}
/* veredictos */
.ver{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:8px 0}
.ver div{border-radius:12px;padding:12px 14px;font-size:13.5px;border:1px solid var(--borde);border-left-width:6px}
.ver b{display:block;font-size:14px;margin-bottom:4px}
.ver .ok{border-left-color:var(--verde);background:rgba(13,125,67,.10)}
.ver .av{border-left-color:var(--amarillo);background:rgba(252,209,70,.14)}
.ver .no{border-left-color:var(--rojo);background:rgba(191,37,49,.10)}
.nota{background:rgba(252,209,70,.13);border:1px solid rgba(252,209,70,.55);border-radius:12px;padding:12px 16px;margin:10px 0;font-size:14.5px}
.formula{background:rgba(29,173,228,.09);border-left:4px solid var(--cian);border-radius:10px;padding:12px 16px;font-size:15px;margin:6px 0 10px}
</style>""")

# ------------------------------------------------------------------ portada
html('<div class="ini"><div class="sobre">Reto 2 · piloto para el IDT</div><h1>Bogotá Cerca de ti</h1>'
     '<p class="lead">El demo emula la app: recibe lo que pide el usuario, le pregunta a Candelaria por un plan, '
     'revisa que ese plan se pueda hacer con los datos oficiales del IDT y, si no, entrega uno propio.</p></div>')
st.page_link("paginas/demo.py", label="Abrir el demo", icon="📱")

html("""<div class="ini flujo">
 <div class="c"><div class="n">1</div><b>Consulta</b><span>Tiempo, punto de salida, cuándo, con quién, qué le provoca, modo y mascota.</span></div>
 <div class="c"><div class="n">2</div><b>Candelaria propone</b><span>El chatbot del IDT arma un plan de 1 a 3 paradas. Se le espera hasta 2 min.</span></div>
 <div class="c"><div class="n">3</div><b>Verificación</b><span>Se busca cada parada en 650 lugares del IDT y se recalcula el recorrido.</span></div>
 <div class="c fin"><div class="n">4</div><b>Plan entregado</b><span>El de Candelaria si se puede hacer; si no, el del selector propio.</span></div>
</div>""")

t_uso, t_dec, t_ver, t_tiempo, t_alt, t_int, t_datos, t_lim = st.tabs(
    ["Cómo usar el demo", "Cómo se decide", "Verificación", "Tiempos de traslado", "Plan alternativo", "Integración con la app",
     "Datos y Power BI", "Candelaria y límites"])

# ------------------------------------------------------------------ 1. uso
with t_uso:
    sub("La pantalla del demo")
    html("""<div class="ini esquema">
      <div class="lat"><i>1</i><b>Barra lateral</b>Fuente del plan (respuestas guardadas, Candelaria en vivo, asistente nuevo o solo selector propio) y la respuesta guardada que quieres ver.</div>
      <div><i>2</i><b>Teléfono</b>«Cuéntame lo esencial», igual al mockup. Modo y mascota están en «Más opciones».</div>
      <div><i>3</i><b>Resultado</b>Lo que ve el usuario: de dónde viene el plan, métricas, ruta en el mapa, «¿Lo ajustamos?» y el paso a paso.</div>
      <div class="idt"><i>4</i><b>Para el IDT</b>Más abajo: verificación chequeo por chequeo, mensaje y respuesta de Candelaria, mapa de demanda y las tablas que recibe Power BI.</div>
    </div>""")
    sub("Paso a paso")
    html("""<div class="ini pasos">
      <div><i>1</i><span>Abre <b>Demo</b> en el menú de la izquierda y elige una <b>respuesta guardada</b> en la barra lateral. Sus parámetros pasan solos al teléfono.</span></div>
      <div><i>2</i><span>Si quieres, cambia algo en el <b>teléfono</b>. Con respuestas guardadas, la respuesta de Candelaria sigue siendo la del escenario.</span></div>
      <div><i>3</i><span>Pulsa <b>Armar mi plan</b> y lee el <b>resultado</b>: la etiqueta azul dice si el plan es de Candelaria o propio, y por qué.</span></div>
      <div><i>4</i><span>Baja a <b>Para el IDT</b> para ver qué revisó el verificador y qué respondió Candelaria.</span></div>
    </div>""")
    sub("Qué fuente usar")
    st.markdown(tabla(pd.DataFrame([
        ("Respuestas guardadas (por defecto)", "Presentaciones y pruebas", "Ninguna", "8 consultas reales a Candelaria, todas con respuesta"),
        ("Candelaria en vivo", "Probar una consulta nueva", f"1 a 2 min (máx. {ESPERA_CANDELARIA_S:.0f} s)", "Cerca de la mitad de los intentos terminan en error 504"),
        ("Asistente nuevo (URL)", "Cuando el IDT entregue su chatbot", "Depende del asistente", "Mismo contrato que Candelaria"),
        ("Solo selector propio", "Ver el plan sin chatbot", "Ninguna", "No consulta ningún chatbot"),
    ], columns=["Fuente", "Para qué", "Espera", "Nota"])))
    html('<div class="ini nota">Para ver el algoritmo en acción, elige una respuesta guardada <b>con mascota</b>: Candelaria propone lugares '
         'sin la etiqueta Pet Friendly, el verificador rechaza su plan y el demo entrega el plan propio.</div>')

# ------------------------------------------------------------------ 2. decisión
with t_dec:
    st.markdown("Se entrega **el plan de Candelaria** si responde a tiempo y el verificador no lo declara **NO LOGRABLE**. "
                "En cualquier otro caso se entrega **el plan del selector propio**, que también pasa por el verificador.")
    diagrama("""
      c [label="Consulta de la app"];
      p [label="Pedir el plan a Candelaria\\n(espera máx. 120 s)"];
      s [label="Selector propio\\narma y verifica una alternativa"];
      r [label="¿Respondió a tiempo?", shape=diamond, fillcolor="#FFF4CC", color="#FCD146"];
      v [label="Verificar su plan\\ncontra la base del IDT"];
      n [label="¿NO LOGRABLE?", shape=diamond, fillcolor="#FFF4CC", color="#FCD146"];
      okc [label="Se entrega el plan de Candelaria\\n(con sus advertencias)", fillcolor="#E1F2E8", color="#0D7D43"];
      oks [label="Se entrega el plan del selector propio", fillcolor="#E1F2E8", color="#0D7D43"];
      {rank=same; p; s;}
      c -> p; c -> s; p -> r; r -> v [label="sí"]; r -> oks [label="no: 504 o tiempo agotado"];
      v -> n; n -> okc [label="no"]; n -> oks [label="sí"]; s -> oks [style=dashed, label="siempre se calcula"];
    """)
    sub("Los tres veredictos")
    html("""<div class="ini ver">
      <div class="ok"><b>LOGRABLE</b>Ningún problema.</div>
      <div class="av"><b>LOGRABLE CON ADVERTENCIAS</b>Algo depende de un supuesto o de un dato que falta, como un horario que la base no tiene. Se entrega igual.</div>
      <div class="no"><b>NO LOGRABLE</b>Al menos una falla: un dato verificable impide el plan. Se entrega el plan propio.</div>
    </div>""")
    html('<div class="ini nota"><b>«Lograble» no es «óptima».</b> El verificador comprueba que el plan <i>se pueda hacer</i>; no busca si existe uno mejor. '
         'Se prefiere a Candelaria porque es la recomendación oficial del IDT, y solo se reemplaza cuando un dato demuestra que su plan no funciona.</div>')

# ------------------------------------------------------------------ 3. verificación
with t_ver:
    st.markdown("El verificador (`codigo/verificador.py`) no confía en lo que dice el chatbot: busca cada parada en la base y vuelve a calcular el recorrido.")
    diagrama("""
      a [label="Respuesta de Candelaria"];
      b [label="1. Leer las paradas\\nJSON pedido → enlaces «Cómo llegar» → nombres"];
      c [label="2. Encontrar cada parada"];
      c1 [label="Catálogo IDT (650 lugares)\\nnombre + cercanía 250 m · coordenadas 60 m", fillcolor="#EAF6FC"];
      c2 [label="RNT de gastronomía\\n(402 restaurantes)", fillcolor="#EAF6FC"];
      c3 [label="No aparece\\n→ falla: posible lugar inventado", fillcolor="#F8E1E3", color="#BF2531"];
      d [label="3. Re-simular el recorrido\\ntraslados por modo + minutos en sitio + regreso"];
      e [label="4. Aplicar los chequeos\\ntiempo · apertura · mascota · compañía · gustos · totales"];
      f [label="Veredicto", fillcolor="#E1F2E8", color="#0D7D43"];
      a -> b -> c; c -> c1; c -> c2 [label="si no está"]; c -> c3 [label="si tampoco"];
      c1 -> d; c2 -> d; d -> e -> f;
    """)
    sub("Los chequeos")
    st.markdown(tabla(pd.DataFrame([
        ("Está en la base", "No está ni en el catálogo ni en el RNT", "Solo coincide por nombre"),
        ("Cabe en tu tiempo", f"Se pasa más de {vf.TOLERANCIA_EXCESO_MIN} min, aun con los minutos declarados o 15 min por parada",
         f"Margen menor a {pl.MARGEN_MIN} min o exceso de hasta {vf.TOLERANCIA_EXCESO_MIN} min (la estimación es aproximada)"),
        ("Abierto cuando llegas", "El horario oficial dice que está cerrado", "Horario supuesto por categoría o sin dato"),
        ("Admite mascotas", "Va con mascota y el lugar no tiene la etiqueta Pet Friendly", "—"),
        ("Apto para quien va", "—", "Sus etiquetas «para quién» no incluyen esa compañía"),
        ("Preferencias", "—", "Ninguna parada cumple lo que le provoca"),
        ("Su total coincide", "—", "El total declarado difiere más de 10 min de la suma real"),
        ("Traslado creíble", "—", "Un traslado declarado difiere mucho del estimado"),
    ], columns=["Chequeo", "Es falla cuando…", "Es advertencia cuando…"])))
    st.caption("Un horario supuesto nunca produce falla: el plan no se descarta por un dato que la base no tiene. "
               "Solo 120 de los 650 lugares tienen horario oficial interpretable.")

# ------------------------------------------------------------------ 4. tiempos
with t_tiempo:
    st.markdown("Cada tramo se calcula con la misma fórmula al verificar a Candelaria y al armar el plan propio (`tiempo_traslado()` en `codigo/planificador.py`).")
    html(f'<div class="ini formula"><b>Distancia por calle</b> = distancia en línea recta × {num(pl.FACTOR_RODEO)}<br>'
         f'<b>Minutos</b> = distancia por calle ÷ velocidad × 60 + minutos fijos del modo<br>'
         f'<span style="opacity:.72">Si el tramo es corto, se camina aunque el modo sea transporte o carro.</span></div>')
    st.markdown(tabla(pd.DataFrame([
        ("🚶 A pie", f"{num(pl.V_PIE)} km/h ({num(pl.V_PIE_NINOS)} con niños)", "—", "Paso urbano típico"),
        ("🚲 Bici", f"{num(pl.V_BICI)} km/h", "—", "Ciclorruta urbana, con cruces"),
        ("🚌 Transporte público", f"{num(pl.V_TRANSPORTE)} km/h",
         f"{pl.ESPERA_TRANSPORTE_MIN + pl.SALIDA_TRANSPORTE_MIN} (espera, acceso y salida); a pie si < {num(pl.TRANSPORTE_MIN_KM)} km",
         "Mezcla de troncal TransMilenio (25,2 km/h en 2024) y SITP zonal"),
        ("🚗 Carro o taxi", f"{num(pl.V_AUTO)} km/h", f"{pl.ESTACIONAR_AUTO_MIN} (parquear o esperar el taxi); a pie si < {num(pl.AUTO_MIN_KM)} km",
         "Promedio diario en Bogotá (Secretaría de Movilidad, 2023)"),
    ], columns=["Modo", "Velocidad", "Minutos fijos por tramo", "De dónde sale"])))
    sub("Pruébalo")
    c1, c2 = st.columns([1, 2])
    with c1:
        km_recta = st.slider("Distancia en línea recta (km)", 0.2, 10.0, 2.5, 0.1)
        ninos = st.toggle("Con niños", value=False)
    a = (4.6495, -74.0624)
    b = (a[0] + km_recta / 111.2, a[1])          # 1° de latitud ≈ 111,2 km
    filas = []
    for etiqueta, modo in (("A pie", "pie"), ("Bici", "bici"), ("Transporte público", "transporte"), ("Carro o taxi", "auto")):
        m, km = pl.tiempo_traslado(a, b, modo, ninos)
        filas.append({"Modo": etiqueta, "Minutos": round(m)})
    with c2:
        st.bar_chart(pd.DataFrame(filas), x="Modo", y="Minutos", horizontal=True, height=200, color=DPA["cian"])
        st.caption(" · ".join(f"{f['Modo']}: {f['Minutos']} min" for f in filas) + f" · {num(round(km, 1))} km por calle")
    sub("Minutos en cada sitio y margen")
    st.markdown("Se usan los minutos que declara Candelaria. Si no los da, o en el plan propio, se usa la duración típica de la categoría: "
                + ", ".join(f"{k.lower()} {v[0]}" for k, v in SUPUESTOS.items() if v[0]) + " (minutos). "
                f"El plan **cabe** si deja al menos **{pl.MARGEN_MIN} min** de margen. El trazado por calles del mapa es solo visual; "
                "para tiempos reales basta con reemplazar `tiempo_traslado()` por una API de rutas (la de ArcGIS del IDT o la de Google).")

# ------------------------------------------------------------------ 5. alternativa
with t_alt:
    st.markdown("El **selector propio** (`planear()` en `codigo/planificador.py`) corre en cada consulta, responda o no Candelaria. Va descartando lugares hasta quedarse con una ruta:")
    diagrama("""
      node [width=4.2];
      a [label="650 lugares de la base"];
      b [label="Alcance: se puede ir y volver en el tiempo\\nradio = (minutos − 15) × velocidad ÷ 1,3 ÷ 2"];
      c [label="Con mascota: solo los Pet Friendly"];
      d [label="Puntaje de cada lugar\\n(preferencias, compañía, niños, «los de siempre»)"];
      e [label="40 candidatos\\nmejor puntaje − 0,5 por km desde el origen"];
      f [label="Todas las rutas de 1 a 3 paradas, en todo orden,\\nabiertas a la llegada y con ≥ 5 min de margen"];
      g [label="La ruta de mayor valor", fillcolor="#E1F2E8", color="#0D7D43"];
      h [label="Pasa por el mismo verificador", fillcolor="#EAF6FC"];
      a -> b -> c -> d -> e -> f -> g -> h;
    """)
    c1, c2 = st.columns(2)
    with c1:
        sub("Puntaje de un lugar")
        st.markdown(tabla(pd.DataFrame([
            ("Base", "1"), ("Cumple una preferencia (cada una)", "+2"), ("Su etiqueta oficial incluye esa compañía", "+1 (−0,5 si no)"),
            ("Lugar para niños, si va con niños", "+1,5 (+0,5 si solo los admite)"), ("Pet Friendly, si va con mascota", "+3"),
            ("«De los de siempre» (Monserrate, Simón Bolívar, Zona T)", "−0,8 (−2 si pidió algo inesperado)"),
            ("Horario no verificado", "−0,3"), ("Parada de paso (menos de 15 min)", "× 0,5"),
        ], columns=["Regla", "Puntos"])))
    with c2:
        sub("Valor de una ruta")
        st.markdown("""
- suma de los puntajes de sus paradas
- **+ 0,5** por cada categoría distinta
- **+ hasta 1,5** por tiempo de visita
- **+ hasta 2** por aprovechar el tiempo disponible
- **− 0,06** por cada minuto de traslado

Se descartan las rutas que usan menos del 40 % del tiempo, si hay otras.
""")
    html('<div class="ini nota"><b>¿Lo ajustamos a tu gusto?</b> vuelve a correr el selector con la preferencia añadida '
         '(caminar menos, algo de comer, más económico) o sin la primera parada (cambiar una parada).</div>')

# ------------------------------------------------------------------ 6. datos
with t_datos:
    st.markdown("Toda la lógica está en `codigo/recomendar.py`. El mismo script alimenta este demo y el dashboard de Power BI:")
    diagrama("""
      e [label="consultas_ejemplo.csv\\n(una consulta por fila)", fillcolor="#FFF4CC", color="#FCD146"];
      r [label="recomendar_lote()\\ncodigo/recomendar.py", fillcolor="#162536", fontcolor="#ffffff", color="#162536"];
      k [label="catalogo_enriquecido.csv\\n+ fuentes_arcgis/", fillcolor="#EAF6FC"];
      q [label="consultas.csv\\n1 fila por consulta"];
      p [label="paradas.csv\\n1 fila por parada"];
      c [label="chequeos.csv\\n1 fila por chequeo"];
      b [label="Power BI", fillcolor="#E1F2E8", color="#0D7D43"];
      e -> r; k -> r [style=dashed, label="base"]; r -> q; r -> p; r -> c; q -> b; p -> b; c -> b; k -> b [style=dashed, label="ficha del lugar"];
    """, direccion="LR")
    st.markdown("""
- Las tres tablas ya están generadas en `datos/powerbi/` con las 8 consultas reales. En producción, la API escribe las mismas tablas en `datos/registro/` con cada consulta de la app (pestaña «Integración con la app»). Se unen por `consulta_id`; `paradas[id_lugar]` se une con `catalogo_enriquecido[id]`.
- `paradas` trae tres planes por consulta (`recomendado`, `chatbot`, `alternativa`): para el plan que ve el usuario, filtra `recomendado`.
- Diccionario de columnas, modelo, medidas DAX y cuidados al importar: **`datos/LEEME.md`**. Integración paso a paso: **`Bogota_Cerca_de_ti_demo_y_Power_BI.docx`**.
""")
    st.code("python3 codigo/recomendar.py --lote datos/consultas_ejemplo.csv --fuente guardada --salida datos/powerbi", language="bash")

# ------------------------------------------------------------------ 6. integración con la app
with t_int:
    st.markdown("Cuando la app manda una consulta, el backend llama al script y le devuelve el plan verificado. "
                "Todo pasa por una sola función, `recomendar()`; `codigo/servicio_api.py` la expone como API lista para usar.")
    diagrama("""
      app [label="App «Bogotá Cerca de ti»\\nCuéntame lo esencial", fillcolor="#FFF4CC", color="#FCD146"];
      api [label="Backend\\nPOST /recomendar\\n(codigo/servicio_api.py)", fillcolor="#162536", fontcolor="#ffffff", color="#162536"];
      rec [label="recomendar(consulta)\\ncodigo/recomendar.py"];
      bot [label="Chatbot\\nasistente nuevo del IDT\\no Candelaria", fillcolor="#EAF6FC"];
      ver [label="Verificación\\n+ plan propio si hace falta", fillcolor="#EAF6FC"];
      reg [label="Registro\\nconsultas · paradas · chequeos", fillcolor="#EAF6FC"];
      pbi [label="Power BI", fillcolor="#E1F2E8", color="#0D7D43"];
      {rank=same; app; api; rec;}
      {rank=same; reg; ver; bot;}
      app -> api [label="1. consulta (JSON)"]; api -> rec [label="2. llama"]; rec -> bot [label="pide el plan"];
      bot -> ver; ver -> api [label="3. plan verificado"]; api -> app [label="4. respuesta (JSON)", style=bold];
      api -> reg [style=dashed, label="registra"]; reg -> pbi [style=dashed];
    """)
    sub("Qué hace el backend al recibir una consulta")
    html("""<div class="ini pasos">
      <div><i>1</i><span><b>Recibe</b> el JSON de la app con los datos de «Cuéntame lo esencial»: tiempo, origen, cuándo, con quién, gustos, modo y mascota.</span></div>
      <div><i>2</i><span><b>Llama</b> a <code>recomendar(consulta)</code>. El script le pide el plan al chatbot (hasta 120 s), lo verifica contra la base del IDT y, si no es lograble, arma uno propio.</span></div>
      <div><i>3</i><span><b>Responde</b> a la app con <code>recomendacion</code>: de dónde salió el plan, el motivo y el plan con paradas, horas, métricas y enlaces.</span></div>
      <div><i>4</i><span><b>Registra</b> la consulta en los tres CSV que lee Power BI (mismas columnas que <code>datos/powerbi/</code>).</span></div>
    </div>""")
    c1, c2 = st.columns(2)
    with c1:
        sub("Petición de la app")
        st.code("""POST /recomendar
{
  "id": "app-001",
  "minutos": 120,
  "origen": "4.73, -74.09",
  "cuando": "2026-11-14 15:00",
  "con": "ninos",
  "prefs": ["naturaleza"],
  "modo": "transporte",
  "mascota": false
}""", language="json", wrap_lines=True)
    with c2:
        sub("Respuesta del backend")
        st.code("""{
  "id": "app-001",
  "recomendacion": {
    "origen": "chatbot",
    "motivo": "Plan del chatbot verificado…",
    "plan": {
      "veredicto": "LOGRABLE CON ADVERTENCIAS",
      "paradas": [
        {"orden": 1, "nombre": "Humedal",
         "lat": 4.7238, "lon": -74.1022,
         "llegada": "15:16", "salida": "16:36"}
      ],
      "duracion_total_min": 114,
      "margen_min": 6,
      "termina_a": "16:53",
      "enlaces": {"google_maps": "…", "whatsapp": "…"}
    }
  },
  "chatbot": {"respondio": true, "segundos": 117}
}""", language="json", wrap_lines=True)
    st.caption("`origen` es `chatbot` (plan de Candelaria o del asistente nuevo) o `selector_propio`. Si `plan` llega vacío, ningún plan cabe con esos parámetros: la app muestra `motivo`. Con `?detalle=true` la respuesta "
               "incluye además la verificación chequeo por chequeo y el plan alternativo.")
    sub("Cómo ponerlo a correr")
    st.code("""pip install -r requirements-api.txt
export URL_CHATBOT_NUEVO="https://…"        # asistente nuevo del IDT; sin esto usa Candelaria
uvicorn servicio_api:app --app-dir codigo --host 0.0.0.0 --port 8000
# documentación interactiva para probar: http://localhost:8000/docs""", language="bash")
    st.markdown(tabla(pd.DataFrame([
        ("`FUENTE_CHATBOT`", "`nuevo`, `candelaria`, `guardada` (pruebas) o `ninguna`", "`nuevo` si hay URL; si no, `candelaria`"),
        ("`URL_CHATBOT_NUEVO`", "URL base del asistente nuevo (contrato `POST {url}/api/chat`)", "—"),
        ("`NUEVO_CHATBOT_TOKEN`", "Token del asistente nuevo, si lo pide", "—"),
        ("`ESPERA_CHATBOT_S`", "Segundos máximos esperando al chatbot", f"{ESPERA_CANDELARIA_S:.0f}"),
        ("`CARPETA_REGISTRO`", "Dónde quedan los CSV para Power BI", "`datos/registro`"),
    ], columns=["Variable", "Qué es", "Por defecto"])))
    sub("Sin API: desde cualquier código en Python")
    st.code("""import sys; sys.path.insert(0, r"C:\\ruta\\a\\bogota_cerca_de_ti\\codigo")
from recomendar import recomendar

r = recomendar({"minutos": 120, "origen": "4.73, -74.09", "cuando": "ahora", "con": "ninos",
                "prefs": ["naturaleza"], "modo": "transporte", "mascota": False},
               fuente="nuevo", url_nuevo="https://…")   # o fuente="candelaria"
plan = r["recomendacion"]["plan"]                        # lo que se devuelve a la app""", language="python")

# ------------------------------------------------------------------ 8. Candelaria y límites
with t_lim:
    sub("Qué pasó al consultar a Candelaria")
    try:
        guardadas = [v for v in json.loads(RESPUESTAS_REALES.read_text(encoding="utf-8")).values() if v.get("prompt_compacto") and v.get("status") == 200]
        rango = f"{min(v['segundos'] for v in guardadas)} a {max(v['segundos'] for v in guardadas)} s"
    except Exception:  # noqa: BLE001
        rango = "66 a 119 s"
    st.markdown(tabla(pd.DataFrame([
        ("Tarda y se corta", f"Responde en {rango}. Su servidor (Cloudflare) corta a los ~120 s con un error 504.",
         f"Espera de {ESPERA_CANDELARIA_S:.0f} s, un reintento y el plan propio como respaldo"),
        ("El mensaje largo no respondía", "Con reglas detalladas solo respondió 1 de 5 consultas; las demás dieron 504.",
         "Mensaje compacto: 8 de 9 escenarios con respuesta"),
        ("Falla la mitad de los intentos", "16 intentos, 8 respuestas. Las consultas simultáneas fallan más.", "Consultas de una en una; 8 respuestas reales guardadas"),
        ("Bloqueo a scripts", "Desde Python a veces responde 403 (Cloudflare bloquea clientes que no son navegador).",
         "Identificación honesta del cliente; pedir al IDT acceso programático"),
        ("Datos incompletos", "Horario «No disponible», traslados de 0 min, lugares sin Pet Friendly para quien va con mascota.",
         "El verificador los detecta"),
    ], columns=["Problema", "Qué se vio", "Cómo se manejó"])))
    sub("Límites del piloto")
    st.markdown("""
- **Traslados estimados**, no calculados por calles: el transporte público no considera rutas ni transbordos, y el carro no considera la hora pico.
- **Horarios:** solo 120 de 650 lugares tienen horario oficial; el resto usa un supuesto por categoría y queda como advertencia.
- **Orígenes de ejemplo:** Suba y Teusaquillo son puntos aproximados, no direcciones reales.
- **Para producción:** acceso programático a Candelaria (o el asistente nuevo del IDT) y una API de rutas.
""")
