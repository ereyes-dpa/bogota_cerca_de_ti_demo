# Candelaria: de dónde saca los datos y qué características tienen

Consultas del 9-nov-2026 al endpoint del widget (`POST https://azurecandelaria.visitbogota.co/api/chat`), cada una en una sesión nueva. Abajo las respuestas tal como llegaron y, al final, lo que se comprobó en las capas reales.

## 1. ¿De dónde sacas los datos de turismo? (respondió en 36 s)

> Uso principalmente fuentes oficiales y públicas de Bogotá:
> - Visit Bogotá (contenido editorial del destino): rutas, experiencias, actividades y planes publicados por el ente oficial de promoción turística de la ciudad.
> - Instituto Distrital de Turismo (IDT) – Inventario turístico oficial en ESRI/ArcGIS: capas y fichas como Atractivos Turísticos de Bogotá, Puntos de Información Turística (PIT), Prestadores de servicios turísticos registrados (RNT) e Infraestructura turística liviana.
> - Agenda de eventos de Bogotá: servicio oficial de eventos gestionado por el IDT/Visit Bogotá (conciertos, festivales, ferias y actividades en la ciudad).
> - Información puntual "en caliente" cuando compartes la página oficial de un lugar específico: si me das la URL y su ubicación, puedo extraer detalles directamente de esa fuente.
>
> Fuentes complementarias para información al viajero (cuando aplica): Aeropuerto El Dorado, TransMilenio/Secretaría de Movilidad, Secretaría de Salud y Policía Metropolitana de Bogotá.

No dio URLs. Una consulta anterior de Esteban en el widget dio una lista equivalente: Visit Bogotá, inventario IDT en ESRI/ArcGIS, RNT y agenda de eventos.

## 2. ¿Qué campos tiene cada lugar? (20 s)

> No puedo listar los campos o columnas internas de las fuentes que consulto.

Luego enumeró en viñetas lo que suele ofrecer de cada lugar (resumen):

- nombre oficial y tipo;
- descripción;
- dirección o localidad, a veces coordenadas;
- horarios de visita cuando están publicados;
- acceso y cómo llegar en transporte público;
- servicios (guías, baños, audios) si la fuente los menciona;
- accesibilidad cuando está informada;
- contacto y enlaces oficiales;
- en algunos casos, sostenibilidad, tecnología o innovación.

## 3. ¿Horarios de apertura? ¿Pet friendly? ¿Accesibilidad, costo, duración, niños? (20 s)

Extracto (cada viñeta abreviada):

> - Horarios de apertura/cierre: los muestro cuando la ficha oficial o Visit Bogotá los publica (más frecuente en museos y centros culturales). Si no aparecen, te aviso y te doy el canal de contacto para confirmarlos.
> - Pet friendly: no es un campo universal. Si el lugar lo declara, te lo confirmo; si no hay mención, sugiero verificar directamente.
> - Accesibilidad: en el inventario oficial (IDT/ESRI) muchos atractivos incluyen un apartado de accesibilidad.
> - Costo/boletas: solo si la fuente lo indica. No invento precios.
> - Duración recomendada: no suele venir como dato oficial. Puedo sugerirte tiempos orientativos (marcados como estimación).
> - Apto para niños: no siempre hay etiqueta oficial.

## 4. Ejemplo completo de una ficha (60 s)

Pedí "Parque Mirador de los Nevados" y no lo encontró con ese nombre. Mostró en cambio Monserrate:

> Descripción…; Dirección: No disponible en la ficha consultada; Ubicación: lat 4.6036, long -74.0614; Clasificación técnica: Medio; Indicadores (escala interna): Promedio general 1.7647, Accesibilidad 1.2143, Sostenibilidad 2.1905, Tecnología 1.5714, Innovación 1.25; Foto: `https://services1.arcgis.com/OnwEbGgbiaZUoK0z/arcgis/rest/services/Atractivos_gdb/FeatureServer/0/24/attachments/47`

Ese enlace reveló el servicio de ArcGIS del IDT, de donde se descargaron las fuentes (ver `fuentes_arcgis/LEEME.md`).

## Lo que se comprobó en las capas

| Característica | ¿Existe? | Dónde | Cobertura |
|---|---|---|---|
| **Horario de apertura** | Parcial, en texto libre | Guía Destino Diverso (`Horario`), Plazas de Mercado (`Horario`) | 131 de 197 y 18 de 18. En las fichas de Visit Bogotá el texto de unas 36 menciona días u horas, pero solo 4 traen un "horario" extraíble. En el catálogo enriquecido: **120 de 650 lugares** con horario interpretable |
| **Pet friendly** | Sí, como etiqueta | Visit Bogotá `field_turpara` | **48 de 245** fichas |
| **Para quién** (Solo, Pareja, Familias, Grupo, LGBTI) | Sí | Visit Bogotá `field_turpara` | 245 de 245 fichas; "Familias" en 113 |
| **Accesibilidad** | Solo puntaje 1–3 | `Atractivos_gdb` (DTI) | 23 atractivos; Candelaria dice "apartado de accesibilidad", pero es un índice, no una descripción |
| Duración de la visita | No | — | Candelaria la estima |
| Costo | No en atractivos | — | — |
| Apto para niños | Indirecto | Etiqueta "Familias" | — |
| Eventos con fecha | Sí | `Eventos_ES` | 41; al 9-nov solo 5 vigentes o futuros (la agenda está desactualizada) |
| Rating y estado del negocio | Sí | Guía Destino Diverso | 189 con rating |

## Discrepancias entre lo que dice Candelaria y los datos

- Dice que muestra horarios "cuando la ficha oficial o Visit Bogotá los publica". En Visit Bogotá casi no hay horarios estructurados; donde más hay es en la Guía Destino Diverso.
- Para la Plaza de Lourdes y la Porciúncula dijo "sin horario de cierre" sin citar fuente. Lo correcto sería "no hay dato".
- Al prompt del piloto (JSON) respondió una sola parada, "PRESTO BTA LOURDES" (un restaurante del RNT), con 100 minutos de estancia y horario "sin información oficial". Las otras 4 consultas del piloto terminaron en **504 a los ~121 s**.
