# Reto 2 · Bogotá Cerca de ti — piloto

Dos piezas:

- **`codigo/recomendar.py`**: un solo script que recibe la consulta de la app y devuelve la recomendación verificada. Es el que se reutilizará en Power BI.
- **`app.py`**: dashboard Streamlit que lo presenta, en dos páginas.
  - **Inicio** (`paginas/inicio.py`): cómo usar el demo y cómo funciona el algoritmo (decisión, verificación, tiempos por modo y alternativa).
  - **Demo** (`paginas/demo.py`), a la izquierda: la pantalla la pantalla «Cuéntame lo esencial» idéntica al mockup de la diapositiva 20.
  - **Demo**, a la derecha: el resultado como lo vería el usuario: «ya tiene plan», la ruta, «¿Lo ajustamos a tu gusto?» y el paso a paso.
  - **Demo**, abajo: los detalles para el IDT.

Para quien arme el dashboard final en Power BI: `datos/LEEME.md` (diccionario de datos, modelo y medidas) y `Bogota_Cerca_de_ti_demo_y_Power_BI.docx` (el demo y la integración del script y lo que pasó con Candelaria, 5 páginas).

## Qué hace `recomendar()`

1. Pide el plan al chatbot. Puede ser Candelaria en vivo, una respuesta guardada, el asistente nuevo o ninguno.
2. Verifica el plan contra la base: ¿existe?, ¿está abierto a esa hora?, ¿cabe en el tiempo?, ¿sirve para quien va y para la mascota?
3. Arma una alternativa con el selector propio y también la verifica.
4. Elige: el plan del chatbot si no es «NO LOGRABLE»; si el chatbot no responde o su plan no es lograble, la alternativa.

```bash
cd bogota_cerca_de_ti/codigo
# una consulta → JSON
python3 recomendar.py --minutos 120 --origen Suba --cuando "2026-11-14 15:00" --con ninos --prefs naturaleza --modo transporte
# lote → consultas.csv, paradas.csv y chequeos.csv
python3 recomendar.py --lote ../datos/consultas_ejemplo.csv --fuente guardada --salida ../datos/powerbi
```

Desde Python: `recomendar({"minutos": 120, "origen": "Suba", "cuando": "ahora", "con": "ninos", "prefs": ["naturaleza"], "modo": "transporte", "mascota": False}, fuente="candelaria")`.

En Power BI (Obtener datos → Script de Python):

```python
import sys; sys.path.insert(0, r"C:/ruta/a/bogota_cerca_de_ti/codigo")
from recomendar import recomendar_lote
consultas, paradas, chequeos = recomendar_lote(r"C:/ruta/a/bogota_cerca_de_ti/datos/consultas_ejemplo.csv", fuente="guardada")
```

Para actualizar en el servicio de Power BI hace falta una puerta de enlace personal con Python. Con `fuente="candelaria"`, cada consulta puede tardar hasta 2 min.

### Tiempo de espera del chatbot: 120 s por defecto

Con el mensaje compacto del piloto, Candelaria tarda **66–119 s**. Su servidor (Cloudflare) corta a los **~120 s** con un 504, así que esperar más no sirve. Se ajusta con `espera_s` en `recomendar()`, `--espera` en la línea de comandos o el control de la barra lateral (30–180 s). Pasado ese tiempo se usa el selector propio.

## Cómo correr el dashboard

```bash
cd bogota_cerca_de_ti
pip install -r requirements.txt
streamlit run app.py
```

Para la demo:

1. Se abre la página **Inicio**; pasa a **Demo** en el menú de la izquierda.
2. En la barra lateral elige una de las 8 «Respuestas guardadas» (todas reales; sus parámetros pasan solos al teléfono).
3. Pulsa **Armar mi plan** en el teléfono.

Mientras el chatbot responde se ve la animación «Candelaria está armando tu plan», con una barra que avanza durante el tiempo de espera máximo. «Reproducir el tiempo real de respuesta» simula la espera que tuvo Candelaria con las respuestas guardadas.

- **Colores:** el tema usa la paleta de Data-Pop Alliance (`.streamlit/config.toml`, cian #1DADE4 y azul noche #162536) y funciona en modo claro y oscuro (menú ⋮ → Settings). El teléfono y el resultado conservan los colores del mockup de la app. Hay que ejecutar `streamlit run` desde esta carpeta para que tome el tema.
- **Funciona sin internet** con las respuestas guardadas.
- **Con internet** se suman las teselas y el trazado del mapa (OSRM para pie, bici y carro), las fuentes tipográficas del mockup y la búsqueda en línea en el RNT.

Pruebas: `cd codigo && python3 -m pytest -q pruebas` (32 pruebas) y `python3 planificador.py --autoprueba`.

## Publicar en Streamlit Community Cloud sin hacerlo público

La carpeta `bogota_cerca_de_ti` es la raíz del repositorio: Streamlit Cloud ejecuta todo desde la raíz y exige `.streamlit/config.toml` ahí. El `.gitignore` deja fuera secretos, cachés y los registros del demo.

1. **Repositorio privado.** En github.com → New repository → **Private**, sin README. Luego, en una terminal:

   ```bash
   cd ~/Documents/projects/Data-Pop-Alliance/bogota/bogota_cerca_de_ti
   git init -b main
   git add .
   git status            # revisa la lista antes de confirmar
   git commit -m "Bogotá Cerca de ti: piloto"
   git remote add origin https://github.com/USUARIO/bogota-cerca-de-ti.git
   git push -u origin main
   ```

   Con GitHub CLI basta `gh repo create bogota-cerca-de-ti --private --source=. --push` después del commit.
2. **App privada.** En share.streamlit.io entra con GitHub y autoriza el acceso a repositorios privados. Create app → el repositorio, rama `main`, archivo `app.py`; en Advanced settings elige Python 3.12. Una app que sale de un repositorio privado es **privada por defecto**: solo la ven los desarrolladores del workspace.
3. **Clave de acceso (opcional, segunda capa).** En Advanced settings → Secrets pega `clave_acceso = "..."` (ver `.streamlit/secrets.toml.ejemplo`). El dashboard la pide antes de mostrar nada. Sin ese secreto, por ejemplo en local, entra directo.
4. **Invitar al equipo.** Botón Share → escribe los correos. Con cuenta de Google entran con Google; si no, con un enlace de un solo uso que llega al correo.

Tener en cuenta:

- El plan gratuito permite **una sola app privada por workspace**.
- Si el repositorio queda en la organización de GitHub de DPA, un administrador de la organización debe autorizar a Streamlit.
- Lo que escribe el demo en `datos/consultas_dashboard.csv` se pierde cuando la app se reinicia en la nube.
- Candelaria en vivo puede bloquear las consultas desde la nube (Cloudflare). Si pasa, el IDT puede autorizar las IP de Streamlit Community Cloud, publicadas en su documentación; las respuestas guardadas funcionan igual.

## Archivos

| Ruta | Qué es |
|---|---|
| `codigo/recomendar.py` | **Consulta → recomendación** (el script para Power BI): `recomendar()`, `recomendar_lote()`, `a_tablas()` |
| `app.py` | Punto de entrada del dashboard: clave de acceso opcional y navegación entre Inicio y Demo |
| `.streamlit/config.toml` | Tema con la paleta de DPA (claro y oscuro) |
| `.streamlit/secrets.toml.ejemplo` | Plantilla de secretos (`clave_acceso`, `NUEVO_CHATBOT_TOKEN`); el real no se sube |
| `.gitignore` | Deja fuera secretos, cachés y registros del demo |
| `paginas/inicio.py` | Cómo usar el demo y cómo funciona el algoritmo; las cifras se leen del código |
| `paginas/demo.py` | Teléfono a la izquierda, resultado a la derecha y detalles para el IDT abajo |
| `codigo/telefono_componente.py` | Declara el componente del teléfono (Streamlit no permite declararlo dentro de una página) |
| `datos/LEEME.md` | **Guía de datos para Power BI**: tablas, columnas, llaves, modelo, medidas DAX e importación |
| `datos/powerbi/` | `consultas.csv`, `paradas.csv` y `chequeos.csv` generadas con las 8 consultas reales |
| `Bogota_Cerca_de_ti_demo_y_Power_BI.docx` | Documento de 5 páginas: el demo, la verificación, qué copiar a Power BI, cómo integrar el script y qué pasó con Candelaria |
| `componentes/app_telefono/index.html` | Pantalla «Cuéntame lo esencial» en HTML, conectada a Streamlit como componente |
| `datos/consultas_ejemplo.csv` | Las 8 consultas reales, para el modo lote / Power BI |
| `codigo/chatbot.py` | Cliente del chatbot (Candelaria, asistente nuevo o guardado) y lector de respuestas (JSON → enlaces "Cómo llegar" → nombres) |
| `codigo/verificador.py` | **Algoritmo de verificación** (ver abajo) |
| `codigo/horarios.py` | Interpreta horarios en español ("Lunes a jueves de 7:00 a.m. a 7:30 p.m. y …") |
| `codigo/planificador.py` | Selector propio: arma hasta 3 planes de 1–3 paradas que caben; con mascota solo usa lugares Pet Friendly |
| `codigo/descargar_fuentes.py` | Actualiza `datos/fuentes_arcgis/` desde ArcGIS del IDT (necesita internet) |
| `codigo/construir_catalogo_enriquecido.py` | Une inventario IDT + Visit Bogotá + Guía + Plazas + DTI → `datos/catalogo_enriquecido.csv` (650 lugares) |
| `codigo/pruebas/respuestas_candelaria.json` | **Respuestas guardadas.** El dashboard ofrece solo las 8 reales con HTTP 200 del mensaje compacto (`prompt_compacto`, con `orden` y `decision`). Las 504, las del mensaje anterior y las 2 sintéticas quedan para las pruebas |
| `datos/fuentes_arcgis/` | Fuentes de Candelaria descargadas y verificadas (ver su `LEEME.md`) |
| `datos/candelaria_fuentes_y_campos.md` | Qué respondió Candelaria sobre sus fuentes, horarios y pet friendly, y lo que se comprobó |
| `datos/consultas_dashboard.csv` | Se crea al usar el dashboard: registro para el mapa de demanda, con las mismas columnas de la tabla `consultas` de Power BI |
| `verificacion_candelaria.md` | Informe de las pruebas a Candelaria |
| `planes_ejemplo/` | Salidas del selector en 4 escenarios |

## Algoritmo de verificación

1. **Resolver cada parada.** Busca por nombre y cercanía (250 m; hasta 1 km si el nombre es idéntico), luego por coordenadas con nombre parecido (60 m) y luego por nombre. Si no aparece, la busca en el RNT de gastronomía: primero la copia local y, si está activado, en línea. Si tampoco está, es **posible lugar inventado** (falla).
2. **Re-simular el recorrido** en el orden del chatbot: traslados estimados por modo, minutos en sitio declarados (o típicos por categoría si faltan) y regreso.
3. **Chequeos:**
   - Cupo de tiempo con margen ≥ 5 min.
   - Apertura a la hora de llegada: horario oficial si existe; si no, un supuesto, que **nunca produce falla**.
   - Total declarado frente a la suma real.
   - Compañía según las etiquetas oficiales.
   - Mascota (solo "Pet Friendly" oficial).
   - Preferencias y número de paradas.
4. **Veredicto:**
   - **NO LOGRABLE** si algún dato verificable lo impide.
   - **CON ADVERTENCIAS** si depende de supuestos.
   - **LOGRABLE** si no hay ni lo uno ni lo otro.

## Límites que conviene decir en la demo

- **«Más opciones» del teléfono:** modo de transporte y mascota no están en el mockup. Van plegados bajo «Más opciones» porque el verificador los necesita.
- **«¿Lo ajustamos a tu gusto?»:** rehace el plan con el selector propio, no con el chatbot.

- **Traslados estimados:** línea recta × 1,3 a la velocidad del modo. Falta la API de rutas (Google o ArcGIS del IDT).
- **Horarios:** solo 120 de 650 lugares tienen horario oficial interpretable; el resto usa supuestos por categoría.
- **Candelaria en vivo:** con el mensaje largo, 4 de 5 consultas dieron 504; con el compacto respondió en 8 de 9 escenarios, pero en 16 intentos solo hubo 8 respuestas. Cuando Miguel tenga la URL del asistente nuevo, se prueba con el mismo contrato (`POST /api/chat {message, user_id, session_id}`).
- **Orígenes de ejemplo:** Suba y Teusaquillo son puntos aproximados, no direcciones reales.
- **Duplicados menores:** quedan algunos entre fuentes (p. ej. "Plaza de Lourdes" y "Plazoleta de Lourdes").
