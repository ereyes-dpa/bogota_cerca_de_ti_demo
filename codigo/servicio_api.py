"""API de referencia para el backend de la app: recibe la consulta, devuelve el plan verificado y lo registra para Power BI.

Flujo
  App ── POST /recomendar {consulta} ──► este servicio ──► recomendar()
                                                            ├─ 1. pide el plan al chatbot (asistente nuevo del IDT o Candelaria)
                                                            ├─ 2. lo verifica contra la base del IDT
                                                            └─ 3. si no es lograble, arma y verifica un plan propio
  App ◄── JSON {recomendacion: {origen, motivo, plan}} ──┘
                     └─► registro: consultas.csv · paradas.csv · chequeos.csv  ──► Power BI

Correr (desde la carpeta bogota_cerca_de_ti)
  pip install -r requirements-api.txt
  uvicorn servicio_api:app --app-dir codigo --host 0.0.0.0 --port 8000
  Documentación interactiva: http://localhost:8000/docs

Configuración (variables de entorno)
  FUENTE_CHATBOT     nuevo | candelaria | guardada | ninguna    (por defecto: nuevo si hay URL_CHATBOT_NUEVO; si no, candelaria)
  URL_CHATBOT_NUEVO  URL base del asistente nuevo del IDT (mismo contrato que Candelaria: POST {url}/api/chat)
  NUEVO_CHATBOT_TOKEN  token del asistente nuevo, si lo pide
  ESPERA_CHATBOT_S   segundos máximos esperando al chatbot (por defecto 120)
  CARPETA_REGISTRO   carpeta de los CSV que lee Power BI (por defecto datos/registro)
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from recomendar import ESPERA_CANDELARIA_S, _json, a_tablas, recomendar

AQUI = Path(__file__).resolve().parent
URL_NUEVO = os.environ.get("URL_CHATBOT_NUEVO", "")
FUENTE = os.environ.get("FUENTE_CHATBOT") or ("nuevo" if URL_NUEVO else "candelaria")
ESPERA = float(os.environ.get("ESPERA_CHATBOT_S", ESPERA_CANDELARIA_S))
REGISTRO = Path(os.environ.get("CARPETA_REGISTRO", AQUI.parent / "datos" / "registro"))
_candado = threading.Lock()

app = FastAPI(title="Bogotá Cerca de ti · recomendador",
              description="Recibe la consulta de la app y devuelve un plan verificado contra la base del IDT.")


class Consulta(BaseModel):
    """Lo que manda la app desde «Cuéntame lo esencial»."""
    minutos: int = Field(..., ge=30, le=360, examples=[120], description="Tiempo disponible, incluido el regreso")
    origen: str | dict = Field(..., examples=["4.73, -74.09"], description="«lat, lon», {lat, lon} o un nombre (Suba, Chapinero…)")
    cuando: str = Field("ahora", examples=["2026-11-14 15:00"], description="«ahora», «HH:MM» o «AAAA-MM-DD HH:MM», hora de Bogotá")
    con: str = Field("solo", examples=["ninos"], description="solo | pareja | amigos | ninos")
    prefs: list[str] = Field(default_factory=list, examples=[["naturaleza"]],
                             description="comer, cultura, naturaleza, inesperado, caminar_poco, economico")
    modo: str = Field("transporte", examples=["transporte"], description="pie | bici | transporte | auto")
    mascota: bool = False
    id: str | None = Field(None, description="Identificador de la consulta en la app; si falta se genera uno")
    escenario: str | None = Field(None, description="Solo con FUENTE_CHATBOT=guardada (pruebas): respuesta guardada a usar")


def registrar(resultado: dict) -> None:
    """Agrega la consulta a los tres CSV que lee Power BI (mismas columnas que recomendar_lote)."""
    consultas, paradas, chequeos = a_tablas([resultado])
    with _candado:
        REGISTRO.mkdir(parents=True, exist_ok=True)
        for nombre, tabla in (("consultas", consultas), ("paradas", paradas), ("chequeos", chequeos)):
            ruta = REGISTRO / f"{nombre}.csv"
            tabla.to_csv(ruta, mode="a", header=not ruta.exists(), index=False, encoding="utf-8")


@app.get("/salud")
def salud() -> dict:
    return {"ok": True, "fuente": FUENTE, "espera_s": ESPERA, "registro": str(REGISTRO)}


@app.post("/recomendar")
def recomendar_api(consulta: Consulta, detalle: bool = False) -> dict[str, Any]:
    """Consulta de la app → plan verificado. Con `?detalle=true` incluye la verificación completa y el plan alternativo."""
    datos = consulta.model_dump(exclude={"id", "escenario"})
    try:
        r = recomendar(datos, fuente=FUENTE, escenario=consulta.escenario, url_nuevo=URL_NUEVO, espera_s=ESPERA,
                       rnt_en_linea=FUENTE != "guardada")
    except ValueError as e:                      # parámetros fuera de rango o desconocidos
        raise HTTPException(status_code=422, detail=str(e)) from e
    r["id"] = consulta.id or uuid.uuid4().hex[:12]
    try:
        registrar(r)
    except OSError:
        pass                                     # el registro nunca debe impedir responder a la app
    r = json.loads(json.dumps(r, default=_json))  # tipos de numpy → JSON
    ch = r["chatbot"]
    respuesta = {"id": r["id"], "generado": r["generado"], "consulta": r["consulta"], "recomendacion": r["recomendacion"],
                 "chatbot": {"fuente": ch["fuente"], "respondio": bool(ch.get("ok")), "status": ch.get("status"),
                             "segundos": ch.get("segundos")}}
    if detalle:
        respuesta["chatbot"] = {k: v for k, v in ch.items() if k != "mensaje"}
        respuesta["alternativa"] = r.get("alternativa")
    return respuesta
