# Datos de Bogotá Cerca de ti — guía para el dashboard de Power BI

Esta carpeta tiene lo que necesita quien arme el dashboard final en Power BI:

- las tablas que produce el recomendador, listas para cargar (`powerbi/`);
- la base de lugares contra la que se verifica;
- el registro de consultas del demo;
- las fuentes originales del IDT.

Hay dos formas de alimentar Power BI:

1. **Cargar los CSV de `powerbi/`** (Obtener datos → Texto/CSV). No necesita Python en el equipo de quien abre el informe; para actualizar, se regeneran los CSV con el comando de la última sección.
2. **Correr el script desde Power BI** (Obtener datos → Script de Python) con `recomendar_lote()`. Devuelve las mismas tres tablas, con las mismas columnas. El paso a paso está en el documento Word del demo y en el `README.md` principal.

## Modelo sugerido

```
                 consultas  (1 fila por consulta)
                  │ consulta_id
        ┌─────────┴──────────┐
        ▼ 1:*                ▼ 1:*
     paradas              chequeos
   (1 fila por parada)   (1 fila por chequeo)
        │ id_lugar
        ▼ *:1
 catalogo_enriquecido (id)   ← los id_lugar que empiezan con «rnt-» van a fuentes_arcgis/rnt_gastronomia.csv (codigo_rnt)
```

- Relación `consultas[consulta_id]` 1 → * `paradas[consulta_id]` y 1 → * `chequeos[consulta_id]`, filtro en una sola dirección.
- `paradas` trae **tres planes por consulta** en la columna `plan`:
  - `recomendado`: el que ve el usuario;
  - `chatbot`: el que propuso Candelaria;
  - `alternativa`: el del selector propio.

  El recomendado repite las paradas de uno de los otros dos. Para mapas y conteos del plan entregado, filtra `plan = "recomendado"`; para comparar a Candelaria con el selector, usa los otros dos.
- `chequeos` solo trae `chatbot` y `alternativa`. El veredicto del plan recomendado está en `consultas[recomendacion_veredicto]`.

## `powerbi/consultas.csv` — una fila por consulta

| Columna | Tipo | Qué es |
|---|---|---|
| `consulta_id` | texto | Llave. En el lote viene de la columna `id` de la entrada; en el demo es `d` + fecha y hora |
| `generado` | fecha/hora | Cuándo se calculó (hora de Bogotá) |
| `origen` | texto | Nombre del punto de salida o «lat, lon» |
| `lat`, `lon` | decimal | Punto de salida |
| `minutos` | entero | Tiempo disponible (30–360) |
| `cuando` | fecha/hora | Hora de salida, `AAAA-MM-DD HH:MM` |
| `dia` | texto | Día de la semana de `cuando` |
| `con` | texto | `solo`, `pareja`, `amigos`, `ninos` |
| `modo` | texto | `pie`, `bici`, `transporte`, `auto` |
| `mascota` | booleano | Va con mascota |
| `prefs` | texto | Preferencias separadas por `\|`: `comer`, `cultura`, `naturaleza`, `inesperado`, `caminar_poco`, `economico` (puede ir vacío) |
| `fuente_chatbot` | texto | `candelaria` (en vivo), `guardada`, `nuevo` o `ninguna` |
| `escenario` | texto | Respuesta guardada usada (solo con `guardada`) |
| `chatbot_status` | entero | Código HTTP de Candelaria: 200 = respondió, 504 = se cortó a los ~120 s, vacío = no se consultó |
| `chatbot_segundos` | decimal | Cuánto tardó Candelaria |
| `chatbot_respondio` | booleano | Candelaria devolvió texto |
| `chatbot_veredicto` | texto | Veredicto del plan de Candelaria: `LOGRABLE`, `LOGRABLE CON ADVERTENCIAS`, `NO LOGRABLE`, `SIN RESPUESTA` o `NO CONSULTADO` |
| `chatbot_paradas` | entero | Paradas que propuso Candelaria |
| `recomendacion_origen` | texto | De dónde salió el plan entregado: `chatbot`, `selector_propio` o `ninguno` |
| `recomendacion_veredicto` | texto | Veredicto del plan entregado |
| `recomendacion_paradas` | entero | Paradas del plan entregado |
| `duracion_total_min` | entero | Traslados + visitas + regreso del plan entregado |
| `margen_min` | entero | `minutos` − `duracion_total_min` (se pide ≥ 5) |
| `km_total` | decimal | Kilómetros por calle estimados |
| `termina_a` | texto `HH:MM` | Hora de regreso al punto de salida |
| `motivo` | texto | Por qué se entregó ese plan, en una frase |

## `powerbi/paradas.csv` — una fila por parada de cada plan

| Columna | Tipo | Qué es |
|---|---|---|
| `consulta_id` | texto | Llave hacia `consultas` |
| `plan` | texto | `recomendado`, `chatbot` o `alternativa` |
| `orden` | entero | 1, 2 o 3 |
| `id_lugar` | texto | Llave hacia `catalogo_enriquecido[id]`; si empieza con `rnt-`, es un restaurante del RNT (`rnt_gastronomia.csv`). Vacío = lugar no encontrado (posible lugar inventado) |
| `nombre`, `categoria` | texto | Nombre oficial y categoría del IDT |
| `lat`, `lon` | decimal | Ubicación |
| `llegada`, `salida` | texto `HH:MM` | Horas recalculadas por el verificador |
| `minutos_visita` | entero | Tiempo en el sitio (declarado por el chatbot o típico de la categoría) |
| `traslado_min` | entero | Minutos desde el punto anterior (fórmula por modo: ver página «Inicio» del demo) |
| `apertura` | texto | `oficial` (horario del IDT), `abierto` (espacio público), `supuesto` (horario por categoría) o `sin dato` |
| `horario` | texto | Horario oficial en texto, si existe |
| `pet_friendly` | booleano | Tiene la etiqueta oficial Pet Friendly de Visit Bogotá |

## `powerbi/chequeos.csv` — una fila por chequeo de la verificación

| Columna | Tipo | Qué es |
|---|---|---|
| `consulta_id` | texto | Llave hacia `consultas` |
| `plan` | texto | `chatbot` o `alternativa` |
| `id_criterio` | texto | Código estable para agrupar (abajo) |
| `criterio` | texto | Nombre legible; en `prefs` incluye la preferencia («Preferencia: naturaleza») |
| `estado` | texto | `ok`, `aviso` (advertencia), `falla` o `na` (no aplica) |
| `parada` | entero, puede ir vacío | Número de parada a la que se refiere; vacío = todo el plan |
| `detalle` | texto | Explicación con cifras |

Códigos de `id_criterio`:

| Código | Criterio |
|---|---|
| `catalogo` | Está en la base |
| `tiempo` | Cabe en tu tiempo |
| `apertura` | Abierto cuando llegas |
| `consistencia` | Su total coincide con la suma real |
| `traslado` | Traslado creíble |
| `minutos` | Minutos por parada declarados |
| `mascota` | Admite mascotas |
| `compania` | Apto para quien va |
| `prefs` | Preferencias |
| `caminar` | Caminar poco (tramos a pie de más de 12 min) |
| `paradas` | De 1 a 3 paradas |
| `lectura` | Formato de la respuesta |

Un plan es **NO LOGRABLE** si tiene al menos un `falla`, y **LOGRABLE CON ADVERTENCIAS** si solo tiene `aviso`.

## `catalogo_enriquecido.csv` — los 650 lugares de la base

| Columna | Qué es |
|---|---|
| `id` | Llave (`paradas[id_lugar]`) |
| `nombre`, `categoria`, `localidad`, `direccion`, `lat`, `lon` | Datos del lugar |
| `minutos_visita_supuesto` | Duración típica de la visita, por categoría |
| `apertura_supuesto` | `abierto`, `diurno` (6:00–18:00), `verificar` (depende de un administrador) o `evento` |
| `etiquetas_supuesto` | Para qué sirve el lugar, separado por `\|`: `comer`, `cultura`, `naturaleza`, `ninos`, `economico`, `caminar_poco`… |
| `es_de_siempre` | Monserrate, Simón Bolívar o Zona T («los de siempre» del reto) |
| `horario_texto`, `horario_fuente` | Horario oficial en texto y de qué capa salió |
| `horario_interpretable` | El horario se pudo convertir en franjas por día (120 lugares) |
| `para` | Etiquetas oficiales de Visit Bogotá: Solo, Pareja, Familias, Grupo, LGBTI |
| `pet_friendly` | `si` si tiene la etiqueta oficial (48 lugares) |
| `accesibilidad_dti` | Índice de accesibilidad 1–3 (solo 23 lugares) |
| `url`, `fuente` | Ficha de Visit Bogotá y capa de origen |

## Otros archivos

| Archivo | Qué es |
|---|---|
| `consultas_ejemplo.csv` | **Entrada** del lote: las 8 consultas reales del piloto. Columnas `id, minutos, origen, cuando, con, prefs, modo, mascota, escenario`. Para nuevas consultas, agrega filas; `escenario` solo se usa con `fuente="guardada"` |
| `consultas_dashboard.csv` | Registro del demo de Streamlit: una fila por cada «Armar mi plan», con las mismas columnas que `powerbi/consultas.csv`. Sirve para el mapa de demanda (solo parámetros, ningún dato personal). Las primeras filas, anteriores al 10 de noviembre, tienen `consulta_id` repetido (`c0001`) |
| `consultas_piloto.csv` | Registro de una versión anterior del demo, con otras columnas. No lo uses |
| `catalogo_atractivos.csv` | Inventario turístico del IDT con los supuestos por categoría (461 lugares); es la entrada del catálogo enriquecido |
| `fuentes_arcgis/` | Capas originales del ArcGIS del IDT, con huella SHA-256 (ver su `LEEME.md`) |
| `candelaria_fuentes_y_campos.md` | Qué dijo Candelaria sobre sus fuentes y qué se comprobó |

## Medidas DAX sugeridas

```DAX
Consultas = COUNTROWS ( consultas )

% plan de Candelaria =
DIVIDE ( CALCULATE ( [Consultas], consultas[recomendacion_origen] = "chatbot" ), [Consultas] )

% Candelaria respondió =
DIVIDE (
    CALCULATE ( [Consultas], consultas[chatbot_respondio] = TRUE () ),
    CALCULATE ( [Consultas], consultas[fuente_chatbot] <> "ninguna" )
)

Segundos de respuesta (promedio) =
CALCULATE ( AVERAGE ( consultas[chatbot_segundos] ), consultas[chatbot_respondio] = TRUE () )

Fallas = CALCULATE ( COUNTROWS ( chequeos ), chequeos[estado] = "falla" )
Advertencias = CALCULATE ( COUNTROWS ( chequeos ), chequeos[estado] = "aviso" )
```

Visuales que salen directo de estas tablas:

- mapa de paradas recomendadas (`paradas`, filtro `plan = "recomendado"`, latitud y longitud);
- mapa de demanda (`consultas[lat]`, `consultas[lon]`);
- barras de fallas y advertencias por `chequeos[criterio]` y `plan`;
- distribución de `consultas[chatbot_segundos]`;
- reparto de `recomendacion_origen`.

## Al importar en Power BI

- **Configuración regional.** Los CSV usan punto decimal (`4.6495`) y UTF-8. En Power Query, al cambiar el tipo de `lat`, `lon`, `km_total` y `chatbot_segundos`, usa «Cambiar tipo → Usar configuración regional → Inglés (Estados Unidos)». Con configuración en español, `4.6495` se lee como 46495.
- `cuando` y `generado` son fecha/hora. `llegada`, `salida` y `termina_a` son horas `HH:MM`: déjalas como texto o pásalas a hora.
- Los booleanos vienen como `True`/`False`.
- `chequeos[parada]` es un entero que puede ir vacío.
- `id_lugar` y `catalogo_enriquecido[id]` deben ser **texto** en ambas tablas: hay ids como `rnt-29801`.

## Cómo regenerar las tablas

```bash
cd bogota_cerca_de_ti/codigo
# con las respuestas guardadas de Candelaria (no necesita internet)
python3 recomendar.py --lote ../datos/consultas_ejemplo.csv --fuente guardada --salida ../datos/powerbi
# consultando a Candelaria en vivo (hasta 2 min por consulta)
python3 recomendar.py --lote ../datos/consultas_ejemplo.csv --fuente candelaria --salida ../datos/powerbi
```

Para actualizar la base de lugares desde el ArcGIS del IDT: `python3 descargar_fuentes.py` y luego `python3 construir_catalogo_enriquecido.py`.
