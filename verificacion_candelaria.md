# ¿Candelaria puede armar un plan tipo "Bogotá Cerca de ti"?

Prueba hecha el 9 de nov de 2026 sobre el widget de texto (`azurecandelaria.visitbogota.co/widget`), una sola sesión, 7 mensajes. El sitio principal (`/`) es una interfaz de voz con avatar; no la probé porque requiere micrófono.

## Veredicto

**Parcial.** Candelaria resuelve la capa conversacional y propone planes razonables basados en el inventario del IDT, pero no garantiza lo que la hipótesis del reto promete ("cabe en tu tiempo y está abierto ahora"). Con esta evidencia yo **no descartaría el selector**; sí bajaría el esfuerzo de revisarlo (ver "Qué recomiendo").

Además, el cliente ya dijo (diapositivas 3 y 4) que el piloto no se hará sobre Candelaria sino sobre un asistente adicional en Azure. Candelaria sirve como referencia y comparación, no como el camino de integración.

## Lo que sí hace bien

- **Pide lo que falta.** Ante "salgo desde Suba" preguntó el punto exacto de salida antes de armar el plan.
- **Usa los parámetros.** Adaptó el plan a la hora (lunes 7:30 pm → solo exteriores y plazas), al modo (pie/bici) y a la compañía (niños → paradas planas, calzado, agua).
- **No inventa lugares.** Las 8 paradas que devolvió coinciden con el inventario del IDT a 0 m (nombre y coordenadas), incluidas Plaza Fundacional de Suba, Iglesia Inmaculada Concepción, Parque Mirador de los Nevados, Basílica de Lourdes, Porciúncula, Quebrada Las Delicias, Castillo del Mono Osorio y Casa Medina.
- **Bilingüe y con JSON si se le pide.** Respondió en inglés y devolvió solo un JSON con paradas, coordenadas y minutos (la suma cuadró: 35+10+8 de visita + 25+12 de traslado = 90).
- **Es honesto cuando no sabe.** Sobre museos del lunes dijo "no tengo confirmación" y ofreció verificar en tiempo real.

## Lo que no garantiza

| Brecha | Evidencia |
|---|---|
| **No calcula, estima en texto** | En la prueba de Chapinero sus propios traslados y estancias suman 50–70 min a pie y 39–53 min en bici, pero declara "80–100 min" y "85–105 min". |
| **Sin tiempos reales de traslado** | En Suba dijo "para ver los tiempos exactos abre cada enlace 'Cómo llegar'". Ese enlace (`lab.visitbogota.co/transmilenio`) es un selector "Llegar en transporte público / por tu cuenta", no una API con minutos. |
| **"Abierto ahora" no está verificado** | Para espacios públicos afirma "sin horario de cierre"; para museos dice "suelen cerrar los lunes". No cita horarios con fuente. |
| **Posible error en horarios de museos** | Listó Museo Botero, Casa de la Moneda y MAMU entre los que cierran los lunes. El Banco de la República (página dic 2019–ene 2020) y Bogotá.gov (2021) los ponen cerrados los **martes**; el Museo del Oro sí cierra los lunes. Las fuentes son antiguas: hay que confirmarlo en los sitios oficiales. |
| **Fiabilidad** | La consulta más completa (lunes 10 am, Plaza de Bolívar, 3 h, pareja, museos y comer) dio **504 "Candelaria tardó demasiado en responder" dos veces seguidas**. Las respuestas tardaron de unas decenas de segundos a más de 2 minutos. |
| **Salida no estructurada** | `POST /api/chat` devuelve `{answer, session_id, user_id}`: texto libre. Solo dio JSON cuando se lo pedí, y no es determinista. |
| **Plan que no aprovecha el tiempo** | El plan nocturno de 2 h usaba 25–30 min de visita (paradas de 5–15 min frente a fachadas). |
| **Sin mapa de demanda** | No pude ver qué logs o analítica guarda; el reto necesita medir tasa de selección y ejecución. |

## Detalle de las pruebas

| # | Consulta | Resultado |
|---|---|---|
| 1 | 2 h, sábado tarde, Suba, con niños, TransMilenio o a pie | Pidió el origen. Con "Portal Suba, 2 adultos y 2 niños de 6 y 9" propuso Suba Pueblo: Plaza Fundacional, Iglesia, Mirador de los Nevados. Sin minutos por parada ni por traslado; afirmó "igual el plan cabe en tus 2 horas" sin calcularlo. |
| 2 | Lunes 7:30 pm, Calle 63 con Cra 13, solo, 2 h, bici o a pie, qué está abierto y a qué hora cierra | Dos planes (Lourdes → Porciúncula a pie; Lourdes → Casa Medina → Porciúncula en bici) con estimados por tramo. Totales declarados no suman (ver tabla). No dio horas de cierre, solo "sin horario de cierre". |
| 3 | Lunes 10 am, Plaza de Bolívar, pareja, 3 h, museos y comer, horario de cada lugar | **504 dos veces.** |
| 4 | Museos cerca de la Plaza de Bolívar abiertos hoy lunes | "Usualmente no abren"; lista seis museos como cerrados los lunes. Ofrece verificar en vivo. |
| 5 | En inglés y solo JSON: 90 min, sábado, Chapinero, con dos amigos, algo inesperado, sin Monserrate | JSON válido con 3 paradas. La primera parada tiene 0 min de traslado desde un origen impreciso ("Chapinero") y no hay tramo de regreso (el esquema que pedí tampoco lo tenía). |

Notas: son pocas pruebas, una sesión y un solo día; los 504 podrían ser transitorios. Los mensajes quedaron en el chat de producción del IDT.

## Comparación con el prototipo del selector (`codigo/planificador.py`)

| Pieza de la diapositiva 19 | Candelaria | Prototipo |
|---|---|---|
| Extraer tiempo, origen, compañía | Sí | No (recibe campos estructurados; esta capa la haría el LLM) |
| Catálogo con horarios y duración | No (solo inventario) | No (supuestos por categoría, marcados `_supuesto`) |
| Tiempos de traslado reales | No | No (estimación geométrica; falta API de rutas) |
| El plan cabe en el tiempo | No garantizado | Sí; `--autoprueba` verifica que traslados + visitas = total ≤ tiempo − margen |
| Resultado reproducible y estructurado | No | Sí (JSON, enlace de Google Maps, texto de WhatsApp) |
| Español e inglés | Sí | Datos en español; textos de salida en español |

## El cuello de botella son los datos, no el algoritmo

La diapositiva 19 marca el catálogo como "EXISTE: horarios, duración típica y coordenadas". El inventario del IDT que tenemos (522 registros) trae nombre, categoría, dirección, localidad y coordenadas, **sin horarios, duración ni accesibilidad**. Sin eso ni Candelaria ni el selector pueden prometer "abierto ahora" (el riesgo ya anotado en la diapositiva 22).

## Qué recomiendo

1. **Pedir a Laura Rojas el catálogo con horarios** (capa de ArcGIS o Consultar Visit Bogotá) y confirmar si incluye duración y accesibilidad. Es lo que más mueve la calidad del plan.
2. **Mantener el selector como herramienta determinista** que el asistente (Candelaria o el propio en Azure) llame con parámetros y reciba JSON. Es chico (~320 líneas) y lo que hay que revisar es poco: horarios reales, API de rutas y los pesos de preferencias.
3. **Decidir la API de rutas** (Google Maps o ruteo de ArcGIS Online del IDT) y reemplazar `tiempo_traslado()`.
4. **Definir las dos localidades del MVP** (la diapositiva 22 dice "dos localidades más el centro").
5. **Probar a Candelaria con un set fijo de 15–20 consultas** antes del piloto, repetidas en dos días, para medir tasa de 504, latencia y consistencia de totales; así la comparación con nuestro asistente queda con números.

Fuentes de horarios consultadas: [Bogotá.gov, horarios y precios de museos (2021)](https://bogota.gov.co/mi-ciudad/cultura-recreacion-y-deporte/horarios-y-precios-de-entrada-los-museos-de-bogota-foto) y [Banco de la República, cierres dic 2019–ene 2020](https://www.banrep.gov.co/es/print/pdf/node/51761).

---

## Actualización 9-nov, noche: fuentes de datos y prompt del piloto

### Fuentes y características (detalle en `datos/candelaria_fuentes_y_campos.md`)

- Candelaria usa **capas públicas del ArcGIS Online del IDT**. Su ficha de ejemplo reveló el servicio; las capas relevantes se descargaron en `datos/fuentes_arcgis/` con huella verificada.
- **Horarios:** solo en texto libre (Guía Destino Diverso 131 de 197; Plazas de Mercado 18 de 18). Visit Bogotá casi no los trae. En la base unificada, **120 de 650 lugares** tienen horario interpretable.
- **Pet friendly:** sí existe, como etiqueta oficial de Visit Bogotá (48 de 245 fichas). Candelaria dice que "no es un campo universal", y es cierto.
- **Accesibilidad:** solo un puntaje 1–3 para 23 atractivos (Destino Turístico Inteligente), no una descripción.
- **No existe en ninguna capa:** duración típica, costo, "apto para niños" (solo la etiqueta "Familias").

### Prompt del piloto (el que envía el dashboard, pidiendo JSON)

Cinco consultas lanzadas a la vez:

| Escenario | Resultado |
|---|---|
| Chapinero, lunes 7:30 pm, 2 h, solo, comer | 200 en 113 s: **una parada**, "PRESTO BTA LOURDES" (restaurante del RNT), 100 min de estancia, horario "sin información oficial" |
| Suba, sábado, 2 h, con niños (mockup) | **504** a los 121 s |
| Plaza de Bolívar, domingo, 3 h, pareja | **504** a los 122 s |
| Usaquén, domingo, 1 h 30, amigos + mascota | **504** a los 122 s |
| Teusaquillo, sábado, 4 h, niños, bici | **504** a los 122 s |

El servidor corta a los ~120 s (Cloudflare). Con este prompt, **4 de 5 consultas fallaron**.

**Decisión:** el piloto usa respuestas guardadas de Candelaria, incluidas las fallidas, y la integración en vivo queda para después: con el asistente nuevo o con Candelaria si mejora su tiempo de respuesta. Cuando el chatbot falla, el dashboard muestra la alternativa verificada del selector propio.

### Lo que el verificador encontró en las respuestas reales

- **Presto Lourdes:** existe en el RNT; cabe en el tiempo; horario no confirmado.
- **Chapinero, prosa:** el total declarado (80–100 min) no coincide con la suma de sus propios tramos (50–70 min). El verificador recalcula 72 min con estancias típicas.
- **Chapinero, JSON en inglés:** **no cabe**. Declaró 0 min desde el origen hasta la primera parada (Quebrada Las Delicias, a ~1,8 km en línea recta).
- **Suba, prosa:** cabe solo si se pasa ≤ ~23 min por parada; marcó 2 paradas como opcionales.
