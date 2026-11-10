#!/usr/bin/env python3
"""Construye el catálogo de trabajo de "Bogotá Cerca de ti" a partir del
inventario turístico del IDT (datos crudos/inventario_turistico_idt.geojson).

El inventario NO trae horarios, duración de visita ni accesibilidad. Por eso este
script agrega, por categoría, SUPUESTOS explícitos (columnas con sufijo _supuesto)
que deben reemplazarse con el catálogo real (Visit Bogotá / ArcGIS / Planes Locales).

Uso:  python3 construir_catalogo.py   (desde cualquier carpeta)
"""
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]          # .../bogota
ENTRADA = RAIZ / "datos crudos" / "inventario_turistico_idt.geojson"
SALIDA = Path(__file__).resolve().parents[1] / "datos" / "catalogo_atractivos.csv"

# categoría IDT -> (minutos de visita, clase de apertura, etiquetas)
# apertura: 'abierto'   = espacio público, sin horario de cierre formal
#           'diurno'    = espacio abierto con uso diurno (06:00-18:00)
#           'verificar' = depende de horario de un administrador (museo, templo, etc.)
#           'evento'    = requiere fechas (se excluye del selector)
SUPUESTOS = {
    "Parque":                                   (45, "diurno",    {"naturaleza", "ninos", "economico", "caminar_poco"}),
    "Atractivo de Naturaleza":                  (60, "diurno",    {"naturaleza", "economico", "ninos_ok"}),
    "Jardín Botánico":                          (90, "verificar", {"naturaleza", "ninos"}),
    "Parque Temático":                          (120, "verificar", {"ninos"}),
    "Museo":                                    (60, "verificar", {"cultura", "ninos_ok"}),
    "Biblioteca":                               (45, "verificar", {"cultura", "economico", "caminar_poco"}),
    "Atractivo Cultural":                       (30, "verificar", {"cultura"}),
    "Monumento y/o escultura":                  (10, "abierto",   {"cultura", "economico", "caminar_poco"}),
    "Escenario Religioso":                      (20, "verificar", {"cultura", "economico"}),
    "Gastronomía":                              (45, "verificar", {"comer"}),
    "Comercio":                                 (45, "verificar", {"comer", "compras"}),
    "Escenario Deportivo":                      (60, "verificar", {"ninos_ok"}),
    "Infraestructura y equipamientos urbanos":  (30, "verificar", set()),
    "Ferias, festividades y eventos":           (0,  "evento",    set()),
}

# Nombres que indican espacio público abierto aunque la categoría sea "Atractivo Cultural"
# (solo si el nombre EMPIEZA así: "Teatro El Parque" o "Teatro Nacional Calle 71" NO son espacio público)
PATRON_ABIERTO = re.compile(r"^(plaza|plazoleta|calle|carrera|paseo|alameda|ciclov[ií]a|barrio|centro hist[oó]rico)\b", re.I)
# Falsos positivos detectados al auditar la clasificación: son recintos con horario
EXCEPCIONES_VERIFICAR = {"Plaza La Santamaría", "Plaza del Concejo de Bogotá Luis Carlos Sarmiento"}
# Los "de siempre" (hipótesis del Reto 2: Monserrate 47 %, Simón Bolívar 35 %, Zona T 35 %)
PATRON_DE_SIEMPRE = re.compile(r"monserrate|sim[oó]n bol[ií]var|zona t\b|zona rosa", re.I)


def sin_tildes(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def main() -> None:
    g = json.loads(ENTRADA.read_text(encoding="utf-8"))
    filas = []
    for f in g["features"]:
        p = f["properties"]
        cat = p["ICONOGRAFI"]
        minutos, apertura, tags = SUPUESTOS.get(cat, (30, "verificar", set()))
        nombre = p["NOMATRACTI"].strip()
        if apertura == "verificar" and cat == "Atractivo Cultural" and PATRON_ABIERTO.search(nombre) and nombre not in EXCEPCIONES_VERIFICAR:
            apertura = "abierto"
            minutos = 20
            tags = tags | {"economico", "caminar_poco"}
        filas.append({
            "id": p["IDATRACTIV"],
            "nombre": nombre,
            "categoria": cat,
            "tipo_idt": p["TIPOATRACT"],
            "localidad": p["LOCALIDAD"].title().replace("De ", "de ") if p["LOCALIDAD"] else "",
            "sector": (p.get("SECCATRAST") or "").title(),
            "direccion": (p["DIRECCION"] or "").strip(),
            "lat": p["Latitud"],
            "lon": p["Longitud"],
            "minutos_visita_supuesto": minutos,
            "apertura_supuesto": apertura,
            "etiquetas_supuesto": "|".join(sorted(tags)),
            "es_de_siempre": bool(PATRON_DE_SIEMPRE.search(nombre)),
        })
    df = pd.DataFrame(filas)
    # Fuera del selector: eventos (necesitan fechas) y registros sin coordenadas válidas
    n0 = len(df)
    df = df[(df.apertura_supuesto != "evento")]
    df = df[df.lat.between(3.7, 4.9) & df.lon.between(-74.3, -73.9)]
    df = df.drop_duplicates(["nombre", "lat", "lon"]).sort_values(["localidad", "categoria", "nombre"])
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SALIDA, index=False, encoding="utf-8")
    print(f"{n0} registros en el inventario -> {len(df)} en el catálogo ({SALIDA})")
    print(df.apertura_supuesto.value_counts().to_string())
    print(df.localidad.value_counts().head(8).to_string())


if __name__ == "__main__":
    main()
