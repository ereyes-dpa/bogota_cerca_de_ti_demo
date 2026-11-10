# Fuentes de Candelaria descargadas (9-nov-2026)

Capas públicas del ArcGIS Online del IDT: `https://services1.arcgis.com/OnwEbGgbiaZUoK0z/arcgis/rest/services`.

Candelaria nombró sus fuentes: Visit Bogotá, el inventario del IDT en ESRI/ArcGIS, el RNT y la agenda de eventos. Su ficha de ejemplo reveló este servicio. El directorio tiene 65 servicios; aquí están los que alimentan la recomendación.

La copia se hizo desde el navegador con consultas REST, porque las terminales no tienen salida a internet. Cada archivo se verificó contra su huella SHA-256 calculada en el navegador. `manifiesto.json` guarda filas y huella.

Para actualizar: `python3 ../../codigo/descargar_fuentes.py`, que produce las mismas columnas, y luego `python3 ../../codigo/construir_catalogo_enriquecido.py`.

| Archivo | Servicio ArcGIS | Filas | Qué aporta al verificador |
|---|---|---|---|
| `visitbogota_atractivos_es.csv` | `Atractivos_ES` | 245 | Contenido de Visit Bogotá. **`field_turpara`**: Solo, Pareja, Familias, Grupo, **Pet Friendly**, LGBTI. Zona, distrito y ruta de la ficha. `horario_en_texto` solo cuando la descripción dice "horario" (4 fichas) |
| `guia_destino_diverso.csv` | `Guia Bogota Destino Diverso` | 197 | **`Horario`** en texto (131 con dato), rating, estado del negocio, categoría y ruta (comer, compras, nocturno, cultura, naturaleza, dormir) |
| `plazas_mercado.csv` | `PlazasMercadoFinal` | 18 | **`Horario`** por día de las plazas distritales de mercado |
| `dti_atractivos.csv` | `Atractivos_gdb` (Destino Turístico Inteligente) | 23 | Índices 1–3: **accesibilidad**, sostenibilidad, tecnología, innovación, gobernanza. Es la capa de la ficha de ejemplo de Candelaria |
| `visitbogota_eventos_es.csv` | `Eventos_ES` | 41 | Agenda con fechas de inicio y fin. Al 9-nov solo 5 siguen vigentes o son futuros |
| `rnt_gastronomia.csv` | `Prestadores_de_Servicios_Turísticos_2025` | 402 | RNT, solo gastronomía activa: razón social, subcategoría, localidad y coordenadas. **Sin teléfonos, correos ni NIT.** Sirve para reconocer restaurantes que recomienda Candelaria (p. ej. "PRESTO BTA LOURDES") |
| `restaurantes_candelaria.csv` | `restaurantes_candelariaJSON` | 18 | Capa hecha para el chatbot: restaurantes destacados de La Candelaria |
| `puntos_accesibles.csv` | `PuntosDestinoAccesibleBogota` | 20 | Puntos del "Destino Accesible" (sobre todo hoteles y equipamientos), sin detalle de accesibilidad |

El inventario turístico (`Inventario_Tur`, 522) es el mismo de `datos crudos/inventario_turistico_idt.geojson` y no se volvió a copiar.

## Qué no existe en ninguna capa

- Duración típica de la visita.
- Costo de entrada.
- Horario estructurado (solo texto libre).
- "Apto para niños" (solo la etiqueta "Familias").
- Detalle de accesibilidad: rampas, baños, etc. Solo hay puntajes.

El catálogo enriquecido interpreta el texto de los horarios (`codigo/horarios.py`). Hoy logra interpretar 120 de los 650 lugares; el resto usa supuestos por categoría, marcados como tales.
