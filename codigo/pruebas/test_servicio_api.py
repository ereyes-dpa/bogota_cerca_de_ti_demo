"""API de referencia (codigo/servicio_api.py). Se salta si FastAPI no está instalado."""
import importlib
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("FUENTE_CHATBOT", "guardada")
    monkeypatch.setenv("CARPETA_REGISTRO", str(tmp_path))
    import servicio_api
    importlib.reload(servicio_api)
    return TestClient(servicio_api.app), tmp_path


def test_consulta_de_la_app(cliente):
    c, carpeta = cliente
    cuerpo = {"minutos": 120, "origen": "4.73, -74.09", "cuando": "2026-11-14 15:00", "con": "ninos", "prefs": ["naturaleza"],
              "modo": "transporte", "mascota": False, "id": "app-001", "escenario": "vivo_suba_ninos_sabado"}
    r = c.post("/recomendar", json=cuerpo)
    assert r.status_code == 200
    j = r.json()
    assert j["id"] == "app-001" and j["recomendacion"]["origen"] == "chatbot"
    plan = j["recomendacion"]["plan"]
    assert plan["paradas"] and plan["enlaces"]["google_maps"].startswith("https://")
    assert "alternativa" not in j                                     # respuesta corta por defecto
    # quedó registrada para Power BI con las columnas de siempre
    reg = pd.read_csv(carpeta / "consultas.csv")
    assert list(reg.consulta_id) == ["app-001"] and (carpeta / "paradas.csv").exists() and (carpeta / "chequeos.csv").exists()


def test_detalle_y_reemplazo(cliente):
    c, _ = cliente
    cuerpo = {"minutos": 90, "origen": "4.6951, -74.03095", "cuando": "2026-11-15 11:00", "con": "amigos", "prefs": ["inesperado", "economico"],
              "modo": "pie", "mascota": True, "escenario": "vivo_usaquen_domingo_mascota"}
    j = c.post("/recomendar?detalle=true", json=cuerpo).json()
    assert j["recomendacion"]["origen"] == "selector_propio" and j["chatbot"]["plan"]["veredicto"] == "NO LOGRABLE"
    assert j["alternativa"]["paradas"]


def test_parametros_invalidos(cliente):
    c, _ = cliente
    assert c.post("/recomendar", json={"minutos": 120, "origen": "Suba", "modo": "avion"}).status_code == 422
    assert c.post("/recomendar", json={"minutos": 10, "origen": "Suba"}).status_code == 422
